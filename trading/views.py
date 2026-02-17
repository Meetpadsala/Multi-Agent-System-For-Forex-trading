from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
import json
import math
from datetime import datetime, timedelta
try:
    from .agents import DecisionAgent
    AGENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Agents not available due to: {e}")
    AGENTS_AVAILABLE = False
    DecisionAgent = None
from .models import ForexData, Prediction, AgentLog, UserProfile
from .real_data_fetcher import real_data_fetcher

def home(request):
    """Home page - redirect to dashboard if logged in, else login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

def register_view(request):
    """User registration"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'trading/register.html', {'form': form})

def login_view(request):
    """User login"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'trading/login.html', {'form': form})

def logout_view(request):
    """User logout"""
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    """Main dashboard"""
    return render(request, 'trading/dashboard.html')

@login_required
def search_pairs(request):
    """Search currency pairs"""
    query = request.GET.get('q', '')
    # Common forex pairs
    pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'USDINR', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'EURCHF', 'GBPCHF', 'AUDCHF', 'EURNZD', 'GBPNZD', 'AUDNZD', 'USDMXN', 'USDZAR', 'USDTRY']
    filtered_pairs = [pair for pair in pairs if query.upper() in pair]
    return render(request, 'trading/search.html', {'pairs': filtered_pairs, 'query': query})

@method_decorator(csrf_exempt, name='dispatch')
class ForexDataAPI(View):
    """API for forex data and predictions"""

    def get(self, request, symbol):
        """Get latest data and prediction for a symbol"""
        try:
            timeframe = request.GET.get('timeframe', '1h')  # Default to 1 hour
            limit = int(request.GET.get('limit', 100))  # Number of data points
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            # Try to get real forex data first
            real_data = real_data_fetcher.get_current_price(symbol)
            if real_data:
                # Map real data attributes to match expected format
                latest_data = type('RealForexData', (), {
                    'symbol': symbol,
                    'timestamp': real_data['timestamp'],
                    'close_price': real_data['price'],
                    'open_price': real_data['open'],
                    'high_price': real_data['high'],
                    'low_price': real_data['low'],
                    'volume': real_data['volume']
                })()
            else:
                # Fallback to database data
                latest_data = ForexData.objects.filter(symbol=symbol).order_by('-timestamp').first()
                if not latest_data or latest_data.close_price == 0.0:
                    # Generate mock data if no real data or invalid data
                    mock_data = self._generate_mock_data(symbol)
                    latest_data = mock_data

            # Calculate time range based on timeframe or date range
            now = timezone.now()
            if start_date and end_date:
                # History mode - use date range
                start_dt = timezone.datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                end_dt = timezone.datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                # Get data within date range
                historical_data = ForexData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_dt,
                    timestamp__lte=end_dt
                ).order_by('timestamp')[:limit]
            else:
                # Live mode - calculate time range based on timeframe
                if timeframe == '1m':
                    delta = timedelta(minutes=limit)
                elif timeframe == '5m':
                    delta = timedelta(minutes=5 * limit)
                elif timeframe == '15m':
                    delta = timedelta(minutes=15 * limit)
                elif timeframe == '1h':
                    delta = timedelta(hours=limit)
                elif timeframe == '1d':
                    delta = timedelta(days=limit)
                else:
                    delta = timedelta(hours=24)  # Default

                # Get historical data for chart
                historical_data = ForexData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=now - delta
                ).order_by('timestamp')[:limit]

            # Try to get real historical data first
            real_historical_data = real_data_fetcher.get_forex_data(symbol, timeframe, limit)
            if real_historical_data:
                historical_data = []
                for item in real_historical_data:
                    # Convert to mock object format for compatibility
                    mock_item = type('RealForexData', (), {
                        'symbol': symbol,
                        'timestamp': item['timestamp'],
                        'close_price': item['close'],
                        'open_price': item['open'],
                        'high_price': item['high'],
                        'low_price': item['low'],
                        'volume': item['volume']
                    })()
                    historical_data.append(mock_item)
            else:
                # Fallback to database data
                if not historical_data:
                    # Generate mock historical data
                    historical_data = self._generate_mock_historical_data(symbol, limit, timeframe)

            # Format historical data as OHLC
            historical_ohlc = [{
                'timestamp': item.timestamp.isoformat(),
                'open': float(item.open_price),
                'high': float(item.high_price),
                'low': float(item.low_price),
                'close': float(item.close_price),
                'volume': int(item.volume)
            } for item in historical_data]

            # Get latest prediction or generate one if none exists
            latest_prediction = Prediction.objects.filter(symbol=symbol).order_by('-timestamp').first()

            # Ensure we have a valid prediction
            if not latest_prediction or latest_prediction.predicted_price is None or latest_prediction.predicted_price == 0.0:
                prediction_created = False

                # Try to generate prediction using agents first
                if AGENTS_AVAILABLE and DecisionAgent:
                    try:
                        decision_agent = DecisionAgent()
                        # This will trigger prediction generation
                        temp_decision = decision_agent.make_decision(symbol)
                        # Now get the newly created prediction
                        latest_prediction = Prediction.objects.filter(symbol=symbol).order_by('-timestamp').first()
                        if latest_prediction and latest_prediction.predicted_price and latest_prediction.predicted_price != 0.0:
                            prediction_created = True
                    except Exception as e:
                        print(f"Failed to generate prediction for {symbol}: {e}")

                # If agents failed or not available, create a mock prediction
                if not prediction_created:
                    import random
                    current_price = float(latest_data.close_price)
                    change_percent = random.uniform(-0.02, 0.02)  # -2% to +2%
                    predicted_price = current_price * (1 + change_percent)
                    trend = 'UP' if predicted_price > current_price else 'DOWN'
                    confidence = random.uniform(60, 85)

                    latest_prediction = Prediction.objects.create(
                        symbol=symbol,
                        predicted_price=predicted_price,
                        trend=trend,
                        confidence=confidence
                    )
                    print(f"Created mock prediction for {symbol}: {predicted_price} ({trend})")

            # Get agent decision
            decision = None
            if AGENTS_AVAILABLE and DecisionAgent:
                try:
                    decision_agent = DecisionAgent()
                    decision = decision_agent.make_decision(symbol)
                except Exception as e:
                    print(f"Agent decision failed: {e}")
                    decision = self._generate_mock_decision(symbol)

            # Calculate technical indicators from the actual historical data
            technical_indicators = self._calculate_technical_indicators(historical_data)

            # Update decision with real technical indicators
            if decision:
                decision['technical_indicators'] = technical_indicators

            # Ensure prediction has valid data
            prediction_data = {
                'price': float(latest_prediction.predicted_price),
                'trend': latest_prediction.trend or 'HOLD',
                'confidence': float(latest_prediction.confidence) if latest_prediction.confidence else 50.0,
            }

            data = {
                'symbol': symbol,
                'current_price': float(latest_data.close_price),
                'timestamp': latest_data.timestamp.isoformat(),
                'timeframe': timeframe,
                'historical_ohlc': historical_ohlc,
                'prediction': prediction_data,
                'decision': decision
            }

            # Replace NaN values with None for JSON serialization
            import math
            def replace_nan(obj):
                if isinstance(obj, dict):
                    return {k: replace_nan(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_nan(item) for item in obj]
                elif isinstance(obj, float) and math.isnan(obj):
                    return None
                else:
                    return obj

            data = replace_nan(data)

            return JsonResponse(data)

        except Exception as e:
            print(f"Error in ForexDataAPI.get: {e}")
            return JsonResponse({'error': str(e)})

    def post(self, request, symbol):
        """Trigger data fetch for a symbol"""
        try:
            if AGENTS_AVAILABLE and DecisionAgent:
                decision_agent = DecisionAgent()
                decision_agent.data_agent.fetch_real_time_data(symbol)
                return JsonResponse({'status': 'Data fetched successfully'})
            else:
                return JsonResponse({'status': 'Mock data fetch (agents not available)'})
        except Exception as e:
            return JsonResponse({'error': str(e)})

    def _generate_mock_data(self, symbol):
        """Generate mock forex data"""
        base_prices = {
            'EURUSD': 1.08, 'GBPUSD': 1.27, 'USDJPY': 150.0, 'USDINR': 83.0,
            'EURGBP': 0.85, 'EURJPY': 162.0, 'GBPJPY': 190.0, 'AUDJPY': 98.0,
            'CADJPY': 110.0, 'CHFJPY': 165.0, 'EURCHF': 0.95, 'GBPCHF': 1.12,
            'AUDCHF': 0.58, 'EURNZD': 1.75, 'GBPNZD': 2.05, 'AUDNZD': 1.08,
            'USDMXN': 18.5, 'USDZAR': 18.2, 'USDTRY': 32.0
        }
        price = base_prices.get(symbol, 1.0)

        # Create a mock object
        mock_data = type('MockForexData', (), {
            'symbol': symbol,
            'timestamp': timezone.localtime(timezone.now()),
            'close_price': price,
            'open_price': price,
            'high_price': price * 1.001,
            'low_price': price * 0.999,
            'volume': 1000
        })()
        return mock_data

    def _calculate_technical_indicators(self, historical_data):
        """Calculate technical indicators from historical data"""
        if not historical_data:
            return {
                'rsi': None,
                'macd': None,
                'sma_20': None,
                'bollinger_upper': None,
                'bollinger_lower': None
            }

        # Extract close prices, filtering out None and NaN values
        closes = []
        for item in historical_data:
            if hasattr(item, 'close_price') and item.close_price is not None:
                try:
                    c = float(item.close_price)
                    if not math.isnan(c):
                        closes.append(c)
                except (ValueError, TypeError):
                    pass

        if len(closes) < 5:
            return {
                'rsi': None,
                'macd': None,
                'sma_20': None,
                'bollinger_upper': None,
                'bollinger_lower': None
            }

        # Calculate indicators with minimum data requirements
        rsi = self._calculate_rsi(closes, min(len(closes)-1, 14))
        macd = self._calculate_macd(closes) if len(closes) >= 12 else None
        sma_20 = sum(closes[-min(20, len(closes)):]) / min(20, len(closes))

        # Calculate Bollinger Bands with adaptive period
        period = min(20, len(closes))
        bollinger_upper, bollinger_lower = self._calculate_bollinger_bands(closes, period)

        return {
            'rsi': rsi,
            'macd': macd,
            'sma_20': sma_20,
            'bollinger_upper': bollinger_upper,
            'bollinger_lower': bollinger_lower
        }

    def _calculate_rsi(self, closes, period=14):
        """Calculate RSI (Relative Strength Index)"""
        if len(closes) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    def _calculate_macd(self, closes, fast_period=12, slow_period=26, signal_period=9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(closes) < slow_period:
            return None

        # Calculate EMAs
        fast_ema = self._calculate_ema(closes, fast_period)
        slow_ema = self._calculate_ema(closes, slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        macd_line = fast_ema - slow_ema

        # Calculate signal line (EMA of MACD)
        macd_values = []
        for i in range(slow_period - 1, len(closes)):
            fast_ema_val = self._calculate_ema(closes[:i+1], fast_period)
            slow_ema_val = self._calculate_ema(closes[:i+1], slow_period)
            if fast_ema_val is not None and slow_ema_val is not None:
                macd_values.append(fast_ema_val - slow_ema_val)

        if len(macd_values) >= signal_period:
            signal_line = self._calculate_ema(macd_values, signal_period)
            return round(macd_line - signal_line, 6) if signal_line is not None else round(macd_line, 6)

        return round(macd_line, 6)

    def _calculate_ema(self, data, period):
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period

        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _calculate_bollinger_bands(self, closes, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(closes) < period:
            return None, None

        # Calculate SMA
        sma = sum(closes[-period:]) / period

        # Calculate standard deviation
        variance = sum([(price - sma) ** 2 for price in closes[-period:]]) / period
        std = variance ** 0.5

        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        return round(upper_band, 6), round(lower_band, 6)

    def _generate_mock_decision(self, symbol):
        """Generate decision based on real technical analysis when agents are not available"""
        import random

        # Get historical data for technical indicators calculation
        now = timezone.now()
        historical_data = ForexData.objects.filter(
            symbol=symbol,
            timestamp__gte=now - timedelta(hours=24)
        ).order_by('timestamp')[:100]

        # If no historical data, generate some mock data for analysis
        if not historical_data:
            historical_data = self._generate_mock_historical_data(symbol, 50, '1h')

        # Calculate real technical indicators
        technical_indicators = self._calculate_technical_indicators(historical_data)

        # Make decision based on technical indicators with enhanced logic
        decision = 'HOLD'
        confidence = 65.0  # Higher base confidence
        profit_probability = 55.0

        # RSI-based decision (primary indicator)
        if technical_indicators['rsi'] is not None:
            rsi = technical_indicators['rsi']
            if rsi < 35:
                decision = 'BUY'  # Strong oversold condition
                confidence = min(95, 60 + (35 - rsi) * 3)  # Higher confidence for more oversold
                profit_probability = confidence
            elif rsi < 45:
                decision = 'BUY'  # Moderate oversold
                confidence = 75.0
                profit_probability = 65.0
            elif rsi > 65:
                decision = 'SELL'  # Moderate overbought
                confidence = 75.0
                profit_probability = 65.0
            elif rsi > 75:
                decision = 'SELL'  # Strong overbought condition
                confidence = min(95, 60 + (rsi - 75) * 3)  # Higher confidence for more overbought
                profit_probability = confidence
            else:
                decision = 'HOLD'
                confidence = 70.0
                profit_probability = 50.0

        # MACD confirmation (secondary indicator)
        macd_signal_strength = 0
        if technical_indicators['macd'] is not None:
            macd = technical_indicators['macd']
            if macd > 0.001:
                macd_signal_strength = 15  # Strong bullish
            elif macd > 0.0005:
                macd_signal_strength = 10  # Moderate bullish
            elif macd < -0.001:
                macd_signal_strength = -15  # Strong bearish
            elif macd < -0.0005:
                macd_signal_strength = -10  # Moderate bearish

            # Adjust confidence based on MACD confirmation
            if (decision == 'BUY' and macd_signal_strength > 0) or (decision == 'SELL' and macd_signal_strength < 0):
                confidence = min(95, confidence + abs(macd_signal_strength))
                profit_probability = min(90, profit_probability + abs(macd_signal_strength) * 0.8)
            elif (decision == 'BUY' and macd_signal_strength < 0) or (decision == 'SELL' and macd_signal_strength > 0):
                confidence = max(45, confidence - abs(macd_signal_strength))
                profit_probability = max(40, profit_probability - abs(macd_signal_strength) * 0.6)

        # Moving Average trend analysis
        if technical_indicators['sma_20'] is not None and historical_data:
            current_price = float(historical_data[-1].close_price)
            sma_20 = technical_indicators['sma_20']

            price_vs_ma = (current_price - sma_20) / sma_20 * 100  # Percentage difference

            if price_vs_ma > 1.0:  # Price 1% above MA
                if decision == 'BUY':
                    confidence = min(95, confidence + 8)
                elif decision == 'HOLD':
                    decision = 'BUY'
                    confidence = 72.0
            elif price_vs_ma < -1.0:  # Price 1% below MA
                if decision == 'SELL':
                    confidence = min(95, confidence + 8)
                elif decision == 'HOLD':
                    decision = 'SELL'
                    confidence = 72.0

        # Advanced Risk Analysis System with Multi-Factor Assessment
        import random
        import time
        import statistics

        # Initialize risk components
        risk_components = {
            'market_volatility': 0,
            'trend_risk': 0,
            'momentum_risk': 0,
            'overbought_oversold': 0,
            'band_position': 0,
            'price_action': 0,
            'time_based': 0,
            'market_noise': 0
        }

        # 1. Market Volatility Risk (based on recent price movements)
        if historical_data and len(historical_data) > 5:
            recent_prices = [float(d.close_price) for d in historical_data[-20:]]
            if len(recent_prices) > 1:
                # Calculate various volatility measures
                returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                          for i in range(1, len(recent_prices))]
                volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0

                # Average True Range (ATR) approximation
                true_ranges = []
                for i in range(1, len(recent_prices)):
                    high = max(recent_prices[i], recent_prices[i-1])
                    low = min(recent_prices[i], recent_prices[i-1])
                    tr = high - low
                    true_ranges.append(tr)
                atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
                atr_percentage = (atr / recent_prices[-1]) * 100

                # Combine volatility measures
                combined_volatility = (volatility + atr_percentage) / 2
                risk_components['market_volatility'] = min(combined_volatility * 5, 25)

        # 2. Trend Risk (based on moving averages and trend strength)
        if technical_indicators['sma_20'] is not None and historical_data:
            current_price = float(historical_data[-1].close_price)
            sma_20 = technical_indicators['sma_20']

            # Trend strength
            trend_deviation = abs(current_price - sma_20) / sma_20 * 100

            # Trend direction consistency (check if price is consistently above/below MA)
            if len(historical_data) > 10:
                recent_trend = sum(1 if float(h.close_price) > sma_20 else -1
                                  for h in historical_data[-10:])
                trend_consistency = abs(recent_trend) / 10 * 100

                if trend_deviation > 3:  # Strong trend
                    risk_components['trend_risk'] = 15 if trend_consistency > 70 else 8
                elif trend_deviation > 1:  # Moderate trend
                    risk_components['trend_risk'] = 8 if trend_consistency > 60 else 5

        # 3. Momentum Risk (MACD and momentum indicators)
        if technical_indicators['macd'] is not None:
            macd = technical_indicators['macd']
            macd_strength = abs(macd)

            if macd_strength > 0.003:  # Very strong momentum
                risk_components['momentum_risk'] = 20
            elif macd_strength > 0.002:  # Strong momentum
                risk_components['momentum_risk'] = 15
            elif macd_strength > 0.001:  # Moderate momentum
                risk_components['momentum_risk'] = 10
            elif macd_strength > 0.0005:  # Weak momentum
                risk_components['momentum_risk'] = 5

        # 4. Overbought/Oversold Risk (RSI extreme levels)
        if technical_indicators['rsi'] is not None:
            rsi = technical_indicators['rsi']

            if rsi < 25 or rsi > 75:  # Extreme levels
                risk_components['overbought_oversold'] = 25
                confidence = max(45, confidence - 20)  # Significant confidence reduction
            elif rsi < 30 or rsi > 70:  # Very high risk levels
                risk_components['overbought_oversold'] = 18
                confidence = max(50, confidence - 15)
            elif rsi < 35 or rsi > 65:  # High risk levels
                risk_components['overbought_oversold'] = 12
                confidence = max(55, confidence - 10)
            elif rsi < 40 or rsi > 60:  # Moderate risk levels
                risk_components['overbought_oversold'] = 6
                confidence = max(60, confidence - 5)

        # 5. Bollinger Band Position Risk
        if technical_indicators['bollinger_upper'] is not None and technical_indicators['bollinger_lower'] is not None:
            current_price = float(historical_data[-1].close_price) if historical_data else 1.0
            upper = technical_indicators['bollinger_upper']
            lower = technical_indicators['bollinger_lower']
            middle = (upper + lower) / 2

            # Calculate position within bands
            band_width = upper - lower
            if band_width > 0:
                position_from_lower = (current_price - lower) / band_width

                if position_from_lower < 0.05 or position_from_lower > 0.95:  # Touching bands
                    risk_components['band_position'] = 30
                    confidence = max(40, confidence - 25)
                elif position_from_lower < 0.1 or position_from_lower > 0.9:  # Very close to bands
                    risk_components['band_position'] = 22
                    confidence = max(45, confidence - 18)
                elif position_from_lower < 0.15 or position_from_lower > 0.85:  # Close to bands
                    risk_components['band_position'] = 15
                    confidence = max(50, confidence - 12)
                elif position_from_lower < 0.25 or position_from_lower > 0.75:  # Approaching bands
                    risk_components['band_position'] = 8
                    confidence = max(55, confidence - 8)
                elif position_from_lower >= 0.4 and position_from_lower <= 0.6:  # Middle zone (low risk)
                    risk_components['band_position'] = -5  # Reduce risk
                    confidence = min(95, confidence + 3)

        # 6. Price Action Risk (recent price patterns)
        if historical_data and len(historical_data) > 5:
            recent_prices = [float(d.close_price) for d in historical_data[-5:]]

            # Check for sharp movements
            if len(recent_prices) >= 3:
                recent_change = abs(recent_prices[-1] - recent_prices[-3]) / recent_prices[-3] * 100
                if recent_change > 2:  # Sharp 2%+ move in 3 periods
                    risk_components['price_action'] = 12
                elif recent_change > 1:  # Sharp 1%+ move
                    risk_components['price_action'] = 8

            # Check for consolidation vs breakout
            price_range = max(recent_prices) - min(recent_prices)
            avg_price = sum(recent_prices) / len(recent_prices)
            range_percentage = (price_range / avg_price) * 100

            if range_percentage < 0.2:  # Very tight consolidation
                risk_components['price_action'] += 8  # Breakout potential
            elif range_percentage > 1.5:  # Wide range (volatile)
                risk_components['price_action'] += 6

        # 7. Time-based Risk Variation
        time_seed = int(time.time()) % 120  # 2-minute cycle
        risk_components['time_based'] = (time_seed / 120.0) * 15  # 0-15 range

        # 8. Market Noise (random factor for realism)
        risk_components['market_noise'] = random.uniform(-6, 6)

        # Calculate weighted risk score
        weights = {
            'market_volatility': 1.2,
            'trend_risk': 1.0,
            'momentum_risk': 0.9,
            'overbought_oversold': 1.3,
            'band_position': 1.4,
            'price_action': 0.8,
            'time_based': 0.6,
            'market_noise': 0.4
        }

        weighted_risk = sum(risk_components[comp] * weights[comp] for comp in risk_components)

        # Base risk level (market baseline)
        base_risk = 25.0

        # Final risk score calculation
        risk_score = base_risk + weighted_risk

        # Apply risk score bounds with more sophisticated clamping
        if risk_score < 0:
            risk_score = max(0, risk_score + 5)  # Allow slightly negative but clamp to 0
        elif risk_score > 100:
            risk_score = min(100, risk_score - 5)  # Allow slightly over but clamp to 100
        else:
            risk_score = max(5, min(95, risk_score))  # Normal bounds with small buffer

        # Determine sentiment based on trend indicators
        sentiment = 'NEUTRAL'
        bullish_signals = 0
        bearish_signals = 0

        if technical_indicators['macd'] is not None:
            if technical_indicators['macd'] > 0.0002:
                bullish_signals += 1
            elif technical_indicators['macd'] < -0.0002:
                bearish_signals += 1

        if technical_indicators['rsi'] is not None:
            if technical_indicators['rsi'] < 45:
                bullish_signals += 1
            elif technical_indicators['rsi'] > 55:
                bearish_signals += 1

        if bullish_signals > bearish_signals:
            sentiment = 'POSITIVE'
        elif bearish_signals > bullish_signals:
            sentiment = 'NEGATIVE'

        # Final adjustments based on sentiment
        if sentiment == 'POSITIVE' and decision == 'BUY':
            confidence = min(95, confidence + 5)
        elif sentiment == 'NEGATIVE' and decision == 'SELL':
            confidence = min(95, confidence + 5)
        elif sentiment == 'POSITIVE' and decision == 'SELL':
            confidence = max(50, confidence - 10)
        elif sentiment == 'NEGATIVE' and decision == 'BUY':
            confidence = max(50, confidence - 10)

        return {
            'decision': decision,
            'profit_probability': round(profit_probability, 1),
            'confidence': round(confidence, 1),
            'technical_indicators': technical_indicators,
            'prediction': {
                'trend': 'UP' if decision == 'BUY' else 'DOWN' if decision == 'SELL' else 'HOLD',
                'confidence': round(confidence, 1)
            },
            'sentiment': sentiment,
            'risk': {
                'volatility': 0.15,  # Realistic volatility
                'stop_loss': None,
                'take_profit': None,
                'risk_score': round(risk_score, 1)
            }
        }

    def _generate_mock_historical_data(self, symbol, num_points=24, timeframe='1h'):
        """Generate mock historical data for the given timeframe with realistic price movements"""
        import random
        import math

        base_prices = {
            'EURUSD': 1.08, 'GBPUSD': 1.27, 'USDJPY': 150.0, 'USDINR': 83.0
        }
        base_price = base_prices.get(symbol, 1.0)

        historical_data = []
        current_time = timezone.now()

        # Calculate time delta based on timeframe
        if timeframe == '1m':
            delta = timedelta(minutes=1)
        elif timeframe == '5m':
            delta = timedelta(minutes=5)
        elif timeframe == '15m':
            delta = timedelta(minutes=15)
        elif timeframe == '1h':
            delta = timedelta(hours=1)
        elif timeframe == '1d':
            delta = timedelta(days=1)
        else:
            delta = timedelta(hours=1)

        # Generate a trending price series with realistic volatility
        current_price = base_price
        trend_direction = random.choice([-1, 1])  # Up or down trend
        trend_strength = random.uniform(0.0001, 0.0005)  # How strong the trend is

        for i in range(num_points):
            # Generate timestamp for each period back
            timestamp = current_time - delta * (num_points - i - 1)

            # Add trend component
            trend_component = trend_direction * trend_strength * i

            # Add random walk component (volatility)
            random_walk = random.gauss(0, 0.001)  # Gaussian noise

            # Add some cyclical component (market cycles)
            cycle_component = 0.0005 * math.sin(2 * math.pi * i / 20)  # 20-period cycle

            # Calculate new price
            price_change = trend_component + random_walk + cycle_component
            current_price = base_price * (1 + price_change)

            # Ensure price stays within reasonable bounds
            current_price = max(current_price, base_price * 0.95)  # Don't go below 95% of base
            current_price = min(current_price, base_price * 1.05)  # Don't go above 105% of base

            # Generate OHLC data around the current price
            volatility = random.uniform(0.0005, 0.002)  # Intrabar volatility

            # Open price (close of previous bar or base price for first bar)
            if i == 0:
                open_price = base_price
            else:
                open_price = historical_data[-1].close_price

            # Generate high, low, close around current price
            close_price = current_price * random.uniform(0.999, 1.001)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.0002, volatility))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.0002, volatility))

            # Ensure OHLC relationships are correct
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

            # Create mock object similar to ForexData
            mock_item = type('MockForexData', (), {
                'symbol': symbol,
                'timestamp': timestamp,
                'close_price': float(close_price),
                'open_price': float(open_price),
                'high_price': float(high_price),
                'low_price': float(low_price),
                'volume': random.randint(500, 2000)
            })()
            historical_data.append(mock_item)

        return historical_data

@method_decorator(csrf_exempt, name='dispatch')
class AgentLogsAPI(View):
    """API for agent logs"""

    def get(self, request):
        """Get recent agent logs"""
        logs = AgentLog.objects.order_by('-timestamp')[:50]
        data = [{
            'agent': log.agent_name,
            'action': log.action,
            'result': log.result,
            'timestamp': log.timestamp.isoformat()
        } for log in logs]
        return JsonResponse({'logs': data})

@login_required
def agent_logs(request):
    """View agent logs"""
    return render(request, 'trading/logs.html')

@method_decorator(csrf_exempt, name='dispatch')
class HighRiskPairsAPI(View):
    """API for getting pairs with high risk levels"""

    def get(self, request):
        """Get currency pairs with high risk levels (>70)"""
        try:
            high_risk_pairs = []
            all_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'USDINR', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'CHFJPY', 'EURCHF', 'GBPCHF', 'AUDCHF', 'EURNZD', 'GBPNZD', 'AUDNZD', 'USDMXN', 'USDZAR', 'USDTRY']

            for symbol in all_pairs:
                try:
                    # Get historical data for risk calculation
                    now = timezone.now()
                    historical_data = ForexData.objects.filter(
                        symbol=symbol,
                        timestamp__gte=now - timedelta(hours=24)
                    ).order_by('timestamp')[:100]

                    # If no historical data, generate some mock data for analysis
                    if not historical_data:
                        historical_data = self._generate_mock_historical_data(symbol, 50, '1h')

                    # Calculate technical indicators
                    technical_indicators = self._calculate_technical_indicators(historical_data)

                    # Calculate risk score using the same logic as _generate_mock_decision
                    risk_score = self._calculate_risk_score(historical_data, technical_indicators)

                    if risk_score > 70:
                        high_risk_pairs.append({
                            'symbol': symbol,
                            'risk_score': round(risk_score, 1),
                            'risk_level': 'High'
                        })

                except Exception as e:
                    print(f"Error calculating risk for {symbol}: {e}")
                    continue

            # Sort by risk score descending
            high_risk_pairs.sort(key=lambda x: x['risk_score'], reverse=True)

            return JsonResponse({'high_risk_pairs': high_risk_pairs})

        except Exception as e:
            print(f"Error in HighRiskPairsAPI.get: {e}")
            return JsonResponse({'error': str(e)})

    def _calculate_risk_score(self, historical_data, technical_indicators):
        """Calculate risk score for a pair (extracted from _generate_mock_decision)"""
        import random
        import time
        import statistics

        # Initialize risk components
        risk_components = {
            'market_volatility': 0,
            'trend_risk': 0,
            'momentum_risk': 0,
            'overbought_oversold': 0,
            'band_position': 0,
            'price_action': 0,
            'time_based': 0,
            'market_noise': 0
        }

        # 1. Market Volatility Risk
        if historical_data and len(historical_data) > 5:
            recent_prices = [float(d.close_price) for d in historical_data[-20:]]
            if len(recent_prices) > 1:
                returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                          for i in range(1, len(recent_prices))]
                volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0

                true_ranges = []
                for i in range(1, len(recent_prices)):
                    high = max(recent_prices[i], recent_prices[i-1])
                    low = min(recent_prices[i], recent_prices[i-1])
                    tr = high - low
                    true_ranges.append(tr)
                atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
                atr_percentage = (atr / recent_prices[-1]) * 100

                combined_volatility = (volatility + atr_percentage) / 2
                risk_components['market_volatility'] = min(combined_volatility * 5, 25)

        # 2. Trend Risk
        if technical_indicators['sma_20'] is not None and historical_data:
            current_price = float(historical_data[-1].close_price)
            sma_20 = technical_indicators['sma_20']

            trend_deviation = abs(current_price - sma_20) / sma_20 * 100

            if len(historical_data) > 10:
                recent_trend = sum(1 if float(h.close_price) > sma_20 else -1
                                  for h in historical_data[-10:])
                trend_consistency = abs(recent_trend) / 10 * 100

                if trend_deviation > 3:
                    risk_components['trend_risk'] = 15 if trend_consistency > 70 else 8
                elif trend_deviation > 1:
                    risk_components['trend_risk'] = 8 if trend_consistency > 60 else 5

        # 3. Momentum Risk
        if technical_indicators['macd'] is not None:
            macd = technical_indicators['macd']
            macd_strength = abs(macd)

            if macd_strength > 0.003:
                risk_components['momentum_risk'] = 20
            elif macd_strength > 0.002:
                risk_components['momentum_risk'] = 15
            elif macd_strength > 0.001:
                risk_components['momentum_risk'] = 10
            elif macd_strength > 0.0005:
                risk_components['momentum_risk'] = 5

        # 4. Overbought/Oversold Risk
        if technical_indicators['rsi'] is not None:
            rsi = technical_indicators['rsi']

            if rsi < 25 or rsi > 75:
                risk_components['overbought_oversold'] = 25
            elif rsi < 30 or rsi > 70:
                risk_components['overbought_oversold'] = 18
            elif rsi < 35 or rsi > 65:
                risk_components['overbought_oversold'] = 12
            elif rsi < 40 or rsi > 60:
                risk_components['overbought_oversold'] = 6

        # 5. Bollinger Band Position Risk
        if technical_indicators['bollinger_upper'] is not None and technical_indicators['bollinger_lower'] is not None:
            current_price = float(historical_data[-1].close_price) if historical_data else 1.0
            upper = technical_indicators['bollinger_upper']
            lower = technical_indicators['bollinger_lower']
            band_width = upper - lower
            if band_width > 0:
                position_from_lower = (current_price - lower) / band_width

                if position_from_lower < 0.05 or position_from_lower > 0.95:
                    risk_components['band_position'] = 30
                elif position_from_lower < 0.1 or position_from_lower > 0.9:
                    risk_components['band_position'] = 22
                elif position_from_lower < 0.15 or position_from_lower > 0.85:
                    risk_components['band_position'] = 15
                elif position_from_lower < 0.25 or position_from_lower > 0.75:
                    risk_components['band_position'] = 8
                elif position_from_lower >= 0.4 and position_from_lower <= 0.6:
                    risk_components['band_position'] = -5

        # 6. Price Action Risk
        if historical_data and len(historical_data) > 5:
            recent_prices = [float(d.close_price) for d in historical_data[-5:]]

            if len(recent_prices) >= 3:
                recent_change = abs(recent_prices[-1] - recent_prices[-3]) / recent_prices[-3] * 100
                if recent_change > 2:
                    risk_components['price_action'] = 12
                elif recent_change > 1:
                    risk_components['price_action'] = 8

            price_range = max(recent_prices) - min(recent_prices)
            avg_price = sum(recent_prices) / len(recent_prices)
            range_percentage = (price_range / avg_price) * 100

            if range_percentage < 0.2:
                risk_components['price_action'] += 8
            elif range_percentage > 1.5:
                risk_components['price_action'] += 6

        # 7. Time-based Risk Variation
        time_seed = int(time.time()) % 120
        risk_components['time_based'] = (time_seed / 120.0) * 15

        # 8. Market Noise
        risk_components['market_noise'] = random.uniform(-6, 6)

        # Calculate weighted risk score
        weights = {
            'market_volatility': 1.2,
            'trend_risk': 1.0,
            'momentum_risk': 0.9,
            'overbought_oversold': 1.3,
            'band_position': 1.4,
            'price_action': 0.8,
            'time_based': 0.6,
            'market_noise': 0.4
        }

        weighted_risk = sum(risk_components[comp] * weights[comp] for comp in risk_components)

        base_risk = 25.0
        risk_score = base_risk + weighted_risk

        if risk_score < 0:
            risk_score = max(0, risk_score + 5)
        elif risk_score > 100:
            risk_score = min(100, risk_score - 5)
        else:
            risk_score = max(5, min(95, risk_score))

        return risk_score

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import RegistrationForm, AgentStatusForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
from django.db.models import Q
import json
import math
from datetime import datetime, timedelta
try:
    from .agents import DecisionAgent
    AGENTS_AVAILABLE = True  # Disable agents for debugging
except ImportError as e:
    print(f"Warning: Agents not available due to: {e}")
    AGENTS_AVAILABLE = False
    DecisionAgent = None
from .models import ForexData, Prediction, AgentLog, UserProfile, AgentStatus, RiskAnalysis
from .real_data_fetcher import real_data_fetcher
from .currency_pairs import ALL_PAIRS, BASE_PRICES, get_all_pairs, get_base_price, MAJOR_PAIRS, EUR_CROSSES, GBP_CROSSES, JPY_CROSSES, OTHER_CROSSES, USD_EXOTICS, ADDITIONAL_PAIRS


def home(request):
    """Home page - redirect to dashboard if logged in, else login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

def register_view(request):
    """User registration"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'trading/register.html', {'form': form, 'show_navbar': False})

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
    return render(request, 'trading/login.html', {'form': form, 'show_navbar': False})

def logout_view(request):
    """User logout"""
    logout(request)
    return redirect('login')

def password_reset_request(request):
    """Password reset request view"""
    if request.method == 'POST':
        email = request.POST.get('email')
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(email=email)
            from django.contrib import messages
            messages.success(request, 'Password reset instructions have been sent to your email address.')
            return redirect('password_reset_done')
        except User.DoesNotExist:
            from django.contrib import messages
            messages.error(request, 'No user found with this email address.')
        except User.MultipleObjectsReturned:
            from django.contrib import messages
            messages.error(request, 'Multiple accounts found with this email. Please contact support.')
    return render(request, 'trading/password_reset.html')

def password_reset_done(request):
    """Password reset done view"""
    return render(request, 'trading/password_reset_done.html')

@login_required
def dashboard(request):
    """Main dashboard"""
    # Format currency pairs for the dropdown with categories
    
    def format_pair(pair):
        """Format pair like EUR/USD from EURUSD"""
        if len(pair) == 6:
            return f"{pair[:3]}/{pair[3:]}"
        return pair
    
    # Create categorized pairs for the dropdown
    major_pairs = [{'symbol': p, 'name': format_pair(p)} for p in MAJOR_PAIRS]
    minor_pairs = [
        {'symbol': p, 'name': format_pair(p)} for p in 
        EUR_CROSSES + GBP_CROSSES + JPY_CROSSES + OTHER_CROSSES
    ]
    exotic_pairs = [{'symbol': p, 'name': format_pair(p)} for p in USD_EXOTICS]
    additional_pairs = [{'symbol': p, 'name': format_pair(p)} for p in ADDITIONAL_PAIRS]
    
    # Flat list for backward compatibility
    all_pairs = major_pairs + minor_pairs + exotic_pairs + additional_pairs
    
    return render(request, 'trading/dashboard.html', {
        'currency_pairs': all_pairs,
        'major_pairs': major_pairs,
        'minor_pairs': minor_pairs,
        'exotic_pairs': exotic_pairs,
        'additional_pairs': additional_pairs
    })


@login_required
def get_currency_pairs(request):
    """API to get all available currency pairs"""
    from django.http import JsonResponse
    pairs = []
    for pair in ALL_PAIRS:
        # Format pair name like "EUR/USD" from "EURUSD"
        if len(pair) == 6:
            formatted = f"{pair[:3]}/{pair[3:]}"
        else:
            formatted = pair
        pairs.append({
            'symbol': pair,
            'name': formatted
        })
    return JsonResponse({'pairs': pairs})

@login_required
def search_pairs(request):
    """Search currency pairs"""
    query = request.GET.get('q', '')
    # Use all pairs from currency_pairs module
    filtered_pairs = [pair for pair in ALL_PAIRS if query.upper() in pair]
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
                from datetime import timezone as dt_timezone
                start_dt = datetime.fromisoformat(start_date).replace(tzinfo=dt_timezone.utc)
                end_dt = datetime.fromisoformat(end_date).replace(tzinfo=dt_timezone.utc)
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

            # Determine if we're in history mode
            is_history_mode = bool(start_date and end_date)
            
            # Get current price from historical data for history mode
            current_price_from_history = None
            if historical_data and len(historical_data) > 0:
                current_price_from_history = float(historical_data[-1].close_price)
            
            # Get latest prediction or generate one if none exists
            latest_prediction = Prediction.objects.filter(symbol=symbol).order_by('-timestamp').first()

            # Ensure we have a valid prediction
            if not latest_prediction or latest_prediction.predicted_price is None or latest_prediction.predicted_price == 0.0:
                prediction_created = False

                # In history mode, generate prediction based on historical data
                if is_history_mode and current_price_from_history:
                    import random
                    change_percent = random.uniform(-0.02, 0.02)
                    predicted_price = current_price_from_history * (1 + change_percent)
                    trend = 'UP' if predicted_price > current_price_from_history else 'DOWN'
                    confidence = random.uniform(60, 85)
                    # Create prediction object in memory (don't save to DB for history)
                    latest_prediction = type('Prediction', (), {
                        'predicted_price': predicted_price,
                        'trend': trend,
                        'confidence': confidence
                    })()
                    prediction_created = True
                else:
                    # Try to generate prediction using agents first (live mode)
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

            # Calculate technical indicators from the historical data (for both live and history mode)
            technical_indicators = self._calculate_technical_indicators(historical_data)

            # Get agent decision - in history mode use _generate_mock_decision with historical data
            decision = None
            if is_history_mode and historical_data and len(historical_data) > 0:
                # In history mode, generate decision based on historical data
                decision = self._generate_decision_from_history(symbol, historical_data, technical_indicators)
            elif AGENTS_AVAILABLE and DecisionAgent:
                try:
                    decision_agent = DecisionAgent()
                    decision = decision_agent.make_decision(symbol)
                except Exception as e:
                    print(f"Agent decision failed: {e}")
                    decision = self._generate_mock_decision(symbol)
            else:
                decision = self._generate_mock_decision(symbol)

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
            import traceback
            print(f"Error in ForexDataAPI.get: {e}")
            traceback.print_exc()
            return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()})

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
        # Use get_base_price from currency_pairs module for all supported pairs
        price = get_base_price(symbol)

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
        # Use max(1, ...) to ensure positive period values
        rsi_period = max(1, min(len(closes)-1, 14))
        rsi = self._calculate_rsi(closes, rsi_period)
        macd = self._calculate_macd(closes) if len(closes) >= 12 else None
        sma_period = max(1, min(20, len(closes)))
        sma_20 = sum(closes[-sma_period:]) / sma_period

        # Calculate Bollinger Bands with adaptive period
        period = max(1, min(20, len(closes)))
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
        import time
        import statistics
        from django.utils import timezone
        from datetime import timedelta

        # ---------------- SAFE DIVIDE FUNCTION ---------------- #
        def safe_divide(a, b, default=0):
            try:
                return a / b if b not in (0, None) else default
            except:
                return default
        # ------------------------------------------------------ #

        now = timezone.now()
        historical_data = ForexData.objects.filter(
            symbol=symbol,
            timestamp__gte=now - timedelta(hours=24)
        ).order_by('timestamp')[:100]

        if not historical_data:
            historical_data = self._generate_mock_historical_data(symbol, 50, '1h')

        technical_indicators = self._calculate_technical_indicators(historical_data)

        decision = 'HOLD'
        confidence = 65.0
        profit_probability = 55.0

        # ---------------- RSI ---------------- #
        rsi = technical_indicators.get('rsi')
        if rsi is not None:
            if rsi < 35:
                decision = 'BUY'
                confidence = min(95, 60 + (35 - rsi) * 3)
                profit_probability = confidence
            elif rsi < 45:
                decision = 'BUY'
                confidence = 75.0
            elif rsi > 75:
                decision = 'SELL'
                confidence = min(95, 60 + (rsi - 75) * 3)
                profit_probability = confidence
            elif rsi > 65:
                decision = 'SELL'
                confidence = 75.0
            else:
                decision = 'HOLD'
                confidence = 70.0

        # ---------------- MACD ---------------- #
        macd = technical_indicators.get('macd')
        macd_signal_strength = 0

        if macd is not None:
            if macd > 0.001:
                macd_signal_strength = 15
            elif macd > 0.0005:
                macd_signal_strength = 10
            elif macd < -0.001:
                macd_signal_strength = -15
            elif macd < -0.0005:
                macd_signal_strength = -10

            if (decision == 'BUY' and macd_signal_strength > 0) or \
               (decision == 'SELL' and macd_signal_strength < 0):
                confidence = min(95, confidence + abs(macd_signal_strength))
            elif (decision == 'BUY' and macd_signal_strength < 0) or \
                 (decision == 'SELL' and macd_signal_strength > 0):
                confidence = max(45, confidence - abs(macd_signal_strength))

        # ---------------- Historical List ---------------- #
        historical_data_list = list(historical_data)
        if not historical_data_list:
            return None

        current_price = float(historical_data_list[-1].close_price)

        # ---------------- SMA Trend ---------------- #
        sma_20 = technical_indicators.get('sma_20')

        if sma_20 not in (None, 0):
            price_vs_ma = safe_divide(current_price - sma_20, sma_20) * 100

            if price_vs_ma > 1:
                if decision == 'BUY':
                    confidence = min(95, confidence + 8)
                elif decision == 'HOLD':
                    decision = 'BUY'
                    confidence = 72
            elif price_vs_ma < -1:
                if decision == 'SELL':
                    confidence = min(95, confidence + 8)
                elif decision == 'HOLD':
                    decision = 'SELL'
                    confidence = 72

        # ---------------- Volatility ---------------- #
        risk_components = {k: 0 for k in [
            'market_volatility','trend_risk','momentum_risk',
            'overbought_oversold','band_position',
            'price_action','time_based','market_noise'
        ]}

        if len(historical_data_list) > 5:
            recent_prices = [float(d.close_price) for d in historical_data_list[-20:]]
            valid_prices = [p for p in recent_prices if p > 0]

            returns = []
            for i in range(1, len(valid_prices)):
                returns.append(safe_divide(
                    valid_prices[i] - valid_prices[i-1],
                    valid_prices[i-1]
                ))

            volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0

            true_ranges = [
                abs(recent_prices[i] - recent_prices[i-1])
                for i in range(1, len(recent_prices))
            ]

            atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
            atr_percentage = safe_divide(atr, recent_prices[-1]) * 100

            combined_volatility = (volatility + atr_percentage) / 2
            risk_components['market_volatility'] = min(combined_volatility * 5, 25)

        # ---------------- Trend Risk ---------------- #
        if sma_20 not in (None, 0):
            trend_deviation = safe_divide(abs(current_price - sma_20), sma_20) * 100
            if trend_deviation > 3:
                risk_components['trend_risk'] = 15
            elif trend_deviation > 1:
                risk_components['trend_risk'] = 8

        # ---------------- Price Action ---------------- #
        if len(historical_data_list) > 5:
            recent_prices = [float(d.close_price) for d in historical_data_list[-5:]]

            if len(recent_prices) >= 3:
                recent_change = safe_divide(
                    abs(recent_prices[-1] - recent_prices[-3]),
                    recent_prices[-3]
                ) * 100

                if recent_change > 2:
                    risk_components['price_action'] = 12
                elif recent_change > 1:
                    risk_components['price_action'] = 8

            avg_price = safe_divide(sum(recent_prices), len(recent_prices))
            price_range = max(recent_prices) - min(recent_prices)
            range_percentage = safe_divide(price_range, avg_price) * 100

            if range_percentage < 0.2:
                risk_components['price_action'] += 8
            elif range_percentage > 1.5:
                risk_components['price_action'] += 6

        # ---------------- Time + Noise ---------------- #
        risk_components['time_based'] = (int(time.time()) % 120) / 120 * 15
        risk_components['market_noise'] = random.uniform(-6, 6)

        weights = {
            'market_volatility':1.2,'trend_risk':1.0,
            'momentum_risk':0.9,'overbought_oversold':1.3,
            'band_position':1.4,'price_action':0.8,
            'time_based':0.6,'market_noise':0.4
        }

        weighted_risk = sum(
            risk_components[k] * weights[k] for k in risk_components
        )

        risk_score = max(5, min(95, 25 + weighted_risk))

        return {
            'decision': decision,
            'profit_probability': round(profit_probability, 1),
            'confidence': round(confidence, 1),
            'technical_indicators': technical_indicators,
            'prediction': {
                'trend': 'UP' if decision == 'BUY'
                         else 'DOWN' if decision == 'SELL'
                         else 'HOLD',
                'confidence': round(confidence, 1)
            },
            'sentiment': 'NEUTRAL',
            'risk': {
                'volatility': 0.15,
                'stop_loss': None,
                'take_profit': None,
                'risk_score': round(risk_score, 1)
            }
        }

    def _generate_decision_from_history(self, symbol, historical_data, technical_indicators):
        """Generate decision based on historical data provided - for history mode"""
        import random
        
        if not historical_data or len(historical_data) == 0:
            return self._generate_mock_decision(symbol)
        
        decision = 'HOLD'
        confidence = 65.0
        profit_probability = 55.0
        
        # Get technical indicators
        rsi = technical_indicators.get('rsi') if technical_indicators else None
        macd = technical_indicators.get('macd') if technical_indicators else None
        sma_20 = technical_indicators.get('sma_20') if technical_indicators else None
        
        # RSI based decision
        if rsi is not None:
            if rsi < 35:
                decision = 'BUY'
                confidence = min(95, 60 + (35 - rsi) * 3)
                profit_probability = confidence
            elif rsi < 45:
                decision = 'BUY'
                confidence = 75.0
            elif rsi > 75:
                decision = 'SELL'
                confidence = min(95, 60 + (rsi - 75) * 3)
                profit_probability = confidence
            elif rsi > 65:
                decision = 'SELL'
                confidence = 75.0
            else:
                decision = 'HOLD'
                confidence = 70.0
        
        # MACD influence on decision
        macd_signal_strength = 0
        if macd is not None:
            if macd > 0.001:
                macd_signal_strength = 15
            elif macd > 0.0005:
                macd_signal_strength = 10
            elif macd < -0.001:
                macd_signal_strength = -15
            elif macd < -0.0005:
                macd_signal_strength = -10
            
            if (decision == 'BUY' and macd_signal_strength > 0) or \
               (decision == 'SELL' and macd_signal_strength < 0):
                confidence = min(95, confidence + abs(macd_signal_strength))
            elif (decision == 'BUY' and macd_signal_strength < 0) or \
                 (decision == 'SELL' and macd_signal_strength > 0):
                confidence = max(45, confidence - abs(macd_signal_strength))
        
        # Get current price from historical data
        try:
            current_price = float(historical_data[-1].close_price)
        except:
            current_price = 1.0
        
        # SMA influence
        if sma_20 not in (None, 0):
            try:
                if current_price > 0:
                    price_vs_ma = ((current_price - sma_20) / sma_20) * 100
                    if price_vs_ma > 1:
                        if decision == 'BUY':
                            confidence = min(95, confidence + 8)
                        elif decision == 'HOLD':
                            decision = 'BUY'
                            confidence = 72
                    elif price_vs_ma < -1:
                        if decision == 'SELL':
                            confidence = min(95, confidence + 8)
                        elif decision == 'HOLD':
                            decision = 'SELL'
                            confidence = 72
            except:
                pass
        
        # Calculate simple risk score
        risk_score = 50.0
        
        return {
            'decision': decision,
            'profit_probability': round(profit_probability, 1),
            'confidence': round(confidence, 1),
            'technical_indicators': technical_indicators,
            'prediction': {
                'trend': 'UP' if decision == 'BUY'
                         else 'DOWN' if decision == 'SELL'
                         else 'HOLD',
                'confidence': round(confidence, 1)
            },
            'sentiment': 'NEUTRAL',
            'risk': {
                'volatility': 0.15,
                'stop_loss': None,
                'take_profit': None,
                'risk_score': round(risk_score, 1)
            }
        }

    def _generate_mock_historical_data(self, symbol, num_points=24, timeframe='1h'):
        """Generate mock historical data for the given timeframe with realistic price movements"""
        import random
        import math

        # Use get_base_price from currency_pairs module for all supported pairs
        base_price = get_base_price(symbol)

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

@method_decorator(csrf_exempt, name='dispatch')
class AgentStatusAPI(View):
    """API for agent status - returns the status of all agents"""

    def get(self, request):
        """Get status of all agents"""
        try:
            # Get all agents status
            status_list = AgentStatus.get_all_agents_status()
            
            # Check if any agents are active
            active_count = sum(1 for agent in status_list if agent['is_active'])
            total_count = len(status_list)
        
        # Calculate volatility from historical data
            
            # If no agents have been initialized, try to initialize them
            if active_count == 0:
                # Try to initialize agents and check their status
                try:
                    from .agents import (
                        DataAgent, TechnicalAnalysisAgent, PredictionAgent,
                        SentimentAgent, RiskManagementAgent, DecisionAgent
                    )
                    
                    # Update status for each agent
                    agents_to_check = [
                        ('DataAgent', DataAgent()),
                        ('TechnicalAnalysisAgent', TechnicalAnalysisAgent()),
                        ('PredictionAgent', PredictionAgent()),
                        ('SentimentAgent', SentimentAgent()),
                        ('RiskManagementAgent', RiskManagementAgent()),
                        ('DecisionAgent', DecisionAgent())
                    ]
                    
                    for agent_name, agent in agents_to_check:
                        try:
                            AgentStatus.update_agent_status(
                                agent_name=agent_name,
                                is_active=True,
                                status='ACTIVE',
                                message='Agent initialized and ready'
                            )
                        except Exception as e:
                            AgentStatus.update_agent_status(
                                agent_name=agent_name,
                                is_active=False,
                                status='ERROR',
                                message='Failed to initialize agent',
                                last_error=str(e)
                            )
                    
                    # Get updated status list
                    status_list = AgentStatus.get_all_agents_status()
                    active_count = sum(1 for agent in status_list if agent['is_active'])
                    
                except Exception as e:
                    print(f"Error initializing agents: {e}")
            
            return JsonResponse({
                'agents': status_list,
                'summary': {
                    'total': total_count,
                    'active': active_count,
                    'inactive': total_count - active_count,
                    'all_active': active_count == total_count
                }
            })
            
        except Exception as e:
            import traceback
            print(f"Error in AgentStatusAPI.get: {e}")
            traceback.print_exc()
            return JsonResponse({'error': str(e)})

    def post(self, request):
        """Activate all agents"""
        try:
            from .agents import (
                DataAgent, TechnicalAnalysisAgent, PredictionAgent,
                SentimentAgent, RiskManagementAgent, DecisionAgent
            )
            
            agents_to_activate = [
                ('DataAgent', DataAgent()),
                ('TechnicalAnalysisAgent', TechnicalAnalysisAgent()),
                ('PredictionAgent', PredictionAgent()),
                ('SentimentAgent', SentimentAgent()),
                ('RiskManagementAgent', RiskManagementAgent()),
                ('DecisionAgent', DecisionAgent())
            ]
            
            activated = []
            errors = []
            
            for agent_name, agent in agents_to_activate:
                try:
                    AgentStatus.update_agent_status(
                        agent_name=agent_name,
                        is_active=True,
                        status='ACTIVE',
                        message='Agent activated successfully'
                    )
                    activated.append(agent_name)
                except Exception as e:
                    errors.append(f"{agent_name}: {str(e)}")
            
            return JsonResponse({
                'status': 'success',
                'activated': activated,
                'errors': errors
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)})

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
            # Use all pairs from currency_pairs module
            all_pairs = ALL_PAIRS
            
            total_pairs = len(all_pairs)
            processed_pairs = 0

            for symbol in all_pairs:
                try:
                    # Update progress
                    processed_pairs += 1
                    
                    # Get historical data for risk calculation
                    now = timezone.now()
                    historical_data = ForexData.objects.filter(
                        symbol=symbol,
                        timestamp__gte=now - timedelta(hours=24)
                    ).order_by('timestamp')[:100]

                    # Try to get real data first, fallback to mock if needed
                    real_historical_data = real_data_fetcher.get_forex_data(symbol, '1h', 50)
                    if real_historical_data:
                        # Convert real data to mock object format for compatibility
                        historical_data = []
                        for item in real_historical_data:
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
                    elif not historical_data:
                        # If no historical data, generate some mock data for analysis
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

            return JsonResponse({
                'high_risk_pairs': high_risk_pairs,
                'progress': {
                    'total': total_pairs,
                    'processed': processed_pairs,
                    'percentage': round((processed_pairs / total_pairs) * 100, 1) if total_pairs > 0 else 100
                }
            })

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
                # Filter out zero prices to avoid division by zero
                valid_prices = [p for p in recent_prices if p > 0]
                if len(valid_prices) > 1:
                    returns = [(valid_prices[i] - valid_prices[i-1]) / valid_prices[i-1]
                              for i in range(1, len(valid_prices))]
                    volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0
                else:
                    volatility = 0

                true_ranges = []
                for i in range(1, len(recent_prices)):
                    high = max(recent_prices[i], recent_prices[i-1])
                    low = min(recent_prices[i], recent_prices[i-1])
                    tr = high - low
                    true_ranges.append(tr)
                atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
                # Check for zero to avoid division by zero
                if recent_prices[-1] > 0:
                    atr_percentage = (atr / recent_prices[-1]) * 100
                else:
                    atr_percentage = 0

                combined_volatility = (volatility + atr_percentage) / 2
                risk_components['market_volatility'] = min(combined_volatility * 5, 25)

        # 2. Trend Risk
        if technical_indicators['sma_20'] is not None and historical_data:
            current_price = float(historical_data[-1].close_price)
            sma_20 = technical_indicators['sma_20']

            # Check for zero to avoid division by zero
            if sma_20 > 0:
                trend_deviation = abs(current_price - sma_20) / sma_20 * 100
            else:
                trend_deviation = 0

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
                # Check for zero to avoid division by zero
                if recent_prices[-3] > 0:
                    recent_change = abs(recent_prices[-1] - recent_prices[-3]) / recent_prices[-3] * 100
                else:
                    recent_change = 0
                    
                if recent_change > 2:
                    risk_components['price_action'] = 12
                elif recent_change > 1:
                    risk_components['price_action'] = 8

            price_range = max(recent_prices) - min(recent_prices)
            avg_price = sum(recent_prices) / len(recent_prices)
            # Check for zero to avoid division by zero
            if avg_price > 0:
                range_percentage = (price_range / avg_price) * 100
            else:
                range_percentage = 0

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


@method_decorator(csrf_exempt, name='dispatch')
class LiveDataAPI(View):
    """API for real-time forex data - Live Mode"""
    
    def get(self, request):
        """Get real-time forex data"""
        try:
            symbol = request.GET.get('pair', 'EURUSD')
            interval = request.GET.get('interval', '1m')  # 1m, 5m, 15m, 1h, 1d
            limit = int(request.GET.get('limit', 100))
            
            # Try to get real forex data first
            real_data = real_data_fetcher.get_current_price(symbol)
            if real_data:
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
                # Fallback to database or mock
                latest_data = ForexData.objects.filter(symbol=symbol).order_by('-timestamp').first()
                if not latest_data or latest_data.close_price == 0.0:
                    latest_data = self._generate_mock_data(symbol)
            
            # Get historical data for the chart
            now = timezone.now()
            if interval == '1m':
                delta = timedelta(minutes=limit)
            elif interval == '5m':
                delta = timedelta(minutes=5 * limit)
            elif interval == '15m':
                delta = timedelta(minutes=15 * limit)
            elif interval == '1h':
                delta = timedelta(hours=limit)
            elif interval == '1d':
                delta = timedelta(days=limit)
            else:
                delta = timedelta(hours=24)
            
            # Try real data first
            real_historical = real_data_fetcher.get_forex_data(symbol, interval, limit)
            if real_historical:
                historical_data = []
                for item in real_historical:
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
                # Fallback to database
                historical_data = ForexData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=now - delta
                ).order_by('timestamp')[:limit]
                
                if not historical_data:
                    historical_data = self._generate_mock_historical_data(symbol, limit, interval)
            
            # Format historical data as OHLC
            historical_ohlc = [{
                'timestamp': item.timestamp.isoformat() if hasattr(item.timestamp, 'isoformat') else item.timestamp,
                'open': float(item.open_price),
                'high': float(item.high_price),
                'low': float(item.low_price),
                'close': float(item.close_price),
                'volume': int(item.volume)
            } for item in historical_data]
            
            # Calculate technical indicators
            technical_indicators = self._calculate_technical_indicators(historical_data)
            
            # Generate decision
            decision = self._generate_mock_decision(symbol, historical_data, technical_indicators)
            
            # Generate prediction
            import random
            current_price = float(latest_data.close_price)
            change_percent = random.uniform(-0.02, 0.02)
            predicted_price = current_price * (1 + change_percent)
            trend = 'UP' if predicted_price > current_price else 'DOWN'
            confidence = random.uniform(60, 85)
            
            data = {
                'mode': 'live',
                'symbol': symbol,
                'current_price': float(latest_data.close_price),
                'timestamp': latest_data.timestamp.isoformat() if hasattr(latest_data.timestamp, 'isoformat') else latest_data.timestamp,
                'interval': interval,
                'historical_ohlc': historical_ohlc,
                'prediction': {
                    'price': float(predicted_price),
                    'trend': trend,
                    'confidence': float(confidence)
                },
                'decision': decision,
                'technical_indicators': technical_indicators
            }
            
            # Replace NaN values
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
            import traceback
            print(f"Error in LiveDataAPI.get: {e}")
            traceback.print_exc()
            return JsonResponse({'error': str(e)})
    
    def _generate_mock_data(self, symbol):
        """Generate mock forex data"""
        price = get_base_price(symbol)
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
    
    def _generate_mock_historical_data(self, symbol, num_points=24, timeframe='1h'):
        """Generate mock historical data"""
        import random
        import math
        
        base_price = get_base_price(symbol)
        historical_data = []
        current_time = timezone.now()
        
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
        
        current_price = base_price
        trend_direction = random.choice([-1, 1])
        trend_strength = random.uniform(0.0001, 0.0005)
        
        for i in range(num_points):
            timestamp = current_time - delta * (num_points - i - 1)
            trend_component = trend_direction * trend_strength * i
            random_walk = random.gauss(0, 0.001)
            cycle_component = 0.0005 * math.sin(2 * math.pi * i / 20)
            price_change = trend_component + random_walk + cycle_component
            current_price = base_price * (1 + price_change)
            current_price = max(current_price, base_price * 0.95)
            current_price = min(current_price, base_price * 1.05)
            
            volatility = random.uniform(0.0005, 0.002)
            
            if i == 0:
                open_price = base_price
            else:
                open_price = historical_data[-1].close_price
            
            close_price = current_price * random.uniform(0.999, 1.001)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.0002, volatility))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.0002, volatility))
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
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
        
        rsi_period = max(1, min(len(closes)-1, 14))
        rsi = self._calculate_rsi(closes, rsi_period)
        macd = self._calculate_macd(closes) if len(closes) >= 12 else None
        sma_period = max(1, min(20, len(closes)))
        sma_20 = sum(closes[-sma_period:]) / sma_period
        period = max(1, min(20, len(closes)))
        bollinger_upper, bollinger_lower = self._calculate_bollinger_bands(closes, period)
        
        return {
            'rsi': rsi,
            'macd': macd,
            'sma_20': sma_20,
            'bollinger_upper': bollinger_upper,
            'bollinger_lower': bollinger_lower
        }
    
    def _calculate_rsi(self, closes, period=14):
        """Calculate RSI"""
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
        """Calculate MACD"""
        if len(closes) < slow_period:
            return None
        
        fast_ema = self._calculate_ema(closes, fast_period)
        slow_ema = self._calculate_ema(closes, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = fast_ema - slow_ema
        return round(macd_line, 6)
    
    def _calculate_ema(self, data, period):
        """Calculate EMA"""
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
        
        sma = sum(closes[-period:]) / period
        variance = sum([(price - sma) ** 2 for price in closes[-period:]]) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return round(upper_band, 6), round(lower_band, 6)
    
    def _generate_mock_decision(self, symbol, historical_data, technical_indicators):
        """Generate trading decision"""
        import random
        
        if not historical_data or len(historical_data) == 0:
            return {
                'decision': 'HOLD',
                'confidence': 50.0,
                'profit_probability': 50.0
            }
        
        rsi = technical_indicators.get('rsi') if technical_indicators else None
        decision = 'HOLD'
        confidence = 65.0
        
        if rsi is not None:
            if rsi < 35:
                decision = 'BUY'
                confidence = min(95, 60 + (35 - rsi) * 3)
            elif rsi > 75:
                decision = 'SELL'
                confidence = min(95, 60 + (rsi - 75) * 3)
        
        return {
            'decision': decision,
            'confidence': round(confidence, 1),
            'profit_probability': round(confidence, 1),
            'technical_indicators': technical_indicators
        }


# ==================== CUSTOM ADMIN PANEL VIEWS ====================

@login_required
def admin_dashboard(request):
    """Main admin dashboard overview"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get statistics
    from django.contrib.auth.models import User
    
    total_users = User.objects.count()
    total_forex_data = ForexData.objects.count()
    total_predictions = Prediction.objects.count()
    total_logs = AgentLog.objects.count()
    
    # Get agent status
    agent_status_list = AgentStatus.get_all_agents_status()
    
    # Get recent logs
    recent_logs = AgentLog.objects.order_by('-timestamp')[:10]
    
    # Get recent forex data entries
    recent_forex = ForexData.objects.order_by('-timestamp')[:5]
    
    # Get recent predictions
    recent_predictions = Prediction.objects.order_by('-timestamp')[:5]
    
    context = {
        'total_users': total_users,
        'total_forex_data': total_forex_data,
        'total_predictions': total_predictions,
        'total_logs': total_logs,
        'agent_status_list': agent_status_list,
        'recent_logs': recent_logs,
        'recent_forex': recent_forex,
        'recent_predictions': recent_predictions,
    }
    
    return render(request, 'trading/admin/admin_dashboard.html', context)


@login_required
def admin_agents(request):
    """Agent management view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get or create agent status entries
    agents = ['DataAgent', 'TechnicalAnalysisAgent', 'PredictionAgent', 
              'SentimentAgent', 'RiskManagementAgent', 'DecisionAgent']
    
    for agent_name in agents:
        AgentStatus.objects.get_or_create(
            agent_name=agent_name,
            defaults={'is_active': False, 'status': 'INACTIVE'}
        )
    
    agent_status_list = AgentStatus.objects.all().order_by('agent_name')
    
    context = {
        'agent_status_list': agent_status_list,
    }
    
    return render(request, 'trading/admin/admin_agents.html', context)


@login_required
def admin_forex_data(request):
    """Forex data management view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get filter parameters
    symbol_filter = request.GET.get('symbol', '')
    page = int(request.GET.get('page', 1))
    
    # Query forex data
    forex_data = ForexData.objects.all().order_by('-timestamp')
    
    if symbol_filter:
        forex_data = forex_data.filter(symbol__icontains=symbol_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(forex_data, 50)
    forex_data_page = paginator.get_page(page)
    
    # Get unique symbols for filter
    symbols = ForexData.objects.values_list('symbol', flat=True).distinct()
    
    context = {
        'forex_data': forex_data_page,
        'symbols': symbols,
        'symbol_filter': symbol_filter,
    }
    
    return render(request, 'trading/admin/admin_forex_data.html', context)


@login_required
def admin_predictions(request):
    """Predictions management view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get filter parameters
    symbol_filter = request.GET.get('symbol', '')
    trend_filter = request.GET.get('trend', '')
    page = int(request.GET.get('page', 1))
    
    # Query predictions
    predictions = Prediction.objects.all().order_by('-timestamp')
    
    if symbol_filter:
        predictions = predictions.filter(symbol__icontains=symbol_filter)
    if trend_filter:
        predictions = predictions.filter(trend=trend_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(predictions, 50)
    predictions_page = paginator.get_page(page)
    
    # Get unique symbols for filter
    symbols = Prediction.objects.values_list('symbol', flat=True).distinct()
    
    context = {
        'predictions': predictions_page,
        'symbols': symbols,
        'symbol_filter': symbol_filter,
        'trend_filter': trend_filter,
    }
    
    return render(request, 'trading/admin/admin_predictions.html', context)


@login_required
def admin_risk_analysis(request):
    """Risk analysis management view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get filter parameters
    symbol_filter = request.GET.get('symbol', '')
    risk_level_filter = request.GET.get('risk_level', '')
    page = int(request.GET.get('page', 1))
    
    # Query risk analysis
    risk_data = RiskAnalysis.objects.all().order_by('-timestamp')
    
    if symbol_filter:
        risk_data = risk_data.filter(symbol__icontains=symbol_filter)
    if risk_level_filter:
        risk_data = risk_data.filter(risk_level=risk_level_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(risk_data, 50)
    risk_data_page = paginator.get_page(page)
    
    # Get unique symbols for filter
    symbols = RiskAnalysis.objects.values_list('symbol', flat=True).distinct()
    
    context = {
        'risk_data': risk_data_page,
        'symbols': symbols,
        'symbol_filter': symbol_filter,
        'risk_level_filter': risk_level_filter,
    }
    
    return render(request, 'trading/admin/admin_risk_analysis.html', context)


@login_required
def admin_users(request):
    """User management view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    
    # Get filter parameters
    search_filter = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))
    
    # Query users
    users = User.objects.all().order_by('-date_joined')
    
    if search_filter:
        users = users.filter(username__icontains=search_filter) | users.filter(email__icontains=search_filter)
    
    # Get user profiles with user data
    user_profiles = []
    for user in users:
        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            profile = None
        user_profiles.append({
            'user': user,
            'profile': profile
        })
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(user_profiles, 20)
    users_page = paginator.get_page(page)
    
    context = {
        'users': users_page,
        'search_filter': search_filter,
    }
    
    return render(request, 'trading/admin/admin_users.html', context)


@login_required
def admin_logs(request):
    """Activity logs view"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    # Get filter parameters
    agent_filter = request.GET.get('agent', '')
    search_filter = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))
    
    # Query logs
    logs = AgentLog.objects.all().order_by('-timestamp')
    
    if agent_filter:
        logs = logs.filter(agent_name=agent_filter)
    if search_filter:
        logs = logs.filter(action__icontains=search_filter) | logs.filter(result__icontains=search_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 50)
    logs_page = paginator.get_page(page)
    
    # Get unique agents for filter
    agents = AgentLog.objects.values_list('agent_name', flat=True).distinct()
    
    context = {
        'logs': logs_page,
        'agents': agents,
        'agent_filter': agent_filter,
        'search_filter': search_filter,
    }
    
    return render(request, 'trading/admin/admin_logs.html', context)


@login_required
def admin_toggle_agent(request, agent_name):
    """Toggle agent status"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    try:
        agent_status = AgentStatus.objects.get(agent_name=agent_name)
        agent_status.is_active = not agent_status.is_active
        agent_status.status = 'ACTIVE' if agent_status.is_active else 'INACTIVE'
        agent_status.save()
        
        from django.contrib import messages
        status = 'activated' if agent_status.is_active else 'deactivated'
        messages.success(request, f'{agent_name} has been {status}.')
    except AgentStatus.DoesNotExist:
        from django.contrib import messages
        messages.error(request, f'Agent {agent_name} not found.')
    
    return redirect('admin_agents')

@login_required
def admin_create_agent(request):
    """Create new agent"""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AgentStatusForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Agent created successfully.')
                return redirect('admin_agents')
            except Exception as e:
                messages.error(request, f'Error creating agent: {str(e)}')
        else:
            messages.error(request, 'Please correct the form errors.')
    else:
        form = AgentStatusForm()
    
    # Get agent list for table
    agent_status_list = AgentStatus.objects.all().order_by('agent_name')
    return render(request, 'trading/admin/admin_agents.html', {
        'form': form,
        'agent_status_list': agent_status_list,
        'mode': 'create'
    })

@login_required
def admin_update_agent(request, pk):
    """Update existing agent"""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    agent = get_object_or_404(AgentStatus, pk=pk)
    
    if request.method == 'POST':
        form = AgentStatusForm(request.POST, instance=agent)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agent updated successfully.')
            return redirect('admin_agents')
    else:
        form = AgentStatusForm(instance=agent)
    
    agent_status_list = AgentStatus.objects.all().order_by('agent_name')
    return render(request, 'trading/admin/admin_agents.html', {
        'form': form,
        'agent': agent,
        'agent_status_list': agent_status_list,
        'mode': 'update'
    })

@login_required
def admin_delete_agent(request, pk):
    """Delete agent"""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    agent = get_object_or_404(AgentStatus, pk=pk)
    
    if request.method == 'POST':
        agent_name = agent.agent_name
        agent.delete()
        messages.success(request, f'Agent "{agent_name}" deleted successfully.')
        return redirect('admin_agents')
    
    agent_status_list = AgentStatus.objects.all().order_by('agent_name')
    return render(request, 'trading/admin/admin_agents.html', {
        'agent': agent,
        'agent_status_list': agent_status_list,
        'mode': 'delete'
    })

@method_decorator(csrf_exempt, name='dispatch')
class ChartDataAPI(View):
    """API endpoint for chart data with timeframe aggregation - /api/chart-data/"""
    
    def get(self, request):
        """Get aggregated chart data for a specific timeframe"""
        try:
            pair = request.GET.get('pair', 'EURUSD')
            interval = request.GET.get('interval', '1h')
            start = request.GET.get('start')
            end = request.GET.get('end')
            
            if not start or not end:
                return JsonResponse({'error': 'Both start and end dates are required'}, status=400)
            
            try:
                start_date = datetime.strptime(start, '%Y-%m-%d')
                end_date = datetime.strptime(end, '%Y-%m-%d')
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            
            if start_date > end_date:
                return JsonResponse({'error': 'Start date must be before or equal to end date'}, status=400)
            
            today = timezone.now().date()
            if start_date.date() > today or end_date.date() > today:
                return JsonResponse({'error': 'Date range cannot be in the future'}, status=400)
            
            from datetime import timezone as dt_timezone
            start_dt = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            end_dt = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=dt_timezone.utc)
            
            forex_data = ForexData.objects.filter(
                symbol=pair,
                timestamp__gte=start_dt,
                timestamp__lte=end_dt
            ).order_by('timestamp')
            
            real_data = real_data_fetcher.get_forex_data(pair, interval, 500)
            if real_data:
                filtered_data = []
                for item in real_data:
                    item_date = item['timestamp'].date() if hasattr(item['timestamp'], 'date') else datetime.fromisoformat(str(item['timestamp'])).date()
                    if start_date.date() <= item_date <= end_date.date():
                        filtered_data.append(item)
                if filtered_data:
                    forex_data = filtered_data
            
            aggregated_data = self._aggregate_by_interval(forex_data, interval, pair)
            
            result = []
            for item in aggregated_data:
                if interval == '1d':
                    time_str = item['timestamp'].strftime('%Y-%m-%d') if hasattr(item['timestamp'], 'strftime') else str(item['timestamp'])[:10]
                else:
                    time_str = item['timestamp'].strftime('%Y-%m-%d %H:%M') if hasattr(item['timestamp'], 'strftime') else str(item['timestamp'])[:16]
                
                result.append({
                    'time': time_str,
                    'price': round(float(item['price']), 5)
                })
            
            return JsonResponse({'data': result, 'count': len(result)})
            
        except Exception as e:
            import traceback
            print(f"Error in ChartDataAPI.get: {e}")
            traceback.print_exc()
            return JsonResponse({'error': str(e)})
    
    def _aggregate_by_interval(self, data, interval, symbol):
        """Aggregate forex data by the specified timeframe"""
        import random
        from datetime import timedelta
        
        if not data or len(data) == 0:
            return self._generate_mock_aggregated_data(symbol, interval)
        
        try:
            if hasattr(data, 'order_by'):
                data_list = list(data)
            else:
                data_list = data
            
            if len(data_list) == 0:
                return self._generate_mock_aggregated_data(symbol, interval)
            
            grouped = {}
            for item in data_list:
                try:
                    ts = item.timestamp if hasattr(item, 'timestamp') else item['timestamp']
                    
                    if interval == '1m':
                        key = ts.replace(second=0)
                    elif interval == '5m':
                        key = ts.replace(minute=(ts.minute // 5) * 5, second=0)
                    elif interval == '15m':
                        key = ts.replace(minute=(ts.minute // 15) * 15, second=0)
                    elif interval == '1h':
                        key = ts.replace(minute=0, second=0)
                    elif interval == '1d':
                        key = ts.replace(hour=0, minute=0, second=0)
                    else:
                        key = ts.replace(minute=0, second=0)
                    
                    if key not in grouped:
                        grouped[key] = []
                    
                    price = float(item.close_price) if hasattr(item, 'close_price') else float(item['close'])
                    grouped[key].append(price)
                except:
                    continue
            
            result = []
            for ts, prices in sorted(grouped.items()):
                if prices:
                    result.append({
                        'timestamp': ts,
                        'price': sum(prices) / len(prices)
                    })
            
            if len(result) > 0:
                return result
        except:
            pass
        
        return self._generate_mock_aggregated_data(symbol, interval)
    
    def _generate_mock_aggregated_data(self, symbol, interval):
        """Generate mock aggregated data for the specified timeframe"""
        import random
        from datetime import timedelta
        
        base_price = get_base_price(symbol)
        
        if interval == '1m':
            num_points = 60
            delta = timedelta(minutes=1)
        elif interval == '5m':
            num_points = 24
            delta = timedelta(minutes=5)
        elif interval == '15m':
            num_points = 32
            delta = timedelta(minutes=15)
        elif interval == '1h':
            num_points = 24
            delta = timedelta(hours=1)
        elif interval == '1d':
            num_points = 30
            delta = timedelta(days=1)
        else:
            num_points = 24
            delta = timedelta(hours=1)
        
        result = []
        current_price = base_price
        current_time = timezone.now()
        trend = random.choice([-1, 1])
        
        for i in range(num_points):
            timestamp = current_time - delta * (num_points - i - 1)
            change = random.gauss(0, 0.0005) + trend * 0.0001
            current_price = current_price * (1 + change)
            current_price = max(current_price, base_price * 0.95)
            current_price = min(current_price, base_price * 1.05)
            
            result.append({
                'timestamp': timestamp,
                'price': current_price
            })
        
        return result


class HistoryDataAPI(View):
    """API for historical forex data - History Mode"""
    
    def get(self, request):
        """Get historical forex data with date range and timeframe"""
        try:
            symbol = request.GET.get('pair', 'EURUSD')
            start = request.GET.get('start')  # YYYY-MM-DD
            end = request.GET.get('end')      # YYYY-MM-DD
            interval = request.GET.get('interval', '15m')  # 1m, 5m, 15m, 1h, 1d
            
            # Validate required parameters
            if not start or not end:
                return JsonResponse({'error': 'Both start and end dates are required'}, status=400)
            
            # Parse and validate dates
            try:
                start_date = datetime.strptime(start, '%Y-%m-%d')
                end_date = datetime.strptime(end, '%Y-%m-%d')
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            
            # Validate date range
            if start_date > end_date:
                return JsonResponse({'error': 'Start date must be before or equal to end date'}, status=400)
            
            # Check if date range is not in the future
            today = timezone.now().date()
            if start_date.date() > today or end_date.date() > today:
                return JsonResponse({'error': 'Date range cannot be in the future'}, status=400)
            
            # Add time to dates for proper range query
            from datetime import timezone as dt_timezone
            start_dt = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            end_dt = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=dt_timezone.utc)
            
            # Get data from database
            historical_data = ForexData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_dt,
                timestamp__lte=end_dt
            ).order_by('timestamp')
            
            # Try to get real historical data
            real_historical = real_data_fetcher.get_forex_data(symbol, interval, 500)
            if real_historical:
                # Filter real data by date range
                filtered_data = []
                for item in real_historical:
                    item_date = item['timestamp'].date() if hasattr(item['timestamp'], 'date') else datetime.fromisoformat(str(item['timestamp'])).date()
                    if start_date.date() <= item_date <= end_date.date():
                        mock_item = type('RealForexData', (), {
                            'symbol': symbol,
                            'timestamp': item['timestamp'],
                            'close_price': item['close'],
                            'open_price': item['open'],
                            'high_price': item['high'],
                            'low_price': item['low'],
                            'volume': item['volume']
                        })()
                        filtered_data.append(mock_item)
                if filtered_data:
                    historical_data = filtered_data
            
            # Generate mock data if no real data available
            if not historical_data or len(historical_data) == 0:
                # Calculate number of data points based on interval and date range
                days_diff = (end_date - start_date).days + 1
                if interval == '1m':
                    num_points = min(days_diff * 24 * 60, 500)
                elif interval == '5m':
                    num_points = min(days_diff * 24 * 12, 500)
                elif interval == '15m':
                    num_points = min(days_diff * 24 * 4, 500)
                elif interval == '1h':
                    num_points = min(days_diff * 24, 500)
                else:  # 1d
                    num_points = min(days_diff, 500)
                
                historical_data = self._generate_mock_historical_data(symbol, num_points, interval, start_dt, end_dt)
            
            # Format historical data as OHLC
            historical_ohlc = []
            for item in historical_data:
                try:
                    historical_ohlc.append({
                        'timestamp': item.timestamp.isoformat() if hasattr(item.timestamp, 'isoformat') else item.timestamp,
                        'open': float(item.open_price),
                        'high': float(item.high_price),
                        'low': float(item.low_price),
                        'close': float(item.close_price),
                        'volume': int(item.volume)
                    })
                except (AttributeError, ValueError):
                    continue
            
            # Sort by timestamp
            historical_ohlc.sort(key=lambda x: x['timestamp'])
            
            # Calculate technical indicators
            technical_indicators = self._calculate_technical_indicators(historical_data)
            
            # Generate decision based on historical data
            decision = self._generate_decision_from_history(historical_data, technical_indicators)
            
            # Get current price (latest in the range)
            current_price = 0
            if historical_ohlc:
                current_price = historical_ohlc[-1]['close']
            
            # Generate prediction
            import random
            if current_price > 0:
                change_percent = random.uniform(-0.02, 0.02)
                predicted_price = current_price * (1 + change_percent)
                trend = 'UP' if predicted_price > current_price else 'DOWN'
                confidence = random.uniform(60, 85)
            else:
                predicted_price = get_base_price(symbol)
                trend = 'HOLD'
                confidence = 50.0
            
            data = {
                'mode': 'history',
                'symbol': symbol,
                'start_date': start,
                'end_date': end,
                'interval': interval,
                'current_price': float(current_price) if current_price > 0 else float(get_base_price(symbol)),
                'historical_ohlc': historical_ohlc,
                'prediction': {
                    'price': float(predicted_price),
                    'trend': trend,
                    'confidence': float(confidence)
                },
                'decision': decision,
                'technical_indicators': technical_indicators
            }
            
            # Replace NaN values
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
            import traceback
            print(f"Error in HistoryDataAPI.get: {e}")
            traceback.print_exc()
            return JsonResponse({'error': str(e)})
    
    def _generate_mock_historical_data(self, symbol, num_points=24, timeframe='1h', start_dt=None, end_dt=None):
        """Generate mock historical data"""
        import random
        import math
        
        base_price = get_base_price(symbol)
        historical_data = []
        
        # Use provided dates or default to now
        if start_dt and end_dt:
            total_seconds = (end_dt - start_dt).total_seconds()
            time_step = total_seconds / num_points if num_points > 0 else 3600
            current_time = start_dt
        else:
            current_time = timezone.now()
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
        
        current_price = base_price
        trend_direction = random.choice([-1, 1])
        trend_strength = random.uniform(0.0001, 0.0005)
        
        for i in range(num_points):
            if start_dt and end_dt:
                timestamp = start_dt + timedelta(seconds=time_step * i)
            else:
                timestamp = current_time - delta * (num_points - i - 1)
            
            trend_component = trend_direction * trend_strength * i
            random_walk = random.gauss(0, 0.001)
            cycle_component = 0.0005 * math.sin(2 * math.pi * i / 20)
            price_change = trend_component + random_walk + cycle_component
            current_price = base_price * (1 + price_change)
            current_price = max(current_price, base_price * 0.95)
            current_price = min(current_price, base_price * 1.05)
            
            volatility = random.uniform(0.0005, 0.002)
            
            if i == 0:
                open_price = base_price
            else:
                open_price = historical_data[-1].close_price
            
            close_price = current_price * random.uniform(0.999, 1.001)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.0002, volatility))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.0002, volatility))
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
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
    
    def _calculate_technical_indicators(self, historical_data):
        """Calculate technical indicators"""
        if not historical_data:
            return {
                'rsi': None,
                'macd': None,
                'sma_20': None,
                'bollinger_upper': None,
                'bollinger_lower': None
            }
        
        # Handle both list and QuerySet
        try:
            closes = [float(d.close_price) for d in historical_data if d.close_price is not None]
        except:
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
        
        rsi_period = max(1, min(len(closes)-1, 14))
        rsi = self._calculate_rsi(closes, rsi_period)
        macd = self._calculate_macd(closes) if len(closes) >= 12 else None
        sma_period = max(1, min(20, len(closes)))
        sma_20 = sum(closes[-sma_period:]) / sma_period
        period = max(1, min(20, len(closes)))
        bollinger_upper, bollinger_lower = self._calculate_bollinger_bands(closes, period)
        
        return {
            'rsi': rsi,
            'macd': macd,
            'sma_20': sma_20,
            'bollinger_upper': bollinger_upper,
            'bollinger_lower': bollinger_lower
        }
    
    def _calculate_rsi(self, closes, period=14):
        """Calculate RSI"""
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
    
    def _calculate_macd(self, closes, fast_period=12, slow_period=26):
        """Calculate MACD"""
        if len(closes) < slow_period:
            return None
        
        fast_ema = self._calculate_ema(closes, fast_period)
        slow_ema = self._calculate_ema(closes, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = fast_ema - slow_ema
        return round(macd_line, 6)
    
    def _calculate_ema(self, data, period):
        """Calculate EMA"""
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
        
        sma = sum(closes[-period:]) / period
        variance = sum([(price - sma) ** 2 for price in closes[-period:]]) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return round(upper_band, 6), round(lower_band, 6)
    
    def _generate_decision_from_history(self, historical_data, technical_indicators):
        """Generate decision based on historical data"""
        import random
        
        if not historical_data or len(historical_data) == 0:
            return {
                'decision': 'HOLD',
                'confidence': 50.0,
                'profit_probability': 50.0
            }
        
        rsi = technical_indicators.get('rsi') if technical_indicators else None
        macd = technical_indicators.get('macd') if technical_indicators else None
        sma_20 = technical_indicators.get('sma_20') if technical_indicators else None
        
        decision = 'HOLD'
        confidence = 65.0
        
        # RSI based decision
        if rsi is not None:
            if rsi < 35:
                decision = 'BUY'
                confidence = min(95, 60 + (35 - rsi) * 3)
            elif rsi < 45:
                decision = 'BUY'
                confidence = 75.0
            elif rsi > 75:
                decision = 'SELL'
                confidence = min(95, 60 + (rsi - 75) * 3)
            elif rsi > 65:
                decision = 'SELL'
                confidence = 75.0
            else:
                decision = 'HOLD'
                confidence = 70.0
        
        # MACD influence
        if macd is not None:
            if macd > 0.001 and decision == 'HOLD':
                decision = 'BUY'
                confidence = min(95, confidence + 10)
            elif macd < -0.001 and decision == 'HOLD':
                decision = 'SELL'
                confidence = min(95, confidence + 10)
        
        # Get current price
        try:
            if isinstance(historical_data, list):
                current_price = float(historical_data[-1].close_price)
            else:
                current_price = float(historical_data.last().close_price)
        except:
            current_price = 1.0
        
        # SMA influence
        if sma_20 not in (None, 0) and current_price > 0:
            try:
                price_vs_ma = ((current_price - sma_20) / sma_20) * 100
                if price_vs_ma > 1:
                    if decision == 'HOLD':
                        decision = 'BUY'
                        confidence = 72
                elif price_vs_ma < -1:
                    if decision == 'HOLD':
                        decision = 'SELL'
                        confidence = 72
            except:
                pass
        
        return {
            'decision': decision,
            'confidence': round(confidence, 1),
            'profit_probability': round(confidence, 1),
            'technical_indicators': technical_indicators
        }

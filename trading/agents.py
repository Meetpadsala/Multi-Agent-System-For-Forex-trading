import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import os
from .models import ForexData, Prediction, AgentLog
from django.conf import settings
import logging
from .currency_pairs import BASE_PRICES, SENTIMENT_MAP, get_base_price, get_sentiment

# Lazy imports for TensorFlow to avoid DLL issues on Windows
def get_tensorflow_imports():
    try:
        from tensorflow import keras
        from keras.models import Sequential, load_model  
        from keras.layers import LSTM, Dense, Dropout  
        return Sequential, load_model, LSTM, Dense, Dropout
    except ImportError as e:
        logger.error(f"TensorFlow import failed: {e}")
        return None, None, None, None, None

logger = logging.getLogger(__name__)

class DataAgent:
    def __init__(self):
        self.api_key = settings.FINNHUB_API_KEY
        self.base_url = 'https://finnhub.io/api/v1'

    def fetch_real_time_data(self, symbol):
        """Fetch real-time forex data from Finnhub"""
        try:
            url = f"{self.base_url}/quote?symbol={symbol}&token={self.api_key}"
            response = requests.get(url)
            data = response.json()

            if 'c' in data:  # Current price
                forex_data = ForexData(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    open_price=data.get('o', data['c']),
                    high_price=data.get('h', data['c']),
                    low_price=data.get('l', data['c']),
                    close_price=data['c'],
                    volume=data.get('v', 0)
                )
                forex_data.save()
                AgentLog.objects.create(agent_name='DataAgent', action=f'Fetched data for {symbol}', result=f'Price: {data["c"]}')
                return forex_data
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
        return None

    def get_historical_data(self, symbol, days=30):
        """Fetch historical data"""
        data = list(ForexData.objects.filter(symbol=symbol).order_by('-timestamp')[:days*24])
        if not data:
            data = self._generate_mock_historical_data(symbol, days)
        return data

    def _generate_mock_historical_data(self, symbol, days):
        """Generate mock historical data for testing"""
        base_price = get_base_price(symbol)
        mock_data = []
        now = datetime.now()
        
        for i in range(days * 24, 0, -1):
            timestamp = now - timedelta(hours=i)
            import random
            variation = random.uniform(-0.01, 0.01)
            close_price = base_price * (1 + variation)
            mock_entry = type('MockForexData', (), {
                'symbol': symbol,
                'timestamp': timestamp,
                'close_price': close_price,
                'open_price': close_price,
                'high_price': close_price * 1.001,
                'low_price': close_price * 0.999,
                'volume': random.randint(1000, 10000)
            })()
            mock_data.append(mock_entry)
        return mock_data

class TechnicalAnalysisAgent:
    def __init__(self):
        pass

    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_moving_average(self, prices, period=20):
        return prices.rolling(window=period).mean()

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        sma = self.calculate_moving_average(prices, period)
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower

    def analyze(self, symbol):
        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol)
        if not historical_data:
            return None

        if hasattr(historical_data, 'values') and hasattr(historical_data, 'model'):
            df = pd.DataFrame([{'timestamp': obj.timestamp, 'close_price': obj.close_price} for obj in historical_data])
        elif isinstance(historical_data, list):
            df = pd.DataFrame([{'timestamp': item.timestamp, 'close_price': item.close_price} for item in historical_data])
        else:
            return None

        df['close'] = df['close_price'].astype(float)
        df = df.set_index('timestamp').sort_index()

        analysis = {
            'rsi': self.calculate_rsi(df['close']).iloc[-1] if len(df) > 14 else None,
            'macd': self.calculate_macd(df['close'])[0].iloc[-1] if len(df) > 26 else None,
            'sma_20': self.calculate_moving_average(df['close'], 20).iloc[-1] if len(df) > 20 else None,
            'bollinger_upper': self.calculate_bollinger_bands(df['close'])[0].iloc[-1] if len(df) > 20 else None,
            'bollinger_lower': self.calculate_bollinger_bands(df['close'])[2].iloc[-1] if len(df) > 20 else None,
        }
        AgentLog.objects.create(agent_name='TechnicalAnalysisAgent', action=f'Analyzed {symbol}', result=str(analysis))
        return analysis

class PredictionAgent:
    def __init__(self):
        self.tf_available = False
        self.Sequential, self.load_model, self.LSTM, self.Dense, self.Dropout = get_tensorflow_imports()
        if self.Sequential is not None:
            self.tf_available = True
            self.models = {}
            self.scalers = {}
        else:
            logger.warning("TensorFlow not available. Using mock predictions.")

    def get_model_path(self, symbol):
        return os.path.join(settings.BASE_DIR, 'trading', f'lstm_model_{symbol}.h5')

    def get_scaler_path(self, symbol):
        return os.path.join(settings.BASE_DIR, 'trading', f'scaler_{symbol}.pkl')

    def load_model_and_scaler(self, symbol):
        if not self.tf_available:
            return None, None
        if symbol in self.models and symbol in self.scalers:
            return self.models[symbol], self.scalers[symbol]
        model_path = self.get_model_path(symbol)
        scaler_path = self.get_scaler_path(symbol)
        if os.path.exists(model_path) and os.path.exists(scaler_path):
            try:
                import joblib
                model = self.load_model(model_path)
                scaler = joblib.load(scaler_path)
                self.models[symbol] = model
                self.scalers[symbol] = scaler
                return model, scaler
            except Exception as e:
                logger.error(f"Error loading model for {symbol}: {e}")
        return None, None

    def train_model(self, symbol):
        if not self.tf_available:
            return False
        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol, days=365)
        if not historical_data:
            return False
        if hasattr(historical_data, "values"):
            df = pd.DataFrame(list(historical_data.values('timestamp', 'close_price')))
        else:
            df = pd.DataFrame([{'timestamp': d.timestamp, 'close_price': d.close_price} for d in historical_data])
        df['close'] = df['close_price'].astype(float)
        df = df.set_index('timestamp').sort_index()
        if len(df) < 100:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} points")
            return False
        scaler = MinMaxScaler(feature_range=(0, 1))
        data = df['close'].values.reshape(-1, 1)
        scaled_data = scaler.fit_transform(data)
        look_back = 60
        X_train, y_train = [], []
        for i in range(look_back, len(scaled_data)):
            X_train.append(scaled_data[i-look_back:i, 0])
            y_train.append(scaled_data[i, 0])
        X_train, y_train = np.array(X_train), np.array(y_train)
        X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
        model = self.Sequential()
        model.add(self.LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], 1)))
        model.add(self.Dropout(0.2))
        model.add(self.LSTM(units=50, return_sequences=False))
        model.add(self.Dropout(0.2))
        model.add(self.Dense(units=1))
        model.compile(optimizer='adam', loss='mean_squared_error')
        model.fit(X_train, y_train, epochs=25, batch_size=32, verbose=0)
        model_path = self.get_model_path(symbol)
        scaler_path = self.get_scaler_path(symbol)
        model.save(model_path)
        import joblib
        joblib.dump(scaler, scaler_path)
        self.models[symbol] = model
        self.scalers[symbol] = scaler
        return True

    def predict(self, symbol):
        model, scaler = self.load_model_and_scaler(symbol)
        if model is None or scaler is None:
            if self.tf_available and not self.train_model(symbol):
                return self._mock_predict(symbol)
            elif self.tf_available:
                model, scaler = self.load_model_and_scaler(symbol)
                if model is None or scaler is None:
                    return self._mock_predict(symbol)
            else:
                return self._mock_predict(symbol)
        try:
            data_agent = DataAgent()
            historical_data = data_agent.get_historical_data(symbol, days=60)
            if not historical_data:
                return self._mock_predict(symbol)
            if hasattr(historical_data, "values"):
                df = pd.DataFrame(list(historical_data.values('timestamp', 'close_price')))
            else:
                df = pd.DataFrame([{'timestamp': d.timestamp, 'close_price': d.close_price} for d in historical_data])
            df['close'] = df['close_price']
            df = df.set_index('timestamp').sort_index()
            if len(df) < 60:
                return self._mock_predict(symbol)
            data = df['close'].values.reshape(-1, 1)
            scaled_data = scaler.transform(data)
            look_back = 60
            X_test = scaled_data[-look_back:].reshape(1, look_back, 1)
            predicted_scaled = model.predict(X_test, verbose=0)
            predicted_price = scaler.inverse_transform(predicted_scaled)[0][0]
            current_price = df['close'].iloc[-1]
            trend = 'UP' if predicted_price > current_price else 'DOWN'
            confidence = min(abs(predicted_price - current_price) / current_price * 100, 100)
            prediction = Prediction.objects.create(symbol=symbol, predicted_price=predicted_price, trend=trend, confidence=confidence)
            AgentLog.objects.create(agent_name='PredictionAgent', action=f'Predicted for {symbol}', result=f'{trend} with {confidence:.1f}% confidence')
            return prediction
        except Exception as e:
            logger.error(f"Error predicting for {symbol}: {e}")
            return self._mock_predict(symbol)

    def _mock_predict(self, symbol):
        try:
            data_agent = DataAgent()
            historical_data = data_agent.get_historical_data(symbol, days=1)
            if historical_data:
                if hasattr(historical_data, 'first'):
                    latest_data = historical_data.first()
                else:
                    latest_data = historical_data[0] if historical_data else None
                if latest_data:
                    current_price = float(latest_data.close_price)
                else:
                    current_price = None
            else:
                current_price = None
            if current_price is None:
                base_prices = {'EURUSD': 1.08, 'GBPUSD': 1.27, 'USDJPY': 150.0, 'USDINR': 83.0}
                current_price = base_prices.get(symbol, 1.0)
            current_price = float(current_price)
            import random
            change_percent = random.uniform(-0.05, 0.05)
            predicted_price = current_price * (1 + change_percent)
            trend = 'UP' if predicted_price > current_price else 'DOWN'
            confidence = random.uniform(50, 90)
            prediction = Prediction.objects.create(symbol=symbol, predicted_price=predicted_price, trend=trend, confidence=confidence)
            AgentLog.objects.create(agent_name='PredictionAgent', action=f'Mock predicted for {symbol}', result=f'{trend} with {confidence:.1f}% confidence (MOCK)')
            return prediction
        except Exception as e:
            logger.error(f"Error creating mock prediction for {symbol}: {e}")
            return None

class SentimentAgent:
    def __init__(self):
        pass

    def analyze_sentiment(self, symbol):
        sentiments = {'EURUSD': 'POSITIVE', 'GBPUSD': 'NEGATIVE', 'USDJPY': 'NEUTRAL', 'USDINR': 'POSITIVE'}
        sentiment = sentiments.get(symbol, 'NEUTRAL')
        AgentLog.objects.create(agent_name='SentimentAgent', action=f'Analyzed sentiment for {symbol}', result=sentiment)
        return sentiment

class RiskManagementAgent:
    """Enhanced Risk Management Agent with comprehensive risk analysis"""
    
    def __init__(self):
        pass

    def calculate_var(self, returns, confidence=0.95):
        """Calculate Value at Risk (VaR) using historical method"""
        if len(returns) < 2:
            return None
        sorted_returns = np.sort(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = abs(sorted_returns[index]) if index < len(sorted_returns) else 0
        return var

    def calculate_cvar(self, returns, confidence=0.95):
        """Calculate Conditional Value at Risk (CVaR / Expected Shortfall)"""
        if len(returns) < 2:
            return None
        var = self.calculate_var(returns, confidence)
        if var is None:
            return None
        tail_returns = returns[returns <= -var]
        if len(tail_returns) == 0:
            return var
        return abs(tail_returns.mean())

    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """Calculate Sharpe Ratio"""
        if len(returns) < 2:
            return None
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        if std_return == 0:
            return None
        annualized_return = mean_return * 252
        annualized_std = std_return * np.sqrt(252)
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe

    def calculate_max_drawdown(self, prices):
        """Calculate Maximum Drawdown"""
        if len(prices) < 2:
            return None
        prices_array = np.array(prices)
        running_max = np.maximum.accumulate(prices_array)
        drawdown = (prices_array - running_max) / running_max
        max_dd = abs(np.min(drawdown))
        return max_dd

    def calculate_atr(self, high_prices, low_prices, close_prices, period=14):
        """Calculate Average True Range (ATR)"""
        if len(high_prices) < 2 or len(low_prices) < 2 or len(close_prices) < 2:
            return None
        high_arr = np.array(high_prices)
        low_arr = np.array(low_prices)
        close_arr = np.array(close_prices)
        tr1 = high_arr - low_arr
        tr2 = abs(high_arr[1:] - close_arr[:-1])
        tr3 = abs(low_arr[1:] - close_arr[:-1])
        tr = np.zeros(len(high_arr))
        tr[0] = tr1[0]
        for i in range(1, len(tr)):
            tr[i] = max(tr1[i], tr2[i-1], tr3[i-1])
        if len(tr) < period:
            return np.mean(tr)
        return np.mean(tr[-period:])

    def calculate_position_size(self, account_balance, risk_tolerance, stop_loss_distance, pip_value=10):
        """Calculate position size based on account balance and risk tolerance"""
        risk_percentages = {'LOW': 0.01, 'MEDIUM': 0.02, 'HIGH': 0.05}
        risk_pct = risk_percentages.get(risk_tolerance, 0.02)
        risk_amount = account_balance * risk_pct
        if stop_loss_distance > 0:
            position_size = risk_amount / (stop_loss_distance * pip_value)
        else:
            position_size = 0
        position_size = min(position_size, 100)
        position_size = max(position_size, 0.01)
        return position_size

    def calculate_risk_reward_ratio(self, entry_price, stop_loss, take_profit):
        """Calculate Risk/Reward Ratio"""
        if stop_loss is None or take_profit is None or entry_price is None:
            return None
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        if risk == 0:
            return None
        return reward / risk

    def calculate_risk_score(self, var_95, volatility, max_drawdown, rsi=None, macd=None):
        """Calculate comprehensive risk score (0-100)"""
        if var_95 is None:
            var_95 = 0.02
        if volatility is None:
            volatility = 0.2
        if max_drawdown is None:
            max_drawdown = 0.1
        
        var_score = min(var_95 * 100 * 5, 100)
        volatility_score = min(volatility * 100 * 2.5, 100)
        drawdown_score = min(max_drawdown * 100 * 5, 100)
        
        momentum_score = 50
        if rsi is not None:
            if rsi > 70 or rsi < 30:
                momentum_score += 20
        if macd is not None:
            if abs(macd) > 0.001:
                momentum_score += 10
        momentum_score = min(momentum_score, 100)
        
        risk_score = (var_score * 0.30 + volatility_score * 0.25 + drawdown_score * 0.25 + momentum_score * 0.20)
        risk_score = max(0, min(100, risk_score))
        return risk_score

    def determine_risk_level(self, risk_score):
        """Determine risk level category"""
        if risk_score < 25:
            return 'LOW'
        elif risk_score < 50:
            return 'MEDIUM'
        elif risk_score < 75:
            return 'HIGH'
        else:
            return 'EXTREME'

    def calculate_risk(self, symbol, account_balance=10000, risk_tolerance='MEDIUM'):
        """Calculate comprehensive risk metrics"""
        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol, days=90)
        if not historical_data:
            return None

        if hasattr(historical_data, 'values'):
            df = pd.DataFrame(list(historical_data.values('close_price', 'high_price', 'low_price')))
        else:
            df = pd.DataFrame([{
                'close_price': item.close_price,
                'high_price': getattr(item, 'high_price', item.close_price),
                'low_price': getattr(item, 'low_price', item.close_price)
            } for item in historical_data])

        close_prices = df['close_price'].astype(float).values
        high_prices = df['high_price'].astype(float).values
        low_prices = df['low_price'].astype(float).values
        
        if len(close_prices) < 2:
            return None

        current_price = close_prices[-1]
        returns = np.diff(close_prices) / close_prices[:-1]
        
        var_95 = self.calculate_var(returns, 0.95)
        var_99 = self.calculate_var(returns, 0.99)
        cvar = self.calculate_cvar(returns, 0.95)
        sharpe_ratio = self.calculate_sharpe_ratio(returns)
        max_drawdown = self.calculate_max_drawdown(close_prices)
        
        if len(returns) > 0:
            volatility = np.std(returns) * np.sqrt(252)
            if np.isnan(volatility):
                volatility = 0.2
        else:
            volatility = 0.2
        
        atr = self.calculate_atr(high_prices, low_prices, close_prices)
        
        if atr is not None:
            atr_stop_loss = current_price - (2 * atr)
            atr_take_profit = current_price + (3 * atr)
        else:
            atr_stop_loss = current_price * 0.98
            atr_take_profit = current_price * 1.04
        
        if atr is not None and current_price > 0:
            stop_loss_distance = (atr * 2) / (current_price * 0.0001)
        else:
            stop_loss_distance = 20
        
        position_size = self.calculate_position_size(account_balance, risk_tolerance, stop_loss_distance)
        
        risk_percentages = {'LOW': 1.0, 'MEDIUM': 2.0, 'HIGH': 5.0}
        risk_per_trade = risk_percentages.get(risk_tolerance, 2.0)
        
        risk_reward_ratio = self.calculate_risk_reward_ratio(current_price, atr_stop_loss, atr_take_profit)
        
        tech_agent = TechnicalAnalysisAgent()
        tech_analysis = tech_agent.analyze(symbol)
        rsi = tech_analysis.get('rsi') if tech_analysis else None
        macd = tech_analysis.get('macd') if tech_analysis else None
        
        risk_score = self.calculate_risk_score(var_95, volatility, max_drawdown, rsi, macd)
        risk_level = self.determine_risk_level(risk_score)
        
        risk_data = {
            'var_95': float(var_95) if var_95 is not None else None,
            'var_99': float(var_99) if var_99 is not None else None,
            'cvar': float(cvar) if cvar is not None else None,
            'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio is not None else None,
            'max_drawdown': float(max_drawdown) if max_drawdown is not None else None,
            'volatility': float(volatility),
            'atr': float(atr) if atr is not None else None,
            'atr_stop_loss': float(atr_stop_loss),
            'atr_take_profit': float(atr_take_profit),
            'position_size': float(position_size),
            'risk_per_trade': risk_per_trade,
            'risk_reward_ratio': float(risk_reward_ratio) if risk_reward_ratio is not None else None,
            'risk_score': float(risk_score),
            'risk_level': risk_level,
            'current_price': float(current_price)
        }

        AgentLog.objects.create(
            agent_name='RiskManagementAgent', 
            action=f'Calculated comprehensive risk for {symbol}', 
            result=f"Risk Score: {risk_score:.1f}, VaR(95%): {var_95:.4f if var_95 else 'N/A'}, Risk Level: {risk_level}"
        )
        return risk_data

class DecisionAgent:
    def __init__(self):
        self.data_agent = DataAgent()
        self.tech_agent = TechnicalAnalysisAgent()
        self.pred_agent = PredictionAgent()
        self.sentiment_agent = SentimentAgent()
        self.risk_agent = RiskManagementAgent()

    def make_decision(self, symbol):
        """Combine all agent outputs to make final decision"""
        latest_data = self.data_agent.fetch_real_time_data(symbol)
        if not latest_data:
            return None

        tech_analysis = self.tech_agent.analyze(symbol)
        prediction = self.pred_agent.predict(symbol)
        sentiment = self.sentiment_agent.analyze_sentiment(symbol)
        risk = self.risk_agent.calculate_risk(symbol)

        if not all([tech_analysis, prediction, risk]):
            return None

        score = 0

        if tech_analysis.get('rsi'):
            if tech_analysis['rsi'] < 30:
                score += 20
            elif tech_analysis['rsi'] > 70:
                score -= 20

        if tech_analysis.get('macd') and tech_analysis['macd'] > 0:
            score += 15

        if prediction.trend == 'UP':
            score += prediction.confidence * 0.3
        else:
            score -= prediction.confidence * 0.3

        if sentiment == 'POSITIVE':
            score += 10
        elif sentiment == 'NEGATIVE':
            score -= 10

        # Enhanced risk adjustment using comprehensive risk metrics
        risk_penalty = risk.get('risk_score', 50) * 0.1
        # Additional penalty for high VaR
        if risk.get('var_95') and risk['var_95'] > 0.02:
            risk_penalty += 5
        # Penalty for extreme risk level
        if risk.get('risk_level') == 'EXTREME':
            risk_penalty += 10
        elif risk.get('risk_level') == 'HIGH':
            risk_penalty += 5
        
        score -= risk_penalty

        if score > 20:
            decision = 'BUY'
            profit_probability = min(score / 100 * 100, 95)
        elif score < -20:
            decision = 'SELL'
            profit_probability = min(-score / 100 * 100, 95)
        else:
            decision = 'HOLD'
            profit_probability = 50

        confidence = abs(score) / 100 * 100

        result = {
            'decision': decision,
            'profit_probability': profit_probability,
            'confidence': confidence,
            'technical_indicators': tech_analysis,
            'prediction': {'trend': prediction.trend, 'confidence': prediction.confidence},
            'sentiment': sentiment,
            'risk': risk
        }

        AgentLog.objects.create(agent_name='DecisionAgent', action=f'Made decision for {symbol}', result=str(result))
        return result

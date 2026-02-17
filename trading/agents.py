import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import os
from .models import ForexData, Prediction, AgentLog
from django.conf import settings
import logging

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
        # Finnhub has limited free historical data, so we'll use stored data
        data = list(ForexData.objects.filter(symbol=symbol).order_by('-timestamp')[:days*24])

        # If no data, generate mock historical data
        if not data:
            data = self._generate_mock_historical_data(symbol, days)

        return data

    def _generate_mock_historical_data(self, symbol, days):
        """Generate mock historical data for testing"""
        from datetime import timedelta

        # Base prices for different symbols
        base_prices = {
            'EURUSD': 1.08, 'GBPUSD': 1.27, 'USDJPY': 150.0, 'USDINR': 83.0
        }
        base_price = base_prices.get(symbol, 1.0)

        mock_data = []
        now = datetime.now()

        for i in range(days * 24, 0, -1):  # Generate data from oldest to newest
            timestamp = now - timedelta(hours=i)

            # Add some random variation
            import random
            variation = random.uniform(-0.01, 0.01)  # ±1% variation
            close_price = base_price * (1 + variation)

            # Create mock ForexData object (but don't save to DB)
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
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD"""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_moving_average(self, prices, period=20):
        """Calculate Simple Moving Average"""
        return prices.rolling(window=period).mean()

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        sma = self.calculate_moving_average(prices, period)
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower

    def analyze(self, symbol):
        """Perform technical analysis"""
        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol)
        if not historical_data:
            return None

        # Handle both QuerySet and list of mock objects
        if hasattr(historical_data, 'values'):
            # It's a QuerySet
            df = pd.DataFrame(list(historical_data.values('timestamp', 'close_price')))
        else:
            # It's a list of mock objects
            data_list = []
            for item in historical_data:
                data_list.append({
                    'timestamp': item.timestamp,
                    'close_price': item.close_price
                })
            df = pd.DataFrame(data_list)

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
            self.models = {}  # Cache for loaded models
            self.scalers = {}  # Cache for loaded scalers
        else:
            logger.warning("TensorFlow not available. Using mock predictions.")

    def get_model_path(self, symbol):
        """Get model path for a symbol"""
        return os.path.join(settings.BASE_DIR, 'trading', f'lstm_model_{symbol}.h5')

    def get_scaler_path(self, symbol):
        """Get scaler path for a symbol"""
        return os.path.join(settings.BASE_DIR, 'trading', f'scaler_{symbol}.pkl')

    def load_model_and_scaler(self, symbol):
        """Load model and scaler for a symbol"""
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
        """Train LSTM model on historical data"""
        if not self.tf_available:
            return False

        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol, days=365)
        if not historical_data:
            return False

        df = pd.DataFrame(list(historical_data.values('timestamp', 'close_price')))
        df['close'] = df['close_price'].astype(float)
        df = df.set_index('timestamp').sort_index()

        if len(df) < 100:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} points")
            return False

        # Prepare data for LSTM
        scaler = MinMaxScaler(feature_range=(0, 1))
        data = df['close'].values.reshape(-1, 1)
        scaled_data = scaler.fit_transform(data)

        # Create training data
        look_back = 60
        X_train, y_train = [], []
        for i in range(look_back, len(scaled_data)):
            X_train.append(scaled_data[i-look_back:i, 0])
            y_train.append(scaled_data[i, 0])

        X_train, y_train = np.array(X_train), np.array(y_train)
        X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))

        # Build LSTM model
        model = self.Sequential()
        model.add(self.LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], 1)))
        model.add(self.Dropout(0.2))
        model.add(self.LSTM(units=50, return_sequences=False))
        model.add(self.Dropout(0.2))
        model.add(self.Dense(units=1))

        model.compile(optimizer='adam', loss='mean_squared_error')
        model.fit(X_train, y_train, epochs=25, batch_size=32, verbose=0)

        # Save model and scaler
        model_path = self.get_model_path(symbol)
        scaler_path = self.get_scaler_path(symbol)

        model.save(model_path)
        import joblib
        joblib.dump(scaler, scaler_path)

        # Cache them
        self.models[symbol] = model
        self.scalers[symbol] = scaler

        return True

    def predict(self, symbol):
        """Make prediction using trained model or mock data"""
        model, scaler = self.load_model_and_scaler(symbol)

        if model is None or scaler is None:
            # Try to train a new model
            if self.tf_available and not self.train_model(symbol):
                # Fall back to mock prediction
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

            df = pd.DataFrame(list(historical_data.values('timestamp', 'close_price')))
            df['close'] = df['close_price']
            df = df.set_index('timestamp').sort_index()

            if len(df) < 60:
                return self._mock_predict(symbol)

            data = df['close'].values.reshape(-1, 1)
            scaled_data = scaler.transform(data)

            # Prepare input for prediction
            look_back = 60
            X_test = scaled_data[-look_back:].reshape(1, look_back, 1)
            predicted_scaled = model.predict(X_test, verbose=0)
            predicted_price = scaler.inverse_transform(predicted_scaled)[0][0]

            current_price = df['close'].iloc[-1]
            trend = 'UP' if predicted_price > current_price else 'DOWN'
            confidence = min(abs(predicted_price - current_price) / current_price * 100, 100)

            prediction = Prediction.objects.create(
                symbol=symbol,
                predicted_price=predicted_price,
                trend=trend,
                confidence=confidence
            )

            AgentLog.objects.create(agent_name='PredictionAgent', action=f'Predicted for {symbol}', result=f'{trend} with {confidence:.1f}% confidence')
            return prediction

        except Exception as e:
            logger.error(f"Error predicting for {symbol}: {e}")
            return self._mock_predict(symbol)

    def _mock_predict(self, symbol):
        """Generate mock prediction when ML is not available"""
        try:
            data_agent = DataAgent()
            historical_data = data_agent.get_historical_data(symbol, days=1)
            if historical_data:
                # Handle both QuerySet and list
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
                # Mock current price based on symbol
                base_prices = {
                    'EURUSD': 1.08, 'GBPUSD': 1.27, 'USDJPY': 150.0, 'USDINR': 83.0
                }
                current_price = base_prices.get(symbol, 1.0)

            # Ensure current_price is float
            current_price = float(current_price)

            # Generate mock prediction with some randomness
            import random
            change_percent = random.uniform(-0.05, 0.05)  # -5% to +5%
            predicted_price = current_price * (1 + change_percent)
            trend = 'UP' if predicted_price > current_price else 'DOWN'
            confidence = random.uniform(50, 90)  # 50-90% confidence

            prediction = Prediction.objects.create(
                symbol=symbol,
                predicted_price=predicted_price,
                trend=trend,
                confidence=confidence
            )

            AgentLog.objects.create(agent_name='PredictionAgent', action=f'Mock predicted for {symbol}', result=f'{trend} with {confidence:.1f}% confidence (MOCK)')
            return prediction

        except Exception as e:
            logger.error(f"Error creating mock prediction for {symbol}: {e}")
            return None

class SentimentAgent:
    def __init__(self):
        # For simplicity, we'll use a mock sentiment analysis
        # In a real implementation, integrate with news API and NLP model
        pass

    def analyze_sentiment(self, symbol):
        """Analyze sentiment for forex pair"""
        # Mock sentiment based on symbol
        # In real implementation, fetch news headlines and analyze
        sentiments = {
            'EURUSD': 'POSITIVE',
            'GBPUSD': 'NEGATIVE',
            'USDJPY': 'NEUTRAL',
            'USDINR': 'POSITIVE'
        }
        sentiment = sentiments.get(symbol, 'NEUTRAL')
        AgentLog.objects.create(agent_name='SentimentAgent', action=f'Analyzed sentiment for {symbol}', result=sentiment)
        return sentiment

class RiskManagementAgent:
    def __init__(self):
        pass

    def calculate_risk(self, symbol):
        """Calculate risk metrics"""
        data_agent = DataAgent()
        historical_data = data_agent.get_historical_data(symbol, days=30)
        if not historical_data:
            return None

        # Handle both QuerySet and list of mock objects
        if hasattr(historical_data, 'values'):
            # It's a QuerySet
            df = pd.DataFrame(list(historical_data.values('close_price')))
        else:
            # It's a list of mock objects
            data_list = []
            for item in historical_data:
                data_list.append({'close_price': item.close_price})
            df = pd.DataFrame(data_list)

        prices = df['close_price'].astype(float)

        if len(prices) < 2:
            volatility = 0.2  # Default volatility if insufficient data
        else:
            volatility = prices.pct_change().std() * np.sqrt(252)  # Annualized volatility
            if np.isnan(volatility) or volatility == 0:
                volatility = 0.2  # Default if calculation fails

        current_price = prices.iloc[-1]

        # Simple stop-loss and take-profit calculation
        stop_loss = current_price * 0.98  # 2% stop loss
        take_profit = current_price * 1.04  # 4% take profit

        risk_score = min(volatility * 100, 100)  # Risk score 0-100

        risk_data = {
            'volatility': volatility,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_score': risk_score
        }

        AgentLog.objects.create(agent_name='RiskManagementAgent', action=f'Calculated risk for {symbol}', result=str(risk_data))
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
        # Fetch latest data
        latest_data = self.data_agent.fetch_real_time_data(symbol)
        if not latest_data:
            return None

        # Get analyses
        tech_analysis = self.tech_agent.analyze(symbol)
        prediction = self.pred_agent.predict(symbol)
        sentiment = self.sentiment_agent.analyze_sentiment(symbol)
        risk = self.risk_agent.calculate_risk(symbol)

        if not all([tech_analysis, prediction, risk]):
            return None

        # Decision logic
        score = 0

        # Technical analysis score
        if tech_analysis['rsi']:
            if tech_analysis['rsi'] < 30:
                score += 20  # Oversold, potential buy
            elif tech_analysis['rsi'] > 70:
                score -= 20  # Overbought, potential sell

        if tech_analysis['macd'] and tech_analysis['macd'] > 0:
            score += 15  # MACD positive

        # Prediction score
        if prediction.trend == 'UP':
            score += prediction.confidence * 0.3
        else:
            score -= prediction.confidence * 0.3

        # Sentiment score
        if sentiment == 'POSITIVE':
            score += 10
        elif sentiment == 'NEGATIVE':
            score -= 10

        # Risk adjustment
        risk_penalty = risk['risk_score'] * 0.1
        score -= risk_penalty

        # Final decision
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
            'prediction': {
                'trend': prediction.trend,
                'confidence': prediction.confidence
            },
            'sentiment': sentiment,
            'risk': risk
        }

        AgentLog.objects.create(agent_name='DecisionAgent', action=f'Made decision for {symbol}', result=str(result))
        return result

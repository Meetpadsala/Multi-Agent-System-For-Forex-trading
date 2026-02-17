#!/usr/bin/env python
"""
LSTM Model Training Script for Forex Prediction
"""

import os
import sys
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forex_trading.settings')
django.setup()

from trading.models import ForexData

def fetch_historical_data(symbol, days=365):
    """Fetch historical data from database or generate mock data"""
    try:
        # Try to get data from database
        data = ForexData.objects.filter(symbol=symbol).order_by('-timestamp')[:days*24]
        if data:
            df = pd.DataFrame(list(data.values('timestamp', 'close_price')))
            df['close'] = df['close_price']
            df = df.set_index('timestamp').sort_index()
            return df
    except:
        pass

    # Generate mock data if no real data available
    print(f"No historical data found for {symbol}. Generating mock data...")
    dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
    np.random.seed(42)  # For reproducible results

    # Generate realistic forex price movements
    base_price = 1.0 if 'EUR' in symbol else 1.3 if 'GBP' in symbol else 110.0 if 'JPY' in symbol else 1.0
    prices = [base_price]
    for i in range(1, len(dates)):
        # Random walk with mean reversion
        change = np.random.normal(0, 0.005)  # 0.5% volatility
        new_price = prices[-1] * (1 + change)
        # Mean reversion to base price
        new_price += (base_price - new_price) * 0.01
        prices.append(max(new_price, 0.0001))  # Ensure positive price

    df = pd.DataFrame({'close': prices}, index=dates)
    return df

def prepare_data(data, look_back=60):
    """Prepare data for LSTM training"""
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data.values.reshape(-1, 1))

    X, y = [], []
    for i in range(look_back, len(scaled_data)):
        X.append(scaled_data[i-look_back:i, 0])
        y.append(scaled_data[i, 0])

    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    return X, y, scaler

def build_model(input_shape):
    """Build LSTM model"""
    model = Sequential()
    model.add(LSTM(units=100, return_sequences=True, input_shape=input_shape))
    model.add(Dropout(0.2))
    model.add(LSTM(units=100, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(units=50, return_sequences=False))
    model.add(Dropout(0.2))
    model.add(Dense(units=25))
    model.add(Dense(units=1))

    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def train_model(symbol, epochs=50, batch_size=32):
    """Train LSTM model for a currency pair"""
    print(f"Training LSTM model for {symbol}...")

    # Fetch historical data
    data = fetch_historical_data(symbol)
    if len(data) < 100:
        print(f"Insufficient data for {symbol}. Need at least 100 data points.")
        return False

    # Prepare data
    look_back = 60
    X, y, scaler = prepare_data(data, look_back)

    # Split data
    train_size = int(len(X) * 0.8)
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]

    # Build model
    model = build_model((X_train.shape[1], 1))

    # Callbacks
    early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    checkpoint = ModelCheckpoint(
        f'trading/lstm_model_{symbol}.h5',
        monitor='val_loss',
        save_best_only=True,
        verbose=1
    )

    # Train model
    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_test, y_test),
        callbacks=[early_stopping, checkpoint],
        verbose=1
    )

    # Save scaler
    import joblib
    scaler_path = f'trading/scaler_{symbol}.pkl'
    joblib.dump(scaler, scaler_path)

    print(f"Model trained and saved for {symbol}")
    print(f"Training completed. Final loss: {history.history['loss'][-1]:.6f}")
    print(f"Validation loss: {history.history['val_loss'][-1]:.6f}")

    return True

def main():
    """Main training function"""
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDINR']

    for symbol in symbols:
        try:
            success = train_model(symbol)
            if success:
                print(f"Successfully trained model for {symbol}")
            else:
                print(f"Failed to train model for {symbol}")
        except Exception as e:
            print(f"Error training model for {symbol}: {e}")

if __name__ == '__main__':
    main()

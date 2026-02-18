import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone
import requests
import os
from alpha_vantage.foreignexchange import ForeignExchange
from alpha_vantage.timeseries import TimeSeries
import time
import random

class RealForexDataFetcher:
    """Real forex data fetcher using multiple APIs"""

    def __init__(self):
        # Alpha Vantage API key (you'll need to get one from alpha_vantage)
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
        self.alpha_vantage_fx = ForeignExchange(key=self.alpha_vantage_key)
        self.alpha_vantage_ts = TimeSeries(key=self.alpha_vantage_key)

        # Rate limiting
        self.last_request_time = 0
        self.request_delay = 15  # Alpha Vantage free tier limit

    def _rate_limit(self):
        """Implement rate limiting for API calls"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get_real_time_price(self, symbol):
        """Get real-time forex price using yfinance"""
        try:
            # Convert forex symbol to yfinance format (e.g., EURUSD=X)
            yf_symbol = f"{symbol[:3]}{symbol[3:]}=X"

            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d", interval="1m")

            if not data.empty:
                latest = data.iloc[-1]
                return {
                    'symbol': symbol,
                    'price': float(latest['Close']),
                    'timestamp': timezone.now(),
                    'high': float(latest['High']),
                    'low': float(latest['Low']),
                    'open': float(latest['Open']),
                    'volume': int(latest['Volume']) if 'Volume' in latest else 0
                }
        except Exception as e:
            print(f"Error fetching real-time data for {symbol}: {e}")

        return None

    def get_historical_data(self, symbol, period="1mo", interval="1h"):
        """Get historical forex data using yfinance"""
        try:
            # Convert forex symbol to yfinance format
            yf_symbol = f"{symbol[:3]}{symbol[3:]}=X"

            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period=period, interval=interval)

            if not data.empty:
                historical_data = []
                for index, row in data.iterrows():
                    dt = index.to_pydatetime()
                    # Check if datetime is already timezone-aware
                    if timezone.is_aware(dt):
                        timestamp = dt
                    else:
                        timestamp = timezone.make_aware(dt)

                    historical_data.append({
                        'timestamp': timestamp,
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'volume': int(row['Volume']) if 'Volume' in row else 0
                    })
                return historical_data
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")

        return None

    def get_intraday_data(self, symbol, interval="1min", outputsize="compact"):
        """Get intraday data using Alpha Vantage"""
        try:
            self._rate_limit()

            # Alpha Vantage forex symbols
            from_symbol = symbol[:3]
            to_symbol = symbol[3:]

            # Get intraday data
            data, meta_data = self.alpha_vantage_fx.get_currency_exchange_intraday(
                from_symbol=from_symbol,
                to_symbol=to_symbol,
                interval=interval,
                outputsize=outputsize
            )

            if data:
                historical_data = []
                for timestamp, values in data.items():
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    historical_data.append({
                        'timestamp': timezone.make_aware(dt),
                        'open': float(values['1. open']),
                        'high': float(values['2. high']),
                        'low': float(values['3. low']),
                        'close': float(values['4. close']),
                        'volume': 0  # Alpha Vantage forex doesn't provide volume
                    })
                return historical_data

        except Exception as e:
            print(f"Error fetching Alpha Vantage data for {symbol}: {e}")

        return None

    def get_forex_data(self, symbol, timeframe='1h', limit=100):
        """Main method to get forex data with fallback options"""
        # Try yfinance first for better data quality
        # Handle both '1m'/'1min', '5m'/'5min', '15m'/'15min' formats
        if timeframe in ['1m', '5m', '15m', '1h', '1d', '1min', '5min', '15min', '30min', '60min']:
            # Map timeframe to yfinance interval
            # yfinance uses: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 1wk, 1mo, 3mo
            interval_map = {
                '1m': '1m',
                '2m': '2m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '2h': '2h',
                '4h': '4h',
                '1d': '1d',
                '1wk': '1wk',
                '1mo': '1mo',
                # Also handle 'min' format from frontend
                '1min': '1m',
                '5min': '5m',
                '15min': '15m',
                '30min': '30m',
                '60min': '1h',
                '60m': '1h'
            }

            # Map limit to period - more comprehensive mapping
            # This ensures we get enough data points based on the limit requested
            if timeframe in ['1m', '1min']:
                # For 1-minute data, we need at least '5d' for 100 points (assuming market hours)
                period_map = {
                    10: "1d",
                    20: "2d",
                    50: "5d",
                    100: "5d",  # 5 days of minute data should give ~3900 points (6.5 hours * 60 * 5)
                    200: "10d",
                    500: "1mo"
                }
            elif timeframe in ['5m', '5min']:
                period_map = {
                    10: "1d",
                    20: "2d",
                    50: "5d",
                    100: "5d",
                    200: "10d",
                    500: "1mo"
                }
            elif timeframe in ['15m', '15min']:
                period_map = {
                    10: "2d",
                    20: "5d",
                    50: "5d",
                    100: "10d",
                    200: "1mo",
                    500: "3mo"
                }
            elif timeframe in ['30m', '30min', '60m', '60min']:
                period_map = {
                    10: "5d",
                    20: "5d",
                    50: "10d",
                    100: "1mo",
                    200: "3mo",
                    500: "6mo"
                }
            elif timeframe == '1h':
                period_map = {
                    10: "5d",
                    20: "10d",
                    50: "1mo",
                    100: "1mo",
                    200: "3mo",
                    500: "6mo"
                }
            else:  # 1d
                period_map = {
                    10: "1mo",
                    20: "3mo",
                    50: "3mo",
                    100: "6mo",
                    200: "1y",
                    500: "2y"
                }
            
            period = period_map.get(limit, "1mo")
            
            # Get the correct interval for yfinance
            yf_interval = interval_map.get(timeframe, '1h')
            
            data = self.get_historical_data(symbol, period=period, interval=yf_interval)
            if data and len(data) > 0:
                # Return the requested number of data points, most recent first
                return data[-limit:] if len(data) > limit else data

        # Fallback to Alpha Vantage for intraday data
        # Also handle the case where yfinance fails
        if timeframe in ['1m', '5m', '15m', '30m', '60m', '1min', '5min', '15min', '30min', '60min']:
            # Map to Alpha Vantage format
            av_interval_map = {
                '1m': '1min',
                '1min': '1min',
                '5m': '5min',
                '5min': '5min',
                '15m': '15min',
                '15min': '15min',
                '30m': '30min',
                '30min': '30min',
                '60m': '60min',
                '60min': '60min'
            }
            
            av_interval = av_interval_map.get(timeframe, '5min')
            
            # Use compact output for smaller datasets, full for larger
            outputsize = "compact" if limit <= 100 else "full"
            
            data = self.get_intraday_data(symbol, interval=av_interval, outputsize=outputsize)
            if data and len(data) > 0:
                return data[-limit:] if len(data) > limit else data

        # If all APIs fail, return None to trigger mock data fallback
        return None

    def get_current_price(self, symbol):
        """Get current forex price"""
        return self.get_real_time_price(symbol)

# Global instance
real_data_fetcher = RealForexDataFetcher()

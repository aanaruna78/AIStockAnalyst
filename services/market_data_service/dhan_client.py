from dhanhq import dhanhq
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import yfinance as yf
from shared.config import settings

logger = logging.getLogger("DhanClient")

class DhanClient:
    def __init__(self):
        self.client_id = settings.DHAN_CLIENT_ID
        self.access_token = settings.DHAN_ACCESS_TOKEN
        self.dhan = None
        # if self.client_id and self.access_token:
        #     self.dhan = dhanhq(self.client_id, self.access_token)
        # else:
        logger.warning("Dhan credentials not configured. Using mock mode.")
    
    def get_live_price(self, security_id: str) -> Optional[Dict[str, Any]]:
        """Fetch live price for a given security"""
        # Try yfinance first for real NSE data
        price_data = self._get_yfinance_price(security_id)
        if price_data:
            return price_data

        if not self.dhan:
            return self._mock_live_price(security_id)
        
        try:
            quote = self.dhan.get_quote(security_id)
            return {
                "symbol": security_id,
                "ltp": quote.get("LTP"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": quote.get("close"),
                "volume": quote.get("volume"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching quote for {security_id}: {e}")
            return None
    
    def get_historical_data(self, security_id: str, interval: str = "1D", from_date: str = None, to_date: str = None) -> Optional[List[Dict]]:
        """Fetch historical OHLC data"""
        # Try yfinance first
        hist_data = self._get_yfinance_historical(security_id, interval)
        if hist_data:
            return hist_data

        if not self.dhan:
            return self._mock_historical_data(security_id, interval)
        
        try:
            # Dhan API expects specific date format
            if not from_date:
                from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not to_date:
                to_date = datetime.now().strftime("%Y-%m-%d")
            
            data = self.dhan.historical_data(security_id, interval, from_date, to_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching historical data for {security_id}: {e}")
            return None
    
    def _get_yfinance_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch real price from NSE using yfinance"""
        try:
            # Append .NS for NSE stocks if not present
            if not symbol.endswith(".NS"):
                yf_symbol = f"{symbol}.NS"
            else:
                yf_symbol = symbol

            ticker = yf.Ticker(yf_symbol)
            # Use history(period='1d') instead of fast_info for more reliability
            df = ticker.history(period="1d")
            
            if df.empty:
                logger.warning(f"yfinance returned empty data for {yf_symbol} (Live)")
                return None
                
            last_row = df.iloc[-1]
            
            return {
                "symbol": symbol,
                "ltp": round(last_row["Close"], 2),
                "open": round(last_row["Open"], 2),
                "high": round(last_row["High"], 2),
                "low": round(last_row["Low"], 2),
                "close": round(last_row["Close"], 2), # live close
                "volume": int(last_row["Volume"]),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"yfinance failed for {symbol}: {e}")
            return None

    def _get_yfinance_historical(self, symbol: str, interval: str) -> Optional[List[Dict]]:
        """Fetch historical data from NSE using yfinance"""
        try:
            if not symbol.endswith(".NS"):
                yf_symbol = f"{symbol}.NS"
            else:
                yf_symbol = symbol

            period = "1mo" # Default to 1 month for historical data
            
            # Map interval to yfinance format
            yf_interval = "1d"
            if interval == "1m": yf_interval = "1m"
            elif interval == "5m": yf_interval = "5m"
            elif interval == "15m": yf_interval = "15m"
            elif interval == "30m": yf_interval = "30m"
            elif interval == "60m" or interval == "1h": yf_interval = "1h"
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=yf_interval)
            
            if df.empty:
                logger.warning(f"yfinance returned empty historical data for {yf_symbol} (Interval: {yf_interval})")
                return None
                
            data = []
            for index, row in df.iterrows():
                data.append({
                    "timestamp": index.isoformat(),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"])
                })
            return data
        except Exception as e:
            logger.warning(f"yfinance historical failed for {symbol}: {e}")
            return None
    
    def _get_mock_base_price(self, symbol: str) -> float:
        # Realistic prices based on user input and recent market data
        prices = {
            "RELIANCE": 1400.0, # User provided
            "HDFCBANK": 920.0,  # User provided
            "TCS": 3150.4,      # Exactly as per user correction
            "INFY": 1600.0,     # Estimate
            "ICICIBANK": 1050.0,# Estimate
            "SBIN": 750.0,
            "ITC": 450.0,
            "TMCV": 980.0,      # Tata Motors Commercial Estimate
            "TMPV": 850.0,      # Tata Motors Passenger Estimate
            "NIFTY": 22000.0,
            "BANKNIFTY": 46000.0
        }
        if symbol in prices:
            return prices[symbol]
        
        # Deterministic fallback based on symbol hash
        import hashlib
        hash_val = int(hashlib.md5(symbol.encode()).hexdigest(), 16)
        return 100.0 + (hash_val % 1000)

    def _mock_live_price(self, security_id: str) -> Dict[str, Any]:
        """Mock data for development without API credentials"""
        base_price = self._get_mock_base_price(security_id)
        # Add random variation
        import random
        variation = base_price * 0.01 * (random.random() - 0.5)
        ltp = base_price + variation
        
        return {
            "symbol": security_id,
            "ltp": round(ltp, 2),
            "open": round(base_price, 2),
            "high": round(base_price * 1.01, 2),
            "low": round(base_price * 0.99, 2),
            "close": round(base_price, 2),
            "volume": 1000000 + int(random.random() * 500000),
            "timestamp": datetime.now().isoformat()
        }
    
    def _mock_historical_data(self, security_id: str, interval: str) -> List[Dict]:
        """Mock historical data"""
        base_price = self._get_mock_base_price(security_id)
        data = []
        for i in range(30):
            # Days AGO: 29, 28, ..., 0
            days_ago = 29 - i
            date = datetime.now() - timedelta(days=days_ago)
            
            # Trend goes from (base_price - total_trend) to base_price
            # Total trend is 15% over 30 days
            total_trend_factor = 0.15
            if hash(security_id) % 2 == 0:
                # Downward trend in history means price was higher in the past
                start_price = base_price * (1 + total_trend_factor)
                daily_trend = (base_price - start_price) / 29
            else:
                # Upward trend in history means price was lower in the past
                start_price = base_price * (1 - total_trend_factor)
                daily_trend = (base_price - start_price) / 29
            
            daily_base = start_price + (daily_trend * i)
            
            # Simple volatility (2%)
            vol = daily_base * 0.02
            
            data.append({
                "timestamp": date.isoformat(),
                "open": round(daily_base, 2),
                "high": round(daily_base + vol, 2),
                "low": round(daily_base - vol, 2),
                "close": round(daily_base + (daily_trend * 0.5), 2), # Some variation
                "volume": 1000000 + (i * 10000)
            })
        return data

# Singleton
dhan_client = DhanClient()

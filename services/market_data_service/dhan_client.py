from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pytz
import logging
import re
import requests
import yfinance as yf
from shared.config import settings

logger = logging.getLogger("DhanClient")

# Index symbols need special handling for yfinance and Google Finance
INDEX_YFINANCE_MAP = {
    "NIFTY_50": "^NSEI",
    "NIFTY_BANK": "^NSEBANK",
    "NIFTY_FIN_SERVICE": "^CNXFIN",
    "NIFTY_IT": "^CNXIT",
    "NIFTY_NEXT_50": "^NSMIDCP",
}
INDEX_SYMBOLS = set(INDEX_YFINANCE_MAP.keys())


class DhanClient:
    def __init__(self):
        self.client_id = settings.DHAN_CLIENT_ID
        self.access_token = settings.DHAN_ACCESS_TOKEN
        self.dhan = None
        self._yfinance_disabled = False  # Circuit breaker: skip yfinance if it keeps failing
        self._yfinance_fail_count = 0
        self._yfinance_max_fails = 2  # Trip after 2 consecutive failures
        # if self.client_id and self.access_token:
        #     self.dhan = dhanhq(self.client_id, self.access_token)
        # else:
        logger.warning("Dhan credentials not configured. Using mock mode.")

    def get_live_price(self, security_id: str) -> Optional[Dict[str, Any]]:
        """Fetch live price for a symbol. Tries yfinance → Google Finance → Dhan → mock."""
        # Try yfinance first (skip if circuit breaker tripped)
        if not self._yfinance_disabled:
            yf_data = self._get_yfinance_price(security_id)
            if yf_data:
                self._yfinance_fail_count = 0  # Reset on success
                return yf_data

        # Try Google Finance scraper (no API key needed, reliable)
        gf_data = self._get_google_finance_price(security_id)
        if gf_data:
            return gf_data

        # Try Dhan API if configured
        if self.dhan:
            try:
                ist = pytz.timezone("Asia/Kolkata")
                quote = self.dhan.get_quote(security_id)
                return {
                    "symbol": security_id,
                    "ltp": quote.get("LTP") or quote.get("ltp"),
                    "open": quote.get("open"),
                    "high": quote.get("high"),
                    "low": quote.get("low"),
                    "close": quote.get("close"),
                    "volume": quote.get("volume"),
                    "timestamp": datetime.now(ist).isoformat()
                }
            except Exception as e:
                logger.error(f"Error fetching quote for {security_id}: {e}")

        # Fallback to mock data
        return self._mock_live_price(security_id)

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
            ist = pytz.timezone("Asia/Kolkata")
            if not from_date:
                from_date = (datetime.now(ist) - timedelta(days=30)).strftime("%Y-%m-%d")
            if not to_date:
                to_date = datetime.now(ist).strftime("%Y-%m-%d")
            
            data = self.dhan.historical_data(security_id, interval, from_date, to_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching historical data for {security_id}: {e}")
            return None
    
    def _get_yfinance_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch real price from NSE using yfinance"""
        try:
            # Map index symbols to yfinance tickers; append .NS for stocks
            if symbol in INDEX_YFINANCE_MAP:
                yf_symbol = INDEX_YFINANCE_MAP[symbol]
            elif not symbol.endswith(".NS"):
                yf_symbol = f"{symbol}.NS"
            else:
                yf_symbol = symbol

            # Use a session with short timeout to prevent SSL hangs
            session = requests.Session()
            session.timeout = 5
            ticker = yf.Ticker(yf_symbol, session=session)
            ist = pytz.timezone("Asia/Kolkata")

            # Try fast_info first — gives actual real-time LTP
            try:
                fi = ticker.fast_info
                if fi and hasattr(fi, 'last_price') and fi.last_price:
                    return {
                        "symbol": symbol,
                        "ltp": round(fi.last_price, 2),
                        "open": round(fi.open, 2) if hasattr(fi, 'open') and fi.open else None,
                        "high": round(fi.day_high, 2) if hasattr(fi, 'day_high') and fi.day_high else None,
                        "low": round(fi.day_low, 2) if hasattr(fi, 'day_low') and fi.day_low else None,
                        "close": round(fi.previous_close, 2) if hasattr(fi, 'previous_close') and fi.previous_close else None,
                        "timestamp": datetime.now(ist).isoformat()
                    }
            except Exception:
                pass  # fast_info failed, try history

            # Fallback: Use history(period='1d')
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
                "close": round(last_row["Close"], 2),
                "volume": int(last_row["Volume"]),
                "timestamp": datetime.now(ist).isoformat()
            }
        except Exception as e:
            logger.warning(f"yfinance failed for {symbol}: {e}")
            self._yfinance_fail_count += 1
            if self._yfinance_fail_count >= self._yfinance_max_fails:
                self._yfinance_disabled = True
                logger.warning("yfinance circuit breaker tripped after 3 consecutive failures — skipping yfinance for future requests")
            return None

    def _get_google_finance_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape real-time LTP from Google Finance (no API key needed)"""
        try:
            # Index symbols use :INDEXNSE suffix, stocks use :NSE
            suffix = "INDEXNSE" if symbol in INDEX_SYMBOLS else "NSE"
            url = f"https://www.google.com/finance/quote/{symbol}:{suffix}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=8, verify=False)
            if resp.status_code != 200:
                return None

            html = resp.text
            ist = pytz.timezone("Asia/Kolkata")

            # Primary: extract from data attribute (most reliable)
            match = re.search(r'data-last-price="([\d\.]+)"', html)
            if match:
                ltp = float(match.group(1))
            else:
                # Fallback: find ₹ followed by numbers
                match_rupee = re.search(r'₹([\d,]+\.\d+)', html)
                if match_rupee:
                    ltp = float(match_rupee.group(1).replace(',', ''))
                else:
                    return None

            # Try to extract other prices from data attributes
            open_match = re.search(r'Open[^>]*>\s*(?:₹)?([\d,]+\.\d+)', html)
            high_match = re.search(r'High[^>]*>\s*(?:₹)?([\d,]+\.\d+)', html)
            low_match = re.search(r'Low[^>]*>\s*(?:₹)?([\d,]+\.\d+)', html)
            close_match = re.search(r'Prev\.?\s*close[^>]*>\s*(?:₹)?([\d,]+\.\d+)', html)

            logger.info(f"Google Finance LTP for {symbol}: {ltp}")
            return {
                "symbol": symbol,
                "ltp": round(ltp, 2),
                "open": round(float(open_match.group(1).replace(',', '')), 2) if open_match else None,
                "high": round(float(high_match.group(1).replace(',', '')), 2) if high_match else None,
                "low": round(float(low_match.group(1).replace(',', '')), 2) if low_match else None,
                "close": round(float(close_match.group(1).replace(',', '')), 2) if close_match else None,
                "timestamp": datetime.now(ist).isoformat()
            }
        except Exception as e:
            logger.warning(f"Google Finance scrape failed for {symbol}: {e}")
            return None

    def _get_yfinance_historical(self, symbol: str, interval: str) -> Optional[List[Dict]]:
        """Fetch historical data from NSE using yfinance"""
        try:
            # Map index symbols to yfinance tickers; append .NS for stocks
            if symbol in INDEX_YFINANCE_MAP:
                yf_symbol = INDEX_YFINANCE_MAP[symbol]
            elif not symbol.endswith(".NS"):
                yf_symbol = f"{symbol}.NS"
            else:
                yf_symbol = symbol

            period = "1mo" # Default to 1 month for historical data
            
            # Map interval to yfinance format
            yf_interval = "1d"
            if interval == "1m":
                yf_interval = "1m"
            elif interval == "5m":
                yf_interval = "5m"
            elif interval == "15m":
                yf_interval = "15m"
            elif interval == "30m":
                yf_interval = "30m"
            elif interval == "60m" or interval == "1h":
                yf_interval = "1h"
            
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
        
        ist = pytz.timezone("Asia/Kolkata")
        return {
            "symbol": security_id,
            "ltp": round(ltp, 2),
            "open": round(base_price, 2),
            "high": round(base_price * 1.01, 2),
            "low": round(base_price * 0.99, 2),
            "close": round(base_price, 2),
            "volume": 1000000 + int(random.random() * 500000),
            "timestamp": datetime.now(ist).isoformat()
        }
    
    def _mock_historical_data(self, security_id: str, interval: str) -> List[Dict]:
        """Mock historical data"""
        base_price = self._get_mock_base_price(security_id)
        data = []
        for i in range(30):
            # Days AGO: 29, 28, ..., 0
            days_ago = 29 - i
            ist = pytz.timezone("Asia/Kolkata")
            date = datetime.now(ist) - timedelta(days=days_ago)
            
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

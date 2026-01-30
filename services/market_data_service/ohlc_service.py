import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dhan_client import dhan_client
from indicators import indicators
import logging

logger = logging.getLogger("OHLCService")

class OHLCService:
    def __init__(self):
        self.supported_intervals = ["1m", "5m", "15m", "30m", "1h", "1D"]
    
    def get_ohlc_data(self, symbol: str, interval: str = "1D", days: int = 30) -> Optional[pd.DataFrame]:
        """Fetch OHLC data and return as DataFrame"""
        if interval not in self.supported_intervals:
            logger.error(f"Unsupported interval: {interval}")
            return None
        
        data = dhan_client.get_historical_data(symbol, interval)
        if not data:
            return None
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    
    def get_ohlc_with_indicators(self, symbol: str, interval: str = "1D", days: int = 30) -> Optional[Dict]:
        """Get OHLC data enriched with technical indicators"""
        df = self.get_ohlc_data(symbol, interval, days)
        if df is None or df.empty:
            return None
        
        try:
            # Calculate indicators
            df['sma_20'] = indicators.calculate_sma(df['close'], 20)
            df['ema_20'] = indicators.calculate_ema(df['close'], 20)
            df['rsi'] = indicators.calculate_rsi(df['close'], 14)
            df['atr'] = indicators.calculate_atr(df['high'], df['low'], df['close'], 14)
            df['adx'] = indicators.calculate_adx(df['high'], df['low'], df['close'], 14)
            
            # ATR Ratio: Current ATR / Historical Average ATR (30 days)
            df['atr_sma'] = df['atr'].rolling(window=30).mean()
            df['atr_ratio'] = df['atr'] / df['atr_sma']
            
            bb = indicators.calculate_bollinger_bands(df['close'], 20)
            df['bb_upper'] = bb['upper']
            df['bb_middle'] = bb['middle']
            df['bb_lower'] = bb['lower']
            
            macd_data = indicators.calculate_macd(df['close'])
            df['macd'] = macd_data['macd']
            df['macd_signal'] = macd_data['signal']
            df['macd_histogram'] = macd_data['histogram']
            
            # Handle NaN/Inf values for JSON serialization
            # Replace inf with nan
            df = df.replace([np.inf, -np.inf], np.nan)
            # Replace nan with None (which becomes null in JSON)
            # We use object dtype to allow None
            df = df.astype(object).where(pd.notnull(df), None)
            
            return {
                "symbol": symbol,
                "interval": interval,
                "data": df.reset_index().to_dict(orient='records')
            }
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None

# Singleton
ohlc_service = OHLCService()

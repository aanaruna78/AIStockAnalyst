from fastapi import FastAPI, HTTPException
import sys
import os
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from dhan_client import dhan_client
from ohlc_service import ohlc_service
from trading_calendar import trading_calendar
from datetime import datetime
import logging

app = FastAPI(title="SignalForge Market Data Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MarketDataService")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """Get live quote for a symbol"""
    quote = dhan_client.get_live_price(symbol)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@app.get("/ohlc/{symbol}")
async def get_ohlc(symbol: str, interval: str = "1D", days: int = 30):
    """Get OHLC data with technical indicators"""
    data = ohlc_service.get_ohlc_with_indicators(symbol, interval, days)
    if not data:
        raise HTTPException(status_code=404, detail="OHLC data not found")
    return data

@app.get("/calendar/is-trading-day")
async def check_trading_day(date: str = None):
    """Check if a date is a trading day"""
    if date:
        dt = datetime.fromisoformat(date)
    else:
        dt = datetime.now()
    
    is_trading = trading_calendar.is_trading_day(dt)
    is_open = trading_calendar.is_market_open(dt)
    
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "is_trading_day": is_trading,
        "is_market_open": is_open
    }

@app.get("/calendar/next-trading-day")
async def get_next_trading_day(date: str = None):
    """Get the next trading day"""
    if date:
        dt = datetime.fromisoformat(date)
    else:
        dt = datetime.now()
    
    next_day = trading_calendar.next_trading_day(dt)
    return {
        "current_date": dt.strftime("%Y-%m-%d"),
        "next_trading_day": next_day.strftime("%Y-%m-%d")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

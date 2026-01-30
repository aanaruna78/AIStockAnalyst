from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import yfinance as yf
import sys
import os
import httpx
from contextlib import asynccontextmanager

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from services.trading_service.trade_manager import TradeManager
from shared.models import Portfolio
from scheduler_job import start_scheduler

trade_manager = TradeManager()

# Background Task: Price Monitor
async def price_monitor_loop():
    print("[TradingService] Price Monitor Started")
    while True:
        try:
            # 1. Get active symbols
            active_trades = trade_manager.portfolio.active_trades
            if not active_trades:
                await asyncio.sleep(60)
                continue

            symbols = [t.symbol + ".NS" for t in active_trades] # NSE symbols
            
            # 2. Fetch live prices via yfinance
            tickers = " ".join(symbols)
            if not tickers:
                await asyncio.sleep(60)
                continue
                
            data = yf.download(tickers, period="1d", interval="1m", progress=False)
            
            current_prices = {}
            if len(symbols) == 1:
                try:
                    price = data['Close'].iloc[-1].item()
                    current_prices[active_trades[0].symbol] = price
                except: pass
            else:
                try:
                    last_row = data['Close'].iloc[-1]
                    for symbol in active_trades:
                        yf_sym = symbol.symbol + ".NS"
                        if yf_sym in last_row:
                            current_prices[symbol.symbol] = last_row[yf_sym].item()
                except: pass

            # 3. Update Trade Manager
            if current_prices:
                trade_manager.update_prices(current_prices)
                
        except Exception as e:
            print(f"[TradingService] Monitor Error: {e}")
        
        await asyncio.sleep(5) # Run every 5 seconds for near real-time updates

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    asyncio.create_task(price_monitor_loop())
    yield
    # Shutdown
    pass

app = FastAPI(title="Trading Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/portfolio", response_model=Portfolio)
async def get_portfolio():
    return trade_manager.get_portfolio_summary()

@app.post("/trade/manual")
async def place_manual_order(symbol: str, price: float, target: float, sl: float, conviction: float, quantity: int = 0):
    trade = trade_manager.place_order(symbol, price, target, sl, conviction, "Manual Trade", quantity)
    if not trade:
        raise HTTPException(status_code=400, detail="Order failed (Insufficient funds or error)")
    return trade

@app.post("/trade/close/{trade_id}")
async def close_trade(trade_id: str, price: float):
    trade_manager.close_trade(trade_id, price, "Manual Close via API")
    return {"status": "closed"}

@app.post("/trade/close-all")
async def close_all_positions():
    # Fetch latest prices for accurate exit
    active_trades = trade_manager.portfolio.active_trades
    price_map = {}
    if active_trades:
        symbols_str = " ".join([t.symbol + ".NS" for t in active_trades])
        try:
            data = yf.download(symbols_str, period="1d", interval="1m", progress=False)
            if len(active_trades) == 1:
                try:
                    price = data['Close'].iloc[-1].item()
                    price_map[active_trades[0].symbol] = price
                except: pass
            else:
                try:
                    last_row = data['Close'].iloc[-1]
                    for t in active_trades:
                        yf_sym = t.symbol + ".NS"
                        if yf_sym in last_row:
                            price_map[t.symbol] = last_row[yf_sym].item()
                except: pass
        except:
            print("[TradingService] Failed to fetch exit prices, using fallback")

    trade_manager.close_all_positions(price_map)
    return {"status": "All positions closed"}

@app.post("/trade/execute-signals")
async def execute_signals():
    """Fetch recommendations and place orders"""
    print("[TradingService] 🤖 Examining signals for auto-entry...")
    async with httpx.AsyncClient() as client:
        try:
            # Fetch active recommendations from API Gateway
            resp = await client.get("http://localhost:8000/api/v1/recommendations/active")
            if resp.status_code != 200:
                print(f"[TradingService] Failed to fetch signals: {resp.status_code}")
                return {"status": "failed", "reason": "Could not fetch recommendations"}
            
            recommendations = resp.json()
            executed_count = 0
            
            for rec in recommendations:
                # Logic: Conviction > 60 and Direction UP (for now Buy only)
                is_active = any(t.symbol == rec['symbol'] and t.status == 'OPEN' for t in trade_manager.portfolio.active_trades)
                
                conviction = rec.get('conviction', 0)
                direction = rec.get('direction', 'NEUTRAL')
                
                if not is_active and conviction > 60 and direction in ['UP', 'Strong Up']:
                    # Calculate Intraday Limits (Max Target 2%, Max SL 1%)
                    entry = rec.get('entry') or rec.get('price', 0)
                    rec_target = rec.get('target1', 0)
                    rec_sl = rec.get('sl', 0)
                    
                    # Clamp Target (min of Rec Target or Entry + 2%)
                    intraday_target = entry * 1.02
                    final_target = min(rec_target, intraday_target) if rec_target > entry else rec_target
                    
                    # Clamp SL (max of Rec SL or Entry - 1%)
                    intraday_sl = entry * 0.99
                    final_sl = max(rec_sl, intraday_sl) if rec_sl < entry else rec_sl
                    
                    # Execute Buy
                    trade_manager.place_order(
                        symbol=rec['symbol'],
                        entry_price=entry,
                        target=final_target,
                        stop_loss=final_sl,
                        conviction=conviction,
                        rationale=rec.get('rationale', '')
                    )
                    executed_count += 1
            
            return {"status": "success", "executed": executed_count}
            
        except Exception as e:
            print(f"[TradingService] Error executing signals: {e}")
            return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)

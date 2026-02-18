from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import asyncio
import yfinance as yf
import sys
import os
import httpx
from contextlib import asynccontextmanager
import pytz
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from trade_manager import TradeManager
from shared.models import Portfolio
from shared.config import settings
from scheduler_job import start_scheduler
from model_report import generate_daily_report, get_daily_report, save_feedback, get_all_feedback

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

            [t.symbol + ".NS" for t in active_trades] # NSE symbols
            
            # 2. Fetch live prices via robust mechanism
            current_prices = {}
            import math
            import random
            import requests
            import urllib3
            
            # Disable SSL warnings for the fallback
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }

            for trade in list(active_trades):
                symbol = trade.symbol
                yf_sym = f"{symbol}.NS"
                price = None
                
                # Method A: Try direct JSON API (often avoids 'NoneType' and SSL issues if verify=False)
                try:
                    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yf_sym}?interval=1m&range=1d"
                    r = requests.get(url, headers=headers, verify=False, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get('chart') and data['chart'].get('result'):
                            price = data['chart']['result'][0]['meta'].get('regularMarketPrice')
                except Exception as e:
                    print(f"[TradingService] Direct Fetch Failed for {yf_sym}: {e}")

                # Method B: Google Finance Scraper (Resilient Fallback)
                if price is None:
                    try:
                        # Google Finance URL: https://www.google.com/finance/quote/RELIANCE:NSE
                        g_url = f"https://www.google.com/finance/quote/{symbol}:NSE"
                        gr = requests.get(g_url, headers=headers, verify=False, timeout=5)
                        if gr.status_code == 200:
                            # Simple regex or split to find price
                            import re
                            # Google Finance often has data-last-price or just the price in a div
                            # We look for the price currency symbol and then the value
                            match = re.search(r'data-last-price="([\d\.]+)"', gr.text)
                            if match:
                                price = float(match.group(1))
                            else:
                                # Fallback to looking for the large price text
                                # The class is often 'YMlKec fxKbKc' but it changes. 
                                # Let's try to find ₹ followed by numbers
                                match_rupee = re.search(r'₹([\d,]+\.\d+)', gr.text)
                                if match_rupee:
                                    price = float(match_rupee.group(1).replace(',', ''))
                    except Exception as ge:
                        print(f"[TradingService] Google Scrape Failed for {symbol}: {ge}")

                # Method C: Fallback to yfinance (if Method A and B failed)
                if price is None:
                    try:
                        ticker = yf.Ticker(yf_sym)
                        info = ticker.fast_info
                        price = info.get('lastPrice') or info.get('last_price')
                    except Exception:
                        # print(f"[TradingService] yfinance Fallback Failed for {yf_sym}: {e}")
                        pass

                if price and not math.isnan(price):
                    print(f"[TradingService] ✅ Fetched {yf_sym}: {price}")
                    # Add a tiny random jitter (0.01%) for paper trading feedback
                    jitter = float(price) * 0.0001 * (random.random() - 0.5)
                    current_prices[symbol] = float(price) + jitter
                else:
                    print(f"[TradingService] ❌ Could not find price for {yf_sym}")

            # 3. Update Trade Manager and timestamp
            if current_prices:
                trade_manager.update_prices(current_prices)
                ist = pytz.timezone("Asia/Kolkata")
                trade_manager.portfolio.last_updated = datetime.now(ist)
                
        except Exception as e:
            print(f"[TradingService] Monitor Error: {e}")
            import traceback
            traceback.print_exc()
        
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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "trading-service"}

@app.get("/portfolio", response_model=Portfolio)
async def get_portfolio():
    return trade_manager.get_portfolio_summary()

@app.post("/trade/manual")
async def place_manual_order(symbol: str, price: float, target: float, sl: float, conviction: float, quantity: int = 0, trade_type: str = "BUY"):
    trade = trade_manager.place_order(symbol, price, target, sl, conviction, "Manual Trade", quantity, trade_type=trade_type)
    if not trade:
        raise HTTPException(status_code=400, detail="Order failed (Insufficient funds or error)")
    return trade

@app.post("/trade/close/{trade_id}")
async def close_trade(trade_id: str, price: float):
    trade_manager.close_trade(trade_id, price, "Manual Close via API")
    return {"status": "closed"}

@app.post("/trade/update-sl/{trade_id}")
async def update_stop_loss(trade_id: str, new_sl: float):
    """Update the stop-loss of an active trade (trailing SL)."""
    success = trade_manager.update_stop_loss(trade_id, new_sl)
    if not success:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "sl_updated", "trade_id": trade_id, "new_sl": new_sl}

@app.post("/trade/close-by-symbol/{symbol}")
async def close_by_symbol(symbol: str, price: float, reason: str = "Trend Reversal"):
    """Close all active trades for a symbol (used for trend-reversal exits)."""
    success = trade_manager.close_by_symbol(symbol, price, reason)
    if not success:
        raise HTTPException(status_code=404, detail=f"No active trades found for {symbol}")
    return {"status": "closed", "symbol": symbol, "reason": reason}

@app.post("/trade/close-all")
async def close_all_positions():
    """Square off all positions using best available price."""
    import requests
    import math
    active_trades = list(trade_manager.portfolio.active_trades)
    price_map = {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    for trade in active_trades:
        symbol = trade.symbol
        yf_sym = f"{symbol}.NS"
        price = None

        # Method A: Yahoo Finance direct JSON API
        try:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yf_sym}?interval=1m&range=1d"
            r = requests.get(url, headers=headers, verify=False, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get('chart') and data['chart'].get('result'):
                    price = data['chart']['result'][0]['meta'].get('regularMarketPrice')
        except Exception:
            pass

        # Method B: Google Finance
        if price is None:
            try:
                import re
                g_url = f"https://www.google.com/finance/quote/{symbol}:NSE"
                gr = requests.get(g_url, headers=headers, verify=False, timeout=5)
                if gr.status_code == 200:
                    match = re.search(r'data-last-price="([\d\.]+)"', gr.text)
                    if match:
                        price = float(match.group(1))
            except Exception:
                pass

        # Method C: yfinance
        if price is None:
            try:
                ticker = yf.Ticker(yf_sym)
                info = ticker.fast_info
                price = info.get('lastPrice') or info.get('last_price')
            except Exception:
                pass

        if price and not math.isnan(price):
            price_map[symbol] = float(price)
            print(f"[TradingService] Square-off price for {symbol}: {price}")
        else:
            # Last resort: use the most recent price from the monitor loop
            if trade.current_price and trade.current_price > 0:
                price_map[symbol] = trade.current_price
                print(f"[TradingService] Using last known price for {symbol}: {trade.current_price}")
            else:
                print(f"[TradingService] ⚠️ No price found for {symbol}, using entry price")

    trade_manager.close_all_positions(price_map)
    closed_count = len(active_trades)
    return {"status": f"{closed_count} positions closed", "prices": price_map}

@app.post("/trade/execute-signals")
async def execute_signals():
    """Fetch recommendations and place orders.
    - Only trades after 9:20 AM IST (skip first 5 min volatility)
    - Uses limit order at +0.1% LTP offset to avoid stale prices
    """
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    market_start = now.replace(hour=9, minute=20, second=0, microsecond=0)
    
    # === TIME GATE: No trades before 9:20 AM IST ===
    if now < market_start:
        print(f"[TradingService] ⏳ Too early for trades ({now.strftime('%H:%M IST')}). Waiting until 9:20 AM.")
        return {"status": "skipped", "reason": f"Before 9:20 AM IST (current: {now.strftime('%H:%M')})"}
    
    # Limit order offset: +0.1% above LTP for BUY, -0.1% below LTP for SELL
    LIMIT_ORDER_OFFSET = 0.001  # 0.1%
    
    print("[TradingService] 🤖 Examining signals for auto-entry...")
    async with httpx.AsyncClient() as client:
        try:
            # Fetch active recommendations from API Gateway
            resp = await client.get(f"{settings.REC_ENGINE_URL}/active")
            if resp.status_code != 200:
                print(f"[TradingService] Failed to fetch signals: {resp.status_code}")
                return {"status": "failed", "reason": "Could not fetch recommendations"}
            
            recommendations = resp.json()
            executed_count = 0
            
            for rec in recommendations:
                symbol = rec.get('symbol', '')
                active_trade = next(
                    (t for t in trade_manager.portfolio.active_trades if t.symbol == symbol and t.status == 'OPEN'),
                    None
                )
                
                conviction = rec.get('conviction', 0)
                direction = rec.get('direction', 'NEUTRAL')
                
                # Support both LONG and SHORT with bidirectional conviction thresholds
                is_bullish = direction in ['UP', 'Strong Up']
                is_bearish = direction in ['DOWN', 'Strong Down']
                
                # Trend reversal detection: if we hold a position and signal flips direction
                if active_trade and conviction > 10 and (is_bullish or is_bearish):
                    current_dir = "BEARISH" if active_trade.type == 'SELL' else "BULLISH"
                    new_dir = "BULLISH" if is_bullish else "BEARISH"
                    if current_dir != new_dir:
                        # Trend reversed — close existing position first
                        exit_price = active_trade.current_price if active_trade.current_price and active_trade.current_price > 0 else active_trade.entry_price
                        trade_manager.close_by_symbol(symbol, exit_price, reason=f"Trend Reversal → {direction}")
                        print(f"[TradingService] 🔄 TREND REVERSAL for {symbol}: {current_dir} → {new_dir}")
                        # Fall through to enter the new direction below
                        active_trade = None  # Allow re-entry
                
                if not active_trade and conviction > 10 and (is_bullish or is_bearish):
                    ltp = rec.get('entry') or rec.get('price', 0)
                    if not ltp or ltp <= 0:
                        continue
                    
                    rec_target = rec.get('target1', 0) or rec.get('target', 0)
                    rec_sl = rec.get('sl', 0)
                    
                    if is_bullish:
                        # Limit order: entry at LTP + 0.1% (slightly above to fill)
                        entry = round(ltp * (1 + LIMIT_ORDER_OFFSET), 2)
                        # LONG: target MUST be above entry, SL MUST be below
                        intraday_target = entry * 1.02
                        final_target = rec_target if rec_target > entry else intraday_target
                        intraday_sl = entry * 0.99
                        final_sl = rec_sl if 0 < rec_sl < entry else intraday_sl
                        trade_type = "BUY"
                    else:
                        # Limit order: entry at LTP - 0.1% (slightly below to fill)
                        entry = round(ltp * (1 - LIMIT_ORDER_OFFSET), 2)
                        # SHORT: target MUST be below entry, SL MUST be above
                        intraday_target = entry * 0.98
                        final_target = rec_target if 0 < rec_target < entry else intraday_target
                        intraday_sl = entry * 1.01
                        final_sl = rec_sl if rec_sl > entry else intraday_sl
                        trade_type = "SELL"
                    
                    print(f"[TradingService] 📝 Limit order {trade_type} {symbol}: LTP={ltp} → Entry={entry} (+0.1% offset)")
                    result = trade_manager.place_order(
                        symbol=rec['symbol'],
                        entry_price=entry,
                        target=final_target,
                        stop_loss=final_sl,
                        conviction=conviction,
                        rationale=rec.get('rationale', ''),
                        trade_type=trade_type
                    )
                    if result:
                        executed_count += 1
            
            return {"status": "success", "executed": executed_count}
            
        except Exception as e:
            print(f"[TradingService] Error executing signals: {e}")
            return {"status": "error", "detail": str(e)}

@app.post("/portfolio/reset")
async def reset_portfolio():
    """Reset portfolio to initial state (₹1,00,000 fresh start).
    Keeps trade_history for audit trail. Use /portfolio/clear-history to wipe history."""
    from trade_manager import INITIAL_CAPITAL
    # Close any active trades at entry price (no P&L impact) and move to history
    for trade in list(trade_manager.portfolio.active_trades):
        trade_manager.close_trade(trade.id, trade.entry_price, reason="Portfolio Reset")
    trade_manager.portfolio.cash_balance = INITIAL_CAPITAL
    trade_manager.portfolio.realized_pnl = 0.0
    trade_manager.portfolio.active_trades = []
    # Keep trade_history intact for audit trail
    ist = pytz.timezone("Asia/Kolkata")
    trade_manager.portfolio.last_updated = datetime.now(ist)
    trade_manager.save_state()
    print(f"[TradingService] ♻️ Portfolio RESET to ₹{INITIAL_CAPITAL:,.0f} (history preserved: {len(trade_manager.portfolio.trade_history)} trades)")
    return {"status": "reset", "cash_balance": INITIAL_CAPITAL, "history_kept": len(trade_manager.portfolio.trade_history)}

@app.post("/portfolio/clear-history")
async def clear_trade_history():
    """Clear trade history (separate from reset to avoid accidental loss)."""
    count = len(trade_manager.portfolio.trade_history)
    trade_manager.portfolio.trade_history = []
    trade_manager.save_state()
    print(f"[TradingService] 🗑️ Trade history cleared ({count} trades removed)")
    return {"status": "cleared", "trades_removed": count}


# ─────────────────────────────────────────────────────────
# MODEL PERFORMANCE REPORT & FEEDBACK ENDPOINTS (Admin UI)
# ─────────────────────────────────────────────────────────

@app.get("/model/report")
async def api_model_report():
    """Generate and return today's model performance report."""
    report = generate_daily_report(trade_manager.portfolio.trade_history)
    return report

@app.get("/model/report/cached")
async def api_model_report_cached():
    """Return last cached report (fast, no recalculation)."""
    return get_daily_report()

@app.post("/model/feedback")
async def api_model_feedback(request: Request):
    """Accept admin feedback for model improvement."""
    data = await request.json()
    feedback_text = data.get("feedback", "").strip()
    category = data.get("category", "general")
    if not feedback_text:
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")
    result = save_feedback(feedback_text, category)
    return result

@app.get("/model/feedback")
async def api_get_feedback():
    """Return all stored feedback."""
    return get_all_feedback()

@app.get("/model/failed-trades")
async def api_failed_trades():
    """Return all failed trades for analysis."""
    from failed_trade_log import get_failed_trades, get_trade_failure_stats
    return {
        "trades": get_failed_trades(),
        "stats": get_trade_failure_stats(),
    }


# ─────────────────────────────────────────────────────────
# TRAILING SL & ICEBERG ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.get("/trailing-sl/status")
async def trailing_sl_status():
    """Return trailing SL state for all active trades."""
    return trade_manager.get_trailing_sl_status()


@app.get("/iceberg/history")
async def iceberg_history():
    """Return iceberg order history."""
    return trade_manager.get_iceberg_history()


# ─────────────────────────────────────────────────────────
# TRADE REPORTING (date-range filtering)
# ─────────────────────────────────────────────────────────

@app.get("/reports/trades")
async def trade_report(start_date: str = None, end_date: str = None):
    """Trade performance report with optional date range.
    Dates in YYYY-MM-DD format.
    """
    from datetime import date as dt_date
    trades = trade_manager.portfolio.trade_history

    # Filter by date range
    filtered = []
    for t in trades:
        t_date = None
        if t.exit_time:
            t_date = t.exit_time if isinstance(t.exit_time, dt_date) else None
            if hasattr(t.exit_time, 'date'):
                t_date = t.exit_time.date()
        elif t.entry_time:
            t_date = t.entry_time if isinstance(t.entry_time, dt_date) else None
            if hasattr(t.entry_time, 'date'):
                t_date = t.entry_time.date()

        if t_date is None:
            filtered.append(t)
            continue

        if start_date:
            sd = dt_date.fromisoformat(start_date)
            if t_date < sd:
                continue
        if end_date:
            ed = dt_date.fromisoformat(end_date)
            if t_date > ed:
                continue
        filtered.append(t)

    # Calculate summary stats
    total_pnl = sum(t.pnl or 0 for t in filtered)
    winners = [t for t in filtered if (t.pnl or 0) > 0]
    losers = [t for t in filtered if (t.pnl or 0) < 0]
    win_rate = (len(winners) / len(filtered) * 100) if filtered else 0
    avg_win = (sum(t.pnl for t in winners) / len(winners)) if winners else 0
    avg_loss = (sum(t.pnl for t in losers) / len(losers)) if losers else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    return {
        "total_trades": len(filtered),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
        "trades": [t.model_dump() for t in filtered],
        "filters": {"start_date": start_date, "end_date": end_date},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

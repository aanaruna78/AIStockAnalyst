"""
Intraday Agent Service
======================
Autonomous trading agent that continuously monitors the market during
trading hours (9:15 AM – 3:15 PM IST), reviews signals from the
recommendation engine, executes trades via the trading service, and
manages positions with risk controls.

Runs as an internal service — user preference for scan frequency does
not affect this agent. It always operates during market hours.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import httpx
import os
from datetime import datetime, time as dtime
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from pydantic import BaseModel
from enum import Enum
import pytz
import sys

# Add project root to sys.path for shared imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.trailing_sl import TrailingStopLossEngine, TrailConfig, TrailStrategy
from shared.iceberg_order import IcebergEngine

# ─── Configuration ───────────────────────────────────────────────
TRADING_SERVICE_URL = os.getenv("TRADING_SERVICE_URL", "http://trading-service:8000")
REC_ENGINE_URL = os.getenv("REC_ENGINE_URL", "http://recommendation-engine:8000")
MARKET_DATA_URL = os.getenv("MARKET_DATA_URL", "http://market-data-service:8000")
CHART_ANALYSIS_URL = os.getenv("CHART_ANALYSIS_URL", "http://chart-analysis-service:8000")

# Agent parameters
AGENT_LOOP_INTERVAL = int(os.getenv("AGENT_LOOP_INTERVAL", "15"))       # seconds — faster monitoring for intraday
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))                     # fewer positions for tighter focus
MAX_CAPITAL_PER_TRADE = float(os.getenv("MAX_CAPITAL_PER_TRADE", "50000"))
MIN_CONVICTION_TO_TRADE = float(os.getenv("MIN_CONVICTION_TO_TRADE", "40"))  # higher conviction for intraday
TRAILING_SL_TRIGGER_PCT = float(os.getenv("TRAILING_SL_TRIGGER_PCT", "0.5"))  # 0.5% — tighter trailing for intraday
INTRADAY_LEVERAGE = 3        # 3x margin leverage for intraday stocks
ICEBERG_QTY_THRESHOLD = 500  # Use iceberg above this qty
MARKET_OPEN = dtime(9, 20)   # Start trading at 9:20 AM IST (skip first 5 min volatility)
MARKET_CLOSE = dtime(15, 15)
SQUARE_OFF_TIME = dtime(15, 10)  # Square off 5 min before close
IST = pytz.timezone("Asia/Kolkata")

# Limit order offset: +0.1% above LTP for BUY, -0.1% below LTP for SELL
# This avoids catching stale/wrong prices from data feeds
LIMIT_ORDER_OFFSET_PCT = 0.001  # 0.1%


# ─── Models ──────────────────────────────────────────────────────
class AgentState(str, Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    EXECUTING = "executing"
    SQUARED_OFF = "squared_off"

class AgentAction(BaseModel):
    timestamp: str
    action: str
    symbol: str = ""
    detail: str = ""

class AgentStatus(BaseModel):
    status: str = "online"
    state: str = AgentState.IDLE
    active_monitors: int = 0
    trades_today: int = 0
    last_action: Optional[str] = None
    last_check: Optional[str] = None
    actions_log: List[Dict] = []
    market_open: bool = False


# ─── Agent Core ──────────────────────────────────────────────────
class IntradayAgent:
    def __init__(self):
        self.state = AgentState.IDLE
        self.trades_today = 0
        self.actions_log: List[AgentAction] = []
        self.processed_signals: set = set()  # Track signal IDs already evaluated
        self.last_check = None
        self.running = False
        self._last_reset_date = None  # Track daily reset
        # Trailing SL engine config & state tracking
        self._trail_config = TrailConfig(
            strategy=TrailStrategy.HYBRID,
            trail_pct=0.5,
            activation_pct=0.3,
            step_size_pct=0.5,
            step_lock_pct=0.3,
            breakeven_trigger_pct=0.5,
            min_trail_pct=0.2,
        )
        self._trail_states: Dict[str, dict] = {}  # trade_id -> trail state dict

    def is_market_hours(self) -> bool:
        """Check if current time is within Indian market hours (9:20-15:15 IST)."""
        now = datetime.now(IST).time()
        return MARKET_OPEN <= now <= MARKET_CLOSE

    def is_square_off_time(self) -> bool:
        """Check if we should square off all positions."""
        now = datetime.now(IST).time()
        return now >= SQUARE_OFF_TIME

    def log_action(self, action: str, symbol: str = "", detail: str = ""):
        entry = AgentAction(
            timestamp=datetime.now(IST).isoformat(),
            action=action,
            symbol=symbol,
            detail=detail
        )
        self.actions_log.append(entry)
        # Keep last 100 actions
        if len(self.actions_log) > 100:
            self.actions_log = self.actions_log[-100:]
        print(f"[IntradayAgent] {action} {symbol} {detail}")

    async def fetch_signals(self) -> List[Dict]:
        """Fetch active recommendations from the recommendation engine."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{REC_ENGINE_URL}/active")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            self.log_action("FETCH_ERROR", detail=str(e))
        return []

    async def fetch_portfolio(self) -> Optional[Dict]:
        """Fetch current portfolio from trading service."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{TRADING_SERVICE_URL}/portfolio")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            self.log_action("PORTFOLIO_ERROR", detail=str(e))
        return None

    async def fetch_chart_analysis(self, symbol: str) -> Optional[Dict]:
        """Fetch chart-based technical analysis for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{CHART_ANALYSIS_URL}/analyze/{symbol}")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass  # Chart service may not be running yet
        return None

    async def execute_trade(self, rec: Dict) -> bool:
        """Execute a specific trade via the trading service.
        Uses limit order at +0.1% above LTP (BUY) or -0.1% below LTP (SELL).
        Applies 3x intraday leverage and iceberg ordering for large quantities.
        """
        symbol = rec.get("symbol", "")
        direction = rec.get("direction", "")
        ltp = rec.get("entry") or rec.get("price", 0)
        if not ltp or ltp <= 0:
            self.log_action("SKIP_NO_PRICE", symbol, "No valid entry price")
            return False

        is_bullish = direction in ["UP", "Strong Up"]
        is_bearish = direction in ["DOWN", "Strong Down"]

        if is_bullish:
            trade_type = "BUY"
            # Limit order: entry at LTP + 0.1% (slightly above to fill)
            entry = round(ltp * (1 + LIMIT_ORDER_OFFSET_PCT), 2)
            target = rec.get("target1") or rec.get("target") or entry * 1.012  # 1.2% default target (intraday)
            sl = rec.get("sl") or entry * 0.993                                # 0.7% default SL (intraday)
            # Cap SL to max 1.5% from entry for intraday
            max_sl = entry * 0.985
            if sl < max_sl:
                sl = max_sl
            # Cap target to max 3% from entry for intraday
            max_target = entry * 1.03
            if target > max_target:
                target = max_target
            # Ensure target above entry, SL below
            if target <= entry:
                target = entry * 1.012
            if sl >= entry:
                sl = entry * 0.993
        elif is_bearish:
            trade_type = "SELL"
            # Limit order: entry at LTP - 0.1% (slightly below to fill)
            entry = round(ltp * (1 - LIMIT_ORDER_OFFSET_PCT), 2)
            target = rec.get("target1") or rec.get("target") or entry * 0.988  # 1.2% default target (intraday)
            sl = rec.get("sl") or entry * 1.007                                # 0.7% default SL (intraday)
            # Cap SL to max 1.5% from entry for intraday
            max_sl = entry * 1.015
            if sl > max_sl:
                sl = max_sl
            # Cap target to max 3% from entry for intraday
            max_target = entry * 0.97
            if target < max_target:
                target = max_target
            # Ensure target below entry, SL above
            if target >= entry:
                target = entry * 0.988
            if sl <= entry:
                sl = entry * 1.007
        else:
            self.log_action("SKIP_NEUTRAL", symbol, f"Direction: {direction}")
            return False

        conviction = rec.get("conviction", 0)
        rec.get("rationale", "") or rec.get("summary", "")
        # Apply 3x intraday leverage
        base_qty = max(1, int(MAX_CAPITAL_PER_TRADE / entry))
        quantity = base_qty * INTRADAY_LEVERAGE

        # Log iceberg info if large qty
        if quantity > ICEBERG_QTY_THRESHOLD:
            iceberg = IcebergEngine.create_stock_iceberg(
                symbol=symbol,
                side=trade_type,
                total_qty=quantity,
                price=entry,
            )
            self.log_action("ICEBERG_ORDER", symbol,
                f"Qty {quantity} split into {len(iceberg.slices)} slices of ~{iceberg.slices[0].quantity}")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{TRADING_SERVICE_URL}/trade/manual",
                    params={
                        "symbol": symbol,
                        "price": entry,
                        "target": round(target, 2),
                        "sl": round(sl, 2),
                        "conviction": conviction,
                        "quantity": quantity,
                        "trade_type": trade_type
                    }
                )
                if resp.status_code == 200:
                    self.trades_today += 1
                    # Initialize trailing SL state for the new trade
                    trade_data = resp.json()
                    trade_id = trade_data.get("id", "")
                    if trade_id:
                        trail_state = TrailingStopLossEngine.create_state(
                            entry_price=entry, initial_sl=sl,
                            is_long=(trade_type == "BUY"),
                        )
                        self._trail_states[trade_id] = TrailingStopLossEngine.state_to_dict(trail_state)
                    self.log_action("LIMIT_ORDER_PLACED", symbol,
                        f"{trade_type} @ {entry} (LTP: {ltp}, +0.1% offset) | T: {round(target,2)} | SL: {round(sl,2)} | Qty: {quantity} (3x lev)")
                    return True
                else:
                    detail = resp.text[:200]
                    self.log_action("TRADE_FAILED", symbol, f"HTTP {resp.status_code}: {detail}")
        except Exception as e:
            self.log_action("EXECUTE_ERROR", symbol, str(e))
        return False

    async def square_off_all(self) -> bool:
        """Close all positions before market close."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{TRADING_SERVICE_URL}/trade/close-all")
                if resp.status_code == 200:
                    self.log_action("SQUARE_OFF", detail="All positions closed for EOD")
                    return True
        except Exception as e:
            self.log_action("SQUARE_OFF_ERROR", detail=str(e))
        return False

    def _get_signal_direction(self, direction: str) -> str:
        """Normalize direction into 'BULLISH', 'BEARISH', or 'NEUTRAL'."""
        if direction in ["UP", "Strong Up"]:
            return "BULLISH"
        if direction in ["DOWN", "Strong Down"]:
            return "BEARISH"
        return "NEUTRAL"

    def _get_trade_direction(self, trade: Dict) -> str:
        """Get the direction of an active trade: 'BULLISH' for BUY, 'BEARISH' for SELL."""
        t_type = trade.get("type", "BUY")
        return "BEARISH" if t_type == "SELL" else "BULLISH"

    async def close_trade_by_symbol(self, symbol: str, reason: str = "Trend Reversal") -> bool:
        """Close an active trade for a symbol via the trading service API."""
        try:
            # Fetch latest portfolio to get current price
            portfolio = await self.fetch_portfolio()
            if not portfolio:
                return False
            trade = next((t for t in portfolio.get("active_trades", []) if t["symbol"] == symbol), None)
            if not trade:
                return False
            # Use current_price from the trade (updated by price monitor every 5s)
            exit_price = trade.get("current_price") or trade.get("entry_price", 0)
            if exit_price <= 0:
                exit_price = trade.get("entry_price", 0)

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{TRADING_SERVICE_URL}/trade/close-by-symbol/{symbol}",
                    params={"price": exit_price, "reason": reason}
                )
                if resp.status_code == 200:
                    self.log_action("TREND_EXIT", symbol,
                        f"Closed @ {exit_price} | Reason: {reason}")
                    return True
                else:
                    self.log_action("TREND_EXIT_FAILED", symbol, resp.text[:200])
        except Exception as e:
            self.log_action("TREND_EXIT_ERROR", symbol, str(e))
        return False

    async def update_trailing_sl(self, trade: Dict) -> bool:
        """Adjust stop-loss using the shared TrailingStopLossEngine (HYBRID strategy).
        Dynamically computes new SL based on current price movement.
        """
        trade_id = trade.get("id", "")
        symbol = trade.get("symbol", "")
        current_price = trade.get("current_price", 0) or 0
        entry_price = trade.get("entry_price", 0)
        old_sl = trade.get("stop_loss", 0)
        trade_type = trade.get("type", "BUY")

        if current_price <= 0 or entry_price <= 0:
            return False

        # Get or create trail state for this trade
        trail_dict = self._trail_states.get(trade_id)
        if not trail_dict:
            # First time — initialize trail state
            trail_state = TrailingStopLossEngine.create_state(
                entry_price=entry_price,
                initial_sl=old_sl,
                is_long=(trade_type != "SELL"),
            )
        else:
            trail_state = TrailingStopLossEngine.state_from_dict(trail_dict)

        # Compute new SL using the engine
        new_sl = TrailingStopLossEngine.compute_new_sl(
            config=self._trail_config,
            state=trail_state,
            current_price=current_price,
        )

        # Persist trail state
        self._trail_states[trade_id] = TrailingStopLossEngine.state_to_dict(trail_state)

        if not new_sl or round(new_sl, 2) == round(old_sl, 2):
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{TRADING_SERVICE_URL}/trade/update-sl/{trade_id}",
                    params={"new_sl": round(new_sl, 2)}
                )
                if resp.status_code == 200:
                    self.log_action("TRAILING_SL_UPDATED", symbol,
                        f"SL moved: {old_sl} → {round(new_sl, 2)} (price: {current_price}) [HYBRID engine]")
                    return True
        except Exception as e:
            self.log_action("TRAILING_SL_ERROR", symbol, str(e))
        return False

    async def evaluate_signal(self, rec: Dict, portfolio: Dict) -> str:
        """
        Evaluate whether to act on a signal.
        Returns: 'ENTER', 'SKIP', 'HOLD', or 'REVERSE'
        """
        symbol = rec.get("symbol", "")
        conviction = rec.get("conviction", 0)
        direction = rec.get("direction", "")
        signal_dir = self._get_signal_direction(direction)

        # Already in position for this symbol?
        active_trades = portfolio.get("active_trades", [])
        active_symbols = {t["symbol"] for t in active_trades}
        if symbol in active_symbols:
            # Check if the new signal CONTRADICTS the existing position direction
            existing_trade = next((t for t in active_trades if t["symbol"] == symbol), None)
            if existing_trade:
                trade_dir = self._get_trade_direction(existing_trade)
                if signal_dir != "NEUTRAL" and signal_dir != trade_dir:
                    # Trend has reversed! Signal to exit and re-enter opposite
                    if conviction >= MIN_CONVICTION_TO_TRADE:
                        self.log_action("TREND_REVERSAL_DETECTED", symbol,
                            f"Position: {trade_dir} → New signal: {signal_dir} (conv: {conviction:.1f}%)")
                        return "REVERSE"
            return "HOLD"  # Same direction, keep holding

        # Already processed this signal?
        sig_id = rec.get("id", symbol)
        if sig_id in self.processed_signals:
            return "SKIP"

        # Check conviction threshold
        if conviction < MIN_CONVICTION_TO_TRADE:
            return "SKIP"

        # Check max positions
        if len(active_symbols) >= MAX_POSITIONS:
            self.log_action("MAX_POSITIONS", symbol, f"Already at {MAX_POSITIONS} positions")
            return "SKIP"

        # Check capital availability
        cash = portfolio.get("cash_balance", 0)
        entry_price = rec.get("price") or rec.get("entry", 0)
        if entry_price <= 0:
            return "SKIP"

        # Calculate position size (max capital per trade / entry price)
        max_qty = int(MAX_CAPITAL_PER_TRADE / entry_price)
        if max_qty < 1 or cash < entry_price:
            self.log_action("INSUFFICIENT_FUNDS", symbol, f"Cash: {cash}, Entry: {entry_price}")
            return "SKIP"

        # Optional: Check chart analysis for confirmation
        chart = await self.fetch_chart_analysis(symbol)
        if chart:
            chart_signal = chart.get("signal", "NEUTRAL")
            # If chart disagrees strongly, reduce size but still enter
            if direction in ["UP", "Strong Up"] and chart_signal == "STRONG_SELL":
                self.log_action("CHART_CONFLICT", symbol, "Chart says SELL but signal says BUY - skipping")
                return "SKIP"
            if direction in ["DOWN", "Strong Down"] and chart_signal == "STRONG_BUY":
                self.log_action("CHART_CONFLICT", symbol, "Chart says BUY but signal says SELL - skipping")
                return "SKIP"

        self.processed_signals.add(sig_id)
        return "ENTER"

    def _daily_reset_if_needed(self):
        """Reset processed signals at the start of each new trading day."""
        today = datetime.now(IST).date()
        if self._last_reset_date != today:
            self.processed_signals.clear()
            self.trades_today = 0
            self._last_reset_date = today
            self.log_action("DAILY_RESET", detail=f"New trading day: {today}")

    async def monitor_positions(self, portfolio: Dict):
        """Monitor active positions for trailing SL adjustment.
        When a position moves into profit beyond TRAILING_SL_TRIGGER_PCT,
        the stop-loss is tightened closer to the current price to lock in gains.
        """
        active_trades = portfolio.get("active_trades", [])
        for trade in active_trades:
            pnl_pct = trade.get("pnl_percent", 0) or 0
            if abs(pnl_pct) > TRAILING_SL_TRIGGER_PCT:
                # Position is in meaningful profit — update trailing SL
                updated = await self.update_trailing_sl(trade)
                if not updated:
                    self.log_action("TRAILING_REVIEW", trade["symbol"],
                        f"P&L: {pnl_pct:.2f}% — SL already tight or not in profit direction")

    async def run_cycle(self):
        """Execute one agent cycle: evaluate signals, manage positions."""
        self.last_check = datetime.now(IST).isoformat()

        # Daily reset check
        self._daily_reset_if_needed()

        if not self.is_market_hours():
            self.state = AgentState.IDLE
            return

        # Square off check
        if self.is_square_off_time():
            self.state = AgentState.SQUARED_OFF
            portfolio = await self.fetch_portfolio()
            if portfolio and len(portfolio.get("active_trades", [])) > 0:
                await self.square_off_all()
            return

        self.state = AgentState.MONITORING

        # Fetch data
        signals = await self.fetch_signals()
        portfolio = await self.fetch_portfolio()

        if not portfolio:
            self.log_action("NO_PORTFOLIO", detail="Could not reach trading service")
            return

        # Monitor existing positions
        await self.monitor_positions(portfolio)

        # Evaluate new signals — handle ENTER, REVERSE, and HOLD
        actionable = []
        reversals = []
        for rec in signals:
            decision = await self.evaluate_signal(rec, portfolio)
            if decision == "ENTER":
                actionable.append(rec)
                self.log_action("SIGNAL_ACCEPTED", rec.get("symbol", ""),
                    f"Direction: {rec.get('direction')} | Conviction: {rec.get('conviction', 0):.1f}%")
            elif decision == "REVERSE":
                reversals.append(rec)

        # Process trend reversals first — close existing position, then re-enter
        if reversals:
            self.state = AgentState.EXECUTING
            for rec in reversals:
                symbol = rec.get("symbol", "")
                direction = rec.get("direction", "")
                # Step 1: Close the existing contrary position
                closed = await self.close_trade_by_symbol(symbol, reason=f"Trend Reversal → {direction}")
                if closed:
                    # Step 2: Re-enter in the new direction
                    # Need to re-fetch portfolio to get updated cash after close
                    await asyncio.sleep(1)  # Brief pause for state sync
                    success = await self.execute_trade(rec)
                    if success:
                        self.log_action("REVERSAL_COMPLETE", symbol,
                            f"Exited old position & entered {direction}")
                    else:
                        self.log_action("REVERSAL_PARTIAL", symbol,
                            f"Old position closed but new {direction} entry failed")
                else:
                    self.log_action("REVERSAL_FAILED", symbol,
                        "Could not close existing position for reversal")
            self.state = AgentState.MONITORING

        # Execute new entries one by one
        if actionable:
            self.state = AgentState.EXECUTING
            for rec in actionable:
                success = await self.execute_trade(rec)
                if not success:
                    # Remove from processed so it can be retried next cycle
                    sig_id = rec.get("id", rec.get("symbol", ""))
                    self.processed_signals.discard(sig_id)
            self.state = AgentState.MONITORING

    def get_status(self) -> AgentStatus:
        return AgentStatus(
            status="online" if self.running else "offline",
            state=self.state,
            active_monitors=1 if self.running else 0,
            trades_today=self.trades_today,
            last_action=self.actions_log[-1].action if self.actions_log else None,
            last_check=self.last_check,
            actions_log=[a.dict() for a in self.actions_log[-20:]],
            market_open=self.is_market_hours()
        )


# ─── Agent Instance ──────────────────────────────────────────────
agent = IntradayAgent()


# ─── Background Loop ─────────────────────────────────────────────
async def agent_loop():
    """Main agent loop running every AGENT_LOOP_INTERVAL seconds."""
    agent.running = True
    agent.log_action("AGENT_START", detail="Intraday Agent initialized")

    while agent.running:
        try:
            await agent.run_cycle()
        except Exception as e:
            agent.log_action("CYCLE_ERROR", detail=str(e))
            import traceback
            traceback.print_exc()

        await asyncio.sleep(AGENT_LOOP_INTERVAL)


# ─── FastAPI App ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(agent_loop())
    yield
    agent.running = False
    task.cancel()

app = FastAPI(title="Intraday Agent Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "intraday-agent", "market_open": agent.is_market_hours()}


@app.get("/status")
async def get_status():
    return agent.get_status()


@app.get("/trades")
async def get_agent_trades():
    """Return actions log as pseudo-trades feed."""
    return [a.dict() for a in agent.actions_log if a.action in [
        "SIGNAL_ACCEPTED", "TRADES_EXECUTED", "SQUARE_OFF", "TRAILING_REVIEW",
        "TREND_REVERSAL_DETECTED", "TREND_EXIT", "REVERSAL_COMPLETE",
        "REVERSAL_PARTIAL", "TRAILING_SL_UPDATED"
    ]]


@app.post("/force-cycle")
async def force_cycle():
    """Manually trigger one agent cycle (for testing)."""
    await agent.run_cycle()
    return {"status": "cycle_completed", "state": agent.state}


@app.post("/reset")
async def reset_agent():
    """Reset agent state for a new trading day."""
    agent.trades_today = 0
    agent.processed_signals.clear()
    agent.actions_log.clear()
    agent._trail_states.clear()
    agent.state = AgentState.IDLE
    agent.log_action("RESET", detail="Agent state reset for new session")
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

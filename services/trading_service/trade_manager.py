
import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional
import uuid

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

# Fix path to import shared models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.models import Trade, TradeType, TradeStatus, Portfolio
from shared.trailing_sl import TrailingStopLossEngine, TrailConfig, TrailStrategy
from shared.iceberg_order import IcebergEngine
from shared.risk_engine import RiskEngine, RiskConfig, RiskMode
from shared.metrics_engine import MetricsEngine, TradeMetrics
from shared.self_learning import SelfLearningEngine
from failed_trade_log import log_failed_trade, get_failed_trades_for_symbol

# Robust path for data file — prefer env var, then /app/data (Docker), then local fallback
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.environ.get(
    "PAPER_TRADES_FILE",
    os.path.join(BASE_DIR, "data", "paper_trades.json")
)

INITIAL_CAPITAL = 100000.0  # ₹1,00,000 starting capital for paper trading
INTRADAY_LEVERAGE = 3       # 3x margin leverage for intraday stocks
ICEBERG_QTY_THRESHOLD = 500 # Use iceberg above this qty

# ── Per-symbol cooldown & re-entry limits ────────────────────────
SYMBOL_COOLDOWN_SEC = 1800     # 30 min cooldown after SL hit on same symbol
MAX_ENTRIES_PER_SYMBOL_DAY = 2 # Max 2 entries per symbol per day

# v2: Equity ATR-based risk engine
equity_risk_engine = RiskEngine(RiskConfig(
    mode=RiskMode.EQUITY_ATR,
    equity_sl_atr_mult=1.0,
    equity_tp1_atr_mult=1.2,
    equity_tp1_book_pct=0.55,
    equity_runner_atr_mult=1.0,
    equity_late_tighten_mult=0.8,
    equity_max_trades_per_day=10,
    daily_loss_cap_pct=0.02,
    consecutive_loss_limit=3,
    cooldown_seconds=1800,
))

# v2: Metrics + Learning engines
equity_metrics = MetricsEngine(data_dir=os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data")))
equity_learning = SelfLearningEngine(data_dir=os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data")))

class TradeManager:
    def __init__(self):
        self.portfolio = Portfolio()
        # Trailing SL states per trade
        self._trail_states: Dict[str, dict] = {}
        self._trail_config = TrailConfig(
            strategy=TrailStrategy.HYBRID,
            trail_pct=1.2,
            activation_pct=0.8,
            step_size_pct=0.8,
            step_lock_pct=0.5,
            breakeven_trigger_pct=1.0,
            min_trail_pct=0.5,
        )
        # Iceberg order history
        self.iceberg_orders: list = []
        # Margin blocked per trade (for leveraged trades)
        self._margin_blocked: Dict[str, float] = {}
        # ── Per-symbol cooldown tracking ──
        self._symbol_last_exit: Dict[str, float] = {}   # symbol -> epoch time of last SL exit
        self._symbol_entries_today: Dict[str, int] = {}  # symbol -> count of entries today
        self._today_date: str = ""
        self.load_state()

    def load_state(self):
        """Load portfolio state from JSON file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    # Convert dicts back to Pydantic models
                    self.portfolio = Portfolio(**data)
                    # Restore trailing SL states
                    self._trail_states = data.get("_trail_states", {})
                    self.iceberg_orders = data.get("iceberg_orders", [])
                    self._margin_blocked = data.get("_margin_blocked", {})
                    # GAP-9: restore cooldown state across restarts
                    cs = data.get("_cooldown_state", {})
                    self._symbol_last_exit = cs.get("symbol_last_exit", {})
                    self._symbol_entries_today = cs.get("symbol_entries_today", {})
                    self._today_date = cs.get("today_date", "")
            except Exception as e:
                print(f"[TradeManager] Error loading state: {e}")
                self.portfolio = Portfolio()
        else:
            print("[TradeManager] No existing state found. Starting fresh.")

    def save_state(self):
        """Save portfolio state to JSON file."""
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            data = json.loads(self.portfolio.model_dump_json())
            data["_trail_states"] = self._trail_states
            data["iceberg_orders"] = self.iceberg_orders[-100:]  # Keep last 100
            data["_margin_blocked"] = self._margin_blocked
            # GAP-9: persist cooldown state across restarts
            data["_cooldown_state"] = {
                "symbol_last_exit": self._symbol_last_exit,
                "symbol_entries_today": self._symbol_entries_today,
                "today_date": self._today_date,
            }
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[TradeManager] Error saving state: {e}")

    def place_order(self, symbol: str, entry_price: float, target: float, stop_loss: float, 
                    conviction: float, rationale: str = "", quantity: int = 0,
                    trade_type: str = "BUY", leverage: int = 1) -> Optional[Trade]:
        """
        Execute a paper trade order (BUY or SELL/SHORT).
        Allocates ~20k per trade if quantity is not specified.
        For SHORT: margin is blocked same as buy cost (simplified paper trading).
        Uses limit order offset: entry_price already has +0.1% LTP applied by caller.
        Leverage: for intraday (leverage=3), margin blocked = cost / leverage.
        """

        # === SAFETY GATE 1: Time gate — no trades before 9:20 AM IST ===
        now = datetime.now(IST)
        market_start = now.replace(hour=9, minute=20, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
        if now.time() < market_start.time() or now.time() > market_end.time():
            print(f"[TradeManager] ⛔ BLOCKED: Outside trading hours ({now.strftime('%H:%M IST')}). Trades only 9:20-15:15.")
            return None

        # === SAFETY GATE 1b: Reset daily per-symbol counters if new day ===
        today_str = now.strftime("%Y-%m-%d")
        if self._today_date != today_str:
            self._today_date = today_str
            self._symbol_entries_today = {}
            self._symbol_last_exit = {}

        # === SAFETY GATE 1c: Per-symbol cooldown after SL hit ===
        import time as _wall_time
        last_exit_epoch = self._symbol_last_exit.get(symbol, 0)
        if last_exit_epoch > 0:
            elapsed = _wall_time.time() - last_exit_epoch
            if elapsed < SYMBOL_COOLDOWN_SEC:
                remaining = int(SYMBOL_COOLDOWN_SEC - elapsed)
                print(f"[TradeManager] ⛔ BLOCKED: {symbol} cooldown active — {remaining}s remaining after SL hit.")
                return None

        # === SAFETY GATE 1d: Max entries per symbol per day ===
        sym_entries = self._symbol_entries_today.get(symbol, 0)
        if sym_entries >= MAX_ENTRIES_PER_SYMBOL_DAY:
            print(f"[TradeManager] ⛔ BLOCKED: {symbol} already entered {sym_entries} times today (max {MAX_ENTRIES_PER_SYMBOL_DAY}).")
            return None

        # === SAFETY GATE 2: Feedback loop — block symbols with repeated failures ===
        recent_failed = get_failed_trades_for_symbol(symbol)
        recent_losses = [t for t in recent_failed if (t.get("pnl") or 0) < 0]
        if len(recent_losses) >= 3:
            print(f"[TradeManager] ⛔ BLOCKED: {symbol} has {len(recent_losses)} recent failures. Cooling off.")
            return None

        # === SAFETY GATE 3: Minimum conviction filter ===
        MIN_CONVICTION = 45  # GAP-5: Raised from 30 → 45 to filter out weak/ambiguous signals
        if conviction < MIN_CONVICTION:
            print(f"[TradeManager] ⛔ BLOCKED: Conviction {conviction:.1f} < {MIN_CONVICTION} minimum for {symbol}.")
            return None

        # Calculate quantity if not specified — apply 3x intraday leverage
        if quantity <= 0:
            base_qty = int(20000 / entry_price)
            if base_qty < 1:
                base_qty = 1
            quantity = base_qty * INTRADAY_LEVERAGE
            print(f"[TradeManager] 3x leverage: base {base_qty} → qty {quantity} for {symbol}")

        cost = quantity * entry_price

        # Intraday leverage: margin requirement is cost / leverage
        margin_required = cost / max(1, leverage)

        # === SAFETY GATE 4: Max loss per trade (3% of initial capital — avoids death spiral) ===
        MAX_LOSS_PER_TRADE_PCT = 0.03
        max_allowed_loss = MAX_LOSS_PER_TRADE_PCT * INITIAL_CAPITAL
        # Use stop-loss distance as projected max loss
        if trade_type.upper() == "BUY":
            projected_loss = (entry_price - stop_loss) * quantity if stop_loss > 0 else cost * 0.05
        else:
            projected_loss = (stop_loss - entry_price) * quantity if stop_loss > 0 else cost * 0.05
        if projected_loss > max_allowed_loss and projected_loss > 0:
            print(f"[TradeManager] ⛔ BLOCKED: Projected loss ₹{projected_loss:.0f} > max ₹{max_allowed_loss:.0f} for {symbol}.")
            return None

        # === SAFETY GATE 5: Max drawdown protection (don't go below 50% of initial capital) ===
        MAX_DRAWDOWN = 0.50
        floor = INITIAL_CAPITAL * (1 - MAX_DRAWDOWN)
        # Use total portfolio value (cash + unrealized) for drawdown check
        unrealized = sum(
            (t.current_price - t.entry_price) * t.quantity * (1 if t.type == TradeType.BUY else -1)
            for t in self.portfolio.active_trades
            if t.current_price is not None
        )
        total_value = self.portfolio.cash_balance + unrealized
        if (total_value - margin_required) < floor:
            print(f"[TradeManager] ⛔ BLOCKED: Would breach {MAX_DRAWDOWN*100:.0f}% drawdown floor (₹{floor:,.0f}). Portfolio value: ₹{total_value:,.0f}")
            return None

        # === SAFETY GATE 6: Stop-loss sanity check ===
        if trade_type.upper() == "BUY":
            if stop_loss >= entry_price:
                print(f"[TradeManager] ⚠️ Fixing BUY SL: {stop_loss} >= entry {entry_price}. Setting SL to entry * 0.97")
                stop_loss = round(entry_price * 0.97, 2)
            if target <= entry_price:
                print(f"[TradeManager] ⚠️ Fixing BUY target: {target} <= entry {entry_price}. Setting target to entry * 1.03")
                target = round(entry_price * 1.03, 2)
        else:
            if stop_loss <= entry_price:
                print(f"[TradeManager] ⚠️ Fixing SELL SL: {stop_loss} <= entry {entry_price}. Setting SL to entry * 1.03")
                stop_loss = round(entry_price * 1.03, 2)
            if target >= entry_price:
                print(f"[TradeManager] ⚠️ Fixing SELL target: {target} >= entry {entry_price}. Setting target to entry * 0.97")
                target = round(entry_price * 0.97, 2)

        # Final funds check (against margin, not full notional)
        if self.portfolio.cash_balance < margin_required:
            print(f"[TradeManager] Insufficient funds for {symbol}. Margin needed: ₹{margin_required:,.0f} (notional ₹{cost:,.0f}, {leverage}x lev), Available: ₹{self.portfolio.cash_balance:,.0f}")
            return None

        # Deduct margin (margin block for both BUY and SHORT)
        self.portfolio.cash_balance -= margin_required

        t_type = TradeType.SELL if trade_type.upper() == "SELL" else TradeType.BUY

        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=symbol,
            type=t_type,
            status=TradeStatus.OPEN,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(IST),
            target=target,
            stop_loss=stop_loss,
            conviction=conviction,
            rationale_summary=rationale
        )

        # Track margin blocked for this trade (for correct cash return on close)
        self._margin_blocked[trade.id] = margin_required

        self.portfolio.active_trades.append(trade)

        # Track per-symbol entries today
        self._symbol_entries_today[symbol] = self._symbol_entries_today.get(symbol, 0) + 1

        # --- Initialize trailing SL state for this trade ---
        trail_state = TrailingStopLossEngine.create_state(
            entry_price=entry_price,
            initial_sl=stop_loss,
            is_long=(t_type == TradeType.BUY),
        )
        self._trail_states[trade.id] = TrailingStopLossEngine.state_to_dict(trail_state)

        # --- Iceberg order tracking (informational for paper trading) ---
        if quantity > ICEBERG_QTY_THRESHOLD:
            try:
                iceberg = IcebergEngine.create_stock_iceberg(
                    symbol=symbol,
                    trade_type="BUY" if t_type == TradeType.BUY else "SELL",
                    quantity=quantity,
                    price=entry_price,
                )
                self.iceberg_orders.append({
                    "trade_id": trade.id,
                    "symbol": symbol,
                    "total_qty": quantity,
                    "num_slices": len(iceberg.slices),
                    "created_at": datetime.now(IST).isoformat(),
                })
                print(f"[TradeManager] ICEBERG: {symbol} split into {len(iceberg.slices)} slices of ~{iceberg.slices[0].quantity} each")
            except Exception as e:
                print(f"[TradeManager] Iceberg planning skipped for {symbol}: {e}")

        self.save_state()
        print(f"[TradeManager] {t_type.value} EXECUTED: {symbol} @ {entry_price} | Qty: {quantity} (3x lev) | Target: {target} | SL: {stop_loss}")
        return trade

    def close_trade(self, trade_id: str, exit_price: float, reason: str = "Manual"):
        """Close a specific trade (handles both BUY/LONG and SELL/SHORT)."""
        trade = next((t for t in self.portfolio.active_trades if t.id == trade_id), None)
        if not trade:
            return

        cost = trade.quantity * trade.entry_price
        margin = self._margin_blocked.pop(trade.id, cost)  # Default to full cost if leverage unknown

        # Calculate P&L based on trade type
        if trade.type == TradeType.SELL:
            # SHORT: profit when price goes down → P&L = (entry - exit) * qty
            pnl = (trade.entry_price - exit_price) * trade.quantity
        else:
            # LONG/BUY: profit when price goes up → P&L = (exit - entry) * qty
            pnl = (exit_price - trade.entry_price) * trade.quantity

        # Return: margin blocked + P&L
        cash_return = margin + pnl
        pnl_percent = (pnl / cost) * 100 if cost > 0 else 0


        # Update Trade
        trade.status = TradeStatus.CLOSED
        trade.exit_price = exit_price
        trade.exit_time = datetime.now(IST)
        trade.pnl = round(pnl, 2)
        trade.pnl_percent = round(pnl_percent, 2)
        trade.rationale_summary = f"{trade.rationale_summary} | Exit: {reason}" if trade.rationale_summary else f"Exit: {reason}"

        # Log failed trades for model learning (large loss or stop loss hit)
        if pnl < -0.03 * cost or reason.lower().startswith("stop loss") or reason.lower().startswith("intraday square-off"):
            log_failed_trade(trade, reason)

        # ── Per-symbol cooldown: record exit time on SL/trailing SL exits ──
        if pnl < 0 and ("sl" in reason.lower() or "stop" in reason.lower() or "trailing" in reason.lower()):
            import time as _wall_time
            self._symbol_last_exit[trade.symbol] = _wall_time.time()
            print(f"[TradeManager] Cooldown set for {trade.symbol}: {SYMBOL_COOLDOWN_SEC}s after SL hit")

        # Update Portfolio
        self.portfolio.cash_balance += cash_return
        self.portfolio.realized_pnl += pnl
        self.portfolio.active_trades.remove(trade)
        self.portfolio.trade_history.append(trade)

        # Cleanup trailing SL state
        self._trail_states.pop(trade.id, None)

        # v2: Record in risk engine + metrics + learning
        equity_risk_engine.record_trade_result(pnl)
        equity_risk_engine.remove_trade(trade.id)

        # v2: Metrics recording
        risk_state = equity_risk_engine.get_trade_state(trade.id)
        mfe_val = risk_state.mfe if risk_state else 0
        mae_val = risk_state.mae if risk_state else 0

        equity_metrics.record_trade(TradeMetrics(
            trade_id=trade.id,
            regime=getattr(trade, '_regime', ''),
            profile_id=getattr(trade, '_profile_id', ''),
            breakout_level=getattr(trade, '_breakout_level', 0),
            entry_mode=getattr(trade, '_entry_mode', ''),
            pnl=pnl,
            pnl_pct=pnl_percent,
            mfe=mfe_val,
            mae=mae_val,
            spread_cost=0,
            slippage_cost=0,
            entry_time=trade.entry_time.isoformat() if trade.entry_time else "",
            exit_time=trade.exit_time.isoformat() if trade.exit_time else "",
            hold_seconds=(trade.exit_time - trade.entry_time).total_seconds() if trade.exit_time and trade.entry_time else 0,
            exit_reason=reason,
        ))

        # v2: Learning engine update
        capture = pnl / mfe_val if mfe_val > 0 and pnl > 0 else 0
        equity_learning.record_trade_result(
            profile_id=getattr(trade, '_profile_id', 'P3_MID_TREND'),
            pnl=pnl,
            drawdown=mae_val,
            regime=getattr(trade, '_regime', ''),
            mfe_capture=capture,
        )

        self.save_state()
        side_label = "SHORT" if trade.type == TradeType.SELL else "LONG"
        print(f"[TradeManager] CLOSED {side_label} {trade.symbol} @ {exit_price}. P&L: {pnl:.2f} ({pnl_percent:.1f}%) | Reason: {reason}")

    def update_prices(self, price_map: Dict[str, float]):
        """
        Update live prices and check for exits.
        Handles both LONG (BUY) and SHORT (SELL) positions.
        price_map: { "RELIANCE": 2405.00, ... }
        """
        import math
        for trade in list(self.portfolio.active_trades):
            current_price = price_map.get(trade.symbol)
            if current_price is None or (isinstance(current_price, float) and math.isnan(current_price)):
                continue

            hit_target = False
            hit_sl = False

            if trade.type == TradeType.SELL:
                # SHORT: target is BELOW entry, SL is ABOVE entry
                hit_target = current_price <= trade.target
                hit_sl = current_price >= trade.stop_loss
            else:
                # LONG/BUY: target is ABOVE entry, SL is BELOW entry
                hit_target = current_price >= trade.target
                hit_sl = current_price <= trade.stop_loss

            if hit_target:
                self.close_trade(trade.id, current_price, reason="Target Hit")
            elif hit_sl:
                self.close_trade(trade.id, current_price, reason="Trailing SL Hit")
            else:
                # --- Trailing SL: dynamically adjust stop loss ---
                trail_dict = self._trail_states.get(trade.id)
                if trail_dict:
                    trail_state = TrailingStopLossEngine.state_from_dict(trail_dict)
                    new_sl = TrailingStopLossEngine.compute_new_sl(
                        config=self._trail_config,
                        state=trail_state,
                        current_price=current_price,
                    )
                    if new_sl and new_sl != trade.stop_loss:
                        old_sl = trade.stop_loss
                        trade.stop_loss = round(new_sl, 2)
                        self._trail_states[trade.id] = TrailingStopLossEngine.state_to_dict(trail_state)
                        side = "SHORT" if trade.type == TradeType.SELL else "LONG"
                        print(f"[TradeManager] TRAIL SL {side} {trade.symbol}: {old_sl} → {new_sl:.2f} (price: {current_price})")

                # Update unrealized P&L
                trade.current_price = current_price
                cost_value = trade.quantity * trade.entry_price
                if trade.type == TradeType.SELL:
                    trade.pnl = round((trade.entry_price - current_price) * trade.quantity, 2)
                else:
                    trade.pnl = round((current_price - trade.entry_price) * trade.quantity, 2)
                trade.pnl_percent = round((trade.pnl / cost_value) * 100, 2) if cost_value > 0 else 0
        
        # Save state to persist price updates
        self.save_state()

    def close_all_positions(self, price_map: Dict[str, float]):
        """Intraday auto-square off at 3:15 PM.
        Uses price_map first, then trade.current_price, then entry_price as last resort.
        """
        for trade in list(self.portfolio.active_trades):
            exit_price = price_map.get(trade.symbol)
            if not exit_price or exit_price <= 0:
                # Use last monitored price (updated every 5s by price_monitor_loop)
                exit_price = trade.current_price if trade.current_price and trade.current_price > 0 else None
            if not exit_price or exit_price <= 0:
                # Absolute last resort
                exit_price = trade.entry_price
                print(f"[TradeManager] ⚠️ No live price for {trade.symbol} — using entry price for square-off")
            self.close_trade(trade.id, exit_price, reason="Intraday Square-off")

    def find_trade_by_symbol(self, symbol: str) -> Optional[Trade]:
        """Find an active trade by symbol."""
        return next((t for t in self.portfolio.active_trades if t.symbol == symbol), None)

    def update_stop_loss(self, trade_id: str, new_sl: float) -> bool:
        """Update the stop-loss of an active trade (for trailing SL)."""
        trade = next((t for t in self.portfolio.active_trades if t.id == trade_id), None)
        if not trade:
            return False
        old_sl = trade.stop_loss
        trade.stop_loss = round(new_sl, 2)
        self.save_state()
        side = "SHORT" if trade.type == TradeType.SELL else "LONG"
        print(f"[TradeManager] TRAILING SL {side} {trade.symbol}: {old_sl} → {new_sl:.2f}")
        return True

    def close_by_symbol(self, symbol: str, exit_price: float, reason: str = "Trend Reversal") -> bool:
        """Close all active trades for a given symbol."""
        trades = [t for t in self.portfolio.active_trades if t.symbol == symbol]
        if not trades:
            return False
        for trade in trades:
            self.close_trade(trade.id, exit_price, reason=reason)
        return True

    def get_portfolio_summary(self):
        """Return full portfolio state with current Unrealized P&L calculation."""
        return self.portfolio

    def get_trailing_sl_status(self) -> dict:
        """Return trailing SL state for all active trades."""
        result = {}
        for trade in self.portfolio.active_trades:
            trail_dict = self._trail_states.get(trade.id)
            result[trade.symbol] = {
                "trade_id": trade.id,
                "current_sl": trade.stop_loss,
                "entry_price": trade.entry_price,
                "trail_state": trail_dict,
            }
        return result

    def get_iceberg_history(self) -> list:
        """Return iceberg order history."""
        return self.iceberg_orders

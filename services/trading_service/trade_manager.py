
import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional
import uuid
import pytz

# Fix path to import shared models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.models import Trade, TradeType, TradeStatus, Portfolio
from shared.trailing_sl import TrailingStopLossEngine, TrailConfig, TrailState, TrailStrategy
from shared.iceberg_order import IcebergEngine
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

class TradeManager:
    def __init__(self):
        self.portfolio = Portfolio()
        # Trailing SL states per trade
        self._trail_states: Dict[str, dict] = {}
        self._trail_config = TrailConfig(
            strategy=TrailStrategy.HYBRID,
            trail_pct=0.5,
            activation_pct=0.3,
            step_size_pct=0.5,
            step_lock_pct=0.3,
            breakeven_trigger_pct=0.5,
            min_trail_pct=0.2,
        )
        # Iceberg order history
        self.iceberg_orders: list = []
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
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[TradeManager] Error saving state: {e}")

    def place_order(self, symbol: str, entry_price: float, target: float, stop_loss: float, 
                    conviction: float, rationale: str = "", quantity: int = 0,
                    trade_type: str = "BUY") -> Optional[Trade]:
        """
        Execute a paper trade order (BUY or SELL/SHORT).
        Allocates ~20k per trade if quantity is not specified.
        For SHORT: margin is blocked same as buy cost (simplified paper trading).
        Uses limit order offset: entry_price already has +0.1% LTP applied by caller.
        """

        # === SAFETY GATE 1: Time gate — no trades before 9:20 AM IST ===
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        market_start = now.replace(hour=9, minute=20, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
        if now.time() < market_start.time() or now.time() > market_end.time():
            print(f"[TradeManager] ⛔ BLOCKED: Outside trading hours ({now.strftime('%H:%M IST')}). Trades only 9:20-15:15.")
            return None

        # === SAFETY GATE 2: Feedback loop — block symbols with repeated failures ===
        recent_failed = get_failed_trades_for_symbol(symbol)
        recent_losses = [t for t in recent_failed if (t.get("pnl") or 0) < 0]
        if len(recent_losses) >= 3:
            print(f"[TradeManager] ⛔ BLOCKED: {symbol} has {len(recent_losses)} recent failures. Cooling off.")
            return None

        # === SAFETY GATE 3: Minimum conviction filter ===
        MIN_CONVICTION = 30  # Don't trade on weak signals
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

        # === SAFETY GATE 4: Max loss per trade (3% of current capital) ===
        MAX_LOSS_PER_TRADE_PCT = 0.03
        max_allowed_loss = MAX_LOSS_PER_TRADE_PCT * self.portfolio.cash_balance
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
        if (self.portfolio.cash_balance - cost) < floor:
            print(f"[TradeManager] ⛔ BLOCKED: Would breach {MAX_DRAWDOWN*100:.0f}% drawdown floor (₹{floor:,.0f}).")
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

        # Final funds check
        if self.portfolio.cash_balance < cost:
            print(f"[TradeManager] Insufficient funds for {symbol}. Needed: ₹{cost:,.0f}, Available: ₹{self.portfolio.cash_balance:,.0f}")
            return None

        # Deduct cash (margin block for both BUY and SHORT)
        self.portfolio.cash_balance -= cost

        t_type = TradeType.SELL if trade_type.upper() == "SELL" else TradeType.BUY

        # Create trade
        ist = pytz.timezone("Asia/Kolkata")
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=symbol,
            type=t_type,
            status=TradeStatus.OPEN,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(ist),
            target=target,
            stop_loss=stop_loss,
            conviction=conviction,
            rationale_summary=rationale
        )

        self.portfolio.active_trades.append(trade)

        # --- Initialize trailing SL state for this trade ---
        trail_state = TrailingStopLossEngine.create_state(
            entry_price=entry_price,
            initial_sl=stop_loss,
            is_long=(t_type == TradeType.BUY),
        )
        self._trail_states[trade.id] = TrailingStopLossEngine.state_to_dict(trail_state)

        # --- Iceberg order tracking (informational for paper trading) ---
        if quantity > ICEBERG_QTY_THRESHOLD:
            iceberg = IcebergEngine.create_stock_iceberg(
                symbol=symbol,
                side="BUY" if t_type == TradeType.BUY else "SELL",
                total_qty=quantity,
                price=entry_price,
            )
            self.iceberg_orders.append({
                "trade_id": trade.id,
                "symbol": symbol,
                "total_qty": quantity,
                "num_slices": len(iceberg.slices),
                "created_at": datetime.now(ist).isoformat(),
            })
            print(f"[TradeManager] ICEBERG: {symbol} split into {len(iceberg.slices)} slices of ~{iceberg.slices[0].quantity} each")

        self.save_state()
        print(f"[TradeManager] {t_type.value} EXECUTED: {symbol} @ {entry_price} | Qty: {quantity} (3x lev) | Target: {target} | SL: {stop_loss}")
        return trade

    def close_trade(self, trade_id: str, exit_price: float, reason: str = "Manual"):
        """Close a specific trade (handles both BUY/LONG and SELL/SHORT)."""
        trade = next((t for t in self.portfolio.active_trades if t.id == trade_id), None)
        if not trade:
            return

        cost = trade.quantity * trade.entry_price

        # Calculate P&L based on trade type
        if trade.type == TradeType.SELL:
            # SHORT: profit when price goes down → P&L = (entry - exit) * qty
            pnl = (trade.entry_price - exit_price) * trade.quantity
            # Return the original margin + profit (or - loss)
            cash_return = cost + pnl
        else:
            # LONG/BUY: profit when price goes up → P&L = (exit - entry) * qty
            pnl = (exit_price - trade.entry_price) * trade.quantity
            cash_return = trade.quantity * exit_price

        pnl_percent = (pnl / cost) * 100 if cost > 0 else 0


        # Update Trade
        trade.status = TradeStatus.CLOSED
        trade.exit_price = exit_price
        ist = pytz.timezone("Asia/Kolkata")
        trade.exit_time = datetime.now(ist)
        trade.pnl = round(pnl, 2)
        trade.pnl_percent = round(pnl_percent, 2)
        trade.rationale_summary = f"{trade.rationale_summary} | Exit: {reason}" if trade.rationale_summary else f"Exit: {reason}"

        # Log failed trades for model learning (large loss or stop loss hit)
        if pnl < -0.03 * cost or reason.lower().startswith("stop loss") or reason.lower().startswith("intraday square-off"):
            log_failed_trade(trade, reason)

        # Update Portfolio
        self.portfolio.cash_balance += cash_return
        self.portfolio.realized_pnl += pnl
        self.portfolio.active_trades.remove(trade)
        self.portfolio.trade_history.append(trade)

        # Cleanup trailing SL state
        self._trail_states.pop(trade.id, None)

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

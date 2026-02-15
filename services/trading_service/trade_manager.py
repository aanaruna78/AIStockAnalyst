import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional
import uuid

# Fix path to import shared models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.models import Trade, TradeType, TradeStatus, Portfolio

# Robust path for data file — prefer env var, then /app/data (Docker), then local fallback
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.environ.get(
    "PAPER_TRADES_FILE",
    os.path.join(BASE_DIR, "data", "paper_trades.json")
)

INITIAL_CAPITAL = 100000.0  # ₹1,00,000 starting capital for paper trading

class TradeManager:
    def __init__(self):
        self.portfolio = Portfolio()
        self.load_state()

    def load_state(self):
        """Load portfolio state from JSON file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    # Convert dicts back to Pydantic models
                    self.portfolio = Portfolio(**data)
            except Exception as e:
                print(f"[TradeManager] Error loading state: {e}")
                self.portfolio = Portfolio()
        else:
            print("[TradeManager] No existing state found. Starting fresh.")

    def save_state(self):
        """Save portfolio state to JSON file."""
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w") as f:
                f.write(self.portfolio.model_dump_json(indent=2))
        except Exception as e:
            print(f"[TradeManager] Error saving state: {e}")

    def place_order(self, symbol: str, entry_price: float, target: float, stop_loss: float, 
                    conviction: float, rationale: str = "", quantity: int = 0,
                    trade_type: str = "BUY") -> Optional[Trade]:
        """
        Execute a paper trade order (BUY or SELL/SHORT).
        Allocates ~20k per trade if quantity is not specified.
        For SHORT: margin is blocked same as buy cost (simplified paper trading).
        """
        if quantity <= 0:
            quantity = int(20000 / entry_price)
            if quantity < 1:
                quantity = 1  # Minimum 1 share

        cost = quantity * entry_price
        if self.portfolio.cash_balance < cost:
            print(f"[TradeManager] Insufficient funds for {symbol}. Needed: {cost}, Available: {self.portfolio.cash_balance}")
            return None

        # Deduct cash (margin block for both BUY and SHORT)
        self.portfolio.cash_balance -= cost

        t_type = TradeType.SELL if trade_type.upper() == "SELL" else TradeType.BUY

        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=symbol,
            type=t_type,
            status=TradeStatus.OPEN,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(),
            target=target,
            stop_loss=stop_loss,
            conviction=conviction,
            rationale_summary=rationale
        )

        self.portfolio.active_trades.append(trade)
        self.save_state()
        print(f"[TradeManager] {t_type.value} EXECUTED: {symbol} @ {entry_price} | Qty: {quantity} | Target: {target} | SL: {stop_loss}")
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
        trade.exit_time = datetime.now()
        trade.pnl = round(pnl, 2)
        trade.pnl_percent = round(pnl_percent, 2)
        trade.rationale_summary = f"{trade.rationale_summary} | Exit: {reason}" if trade.rationale_summary else f"Exit: {reason}"

        # Update Portfolio
        self.portfolio.cash_balance += cash_return
        self.portfolio.realized_pnl += pnl
        self.portfolio.active_trades.remove(trade)
        self.portfolio.trade_history.append(trade)
        
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
                self.close_trade(trade.id, current_price, reason="Stop Loss Hit")
            else:
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

    def get_portfolio_summary(self):
        """Return full portfolio state with current Unrealized P&L calculation."""
        # Note: In a real app, we'd fetch live prices here too, but for now we rely on the last pushed state
        return self.portfolio

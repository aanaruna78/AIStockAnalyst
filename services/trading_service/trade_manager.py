import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
import uuid

# Fix path to import shared models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.models import Trade, TradeType, TradeStatus, Portfolio

DATA_FILE = "../../data/paper_trades.json"

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
                    conviction: float, rationale: str = "", quantity: int = 0) -> Optional[Trade]:
        """
        Execute a paper buy order.
        Allocates ~20k per trade if quantity is not specified.
        """
        if quantity <= 0:
            quantity = int(20000 / entry_price)
            if quantity < 1:
                quantity = 1  # Minimum 1 share

        cost = quantity * entry_price
        if self.portfolio.cash_balance < cost:
            print(f"[TradeManager] Insufficient funds for {symbol}. Needed: {cost}, Available: {self.portfolio.cash_balance}")
            return None

        # Deduct cash
        self.portfolio.cash_balance -= cost

        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=symbol,
            type=TradeType.BUY,
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
        print(f"[TradeManager] BUY EXECUTED: {symbol} @ {entry_price} | Qty: {quantity}")
        return trade

    def close_trade(self, trade_id: str, exit_price: float, reason: str = "Manual"):
        """Close a specific trade."""
        trade = next((t for t in self.portfolio.active_trades if t.id == trade_id), None)
        if not trade:
            return

        # Calculate P&L
        revenue = trade.quantity * exit_price
        cost = trade.quantity * trade.entry_price
        pnl = revenue - cost
        pnl_percent = (pnl / cost) * 100

        # Update Trade
        trade.status = TradeStatus.CLOSED
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.pnl = round(pnl, 2)
        trade.pnl_percent = round(pnl_percent, 2)
        trade.rationale_summary = f"{trade.rationale_summary} | Exit: {reason}" if trade.rationale_summary else f"Exit: {reason}"

        # Update Portfolio
        self.portfolio.cash_balance += revenue
        self.portfolio.realized_pnl += pnl
        self.portfolio.active_trades.remove(trade)
        self.portfolio.trade_history.append(trade)
        
        self.save_state()
        print(f"[TradeManager] CLOSED {trade.symbol} @ {exit_price}. P&L: {pnl:.2f} ({pnl_percent:.1f}%) | Reason: {reason}")

    def update_prices(self, price_map: Dict[str, float]):
        """
        Update live prices and check for exits.
        price_map: { "RELIANCE": 2405.00, ... }
        """
        for trade in list(self.portfolio.active_trades):
            current_price = price_map.get(trade.symbol)
            if not current_price:
                continue

            # Check Target
            if current_price >= trade.target:
                self.close_trade(trade.id, current_price, reason="Target Hit")
            
            # Check Stop Loss
            elif current_price <= trade.stop_loss:
                self.close_trade(trade.id, current_price, reason="Stop Loss Hit")
            
            else:
                # Update unrealized P&L
                trade.current_price = current_price
                market_value = trade.quantity * current_price
                cost_value = trade.quantity * trade.entry_price
                trade.pnl = round(market_value - cost_value, 2)
                trade.pnl_percent = round((trade.pnl / cost_value) * 100, 2)
        
        # Save state to persist price updates
        self.save_state()

    def close_all_positions(self, price_map: Dict[str, float]):
        """Intraday auto-square off at 3:15 PM"""
        for trade in list(self.portfolio.active_trades):
            exit_price = price_map.get(trade.symbol, trade.entry_price) # Fallback to entry if no live data
            self.close_trade(trade.id, exit_price, reason="Intraday Square-off")

    def get_portfolio_summary(self):
        """Return full portfolio state with current Unrealized P&L calculation."""
        # Note: In a real app, we'd fetch live prices here too, but for now we rely on the last pushed state
        return self.portfolio

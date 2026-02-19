"""
Persistent failed trade log for model learning and analysis.
Stores failed trades to a JSON file so they survive service restarts.
Each entry contains trade details, failure reason, and timestamp.
"""

import json
import os
from datetime import datetime

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAILED_TRADES_FILE = os.environ.get(
    "FAILED_TRADES_FILE",
    os.path.join(BASE_DIR, "data", "failed_trades.json")
)


def _load_failed_trades():
    """Load failed trades from disk."""
    if os.path.exists(FAILED_TRADES_FILE):
        try:
            with open(FAILED_TRADES_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[FailedTradeLog] Error loading: {e}")
    return []


def _save_failed_trades(trades):
    """Persist failed trades to disk."""
    try:
        os.makedirs(os.path.dirname(FAILED_TRADES_FILE), exist_ok=True)
        with open(FAILED_TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=2, default=str)
    except Exception as e:
        print(f"[FailedTradeLog] Error saving: {e}")


def log_failed_trade(trade, reason):
    """Log a failed trade with all details for model analysis."""
    trades = _load_failed_trades()
    entry = {
        "id": trade.id,
        "symbol": trade.symbol,
        "type": trade.type.value if hasattr(trade.type, "value") else str(trade.type),
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "quantity": trade.quantity,
        "entry_time": str(trade.entry_time),
        "exit_time": str(trade.exit_time),
        "pnl": trade.pnl,
        "pnl_percent": trade.pnl_percent,
        "conviction": trade.conviction,
        "target": trade.target,
        "stop_loss": trade.stop_loss,
        "rationale_summary": trade.rationale_summary,
        "reason": reason,
        "logged_at": datetime.now(IST).isoformat(),
    }
    trades.append(entry)
    _save_failed_trades(trades)
    print(f"[FailedTradeLog] Logged: {trade.symbol} | {reason} | P&L: {trade.pnl}")


def get_failed_trades():
    """Return all failed trades from persistent storage."""
    return _load_failed_trades()


def get_failed_trades_for_symbol(symbol):
    """Return failed trades for a specific symbol."""
    return [t for t in _load_failed_trades() if t.get("symbol") == symbol]


def get_failed_trades_today():
    """Return failed trades logged today (IST)."""
    today = datetime.now(IST).date()
    result = []
    for t in _load_failed_trades():
        try:
            logged = t.get("logged_at") or t.get("exit_time", "")
            if logged and datetime.fromisoformat(str(logged)).date() == today:
                result.append(t)
        except Exception:
            pass
    return result


def get_trade_failure_stats():
    """Return aggregate stats for model learning."""
    trades = _load_failed_trades()
    if not trades:
        return {"total": 0, "by_symbol": {}, "by_reason": {}, "avg_loss": 0}

    by_symbol = {}
    by_reason = {}
    total_loss = 0
    for t in trades:
        sym = t.get("symbol", "UNKNOWN")
        reason = t.get("reason", "Unknown")
        pnl = t.get("pnl", 0) or 0

        by_symbol[sym] = by_symbol.get(sym, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
        total_loss += pnl

    return {
        "total": len(trades),
        "by_symbol": by_symbol,
        "by_reason": by_reason,
        "avg_loss": round(total_loss / len(trades), 2) if trades else 0,
        "total_loss": round(total_loss, 2),
        "worst_symbols": sorted(by_symbol.items(), key=lambda x: -x[1])[:5],
    }

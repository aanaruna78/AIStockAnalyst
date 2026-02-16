"""
Model Daily Performance Report Generator.
Produces daily win/loss reports, tracks trade outcomes over time,
and provides data for the admin UI feedback loop.
"""

import json
import os
from datetime import datetime
import pytz

from failed_trade_log import get_failed_trades, get_failed_trades_today, get_trade_failure_stats

IST = pytz.timezone("Asia/Kolkata")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_FILE = os.environ.get(
    "MODEL_REPORT_FILE",
    os.path.join(BASE_DIR, "data", "model_daily_report.json")
)
FEEDBACK_FILE = os.environ.get(
    "MODEL_FEEDBACK_FILE",
    os.path.join(BASE_DIR, "data", "model_feedback.json")
)


def generate_daily_report(trade_history):
    """Generate a daily report from trade history. Called from main.py which has access to TradeManager."""
    today = datetime.now(IST).date()

    successes = []
    misses = []
    for trade in trade_history:
        try:
            exit_str = str(trade.exit_time) if trade.exit_time else ""
            if not exit_str:
                continue
            exit_date = datetime.fromisoformat(exit_str).date()
            if exit_date == today:
                if trade.pnl and trade.pnl > 0:
                    successes.append({
                        "id": trade.id,
                        "symbol": trade.symbol,
                        "type": trade.type.value if hasattr(trade.type, "value") else str(trade.type),
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "pnl": trade.pnl,
                        "pnl_percent": trade.pnl_percent,
                        "conviction": trade.conviction,
                    })
                else:
                    misses.append({
                        "id": trade.id,
                        "symbol": trade.symbol,
                        "type": trade.type.value if hasattr(trade.type, "value") else str(trade.type),
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "pnl": trade.pnl,
                        "pnl_percent": trade.pnl_percent,
                        "conviction": trade.conviction,
                        "rationale_summary": trade.rationale_summary,
                    })
        except Exception as e:
            print(f"[ModelReport] Skipping trade: {e}")

    failed_today = get_failed_trades_today()
    failure_stats = get_trade_failure_stats()

    total_pnl = sum(t["pnl"] for t in successes) + sum(t["pnl"] for t in misses)
    win_rate = round(len(successes) / (len(successes) + len(misses)) * 100, 1) if (successes or misses) else 0

    report = {
        "date": str(today),
        "generated_at": datetime.now(IST).isoformat(),
        "summary": {
            "total_trades": len(successes) + len(misses),
            "wins": len(successes),
            "losses": len(misses),
            "win_rate": win_rate,
            "total_pnl": round(total_pnl, 2),
        },
        "success_trades": successes,
        "miss_trades": misses,
        "failed_trades_today": failed_today,
        "failure_stats": failure_stats,
    }

    try:
        os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
        with open(REPORT_FILE, "w") as f:
            json.dump(report, f, indent=2, default=str)
    except Exception as e:
        print(f"[ModelReport] Error saving report: {e}")

    return report


def get_daily_report():
    """Load the last generated daily report."""
    if os.path.exists(REPORT_FILE):
        try:
            with open(REPORT_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "date": str(datetime.now(IST).date()),
        "summary": {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0},
        "success_trades": [],
        "miss_trades": [],
        "failed_trades_today": [],
        "failure_stats": {"total": 0},
    }


def save_feedback(feedback_text, category="general"):
    """Save admin feedback for model improvement."""
    feedbacks = []
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r") as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []

    feedbacks.append({
        "timestamp": datetime.now(IST).isoformat(),
        "feedback": feedback_text,
        "category": category,
    })

    try:
        os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(feedbacks, f, indent=2)
    except Exception as e:
        print(f"[ModelReport] Error saving feedback: {e}")

    return {"status": "saved", "total_feedbacks": len(feedbacks)}


def get_all_feedback():
    """Return all stored feedback."""
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

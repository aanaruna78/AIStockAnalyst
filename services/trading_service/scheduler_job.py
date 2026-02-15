from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import httpx
import os
import sys
from datetime import datetime
import pytz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.config import settings

# API Gateway URL
API_GATEWAY_URL = f"{settings.API_GATEWAY_URL}/api/v1"
TRADING_SERVICE_URL = settings.TRADING_SERVICE_URL

# IST timezone for market hours
IST = pytz.timezone("Asia/Kolkata")

scheduler = AsyncIOScheduler(timezone=IST)

def is_market_day():
    """Check if today is a market working day (Mon-Fri, not a known holiday)."""
    now = datetime.now(IST)
    # Weekday check (0=Mon, 4=Fri)
    if now.weekday() > 4:
        print(f"[Scheduler] Skipping — weekend ({now.strftime('%A')})")
        return False
    return True

async def trigger_daily_scan():
    """Trigger the morning scan at 9:15 AM IST"""
    if not is_market_day():
        return
    print("[Scheduler] ⏰ 9:15 AM IST - Triggering Daily Scan...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{API_GATEWAY_URL}/crawl", timeout=600)
            print(f"[Scheduler] Scan Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger scan: {e}")

async def auto_square_off():
    """Close all positions at 3:15 PM IST"""
    if not is_market_day():
        return
    print("[Scheduler] ⏰ 3:15 PM IST - Auto Square Off...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/close-all")
            print(f"[Scheduler] Square Off Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger square off: {e}")

async def execute_trades_job():
    """Execute trades at 9:20 AM IST (5 mins after scan)"""
    if not is_market_day():
        return
    print("[Scheduler] ⏰ 9:20 AM IST - Executing Trades...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/execute-signals")
            print(f"[Scheduler] Auto-Entry Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger auto-entry: {e}")

def start_scheduler():
    # 9:15 AM IST - Morning Scan (Mon-Fri)
    scheduler.add_job(trigger_daily_scan, CronTrigger(hour=9, minute=15, day_of_week='mon-fri', timezone=IST))
    
    # 9:20 AM - 9:50 AM IST - Execute Trades (Every 5 mins, Mon-Fri)
    scheduler.add_job(execute_trades_job, CronTrigger(hour=9, minute='20-50/5', day_of_week='mon-fri', timezone=IST))
    
    # 3:15 PM - 3:28 PM IST - Square Off (Every 2 mins, Mon-Fri)
    scheduler.add_job(auto_square_off, CronTrigger(hour=15, minute='15-28/2', day_of_week='mon-fri', timezone=IST))
    
    scheduler.start()
    print("[Scheduler] 📅 Scheduler Started (IST, Mon-Fri only)")
    print("[Scheduler]   9:15 AM  → Scan")
    print("[Scheduler]   9:20-9:50 AM → Auto-Entry (every 5m)")
    print("[Scheduler]   3:15-3:28 PM → Auto Square-off (every 2m)")

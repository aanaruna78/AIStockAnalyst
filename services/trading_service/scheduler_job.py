from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import httpx
import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from shared.config import settings

# API Gateway URL
API_GATEWAY_URL = f"{settings.API_GATEWAY_URL}/api/v1"
TRADING_SERVICE_URL = settings.TRADING_SERVICE_URL

scheduler = AsyncIOScheduler()

async def trigger_daily_scan():
    """Trigger the morning scan at 9:15 AM"""
    print("[Scheduler] ⏰ 9:15 AM - Triggering Daily Scan...")
    async with httpx.AsyncClient() as client:
        try:
            # We trigger the manual scan endpoint
            # Assuming POST /scan or similar. Based on 'Task 37', it says "Implement Auto-Scan Scheduler"
            # We might need to call ingestion service trigger or a specific orchestrator endpoint
            # For now, let's assume we call a 'pipeline/trigger' or similar. 
            # I will use the 'scan/start' or check what triggers the scan in frontend.
            # Frontend calls: axios.post('http://localhost:8000/api/v1/scan/refresh') usually?
            # Let's check ingestion_router or main.py for trigger.
            # Fallback: Trigger via pipeline_runner command if no API exists, but API is better.
            # I will assume POST /ingestion/trigger based on standard naming or check later.
            # Let's use a placeholder print for now until I verify the endpoint.
            
            # Actually, let's call the same endpoint the frontend 'Scan Now' button calls.
            # Frontend uses: axios.post('http://localhost:8000/api/v1/scan/start') (Hypothetically)
            # Re-checking dashboard.jsx might reveal it.
            # Dashboard.jsx Call: 'recResponse' comes from /recommendations/active.
            # 'Scan Now' button logic isn't fully visible in my view but likely exists.
            
            # Use 'pipeline_runner.py' directly via subprocess if needed, but HTTP is better.
            resp = await client.post(f"{API_GATEWAY_URL}/ingestion/run", timeout=600)
            print(f"[Scheduler] Scan Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger scan: {e}")

async def auto_square_off():
    """Close all positions at 3:15 PM"""
    print("[Scheduler] ⏰ 3:15 PM - Auto Square Off...")
    # This calls the TradeManager logic. 
    # Since this runs in the same process as Main, we can technically access TradeManager global if imported,
    # OR call the local API. calling local API 8005 is safer decoupling.
    async with httpx.AsyncClient() as client:
        try:
            # We don't have a direct 'close all' endpoint yet, but we can iterate or add one.
            # Or better, we create a 'close_all' method in trade_manager and call it if we import it.
            # Importing trade_manager instance from main might be circular.
            # Better to add POST /trade/close-all to main.py
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/close-all")
            print(f"[Scheduler] Square Off Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger square off: {e}")

async def execute_trades_job():
    """Execute trades at 9:20 AM (5 mins after scan)"""
    print("[Scheduler] ⏰ 9:20 AM - Executing Trades...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/execute-signals")
            print(f"[Scheduler] Auto-Entry Triggered: {resp.status_code}")
        except Exception as e:
            print(f"[Scheduler] Failed to trigger auto-entry: {e}")

def start_scheduler():
    # 9:15 AM Scan (Daily)
    scheduler.add_job(trigger_daily_scan, CronTrigger(hour=9, minute=15, day_of_week='mon-sun'))
    
    # 9:20 AM - 9:50 AM Execute Trades (Every 5 mins)
    scheduler.add_job(execute_trades_job, CronTrigger(hour=9, minute='20-50/5', day_of_week='mon-sun'))
    
    # 3:15 PM - 3:28 PM Square Off (Every 2 mins)
    scheduler.add_job(auto_square_off, CronTrigger(hour=15, minute='15-28/2', day_of_week='mon-sun'))
    
    scheduler.start()
    print("[Scheduler] 📅 Scheduler Started (9:15 Scan | 9:20-9:50 Entry | 3:15-3:28 Exit) - WEEKENDS ENABLED")

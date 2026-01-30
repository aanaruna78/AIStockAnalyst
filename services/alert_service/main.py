from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from price_watcher import price_watcher
from notifications import notification_manager
import logging

app = FastAPI(title="SignalForge Alert & Notification Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlertService")

class PriceCheckRequest(BaseModel):
    recommendation: Dict[str, Any]
    current_price: float

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/check")
async def check_price_levels(request: PriceCheckRequest):
    """
    Check if a recommendation's levels have been hit and trigger notification.
    """
    alert = price_watcher.check_levels(request.recommendation, request.current_price)
    
    if alert:
        logged_alert = notification_manager.log_alert(alert)
        logger.info(f"Alert triggered: {logged_alert['message']}")
        return {"alert_triggered": True, "alert": logged_alert}
        
    return {"alert_triggered": False}

@app.get("/history")
async def get_alert_history():
    """
    Get in-app notification history.
    """
    return notification_manager.history

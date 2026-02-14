from typing import Optional
import httpx
from fastapi import APIRouter, Depends
from shared.config import settings
from auth_router import oauth2_scheme

router = APIRouter(prefix="/alerts", tags=["alerts"])

ALERT_SERVICE_URL = settings.ALERT_SERVICE_URL


@router.get("/active")
async def get_active_alerts(token: Optional[str] = Depends(oauth2_scheme)):
    """
    Get active alerts (proxies to alert-service /history).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ALERT_SERVICE_URL}/history")
            alerts = response.json()
            # Normalize to list
            if isinstance(alerts, list):
                return alerts
            return []
    except Exception:
        return []


@router.post("/check")
async def check_price_alert(data: dict):
    """
    Check if price levels have been hit (proxies to alert-service /check).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{ALERT_SERVICE_URL}/check", json=data)
            return response.json()
    except Exception:
        return {"alert_triggered": False, "error": "Alert service unavailable"}

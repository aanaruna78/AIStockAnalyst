from fastapi import APIRouter, HTTPException, Request
import httpx
from shared.config import settings

TRADING_SERVICE_URL = settings.TRADING_SERVICE_URL

router = APIRouter(prefix="/trading", tags=["trading"])

@router.get("/portfolio")
async def get_portfolio():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/portfolio")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/trade/manual")
async def place_manual_order(request: Request):
    # Proxy the JSON body directly
    try:
        body = await request.json()
    except Exception:
        body = {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/manual", params=request.query_params, json=body)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/trade/close/{trade_id}")
async def close_trade(trade_id: str, price: float):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/trade/close/{trade_id}", params={"price": price})
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/portfolio/reset")
async def reset_portfolio():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/portfolio/reset")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/portfolio/clear-history")
async def clear_trade_history():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/portfolio/clear-history")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")


# ─── Model Performance Report & Feedback (Admin) ───────────────

@router.get("/model/report")
async def get_model_report():
    """Get today's model performance report (generates fresh)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/model/report", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.get("/model/failed-trades")
async def get_failed_trades():
    """Get all failed trades with stats."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/model/failed-trades", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/model/feedback")
async def submit_model_feedback(request: Request):
    """Submit admin feedback for model improvement."""
    body = await request.json()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{TRADING_SERVICE_URL}/model/feedback", json=body, timeout=10)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.get("/model/feedback")
async def get_model_feedback():
    """Get all stored feedback."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/model/feedback", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")


# ─── Trailing SL & Iceberg Endpoints ───────────────────────

@router.get("/trailing-sl/status")
async def trailing_sl_status():
    """Return trailing SL state for all active trades."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/trailing-sl/status", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.get("/iceberg/history")
async def iceberg_history():
    """Return iceberg order history."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/iceberg/history", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")


# ─── Trade Reporting (date-range filtering) ──────────────

@router.get("/reports/trades")
async def trade_report(start_date: str = None, end_date: str = None):
    """Trade performance report with optional date range (YYYY-MM-DD)."""
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{TRADING_SERVICE_URL}/reports/trades", params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

@router.post("/trade/update-sl/{trade_id}")
async def update_stop_loss(trade_id: str, new_sl: float):
    """Update stop-loss for an active trade (trailing SL)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{TRADING_SERVICE_URL}/trade/update-sl/{trade_id}",
                params={"new_sl": new_sl}
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Trading Service Unavailable")

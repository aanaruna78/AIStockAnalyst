from typing import Optional
import httpx
import websockets
import asyncio
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from shared.config import settings
from auth_router import get_current_user, oauth2_scheme
from shared.models import User

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

REC_ENGINE_URL = settings.REC_ENGINE_URL
REC_ENGINE_WS_URL = settings.REC_ENGINE_WS_URL

@router.get("/active")
async def get_active_recommendations(
    risk: Optional[str] = None, 
    horizon: Optional[str] = None, 
    sectors: Optional[str] = None,
    token: Optional[str] = Depends(oauth2_scheme)
):
    # Try to get user if token is present
    user = None
    if token:
        try:
            user = await get_current_user(token)
        except HTTPException:
            pass

    # Determine preferences logic: User profile > Query params
    params = {
        "risk": user.preferences.risk_tolerance if user else risk,
        "horizon": user.preferences.investment_horizon if user else horizon,
        "sectors": ",".join(user.preferences.preferred_sectors) if user else sectors
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{REC_ENGINE_URL}/active", params=params)
            return response.json()
        except Exception:
            return []

@router.post("/generate")
async def trigger_recommendation(data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{REC_ENGINE_URL}/generate", json=data)
        return response.json()

@router.websocket("/ws")
async def websocket_recommendations(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(f"{REC_ENGINE_WS_URL}/ws") as target_ws:
            while True:
                try:
                    data = await target_ws.recv()
                    await websocket.send_text(data)
                except websockets.exceptions.ConnectionClosed:
                    break
                except WebSocketDisconnect:
                    break
    except Exception as e:
        import logging
        logging.error(f"Rec WS Proxy Error (connecting to {REC_ENGINE_WS_URL}/ws): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

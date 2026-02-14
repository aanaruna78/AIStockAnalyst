from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import httpx
import websockets
import asyncio
import json
from shared.config import settings

router = APIRouter(tags=["Ingestion"])

INGESTION_SERVICE_URL = settings.INGESTION_SERVICE_URL
INGESTION_WS_URL = f"{settings.INGESTION_WS_URL}/ws/progress"

# Longer timeout for endpoints that fetch external market data
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

@router.get("/market/status")
async def get_market_status():
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{INGESTION_SERVICE_URL}/market/status")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crawl")
async def trigger_crawl(limit: int = 100):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{INGESTION_SERVICE_URL}/batch/run", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scan/config")
async def get_scan_config():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{INGESTION_SERVICE_URL}/scan/config")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scan/config")
async def update_scan_config(interval: int, enabled: bool):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{INGESTION_SERVICE_URL}/scan/config", 
                params={"interval": interval, "enabled": enabled}
            )
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger/{source_id}")
async def trigger_source_ingestion(source_id: str, symbol: str = None):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}", params={"symbol": symbol})
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/progress")
async def websocket_progress(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(INGESTION_WS_URL) as target_ws:
            while True:
                try:
                    # Receive from Ingestion Service
                    data = await target_ws.recv()
                    # Send to Frontend client
                    await websocket.send_text(data)
                except websockets.exceptions.ConnectionClosed:
                    break
                except WebSocketDisconnect:
                    break
    except Exception as e:
        import logging
        logging.error(f"Ingestion WS Proxy Error (connecting to {INGESTION_WS_URL}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass # Already closed or other error

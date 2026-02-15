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

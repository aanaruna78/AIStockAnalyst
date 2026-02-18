"""
Options Router — Proxies requests to the Options Scalping Service.
Nifty 50 weekly options scalping with paper trading.
"""
from fastapi import APIRouter, HTTPException, Request
import httpx
import os

router = APIRouter(prefix="/options", tags=["options-scalping"])

OPTIONS_SCALPING_URL = os.getenv(
    "OPTIONS_SCALPING_URL", "http://options-scalping-service:8000"
)

TIMEOUT = 20


async def _proxy_get(path: str, params: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{OPTIONS_SCALPING_URL}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        raise HTTPException(503, f"Options scalping service unavailable: {e}")


async def _proxy_post(path: str, body: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{OPTIONS_SCALPING_URL}{path}", json=body or {}
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        raise HTTPException(503, f"Options scalping service unavailable: {e}")


# ─── Read endpoints ──────────────────────────────────────────────

@router.get("/spot")
async def get_spot():
    return await _proxy_get("/spot")


@router.get("/chain")
async def get_chain():
    return await _proxy_get("/chain")


@router.get("/signal")
async def get_signal():
    return await _proxy_get("/signal")


@router.get("/portfolio")
async def get_portfolio():
    return await _proxy_get("/portfolio")


@router.get("/stats/daily")
async def get_daily_stats():
    return await _proxy_get("/stats/daily")


# ─── Write endpoints ─────────────────────────────────────────────

@router.post("/trade/place")
async def place_trade(request: Request):
    body = await request.json()
    return await _proxy_post("/trade/place", body)


@router.post("/trade/close")
async def close_trade(request: Request):
    body = await request.json()
    return await _proxy_post("/trade/close", body)


@router.post("/portfolio/reset")
async def reset_portfolio():
    return await _proxy_post("/portfolio/reset")


@router.get("/auto-trade/status")
async def auto_trade_status():
    return await _proxy_get("/auto-trade/status")


@router.post("/auto-trade/toggle")
async def toggle_auto_trade():
    return await _proxy_post("/auto-trade/toggle")


@router.get("/learning/stats")
async def get_learning_stats():
    return await _proxy_get("/learning/stats")


@router.post("/learning/reset")
async def reset_learning():
    return await _proxy_post("/learning/reset")


# ─── Trailing SL & Iceberg for Options ─────────────────

@router.get("/trailing-sl/status")
async def trailing_sl_status():
    return await _proxy_get("/trailing-sl/status")


@router.get("/iceberg/history")
async def iceberg_history():
    return await _proxy_get("/iceberg/history")

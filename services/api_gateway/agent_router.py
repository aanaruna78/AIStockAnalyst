"""
Agent Router — Proxies requests to the Intraday Agent Service.
"""
from fastapi import APIRouter, HTTPException
import httpx
import os

router = APIRouter(prefix="/agent", tags=["agent"])

INTRADAY_AGENT_URL = os.getenv("INTRADAY_AGENT_URL", "http://intraday-agent:8000")


@router.get("/status")
async def agent_status():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{INTRADAY_AGENT_URL}/status")
            return resp.json()
    except Exception as e:
        return {"status": "offline", "error": str(e)}


@router.get("/trades")
async def agent_trades():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{INTRADAY_AGENT_URL}/trades")
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Agent service unavailable: {e}")


@router.post("/force-cycle")
async def force_cycle():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{INTRADAY_AGENT_URL}/force-cycle")
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Agent service unavailable: {e}")


@router.post("/reset")
async def reset_agent():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{INTRADAY_AGENT_URL}/reset")
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Agent service unavailable: {e}")

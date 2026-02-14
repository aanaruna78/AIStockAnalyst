"""
Chart Router — Proxies requests to the Chart Analysis Service.
"""
from fastapi import APIRouter, HTTPException
from typing import List
import httpx
import os

router = APIRouter(prefix="/chart", tags=["chart-analysis"])

CHART_ANALYSIS_URL = os.getenv("CHART_ANALYSIS_URL", "http://chart-analysis-service:8000")


@router.get("/analyze/{symbol}")
async def analyze_symbol(symbol: str, interval: str = "1d", limit: int = 100):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{CHART_ANALYSIS_URL}/analyze/{symbol}",
                params={"interval": interval, "limit": limit}
            )
            if resp.status_code == 404:
                raise HTTPException(404, f"No OHLC data for {symbol}")
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Chart analysis service unavailable: {e}")


@router.get("/patterns/{symbol}")
async def get_patterns(symbol: str, interval: str = "1d", limit: int = 50):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{CHART_ANALYSIS_URL}/patterns/{symbol}",
                params={"interval": interval, "limit": limit}
            )
            if resp.status_code == 404:
                raise HTTPException(404, f"No OHLC data for {symbol}")
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Chart analysis service unavailable: {e}")


@router.get("/indicators/{symbol}")
async def get_indicators(symbol: str, interval: str = "1d", limit: int = 100):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{CHART_ANALYSIS_URL}/indicators/{symbol}",
                params={"interval": interval, "limit": limit}
            )
            if resp.status_code == 404:
                raise HTTPException(404, f"No OHLC data for {symbol}")
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Chart analysis service unavailable: {e}")


@router.post("/analyze-batch")
async def analyze_batch(symbols: List[str]):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{CHART_ANALYSIS_URL}/analyze-batch",
                json=symbols
            )
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Chart analysis service unavailable: {e}")

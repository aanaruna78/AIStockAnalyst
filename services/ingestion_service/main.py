from fastapi import FastAPI, Query
from source_registry import SOURCE_REGISTRY, get_source_by_id
from valuepickr_crawler import ValuePickrCrawler
from tradingview_crawler import TradingViewCrawler
from five_paisa_crawler import FivePaisaCrawler
from moneycontrol_crawler import MoneycontrolCrawler
from trendlyne_crawler import TrendlyneCrawler
from reddit_crawler import RedditCrawler
from dedup import deduplicator
from provenance import ProvenanceTracker
from health_monitor import health_monitor
import logging
import asyncio
from typing import List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect, BackgroundTasks
from batch_job import run_batch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
from shared.config import settings

app = FastAPI(title="SignalForge Ingestion Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestionService")

# Scheduler State
scheduler = AsyncIOScheduler()
scan_config = {
    "interval_minutes": settings.DEFAULT_SCAN_INTERVAL,
    "enabled": True,
    "last_scan_time": None
}

# Crawler Factory
CRAWLER_MAP = {
    "SRC-01": ValuePickrCrawler,
    "SRC-02": ValuePickrCrawler,
    "SRC-03": TradingViewCrawler,
    "SRC-04": TradingViewCrawler,
    "SRC-05": FivePaisaCrawler,
    "SRC-14": MoneycontrolCrawler,
    "SRC-15": TrendlyneCrawler,
    "SRC-08": RedditCrawler,
    "SRC-09": RedditCrawler
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):  # Iterate over a copy
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        # Clean up dead connections
        for conn in dead_connections:
            self.active_connections.discard(conn)

manager = ConnectionManager()

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/trigger/{source_id}")
async def trigger_ingestion(source_id: str, symbol: str = None):
    source = get_source_by_id(source_id)
    if not source:
        return {"error": "Source not found"}
    
    crawler_class = CRAWLER_MAP.get(source_id)
    if not crawler_class:
        return {"error": "Crawler implementation not found for this source"}
    
    logger.info(f"Triggering ingestion for {source.name}")
    crawler = crawler_class(source.id, source.base_url, source.rate_limit_seconds, source.robots_url)
    
    signals = []
    
    try:
        if source_id in ["SRC-01", "SRC-02"]:
            # Mock thread url for demonstration
            thread_url = f"{source.base_url}/t/reliance-industries/1234"
            posts = await crawler.crawl_thread(thread_url)
            if posts:
                for post in posts:
                    signals.append({"content": post, "url": thread_url})
                    
        elif source_id in ["SRC-03", "SRC-04"]:
            ideas = await crawler.crawl_ideas(symbol or "RELIANCE")
            if ideas:
                for idea in ideas:
                    signals.append({"content": idea["body"], "url": source.base_url})
                    
        elif source_id == "SRC-05" or source_id == "SRC-14" or source_id == "SRC-15":
            recs = await crawler.crawl_recommendations()
            if recs:
                for rec in recs:
                    # Filter by symbol if provided
                    if symbol and rec["symbol"] != symbol:
                        continue
                    signals.append({
                        "content": rec["content"],
                        "url": source.base_url,
                        "metadata": rec
                    })
        
        elif source_id in ["SRC-08", "SRC-09"]:
            # Reddit handling (SRC-08: IndiaInvestments, SRC-09: Stocks)
            # symbol mapping for subreddits is usually handled by searching the front page or specific search URLs
            # For simplicity, we crawl the main page
            threads = await crawler.crawl_subreddit(source.base_url)
            if threads:
                for thread in threads:
                    signals.append({
                        "content": f"{thread['title']} - {thread['content']}",
                        "url": source.base_url
                    })

    except Exception as e:
        logger.error(f"Error during ingestion for {source.name}: {e}")
        health_monitor.log_attempt(source.id, False, str(e))
        return {"status": "failed", "error": str(e)}

    # Process signals (dedup + provenance)
    processed_signals = []
    for sig in signals:
        if not deduplicator.is_duplicate(sig["content"]):
            sig["provenance"] = ProvenanceTracker.create_provenance(source.id, sig["url"])
            processed_signals.append(sig)

    health_monitor.log_attempt(source.id, True)
    logger.info(f"Ingested {len(processed_signals)} unique signals from {source.name}")
    return {"status": "success", "count": len(processed_signals), "signals": processed_signals}

@app.get("/health/sources")
async def get_sources_health():
    return health_monitor.health_stats

@app.get("/sources")
async def list_sources():
    return SOURCE_REGISTRY

@app.get("/market/status")
async def get_market_status():
    from global_market_crawler import GlobalMarketCrawler
    crawler = GlobalMarketCrawler()
    
    indices_task = crawler.fetch_indices_live()
    news_task = crawler.fetch_market_news()
    
    indices, news = await asyncio.gather(indices_task, news_task)
    
    return {
        "indices": indices,
        "news": news,
        "timestamp": datetime.now(tz=timezone.utc).isoformat()
    }

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def progress_callback(data: dict):
    await manager.broadcast(data)

@app.post("/batch/run")
async def trigger_batch_run(background_tasks: BackgroundTasks, limit: int = 100):
    scan_config["last_scan_time"] = datetime.now(tz=timezone.utc).isoformat()
    background_tasks.add_task(run_batch, limit=limit, progress_callback=progress_callback)
    return {"status": "started", "limit": limit}

@app.get("/scan/config")
async def get_scan_config():
    return scan_config

@app.post("/scan/config")
async def update_scan_config(interval: int, enabled: bool):
    scan_config["interval_minutes"] = interval
    scan_config["enabled"] = enabled
    setup_scheduler()
    return scan_config

def setup_scheduler():
    # Remove existing job if any
    for job in scheduler.get_jobs():
        job.remove()
    
    if scan_config["enabled"] and scan_config["interval_minutes"] > 0:
        scheduler.add_job(
            scheduled_scan, 
            'interval', 
            minutes=scan_config["interval_minutes"],
            id='market_scan'
        )
        logger.info(f"Scheduler configured for {scan_config['interval_minutes']} minutes.")

async def scheduled_scan():
    logger.info("Starting scheduled market scan...")
    scan_config["last_scan_time"] = datetime.now().isoformat()
    await run_batch(limit=10, progress_callback=progress_callback)

@app.on_event("startup")
async def startup_event():
    setup_scheduler()
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.INGESTION_SERVICE_PORT)

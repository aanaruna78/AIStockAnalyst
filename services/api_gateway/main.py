from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from auth_router import router as auth_router
from recommendation_router import router as rec_router
from ingestion_router import router as ingestion_router
from trading_router import router as trading_router
import time
from shared.config import settings

app = FastAPI(title="SignalForge API Gateway", version="1.0.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic In-Memory Rate Limiting
# In production, use Redis
requests_history = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip health check from rate limiting
    if request.url.path == "/health" or request.url.path == "/":
        return await call_next(request)

    client_ip = request.client.host
    current_time = time.time()
    
    # 60 requests per minute per IP
    window = 60
    max_requests = 60
    
    if client_ip not in requests_history:
        requests_history[client_ip] = []
    
    # Filter out requests outside the window
    requests_history[client_ip] = [t for t in requests_history[client_ip] if current_time - t < window]
    
    if len(requests_history[client_ip]) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests")
    
    requests_history[client_ip].append(current_time)
    response = await call_next(request)
    # Necessary for Google GSI / One Tap
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    # response.headers["Cross-Origin-Embedder-Policy"] = "require-corp" # Be careful with this one
    return response

# Include Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(rec_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to SignalForge API Gateway", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.API_GATEWAY_PORT)

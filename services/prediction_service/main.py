from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from model import model
import logging
from shared.config import settings

app = FastAPI(title="SignalForge Prediction Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PredictionService")

class PredictionRequest(BaseModel):
    symbol: str
    indicators: dict

class PredictionResponse(BaseModel):
    symbol: str
    ml_score: float
    confidence: float

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    logger.info(f"ML Inference request for {request.symbol}")
    
    score = model.predict(request.indicators)
    
    return {
        "symbol": request.symbol,
        "ml_score": score,
        "confidence": 0.85 # Mock confidence level of the model
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PREDICTION_SERVICE_PORT)

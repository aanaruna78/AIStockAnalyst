from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from entity_extractor import entity_extractor
from sentiment import sentiment_analyzer
from relevance import relevance_scorer
import logging

app = FastAPI(title="SignalForge Signal Processing Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SignalProcessor")

class SignalRequest(BaseModel):
    text: str
    source_id: str
    url: str

class SignalResponse(BaseModel):
    symbols: List[str]
    sentiment: float
    subjectivity: float
    relevance: float
    status: str  # 'active', 'ignored'
    meta: dict

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/process", response_model=SignalResponse)
async def process_signal(request: SignalRequest):
    logger.info(f"Processing signal from {request.source_id}")
    
    # 1. Entity Extraction
    symbols = entity_extractor.extract_entities(request.text)
    
    # 2. Relevance Scoring
    relevance = relevance_scorer.score(request.text, symbols)
    
    # 3. Sentiment Analysis
    sentiment_data = sentiment_analyzer.analyze(request.text)
    
    # 4. Noise Filtering Logic
    status = "active"
    if relevance < 0.4:
        status = "ignored"
    elif not symbols:
        status = "ignored" # No linked symbol implies general market noise or irrelevant
    
    return {
        "symbols": symbols,
        "sentiment": sentiment_data.get("polarity", 0.0),
        "subjectivity": sentiment_data.get("subjectivity", 0.0),
        "relevance": relevance,
        "status": status,
        "meta": sentiment_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

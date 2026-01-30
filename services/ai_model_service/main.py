from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from model_router import model_router
from prompts import prompt_registry
import logging
import json

app = FastAPI(title="SignalForge AI Model Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIModelService")

class InferenceRequest(BaseModel):
    task: str
    payload: Dict[str, Any]
    use_consensus: bool = False

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/inference")
async def run_inference(request: InferenceRequest):
    logger.info(f"Running AI inference for task: {request.task}")
    
    # 1. Get Prompt
    try:
        prompt = prompt_registry.get_prompt(request.task, **request.payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Route to Model
    model = model_router.get_model_for_task(request.task)
    
    # 3. Simulate Multi-model Consensus or Single Inference
    # In a real impl, this would call LiteLLM or direct SDKs
    logger.info(f"Routing to {model}")
    
    # Mock Response for now
    if request.task == "sentiment_analysis":
        mock_response = {
            "symbol": request.payload.get("symbol", "UNKNOWN"),
            "sentiment_score": 0.75,
            "subjectivity_score": 0.4,
            "key_drivers": ["Positive earnings", "Market momentum"],
            "confidence": 0.92
        }
    else:
        mock_response = { "info": "Task response not mocked yet" }

    return {
        "task": request.task,
        "model": model,
        "output": mock_response,
        "status": "success"
    }

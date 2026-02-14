from pydantic import BaseModel, Field
from typing import List, Dict, Any

class SentimentAnalysisOutput(BaseModel):
    symbol: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    subjectivity_score: float = Field(..., ge=0.0, le=1.0)
    key_drivers: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)

class TradeRationaleOutput(BaseModel):
    symbol: str
    bias: str = Field(..., pattern="^(BULLISH|BEARISH|NEUTRAL)$")
    technical_observations: List[str]
    fundamental_highlights: List[str]
    risk_factors: List[str]
    conviction_level: float = Field(..., ge=0.0, le=1.0)

class ConsensusOutput(BaseModel):
    final_bias: str
    aggregated_confidence: float
    model_agreement: float
    summary: str
    individual_model_outputs: Dict[str, Any]

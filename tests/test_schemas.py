"""Tests for services/ai_model_service/schemas.py — Pydantic schema validations."""
import pytest
from pydantic import ValidationError
from services.ai_model_service.schemas import (
    SentimentAnalysisOutput,
    TradeRationaleOutput,
    ConsensusOutput,
)


class TestSentimentAnalysisOutput:
    def test_valid_sentiment(self):
        s = SentimentAnalysisOutput(
            symbol="RELIANCE",
            sentiment_score=0.75,
            subjectivity_score=0.5,
            key_drivers=["Strong Q3 results", "Jio growth"],
            confidence=0.9,
        )
        assert s.symbol == "RELIANCE"
        assert s.sentiment_score == 0.75

    def test_sentiment_score_bounds(self):
        # sentiment_score must be between -1.0 and 1.0
        with pytest.raises(ValidationError):
            SentimentAnalysisOutput(
                symbol="TCS",
                sentiment_score=1.5,  # out of range
                subjectivity_score=0.5,
                key_drivers=[],
                confidence=0.5,
            )

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            SentimentAnalysisOutput(
                symbol="TCS",
                sentiment_score=0.5,
                subjectivity_score=0.5,
                key_drivers=[],
                confidence=2.0,  # out of range
            )

    def test_negative_sentiment(self):
        s = SentimentAnalysisOutput(
            symbol="ADANI",
            sentiment_score=-0.8,
            subjectivity_score=0.9,
            key_drivers=["Hindenburg report"],
            confidence=0.95,
        )
        assert s.sentiment_score == -0.8


class TestTradeRationaleOutput:
    def test_valid_rationale(self):
        r = TradeRationaleOutput(
            symbol="INFY",
            bias="BULLISH",
            technical_observations=["RSI oversold", "MACD bullish cross"],
            fundamental_highlights=["Strong earnings"],
            risk_factors=["IT sector headwinds"],
            conviction_level=0.7,
        )
        assert r.bias == "BULLISH"

    def test_invalid_bias_rejected(self):
        with pytest.raises(ValidationError):
            TradeRationaleOutput(
                symbol="INFY",
                bias="MAYBE",  # not BULLISH/BEARISH/NEUTRAL
                technical_observations=[],
                fundamental_highlights=[],
                risk_factors=[],
                conviction_level=0.5,
            )

    def test_conviction_bounds(self):
        with pytest.raises(ValidationError):
            TradeRationaleOutput(
                symbol="INFY",
                bias="NEUTRAL",
                technical_observations=[],
                fundamental_highlights=[],
                risk_factors=[],
                conviction_level=1.5,  # out of range
            )


class TestConsensusOutput:
    def test_valid_consensus(self):
        c = ConsensusOutput(
            final_bias="BULLISH",
            aggregated_confidence=0.82,
            model_agreement=0.9,
            summary="Strong consensus for upside",
            individual_model_outputs={"gpt4": {"bias": "BULLISH"}, "gemini": {"bias": "BULLISH"}},
        )
        assert c.final_bias == "BULLISH"
        assert len(c.individual_model_outputs) == 2

    def test_empty_individual_outputs(self):
        c = ConsensusOutput(
            final_bias="NEUTRAL",
            aggregated_confidence=0.5,
            model_agreement=0.0,
            summary="No consensus",
            individual_model_outputs={},
        )
        assert c.individual_model_outputs == {}

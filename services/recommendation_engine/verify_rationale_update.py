import asyncio
from main import generate_recommendation, RecommendationRequest
from scoring_model import scoring_model
from unittest.mock import MagicMock, AsyncMock

# Mock scoring model to avoid external calls
scoring_model.calculate_conviction = AsyncMock(return_value={
    "final_score": 85.0,
    "sentiment_score": 0.9,
    "technical_score": 0.7,
    "ml_score": 0.8,
    "ml_confidence": 0.8,
    "regime": "TRENDING",
    "weights": {"sentiment": 0.4, "technical_rules": 0.3, "ml_xgboost": 0.3},
    "risk_penalty": 0.0
})

async def test_rationale():
    req = RecommendationRequest(
        symbol="TATASTEEL",
        current_price=150.0,
        atr=2.5,
        indicators={
            "rsi": 25.0, 
            "adx": 40.0, 
            "atr_ratio": 1.2
        },
        signals=[
            {
                "source": "Trendlyne", 
                "sentiment": 1.0, 
                "confidence": 0.9, 
                "raw_text": "Trendlyne report: IDBI Capital recommends BUY on TATASTEEL with target 180."
            },
            {
                "source": "Trendlyne", 
                "sentiment": 1.0, 
                "confidence": 0.9, 
                "raw_text": "Trendlyne report: HDFC Securities recommends ADD on TATASTEEL with target 175."
            },
            {
                "source": "Moneycontrol", 
                "sentiment": 1.0, 
                "confidence": 0.9, 
                "raw_text": "Buy"
            }
        ]
    )

    print("Running generate_recommendation...")
    try:
        # We need to mock level calculator and lifecycle engine too 
        # or just import the function and run the logic we successfully changed.
        # But generate_recommendation calls them.
        # Let's mock the services imported in main.py
        import main
        main.level_calculator.calculate_levels = MagicMock(return_value={"stop_loss": 140, "target": 180, "rr": 3.0})
        main.lifecycle_engine.publish = MagicMock(return_value="REC-123")
        main.manager.broadcast = AsyncMock()

        result = await generate_recommendation(req)
        
        print("\n--- Result (Full Signals) ---")
        print(f"Status: {result.get('status')}")
        rec = result.get('recommendation', {})
        print(f"Rationale: {rec.get('rationale')}")

        # Test Case 2: No Analyst/Sentiment Signals
        print("\nRunning Test Case 2: No Signals...")
        req_empty = RecommendationRequest(
            symbol="INFY",
            current_price=1000.0,
            atr=20.0,
            indicators={"rsi": 50.0},
            signals=[
                # Only technical
                {"source": "Technical", "sentiment": 0.5, "confidence": 1.0}
            ]
        )
        # Mock high conviction for both to ensure rationale generation
        scoring_model.calculate_conviction.side_effect = [
            {"final_score": 85.0, "sentiment_score": 0.9, "technical_score": 0.7, "ml_score": 0.8, "ml_confidence": 0.8, "regime": "TRENDING", "weights": {"sentiment": 0.4, "technical_rules": 0.3, "ml_xgboost": 0.3}},
            {"final_score": 75.0, "sentiment_score": 0.5, "technical_score": 0.8, "ml_score": 0.5, "ml_confidence": 0.5, "regime": "CHOP", "weights": {"sentiment": 0.3, "technical_rules": 0.3, "ml_xgboost": 0.4}}
        ]
        
        result_empty = await generate_recommendation(req_empty)
        print("\n--- Result (Empty Signals) ---")
        result_empty.get('recommendation', result_empty) # fallback if in root
        if "recommendation" in result_empty:
             print(f"Rationale: {result_empty['recommendation'].get('rationale')}")
        else:
             print(f"Rationale (Direct): {result_empty.get('rationale')}") # won't be here if ignored
             print(f"Status: {result_empty.get('status')}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rationale())


class PromptRegistry:
    TEMPLATES = {
        "sentiment_analysis": {
            "v1": """
            Analyze the following market discussion for {symbol}.
            Text: {text}
            
            Extract the sentiment score (-1 to 1), subjectivity, and key drivers.
            Return ONLY a JSON object matching the following schema:
            {{ "symbol": "...", "sentiment_score": 0.0, "subjectivity_score": 0.0, "key_drivers": ["...", "..."], "confidence": 0.0 }}
            """,
        },
        "trade_rationale": {
            "v1": """
            Generate a trade rationale for {symbol} based on these signals and technicals.
            Signals: {signals}
            Technicals: {indicators}
            
            Return ONLY a JSON object matching:
            {{ "symbol": "...", "bias": "BULLISH/BEARISH/NEUTRAL", "technical_observations": [], "fundamental_highlights": [], "risk_factors": [], "conviction_level": 0.0 }}
            """,
        }
    }

    @staticmethod
    def get_prompt(task: str, version: str = "v1", **kwargs) -> str:
        template = PromptRegistry.TEMPLATES.get(task, {}).get(version)
        if not template:
            raise ValueError(f"Prompt template for {task} version {version} not found.")
        return template.format(**kwargs)

# Singleton
prompt_registry = PromptRegistry()

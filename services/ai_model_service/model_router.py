import os

class ModelRouter:
    def __init__(self):
        # Default providers from environment
        self.primary_provider = os.getenv("PRIMARY_AI_PROVIDER", "gemini")
        self.fallback_provider = os.getenv("FALLBACK_AI_PROVIDER", "claude")

    def get_model_for_task(self, task: str) -> str:
        """
        Route to specific models based on task complexity.
        """
        if task == "sentiment_analysis":
            return "gemini-pro" # Fast and cost-effective
        elif task == "trade_rationale":
            return "claude-3-opus" # High reasoning capability
        return "gemini-pro"

    def get_provider_config(self, provider: str) -> dict:
        configs = {
            "gemini": {"api_key": os.getenv("GOOGLE_API_KEY"), "model": "gemini-pro"},
            "claude": {"api_key": os.getenv("ANTHROPIC_API_KEY"), "model": "claude-3-opus"},
            "gpt": {"api_key": os.getenv("OPENAI_API_KEY"), "model": "gpt-4-turbo"}
        }
        return configs.get(provider, {})

# Singleton
model_router = ModelRouter()

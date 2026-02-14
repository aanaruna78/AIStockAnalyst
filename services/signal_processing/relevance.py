
class RelevanceScorer:
    def __init__(self):
        self.market_keywords = [
            "support", "resistance", "breakout", "target", "stoploss", "sl", 
            "bullish", "bearish", "trend", "volume", "chart", "consolidating",
            "moving average", "ema", "rsi", "fundamental", "quarterly result"
        ]

    def score(self, text: str, entities: list) -> float:
        score = 0.0
        text_lower = text.lower()
        
        # 1. Length Bonus (filtering out very short noises)
        if len(text) > 50:
            score += 0.2
        if len(text) > 200:
            score += 0.1
            
        # 2. Entity Presence
        if entities:
            score += 0.3
            
        # 3. Market Keyword matching
        info_richness = sum(1 for kw in self.market_keywords if kw in text_lower)
        # Cap keyword score
        score += min(0.4, info_richness * 0.1)
        
        # 4. Cashtag/Hash density penalty (spam detection)
        words = text.split()
        if words:
            tag_count = sum(1 for w in words if w.startswith('$') or w.startswith('#'))
            if tag_count / len(words) > 0.5:
                score -= 0.3  # Penalty for tag-stuffing
        
        return min(1.0, max(0.0, score))

# Singleton
relevance_scorer = RelevanceScorer()

from typing import List, Dict, Any
import numpy as np

class ConsensusEngine:
    def aggregate_sentiment(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate sentiment scores and check for agreement.
        """
        scores = [obj["sentiment_score"] for obj in model_outputs]
        confidences = [obj["confidence"] for obj in model_outputs]
        
        np.mean(scores)
        weighted_conf = np.average(scores, weights=confidences)
        
        # Agreement: standard deviation (lower is better)
        std_dev = np.std(scores)
        agreement = max(0.0, 1.0 - (std_dev * 2)) # Heuristic
        
        return {
            "final_sentiment": round(float(weighted_conf), 2),
            "agreement_score": round(float(agreement), 2),
            "sample_size": len(model_outputs)
        }

    def merge_rationales(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge technical and fundamental observations from multiple models.
        """
        all_tech = []
        all_fund = []
        all_risks = []
        
        for obj in model_outputs:
            all_tech.extend(obj.get("technical_observations", []))
            all_fund.extend(obj.get("fundamental_highlights", []))
            all_risks.extend(obj.get("risk_factors", []))
            
        return {
            "technical_observations": list(set(all_tech)), # Deduplicate
            "fundamental_highlights": list(set(all_fund)),
            "risk_factors": list(set(all_risks))
        }

# Singleton
consensus_engine = ConsensusEngine()

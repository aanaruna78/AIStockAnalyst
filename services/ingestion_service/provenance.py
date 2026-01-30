from datetime import datetime
from typing import Dict, Any

class ProvenanceTracker:
    @staticmethod
    def create_provenance(source_id: str, url: str, confidence_delta: float = 0.0) -> Dict[str, Any]:
        return {
            "source_id": source_id,
            "url": url,
            "ingested_at": datetime.utcnow().isoformat(),
            "confidence_adjustment": confidence_delta
        }

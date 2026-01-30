import time
from typing import Dict, Any

class SourceHealthMonitor:
    def __init__(self):
        self.health_stats: Dict[str, Dict[str, Any]] = {}

    def log_attempt(self, source_id: str, success: bool, error: str = None):
        if source_id not in self.health_stats:
            self.health_stats[source_id] = {
                "success_count": 0,
                "failure_count": 0,
                "last_attempt": None,
                "last_success": None,
                "last_error": None
            }
        
        stats = self.health_stats[source_id]
        stats["last_attempt"] = time.time()
        
        if success:
            stats["success_count"] += 1
            stats["last_success"] = time.time()
        else:
            stats["failure_count"] += 1
            stats["last_error"] = error

    def get_health(self, source_id: str) -> Dict[str, Any]:
        return self.health_stats.get(source_id, {"status": "unknown"})

# Singleton
health_monitor = SourceHealthMonitor()

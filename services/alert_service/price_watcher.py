from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("PriceWatcher")

class PriceWatcher:
    def check_levels(self, recommendation: Dict[str, Any], current_price: float) -> Optional[Dict[str, Any]]:
        """
        Check if any trade levels (Entry, Target, SL) have been hit.
        """
        symbol = recommendation["symbol"]
        direction = recommendation["direction"]
        
        # 1. Target Hit
        if direction == "UP" and current_price >= recommendation["target1"]:
            return self._create_alert(recommendation, "TARGET_HIT", current_price)
        if direction == "DOWN" and current_price <= recommendation["target1"]:
            return self._create_alert(recommendation, "TARGET_HIT", current_price)
            
        # 2. Stop Loss Hit
        if direction == "UP" and current_price <= recommendation["sl"]:
            return self._create_alert(recommendation, "SL_HIT", current_price)
        if direction == "DOWN" and current_price >= recommendation["sl"]:
            return self._create_alert(recommendation, "SL_HIT", current_price)
            
        return None

    def _create_alert(self, recommendation: Dict[str, Any], alert_type: str, price: float) -> Dict[str, Any]:
        return {
            "symbol": recommendation["symbol"],
            "type": alert_type,
            "recommendation_id": recommendation["id"],
            "price": price,
            "timestamp": recommendation.get("timestamp"), # In real app, current time
        }

# Singleton
price_watcher = PriceWatcher()

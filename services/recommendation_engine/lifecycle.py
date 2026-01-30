from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import os
import logging

logger = logging.getLogger("Lifecycle")

DATA_FILE = "data/recommendations.json"

class RecommendationLifecycle:
    def __init__(self):
        # In-memory store
        self.active_recommendations: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                
                # Filter out stale/invalid on load
                from shared.config import settings
                threshold = settings.MIN_CONFIDENCE_SCORE * 100
                
                self.active_recommendations = {
                    k: v for k, v in data.items() 
                    if v.get("conviction", 0) > threshold and 
                    "No sufficient community ideas" not in v.get("rationale", "")
                }
                logger.info(f"Loaded {len(self.active_recommendations)} valid recommendations from disk.")
            except Exception as e:
                logger.error(f"Failed to load recommendations: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, 'w') as f:
                json.dump(self.active_recommendations, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save recommendations: {e}")

    def publish(self, symbol: str, recommendation: Dict[str, Any]):
        # Deduplication Logic
        existing_active = [k for k, v in self.active_recommendations.items() 
                          if v["symbol"] == symbol and v["status"] == "active"]
        
        if existing_active:
            # We assume one active per symbol for now, but list comprehension handles multiples just in case
            old_id = existing_active[0]
            old_rec = self.active_recommendations[old_id]
            
            # Check conviction
            if recommendation["conviction"] >= old_rec["conviction"]:
                # New one is better, deactivate old and publish new
                logger.info(f"Replacing {old_id} ({old_rec['conviction']}%) with new recommendation for {symbol} ({recommendation['conviction']}%)")
                old_rec["status"] = "replaced"
            else:
                # Old one is better or equal, ignore new
                logger.info(f"Suppressing new recommendation for {symbol} ({recommendation['conviction']}%) in favor of {old_id} ({old_rec['conviction']}%)")
                return None

        rec_id = f"{symbol}_{int(datetime.now().timestamp())}"
        recommendation["id"] = rec_id
        recommendation["created_at"] = datetime.now().isoformat()
        recommendation["status"] = "active"
        # Default expiry: 4 hours
        recommendation["expires_at"] = (datetime.now() + timedelta(hours=4)).isoformat()
        
        self.active_recommendations[rec_id] = recommendation
        self.save()
        return rec_id

    def update_states(self, current_prices: Dict[str, float]):
        """
        Check active recommendations against current prices to update status.
        """
        changed = False
        for rec_id, rec in list(self.active_recommendations.items()):
            if rec["status"] != "active":
                continue
                
            # Check expiry
            if datetime.now().isoformat() > rec["expires_at"]:
                rec["status"] = "expired"
                changed = True
                continue
                
            curr_price = current_prices.get(rec["symbol"])
            if not curr_price:
                continue
                
            # Logic for hitting Target or SL
            if rec["direction"] == "UP":
                if curr_price >= rec["target1"]:
                    rec["status"] = "target_hit"
                    changed = True
                elif curr_price <= rec["sl"]:
                    rec["status"] = "sl_hit"
                    changed = True
            else: # DOWN
                if curr_price <= rec["target1"]:
                    rec["status"] = "target_hit"
                    changed = True
                elif curr_price >= rec["sl"]:
                    rec["status"] = "sl_hit"
                    changed = True
        
        if changed:
            self.save()

    def get_active(self) -> List[Dict[str, Any]]:
        # Return newest first
        active = [r for r in self.active_recommendations.values() if r["status"] == "active"]
        return sorted(active, key=lambda x: x["created_at"], reverse=True)

# Singleton
lifecycle_engine = RecommendationLifecycle()

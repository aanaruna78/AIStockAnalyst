from typing import List, Dict, Any
from datetime import datetime

class NotificationManager:
    def __init__(self):
        # In-memory history for MVP
        self.history: List[Dict[str, Any]] = []

    def generate_message(self, alert: Dict[str, Any]) -> str:
        symbol = alert["symbol"]
        alert_type = alert["type"]
        price = alert["price"]
        
        if alert_type == "TARGET_HIT":
            return f"🎯 Target hit for {symbol} at ₹{price}. Conviction validated."
        elif alert_type == "SL_HIT":
            return f"⚠️ Stop Loss hit for {symbol} at ₹{price}. Exit immediately."
        elif alert_type == "EXPIRY_WARNING":
            return f"⏳ Recommendation for {symbol} is expiring in 30 minutes."
            
        return f"Alert for {symbol}: {alert_type} at ₹{price}"

    def log_alert(self, alert: Dict[str, Any]):
        alert["message"] = self.generate_message(alert)
        alert["created_at"] = datetime.now().isoformat()
        self.history.insert(0, alert) # Latest first
        
        # Keep history manageable
        if len(self.history) > 100:
            self.history.pop()
            
        return alert

# Singleton
notification_manager = NotificationManager()

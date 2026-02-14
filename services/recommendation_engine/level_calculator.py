from typing import Dict, Any, Optional

class LevelCalculator:
    def __init__(self, min_rr: float = 2.0):
        self.min_rr = min_rr

    def calculate_levels(self, current_price: float, atr: float, direction: str, vix: float = 0.0) -> Optional[Dict[str, float]]:
        """
        Calculate Entry, Target 1, Target 2, and SL based on ATR and direction (VIX Scaled).
        """
        if atr <= 0:
            return None

        # Volatility Scaling
        # If VIX is high (e.g. 20+), widen the levels to avoid premature stop-outs
        # and capture larger volatility swings.
        multiplier = 1.0
        if vix > 20: multiplier = 1.2
        if vix > 25: multiplier = 1.5
        
        # SL = 1.0 * ATR * multiplier (realistic swing trade stop-loss)
        stop_loss_dist = 1.0 * atr * multiplier
        
        if direction.upper() == "UP":
            sl = current_price - stop_loss_dist
            risk = current_price - sl
            
            # Target 1: 2.0 * ATR * multiplier (R:R = 2.0)
            # Target 2: 3.0 * ATR * multiplier (R:R = 3.0)
            target1 = current_price + (2.0 * atr * multiplier)
            target2 = current_price + (3.0 * atr * multiplier)
            
            return {
                "entry": current_price,
                "target1": round(target1, 2),
                "target2": round(target2, 2),
                "sl": round(sl, 2),
                "rr": round((target1 - current_price) / risk, 2),
                "vix_multiplier": multiplier
            }
        
        elif direction.upper() == "DOWN":
            sl = current_price + stop_loss_dist
            risk = sl - current_price
            
            target1 = current_price - (2.0 * atr * multiplier)
            target2 = current_price - (3.0 * atr * multiplier)
            
            return {
                "entry": current_price,
                "target1": round(target1, 2),
                "target2": round(target2, 2),
                "sl": round(sl, 2),
                "rr": round((current_price - target1) / risk, 2),
                "vix_multiplier": multiplier
            }
            
        return None

# Singleton
level_calculator = LevelCalculator()

from typing import Dict, Optional

class LevelCalculator:
    def __init__(self, min_rr: float = 2.0):
        self.min_rr = min_rr

    def calculate_levels(self, current_price: float, atr: float, direction: str, vix: float = 0.0, mode: str = "intraday") -> Optional[Dict[str, float]]:
        """
        Calculate Entry, Target 1, Target 2, and SL based on ATR and direction (VIX Scaled).
        
        mode:
          - 'intraday': Tight SL/Target suited for same-day trades (default)
          - 'swing': Wider SL/Target for multi-day positions
        """
        if atr <= 0:
            return None

        # Volatility Scaling
        multiplier = 1.0
        if vix > 20:
            multiplier = 1.2
        if vix > 25:
            multiplier = 1.5

        if mode == "intraday":
            # Intraday: tighter levels — SL = 0.4×ATR, T1 = 0.8×ATR, T2 = 1.2×ATR
            # Typical intraday ATR for mid-cap NSE stocks is 20-60 pts
            # This gives SL ~8-24 pts, Target ~16-48 pts — realistic for intraday
            sl_mult = 0.4
            t1_mult = 0.8
            t2_mult = 1.2
            # Cap maximum SL at 1.5% of price for intraday safety
            max_sl_pct = 0.015
        else:
            # Swing: original wider levels
            sl_mult = 1.0
            t1_mult = 2.0
            t2_mult = 3.0
            max_sl_pct = 0.05  # 5% cap for swing
        
        stop_loss_dist = sl_mult * atr * multiplier
        # Cap SL distance to max % of price
        max_sl_dist = current_price * max_sl_pct
        stop_loss_dist = min(stop_loss_dist, max_sl_dist)
        
        if direction.upper() == "UP":
            sl = current_price - stop_loss_dist
            risk = current_price - sl
            
            target1 = current_price + (t1_mult * atr * multiplier)
            target2 = current_price + (t2_mult * atr * multiplier)
            
            # Cap targets at reasonable intraday % moves
            if mode == "intraday":
                max_target_dist = current_price * 0.03  # 3% max target for intraday
                target1 = min(target1, current_price + max_target_dist)
                target2 = min(target2, current_price + max_target_dist * 1.5)
            
            return {
                "entry": current_price,
                "target1": round(target1, 2),
                "target2": round(target2, 2),
                "sl": round(sl, 2),
                "rr": round((target1 - current_price) / risk, 2) if risk > 0 else 2.0,
                "vix_multiplier": multiplier,
                "mode": mode
            }
        
        elif direction.upper() == "DOWN":
            sl = current_price + stop_loss_dist
            risk = sl - current_price
            
            target1 = current_price - (t1_mult * atr * multiplier)
            target2 = current_price - (t2_mult * atr * multiplier)
            
            if mode == "intraday":
                max_target_dist = current_price * 0.03
                target1 = max(target1, current_price - max_target_dist)
                target2 = max(target2, current_price - max_target_dist * 1.5)
            
            return {
                "entry": current_price,
                "target1": round(target1, 2),
                "target2": round(target2, 2),
                "sl": round(sl, 2),
                "rr": round((current_price - target1) / risk, 2) if risk > 0 else 2.0,
                "vix_multiplier": multiplier,
                "mode": mode
            }
            
        return None

# Singleton
level_calculator = LevelCalculator()

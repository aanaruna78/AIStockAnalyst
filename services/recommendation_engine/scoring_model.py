from typing import List, Dict, Any
import numpy as np
import httpx
import logging
import re
from shared.config import settings

logger = logging.getLogger("ScoringModel")

class ScoringModel:
    def __init__(self):
        # Base weights from centralized config
        self.base_weights = {
            "sentiment": settings.BASE_WEIGHT_SENTIMENT,
            "technical_rules": settings.BASE_WEIGHT_TECHNICAL,
            "ml_xgboost": settings.BASE_WEIGHT_ML,
            "fundamental": settings.BASE_WEIGHT_FUNDAMENTAL,
            "analyst_ratings": settings.BASE_WEIGHT_ANALYST
        }

    def _get_dynamic_weights(self, regime: str, signals: List[Dict[str, Any]], ml_confidence: float, has_analyst_data: bool = True) -> Dict[str, float]:
        """
        Adjust weights based on regime and signal metadata (Dynamic Gating).
        """
        # 1. Base weights from regime
        weights = self.base_weights.copy()
        if regime == "TRENDING":
            weights["technical_rules"] += 0.05
            weights["ml_xgboost"] -= 0.05
        elif regime == "CHOP":
            weights["ml_xgboost"] += 0.05
            weights["technical_rules"] -= 0.05
            
        # 2. Apply Confidence x Freshness gating for each layer
        # Sentiment gating
        sent_signals = [s for s in signals if s.get("source") in ["Reddit", "ValuePickr", "TradingView", "Moneycontrol", "5paisa"]]
        if sent_signals:
            sent_conf = np.mean([s.get("confidence", 0.5) * s.get("freshness", 1.0) for s in sent_signals])
            sent_weight_mult = sent_conf
        else:
            # If no sentiment signals, DON'T penalize heavily. 
            # Redistribute half of sentiment weight to Technicals
            weights["technical_rules"] += weights["sentiment"] * 0.5
            weights["sentiment"] *= 0.5 
            sent_weight_mult = 1.0 # Trust the neutral baseline
        
        # Analyst gating — redistribute weight when no analyst data
        if not has_analyst_data:
            analyst_weight = weights["analyst_ratings"]
            # Redistribute to Technical and Fundamental equally
            weights["technical_rules"] += analyst_weight * 0.4
            weights["fundamental"] += analyst_weight * 0.4
            weights["ml_xgboost"] += analyst_weight * 0.2
            weights["analyst_ratings"] = 0.0
            
        # ML Gating - Boost confidence to avoid killing the score
        ml_gating = max(ml_confidence, settings.ML_CONFIDENCE_FLOOR)
        
        effective_weights = {
            "sentiment": weights["sentiment"] * sent_weight_mult,
            "technical_rules": weights["technical_rules"] * 1.0, 
            "ml_xgboost": weights["ml_xgboost"] * ml_gating,
            "fundamental": weights.get("fundamental", settings.BASE_WEIGHT_FUNDAMENTAL) * 1.0,
            "analyst_ratings": weights.get("analyst_ratings", settings.BASE_WEIGHT_ANALYST) * 1.0 
        }
        
        # Normalize
        total = sum(effective_weights.values())
        if total > 0:
            return {k: v / total for k, v in effective_weights.items()}
        return self.base_weights

    def _calculate_analyst_score(self, tickertape_data: Dict[str, Any]) -> float:
        """
        Score based on professional analyst ratings and forecasts from TickerTape.
        Range: 0.0 to 1.0 (0.5 Neutral)
        """
        if not tickertape_data:
            return 0.5
            
        score = 0.5
        
        # 1. Forecast Upside
        forecast = tickertape_data.get("forecast", {})
        upside_str = forecast.get("upside") # e.g. "High (23.5%)" or just "23.5%"
        if upside_str:
            try:
                # Extract number
                match = re.search(r"(\d+\.?\d*)", upside_str)
                if match:
                    upside_val = float(match.group(1))
                    if "Low" in upside_str or upside_val < 0:
                        score -= 0.1
                    elif upside_val > settings.ANALYST_UPSIDE_HIGH:
                        score += 0.2 # Bonus for > 20% upside
                    elif upside_val > settings.ANALYST_UPSIDE_MID:
                        score += 0.1 # Bonus for > 10% upside
            except Exception:
                pass
            
        # 2. Analyst Ratings
        # "80% Buy" -> Parse
        rating_str = forecast.get("analyst_rating") # "80% Buy"
        if rating_str:
            try:
                match = re.search(r"(\d+)%", rating_str)
                if match:
                    percent = float(match.group(1))
                    if "Buy" in rating_str:
                        if percent > settings.ANALYST_BUY_PERCENT_HIGH:
                            score += 0.2
                        elif percent > settings.ANALYST_BUY_PERCENT_MID:
                            score += 0.1
                        elif percent < settings.ANALYST_BUY_PERCENT_LOW:
                            score -= 0.1
                    elif "Sell" in rating_str:
                        score -= (percent / 100) * 0.2
            except Exception:
                pass
            
        # 3. Technical Rating from TickerTape (Direct confirmation)
        tech_rating = tickertape_data.get("technical_rating") # "Bullish", "Bearish", "Neutral"
        if tech_rating:
            if "Very Bull" in tech_rating:
                score += 0.2
            elif "Very Bear" in tech_rating:
                score -= 0.2
            elif "Bull" in tech_rating:
                score += 0.1
            elif "Bear" in tech_rating:
                score -= 0.1
            
        return min(1.0, max(0.0, score))

    async def calculate_conviction(self, symbol: str, signals: List[Dict[str, Any]], indicators: Dict[str, Any], screener_analysis: Dict[str, Any] = None, tickertape_analysis: Dict[str, Any] = None, global_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fused scoring with Dynamic Gating, Regime Detection, Risk Penalty, Fundamental/Analyst Analysis AND Global Sentiment (VIX Aware).
        """
        vix = 0.0
        if global_analysis:
            vix = global_analysis.get("vix", 0.0)

        # 1. Regime Detection
        regime = self._detect_regime(indicators, vix)
        
        # 2. Aggregate Sentiment
        sentiment_score = 0.5
        if signals:
            weighted_sent_sum = sum(s["sentiment"] * s.get("confidence", 1.0) * s.get("freshness", 1.0) for s in signals)
            total_weight = sum(s.get("confidence", 1.0) * s.get("freshness", 1.0) for s in signals)
            if total_weight > 0:
                avg_sent = weighted_sent_sum / total_weight
                sentiment_score = (avg_sent + 1) / 2 # Normalize to [0, 1]

        # 3. Continuous Technical Scoring
        rule_score = self._calculate_continuous_technical_score(indicators)
        
        # 3.5 Fundamental Scoring (Screener)
        fund_score = self._calculate_fundamental_score(screener_analysis)
        
        # 3.6 Analyst Scoring (TickerTape)
        analyst_score = self._calculate_analyst_score(tickertape_analysis)

        # 4. ML Score
        ml_score = 0.5
        ml_confidence = 0.5
        try:
            async with httpx.AsyncClient(timeout=settings.ML_FETCH_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.PREDICTION_SERVICE_URL}/predict",
                    json={"symbol": symbol, "indicators": indicators}
                )
                if resp.status_code == 200:
                    ml_data = resp.json()
                    ml_score = ml_data.get("ml_score", 0.5)
                    ml_confidence = 2 * abs(ml_score - 0.5)
                    logger.info(f"Integrated XGBoost: p={ml_score:.2f}, conf={ml_confidence:.2f}")
        except Exception as e:
            logger.error(f"Failed to fetch XGBoost: {e}")

        # 5. Dynamic Weighting (Fusion)
        has_analyst_data = bool(tickertape_analysis)
        dyn_weights = self._get_dynamic_weights(regime, signals, ml_confidence, has_analyst_data)
        
        # Adjust weights if VIX is high (Less trust in ML/Technicals, more in Fundamentals/Analyst)
        if vix > settings.VIX_HIGH:
            dyn_weights["ml_xgboost"] *= 0.8
            dyn_weights["technical_rules"] *= 0.8
            total = sum(dyn_weights.values())
            dyn_weights = {k: v / total for k, v in dyn_weights.items()}

        final_score = (
            sentiment_score * dyn_weights["sentiment"] +
            rule_score * dyn_weights["technical_rules"] +
            ml_score * dyn_weights["ml_xgboost"] +
            fund_score * dyn_weights.get("fundamental", settings.BASE_WEIGHT_FUNDAMENTAL) +
            analyst_score * dyn_weights.get("analyst_ratings", settings.BASE_WEIGHT_ANALYST)
        )
        
        # Normalize
        total_weight = sum(dyn_weights.values())
        if total_weight > 0:
            final_score = final_score / total_weight

        # 6. Risk Penalty — reduces conviction magnitude, does not change direction
        risk_penalty = self._calculate_risk_penalty(indicators, vix)
        # Shrink distance from 0.5 (neutral) by penalty factor
        final_score = 0.5 + (final_score - 0.5) * (1 - risk_penalty)

        # 7. Global Market Sentiment Modifier — shifts score toward bearish/bullish
        global_score = 0.0
        global_shift = 0.0
        if global_analysis:
            global_score = global_analysis.get("global_score", 0.0)
            if global_score < -0.3:
                # Global bearish: shift score toward bearish (lower)
                severity = min(1.0, abs(global_score))
                global_shift = -severity * 0.04  # max -0.04 shift (balanced)
            elif global_score > 0.3:
                # Global bullish: shift score toward bullish (higher)
                global_shift = min(1.0, global_score) * 0.04  # max +0.04 shift (symmetric)
            final_score = max(0.0, min(1.0, final_score + global_shift))

        # 8. ADR Signal (Pre-Market/Overlay) — directional shift
        adr_score = 0.0
        if global_analysis and "adr" in global_analysis:
            adr_info = global_analysis["adr"]
            adr_info.get("ticker")
            data = adr_info.get("data", {})
            change_pct = data.get("change_pct", 0.0)
            
            if change_pct > 1.5:
                final_score = min(1.0, final_score + 0.03)
                adr_score = 0.03
            elif change_pct < -1.5:
                final_score = max(0.0, final_score - 0.03)
                adr_score = -0.03

        # --- Bidirectional conviction ---
        # raw_score: 0.0 = strongly bearish, 0.5 = neutral, 1.0 = strongly bullish
        # direction: derived from which side of 0.5
        # conviction: how far from neutral, scaled to 0-100%
        #   Raw distance from 0.5 is 0.0–0.5, but practical max is ~0.20
        #   Rescale so practical range maps to 0-100%:
        #   distance 0.05 → ~25%, 0.10 → ~50%, 0.15 → ~75%, 0.20 → ~100%
        direction = "UP" if final_score >= 0.5 else "DOWN"
        distance = abs(final_score - 0.5)
        conviction = min(100.0, (distance / 0.20) * 100)  # 0.20 distance = 100%

        return {
            "final_score": round(conviction, 2),
            "direction": direction,
            "raw_score": round(final_score, 4),
            "breakdown": {
                "regime": regime,
                "sentiment_score": round(sentiment_score * 100, 2),
                "technical_score": round(rule_score * 100, 2),
                "fundamental_score": round(fund_score * 100, 2),
                "ml_model": {
                    "probability": float(round(ml_score, 4)),
                    "confidence": float(round(ml_confidence, 4))
                },
                "analyst_score": round(analyst_score * 100, 2),
                "vix": vix
            },
            "weights": {k: round(v, 2) for k, v in dyn_weights.items()},
            "risk_penalty": round(risk_penalty, 4),
            "global_shift": round(global_shift, 4),
            "adr_score": round(adr_score, 4)
        }

    def _calculate_fundamental_score(self, screener_data: Dict[str, Any]) -> float:
        if not screener_data:
            return 0.5
        score = 0.5
        
        # Pros vs Cons
        pros = screener_data.get("pros", [])
        cons = screener_data.get("cons", [])
        net_pros = len(pros) - len(cons)
        score += max(-0.15, min(0.15, net_pros * 0.03))
        
        # Detect strong fundamental keywords in pros
        pro_text = " ".join(pros).lower()
        if "debt free" in pro_text or "almost debt free" in pro_text:
            score += 0.05
        if "good dividend" in pro_text or "dividend yield" in pro_text:
            score += 0.03
        if "consistent profit" in pro_text or "consistent compounding" in pro_text:
            score += 0.03
        
        # Detect negative keywords in cons
        con_text = " ".join(cons).lower()
        if "poor sales growth" in con_text or "declining" in con_text:
            score -= 0.03
        if "high valuation" in con_text or "trading at" in con_text:
            score -= 0.02
        
        # Key Metrics
        funds = screener_data.get("fundamentals", {})
        
        # ROCE scoring (Return on Capital Employed)
        roce = funds.get("roce")
        if roce:
            try:
                roce_val = float(roce)
                if roce_val > 30:
                    score += 0.10  # Exceptional ROCE
                elif roce_val > 20:
                    score += 0.07
                elif roce_val > 15:
                    score += 0.04
                elif roce_val < 8:
                    score -= 0.05  # Poor ROCE
            except Exception:
                pass
        
        # ROE scoring (Return on Equity)
        roe = funds.get("roe")
        if roe:
            try:
                roe_val = float(roe)
                if roe_val > 25:
                    score += 0.07  # Excellent ROE
                elif roe_val > 15:
                    score += 0.04
                elif roe_val < 5:
                    score -= 0.04  # Poor ROE
            except Exception:
                pass
            
        return min(1.0, max(0.0, score))

    def _detect_regime(self, indicators: Dict[str, Any], vix: float = 0.0) -> str:
        """
        Classify market state into TRENDING, CHOP, or VOLATILE (VIX Aware).
        """
        adx = indicators.get("adx")
        atr_ratio = indicators.get("atr_ratio")
        
        # Default to neutral/chop if data missing
        if adx is None:
            adx = settings.REGIME_ADX_TRENDING
        if atr_ratio is None:
            atr_ratio = 1.0
        
        if vix > settings.VIX_HIGH or atr_ratio > settings.REGIME_ATR_RATIO_VOLATILE:
            return "VOLATILE"
        if adx > settings.REGIME_ADX_TRENDING:
            return "TRENDING"
        return "CHOP"

    def _calculate_continuous_technical_score(self, indicators: Dict[str, Any]) -> float:
        """Multi-indicator technical score using RSI, MACD, Bollinger, MA trend.
        Extreme RSI values (< 20 or > 80) get amplified weight to prevent dilution."""
        scores = []
        weights = []
        
        # 1. RSI (continuous mapping)
        rsi = indicators.get("rsi")
        if rsi is not None:
            rsi = float(rsi)
            if rsi < 20:
                scores.append(0.9)
                weights.append(2.0)  # Double weight for extreme oversold
            elif rsi < settings.RSI_OVERSOLD:
                scores.append(0.6 + 0.3 * (settings.RSI_OVERSOLD - rsi) / (settings.RSI_OVERSOLD - 20))
                weights.append(1.5)  # 1.5x weight for oversold zone
            elif rsi > 80:
                scores.append(0.1)
                weights.append(2.0)  # Double weight for extreme overbought
            elif rsi > settings.RSI_OVERBOUGHT:
                scores.append(0.4 - 0.3 * (rsi - settings.RSI_OVERBOUGHT) / (80 - settings.RSI_OVERBOUGHT))
                weights.append(1.5)  # 1.5x weight for overbought zone
            else:
                # Momentum-aware RSI scoring for intraday:
                if rsi <= 50:
                    scores.append(0.5 + (50 - rsi) * 0.005)
                elif rsi <= 60:
                    scores.append(0.5)
                else:
                    scores.append(0.5 - (rsi - 60) * 0.01)
                weights.append(1.0)
        
        # 2. MACD histogram direction
        macd_hist = indicators.get("macd_histogram")
        if macd_hist is not None:
            h = float(macd_hist)
            close = float(indicators.get("close", 1))
            if close > 0:
                norm = h / close * 100  # Normalize to percentage
                scores.append(min(0.8, max(0.2, 0.5 + norm * 0.1)))
                weights.append(1.0)
        
        # 3. Bollinger Band position
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        close = indicators.get("close")
        if bb_upper and bb_lower and close:
            bb_range = float(bb_upper) - float(bb_lower)
            if bb_range > 0:
                position = (float(close) - float(bb_lower)) / bb_range
                # Near lower band = bullish, near upper band = bearish
                scores.append(min(0.8, max(0.2, 1.0 - position)))
                weights.append(1.0)
        
        # 4. Price vs SMA-20 trend
        sma_20 = indicators.get("sma_20")
        if sma_20 and close:
            ratio = float(close) / float(sma_20)
            scores.append(min(0.8, max(0.2, 0.5 + (ratio - 1.0) * 5)))
            weights.append(1.0)
        
        if not scores:
            return 0.5
        return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    def _calculate_risk_penalty(self, indicators: Dict[str, Any], vix: float = 0.0) -> float:
        penalty = 0.0
        atr_ratio = indicators.get("atr_ratio") or 1.0
        
        # ATR based penalty
        if atr_ratio > settings.REGIME_ATR_RATIO_RISK:
            penalty += (atr_ratio - settings.REGIME_ATR_RATIO_RISK) * 0.5
            
        # VIX based penalty
        if vix > settings.VIX_HIGH:
            penalty += (vix - settings.VIX_HIGH) * 0.02
            
        return min(0.4, penalty) # Increased max penalty to 40%

scoring_model = ScoringModel()

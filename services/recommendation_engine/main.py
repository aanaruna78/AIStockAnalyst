from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from scoring_model import scoring_model
from level_calculator import level_calculator
from lifecycle import lifecycle_engine
from shared.config import settings
import numpy as np
import logging
import json

app = FastAPI(title="SignalForge Recommendation Engine")
logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RecommendationEngine")

# Color Constants for Rationale (Hex matching Frontend Theme)
C_GREEN = settings.COLOR_GREEN
C_RED = settings.COLOR_RED
C_ORANGE = settings.COLOR_ORANGE
C_CYAN = settings.COLOR_CYAN

def colorize(text: str, color: str) -> str:
    return f'<span style="color: {color}; font-weight: bold;">{text}</span>'

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                # Ideally remove dead connection here

manager = ConnectionManager()

class RecommendationRequest(BaseModel):
    symbol: str
    current_price: float
    atr: float
    indicators: Dict[str, Any]
    signals: List[Dict[str, Any]]
    fundamentals: Optional[Dict[str, Any]] = None
    checklist: Optional[Dict[str, Any]] = None
    financials: Optional[Dict[str, List[Dict[str, Any]]]] = None
    screener_analysis: Optional[Dict[str, Any]] = None
    tickertape_analysis: Optional[Dict[str, Any]] = None
    global_analysis: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe handle heartbeats
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        # manager.disconnect(websocket) # Safe removal

@app.post("/generate")
async def generate_recommendation(request: RecommendationRequest):
    # 1. Calculate Conviction Breakdown
    breakdown = await scoring_model.calculate_conviction(
        request.symbol,
        request.signals,
        request.indicators,
        request.screener_analysis, # Pass aggregated screener data
        request.global_analysis # Pass global market context
    )
    conviction = breakdown["final_score"]

    # 2. Threshold check (e.g., conviction > 70%)
    threshold = settings.MIN_CONFIDENCE_SCORE * 100
    if conviction <= threshold:
        return {"status": "ignored", "reason": "Low conviction score", "score": conviction, "threshold": threshold}
    
    # 3. Construct Waterfall Rationale
    regime = breakdown.get("regime", "CHOP")
    weights = breakdown.get("weights", {})
    penalty = breakdown.get("risk_penalty", 0.0)
    
    # Helper to map regime code to description
    regime_desc = {
        "BULL": colorize("Bullish", C_GREEN), 
        "BEAR": colorize("Bearish", C_RED), 
        "CHOP": colorize("Choppy/Sideways", C_ORANGE),
        "VOLATILE": colorize("High Volatility", C_RED),
        "TRENDING": colorize("Trending", C_CYAN)
    }.get(regime, regime)
    
    # Global Outlook Text
    global_outlook = ""
    if request.global_analysis:
        summary = request.global_analysis.get("global_summary", "")
        
        # Currency
        usd_inr = request.global_analysis.get("indices", {}).get("USD/INR")
        currency_text = ""
        if usd_inr is not None:
            c_color = C_RED if usd_inr > 0.2 else (C_GREEN if usd_inr < -0.2 else C_ORANGE)
            direction = "Weakening" if usd_inr > 0.2 else ("Strengthening" if usd_inr < -0.2 else "Stable")
            currency_text = f" | Rupee: {colorize(direction, c_color)} ({usd_inr}%)"
        
        # ADR
        adr_text = ""
        if "adr" in request.global_analysis:
            adr = request.global_analysis["adr"]
            ticker = adr.get("ticker")
            chg = adr.get("data", {}).get("change_pct", 0.0)
            if abs(chg) > 1.5:
                direction = "Bullish" if chg > 0 else "Bearish"
                adr_text = f" | ADR ({ticker}): {chg}% ({direction})"
            else:
                adr_text = f" | ADR ({ticker}): {chg}% (Flat)"

        score = request.global_analysis.get("global_score", 0.0)
        c = C_RED if score < -0.3 else (C_GREEN if score > 0.3 else C_ORANGE)
        status = "Bearish" if score < -0.3 else ("Bullish" if score > 0.3 else "Neutral")
        global_outlook = f" | Global: {colorize(status, c)}{currency_text}{adr_text}"

    rationale_text = f"Market Context: {regime_desc}{global_outlook}. "
    
    # Conviction description with uncertainty
    conf_level = colorize("High", C_GREEN) if conviction > 80 else (colorize("Medium", C_ORANGE) if conviction > 60 else colorize("Low", C_RED))
    
    # Extract detailed scores from the nested 'breakdown' dict
    details = breakdown.get("breakdown", {})
    ml_confidence = details.get("ml_model", {}).get("confidence", 0.5)
    
    # 5. Full Score Breakdown for UI
    scores = {
        "Sentiment": round(details.get("sentiment_score", 0) * weights.get("sentiment", settings.BASE_WEIGHT_SENTIMENT), 1),
        "Technical": round(details.get("technical_score", 0) * weights.get("technical_rules", settings.BASE_WEIGHT_TECHNICAL), 1),
        "AI Model": round(details.get("ml_model", {}).get("probability", 0.5) * 100 * weights.get("ml_xgboost", settings.BASE_WEIGHT_ML), 1),
        "Fundamental": round(details.get("fundamental_score", 0) * weights.get("fundamental", settings.BASE_WEIGHT_FUNDAMENTAL), 1),
        "Analyst": round(details.get("analyst_score", 0) * weights.get("analyst_ratings", settings.BASE_WEIGHT_ANALYST), 1)
    }
    logger.info(f"Score Breakdown for {request.symbol}: {scores}")
    
    rationale_text += f"AI Confidence: {round(conviction)}% ({conf_level}), "
    
    # Identify top driver
    top_driver = max(scores, key=scores.get)
    driver_val = scores[top_driver]
    
    rationale_text += f"driven primarily by {top_driver} signals (+{driver_val}% contribution). "
    
    # Technical Key Details
    rsi = request.indicators.get("rsi", "N/A")
    adx = request.indicators.get("adx", "N/A")
    try:
        rsi_val = float(rsi)
        rsi_desc = colorize("Oversold", C_GREEN) if rsi_val < 30 else (colorize("Overbought", C_RED) if rsi_val > 70 else "Neutral")
        rsi_str = f"{round(rsi_val, 1)} ({rsi_desc})"
    except: # noqa: E722
        rsi_str = "N/A"
        
    rationale_text += f"Key Indicators: RSI is {rsi_str}"
    if adx != "N/A":
        try:
            val = float(adx)
            if val > 25:
                rationale_text += f", ADX {round(val, 1)} ({colorize('Trending', C_CYAN)})"
        except: # noqa: E722
            pass
    rationale_text += ". "
    
    # Comprehensive Sentiment Analysis Section
    analyst_signals = [s for s in request.signals if s.get("source") in ["Moneycontrol", "5paisa", "Trendlyne", "Trendlyne Research"]]
    community_signals = [s for s in request.signals if s.get("source") in ["Reddit", "ValuePickr", "TradingView"]]
    
    sentiment_details = []
    
    # 1. Analyst Signals
    if analyst_signals:
        trendlyne_reports = [s for s in analyst_signals if "Trendlyne" in s.get("source", "")]
        other_reports = [s for s in analyst_signals if "Trendlyne" not in s.get("source", "")]
        
        if trendlyne_reports:
            for rep in trendlyne_reports:
                raw = rep.get("raw_text", "")
                # Format: "Trendlyne report: {analyst} recommends {action} on {stock} with target {target}..."
                if "recommends" in raw:
                    try:
                        # "Trendlyne report: IDBI Capital recommends BUY on TATASTEEL with target 180."
                        parts = raw.split("recommends")
                        author = parts[0].replace("Trendlyne report:", "").strip()
                        rest = parts[1]
                        action = rest.split(" on ")[0].strip()
                        if "target" in rest:
                            tgt = rest.split("target")[1].split(".")[0].strip()
                            sentiment_details.append(f"{author} ({action}, Tgt {tgt})")
                        else:
                            sentiment_details.append(f"{author} ({action})")
                    except: # noqa: E722
                        sentiment_details.append("Trendlyne Report (Buy)")
                else:
                    sentiment_details.append("Trendlyne Positive")
        
        if other_reports:
            for rep in other_reports:
                source = rep.get("source", "")
                raw = rep.get("raw_text", "")
                
                if source == "5paisa":
                    # Format: "5paisa recommends {action} for {symbol}. Entry: {entry}, SL: {sl}, Target 1: {target1}, Target 2: {target2}."
                    if "recommends" in raw:
                        try:
                            action = raw.split("recommends")[1].split("for")[0].strip()
                            if "Target 1:" in raw:
                                tgt = raw.split("Target 1:")[1].split(",")[0].strip()
                                sentiment_details.append(f"5paisa ({action}, Tgt {tgt})")
                            else:
                                sentiment_details.append(f"5paisa ({action})")
                        except: # noqa: E722
                            sentiment_details.append("5paisa Analyst (Positive)")
                    else:
                         sentiment_details.append("5paisa Analyst (Positive)")

                elif source == "Moneycontrol":
                    # Format: "Moneycontrol reports {action} for {stock} by {analyst} on {date} with target {target}."
                    if "reports" in raw and "by" in raw:
                        try:
                            parts = raw.split("reports")
                            action = parts[1].split("for")[0].strip()
                            analyst = raw.split("by")[1].split("on")[0].strip()
                            if "target" in raw:
                                tgt = raw.split("target")[1].strip().rstrip(".")
                                sentiment_details.append(f"{analyst} via MC ({action}, Tgt {tgt})")
                            else:
                                sentiment_details.append(f"{analyst} via MC ({action})")
                        except: # noqa: E722
                            sentiment_details.append("Moneycontrol Analyst (Positive)")
                    else:
                        sentiment_details.append("Moneycontrol Analyst (Positive)")
                else:
                    sentiment_details.append(f"Analyst from {source}")
        
    else:
        # Explicitly state no analyst coverage if that's the case, helps user know it was checked
        # Only show this if we are driven by something else or if we want to validata "No news is good news"? 
        # Actually user wants to know about "crawling result recommendation".
        pass # We'll add a generic "No specific analyst coverage" only if community is also empty? 
             # Or maybe just append "Analyst Coverage: None found." to be thorough?
             # Let's add it to sentiment_details if empty so it shows up.
        # sentiment_details.append("No direct analyst coverage found")
        pass

    # 2. Community Signals
    if community_signals:
        sources = list(set([s.get("source") for s in community_signals]))
        sentiment_details.append(f"Community discussion on {', '.join(sources)}")
        
    if sentiment_details:
        rationale_text += f"Sentiment Analysis: {'; '.join(sentiment_details)}."
    else:
        rationale_text += "Sentiment Analysis: Neutral (No major analyst/community signals detected)."
    
    # Standalone Fundamentals block removed - merged into unified section below
    # Add Financial Statement Analysis
    if request.financials:
        income = request.financials.get("income_statement", [])
        if len(income) >= 2:
            latest = income[-1]
            prev = income[-2]
            
            # Revenue Growth
            rev_curr = latest.get("incTrev")
            rev_prev = prev.get("incTrev")
            if rev_curr and rev_prev:
                growth = ((rev_curr - rev_prev) / rev_prev) * 100
                rationale_text += f" Revenue Growth: {round(growth, 1)}% YoY."
            
            # Net Margin
            net_income = latest.get("incNinc")
            if net_income and rev_curr:
                margin = (net_income / rev_curr) * 100
                rationale_text += f" Net Margin: {round(margin, 1)}%."
    
    # Add Unified Insights (Screener + TickerTape + Generic Fundamentals)
    if request.fundamentals or request.checklist or request.screener_analysis or request.tickertape_analysis:
        rationale_text += "\n\n**Fundamental Analysis**\n"
        
        # 0. Generic Fundamentals (PE, PB from TickerTape/Screener fallback)
        if request.fundamentals:
            f = request.fundamentals
            rationale_text += f"- Metrics: PE {f.get('pe_ratio', 'N/A')} (Sector {f.get('sector_pe', 'N/A')}), PB {f.get('pb_ratio', 'N/A')}\n"
             
        if request.checklist:
             c = request.checklist
             # Colorize Scorecard values
             val = c.get('valuation','N/A')
             val_c = colorize(val, C_RED) if val == "High" else (colorize(val, C_GREEN) if val in ["Low", "Fair"] else val)
             
             prof = c.get('profitability','N/A')
             prof_c = colorize(prof, C_GREEN) if prof == "High" else (colorize(prof, C_RED) if prof == "Low" else prof)
             
             entry = c.get('entry_point','N/A')
             entry_c = colorize(entry, C_GREEN) if entry == "Good" else (colorize(entry, C_RED) if entry == "Bad" else entry)

             rationale_text += f"- Scorecard: Valuation {val_c}, Profitability {prof_c}, Entry {entry_c}\n"

        # 1. Screener Parts
        if request.screener_analysis:
            sc = request.screener_analysis
            
            pros = sc.get("pros", [])
            cons = sc.get("cons", [])
            if pros: rationale_text += f"- Strengths: {'; '.join(pros[:2])}\n"
            if cons: rationale_text += f"- Weaknesses: {'; '.join(cons[:2])}\n"
            
            sc_funds = sc.get("fundamentals", {})
            if sc_funds:
                roce = sc_funds.get("roce")
                roe = sc_funds.get("roe")
                if roce or roe:
                    vals = []
                    if roce: vals.append(f"ROCE {roce}%")
                    if roe: vals.append(f"ROE {roe}%")
                    rationale_text += f"- Efficiency: {', '.join(vals)}\n"

        # 2. TickerTape Parts
        if request.tickertape_analysis:
            tt = request.tickertape_analysis
            
            forecast = tt.get("forecast", {})
            if forecast:
                upside = forecast.get("upside")
                analyst_rating = forecast.get("analyst_rating")
                if upside: rationale_text += f"- Analyst Forecast: Upside {colorize(str(upside), C_GREEN)}\n"
                if analyst_rating: 
                    ar = str(analyst_rating)
                    c = C_GREEN if "Buy" in ar else (C_RED if "Sell" in ar else C_ORANGE)
                    rationale_text += f"- Analyst Consensus: {colorize(ar, c)}\n"
            
            tech_rating = tt.get("technical_rating") 
            if tech_rating:
                 tr = str(tech_rating)
                 c = C_GREEN if "Bullish" in tr else (C_RED if "Bearish" in tr else C_ORANGE)
                 rationale_text += f"- Technical Outlook: {colorize(tr, c)}\n"

    if penalty > 0:
        rationale_text += f" Note: Confidence reduced by {round(penalty*100)}% due to volatility risk."

    rationale = rationale_text
    logger.info(f"Generated rationale for {request.symbol}: {rationale}")

    # 4. Determine Direction
    direction = "UP" if np.mean([s["sentiment"] for s in request.signals]) > 0 else "DOWN"
    
    # 5. Calculate Levels (VIX Aware)
    vix = request.global_analysis.get("vix", 0.0) if request.global_analysis else 0.0
    levels = level_calculator.calculate_levels(request.current_price, request.atr, direction, vix)
    if not levels:
        return {"status": "error", "reason": "Failed to calculate levels"}
    
    # 6. Risk-Reward Guardrail
    if levels["rr"] < 2.0:
        return {"status": "ignored", "reason": "Insufficient risk-reward ratio", "rr": levels["rr"]}
    
    # Add Volatility Info to Rationale
    if vix > settings.VIX_HIGH:
        mult = levels.get("vix_multiplier", 1.0)
        rationale += f"\n\n**Volatility Alert**: India VIX at {vix}. Targets and Stop-Loss range widened by {round((mult-1)*100)}% to handle current market swings."
    
    # 7. Publish to Lifecycle
    recommendation = {
        "symbol": request.symbol,
        "direction": direction,
        "conviction": conviction,
        "rationale": rationale,
        "score_breakdown": scores,
        **levels
    }
    
    rec_id = lifecycle_engine.publish(request.symbol, recommendation)
    
    if not rec_id:
        return {"status": "suppressed", "reason": "Duplicate or lower conviction than active recommendation"}

    # 7. Broadcast via WebSocket
    await manager.broadcast({
        "type": "NEW_RECOMMENDATION",
        "data": recommendation
    })
    
    return {"status": "published", "id": rec_id, "recommendation": recommendation}

@app.get("/active")
async def get_active_recommendations(
    risk: Optional[str] = None, 
    horizon: Optional[str] = None, 
    sectors: Optional[str] = None
):
    recommendations = lifecycle_engine.get_active()
    
    # Simple filtering logic based on preferences
    if risk == "low":
        # Low risk users might not want bearish signals or high-volatility ones
        recommendations = [r for r in recommendations if r.get("direction") == "UP"]
    
    if sectors:
        preferred_sectors = sectors.split(",")
        # In a real app, we would map symbols to sectors. 
        # For now, we'll just allow all or implement a basic check if symbol is in a list.
        pass

    return recommendations

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.REC_ENGINE_PORT)

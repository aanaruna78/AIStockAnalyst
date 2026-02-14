
import asyncio
import pandas as pd
import httpx
import logging
import math
import random
from datetime import datetime, timedelta, timezone
import os
import re
from tickertape_crawler import TickerTapeCrawler
from screener_crawler import ScreenerCrawler
from global_market_crawler import GlobalMarketCrawler
from shared.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchCrawler")

# Service URLs from centralised config (overridden by env vars in Docker)
MARKET_DATA_URL = settings.MARKET_DATA_SERVICE_URL
REC_ENGINE_URL = settings.REC_ENGINE_URL
INGESTION_SERVICE_URL = settings.INGESTION_SERVICE_URL
SIGNAL_PROCESSOR_URL = settings.SIGNAL_PROCESSING_URL

STOCKS_CSV = "data/nse_stocks.csv"

# Persistent Crawlers
tt_crawler = TickerTapeCrawler("tickertape", "https://www.tickertape.in")
sc_crawler = ScreenerCrawler("screener", "https://www.screener.in")
global_crawler = GlobalMarketCrawler()

async def fetch_market_data(client, symbol, days=2):
    try:
        # Requesting OHLC for "today and last 1 day" (2 days total)
        response = await client.get(f"{MARKET_DATA_URL}/ohlc/{symbol}", params={"interval": "1D", "days": days})
        if response.status_code == 200:
            data = response.json()
            if data and "data" in data and len(data["data"]) > 0:
                return data["data"][-1]
    except Exception as e:
        logger.error(f"Failed to fetch market data for {symbol}: {e}")
    return None

async def fetch_news_signals(client, symbol, progress_callback=None):
    source_id = "SRC-03"
    source_url = "https://www.tradingview.com/ideas"
    try:
        response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}", params={"symbol": symbol})
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return result.get("signals", [])
    except Exception as e:
        logger.error(f"Failed to fetch news for {symbol}: {e}")
    return []

async def fetch_5paisa_recommendations(client, progress_callback=None):
    source_id = "SRC-05"
    if progress_callback:
        await progress_callback({"status": "processing", "log": "Scanning 5paisa for professional analyst picks..."})
    
    try:
        response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}")
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                recs = result.get("signals", [])
                if progress_callback:
                    await progress_callback({"status": "processing", "log": f"Found {len(recs)} active recommendations on 5paisa."})
                # Map by symbol for easy lookup
                return {r["metadata"]["symbol"]: r for r in recs}
    except Exception as e:
        logger.error(f"Failed to fetch 5paisa recs: {e}")
    return {}

async def fetch_moneycontrol_recommendations(client, progress_callback=None):
    source_id = "SRC-14"
    if progress_callback:
        await progress_callback({"status": "processing", "log": "Scanning Moneycontrol for latest analyst calls..."})
    
    try:
        response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}")
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                recs = result.get("signals", [])
                if progress_callback:
                    await progress_callback({"status": "processing", "log": f"Found {len(recs)} active calls on Moneycontrol."})
                # Map by symbol
                return {r["metadata"]["symbol"]: r for r in recs}
    except Exception as e:
        logger.error(f"Failed to fetch Moneycontrol recs: {e}")
    return {}

async def fetch_trendlyne_recommendations(client, progress_callback=None):
    source_id = "SRC-15"
    if progress_callback:
        await progress_callback({"status": "processing", "log": "Scanning Trendlyne for research reports..."})
    
    try:
        response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}")
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                recs = result.get("signals", [])
                if progress_callback:
                    await progress_callback({"status": "processing", "log": f"Found {len(recs)} reports on Trendlyne."})
                # Map by symbol
                return {r["metadata"]["symbol"]: r for r in recs}
    except Exception as e:
        logger.error(f"Failed to fetch Trendlyne recs: {e}")
    return {}

async def fetch_reddit_signals(client, progress_callback=None):
    sources = ["SRC-08", "SRC-09"]
    all_signals = []
    for source_id in sources:
        try:
            response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}")
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    all_signals.extend(result.get("signals", []))
        except Exception as e:
            logger.error(f"Failed to fetch Reddit signals for {source_id}: {e}")
    return all_signals

async def fetch_valuepickr_signals(client, progress_callback=None):
    source_id = "SRC-01"
    try:
        response = await client.post(f"{INGESTION_SERVICE_URL}/trigger/{source_id}")
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return result.get("signals", [])
    except Exception as e:
        logger.error(f"Failed to fetch ValuePickr signals: {e}")
    return []

async def analyze_sentiment(client, text, source_id="general"):
    """
    Call the signal-processing service to get sentiment and relevance.
    """
    try:
        resp = await client.post(
            f"{SIGNAL_PROCESSOR_URL}/process",
            json={"text": text, "source_id": source_id, "url": "batch_scan"}
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("sentiment", 0.0), data.get("relevance", 1.0)
    except Exception as e:
        logger.error(f"Signal processing failed: {e}")
    return 0.0, 1.0

def calculate_confidence(source, mentions):
    """
    Calculate confidence based on source credibility and mention count.
    ValuePickr (1.0) > TradingView (0.7) > Reddit (0.5)
    """
    base_credibility = {
        "ValuePickr": 1.0,
        "TradingView": 0.7,
        "Reddit": 0.5,
        "Moneycontrol": 0.9,
        "5paisa": 0.9,
        "Technical": 1.0
    }
    cred = base_credibility.get(source, 0.5)
    
    # Mention count boost (logarithmic)
    # Target 5 mentions for full confidence for community sources
    if source in ["Reddit", "ValuePickr", "TradingView"]:
        m_target = 5
        count_boost = min(1.0, math.log(1 + mentions) / math.log(1 + m_target))
        return cred * count_boost
    
    return cred

def calculate_freshness(timestamp_str=None):
    """
    Calculate freshness using exponential decay.
    For now, if no timestamp, assume 1.0 (recent).
    """
    if not timestamp_str:
        return 1.0
    
    try:
        # Assuming ISO format
        created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600
        
        # Exponential decay: half-life = 48 hours for general signals
        half_life = 48
        return math.exp(-0.693 * age_hours / half_life)
    except:
        return 1.0

def is_symbol_in_text(symbol, text):
    """
    Check if symbol exists in text as a whole word.
    """
    if not text:
        return False
    # Simple regex for word boundary
    pattern = r'\b' + re.escape(symbol.upper()) + r'\b'
    return bool(re.search(pattern, text.upper()))

async def process_symbol(client, symbol, five_paisa_recs=None, mc_recs=None, tl_recs=None, sig_context=None, global_analysis=None, progress_callback=None):
    logger.info(f"Processing {symbol}...")
    if progress_callback:
        await progress_callback({"status": "processing", "symbol": symbol, "log": f"Initializing analysis for {symbol} (Filter: Today + Last 24h)..."})
    
    # 1. Get Market Data
    if progress_callback:
        await progress_callback({"status": "processing", "symbol": symbol, "log": f"Fetching technical data from Dhan/yfinance for {symbol}..."})
    market_data = await fetch_market_data(client, symbol)
    if not market_data:
        logger.warning(f"No market data for {symbol}. Skipping.")
        if progress_callback:
            await progress_callback({"status": "processing", "symbol": symbol, "log": f"Warning: No valid market data found for {symbol} in requested timeframe. Skipping."})
        return

    # 2. Get News/Signals
    signals = await fetch_news_signals(client, symbol, progress_callback=progress_callback)
    
    # 2.5 Crawl TickerTape & Screener (New)
    if progress_callback:
        await progress_callback({"status": "processing", "symbol": symbol, "log": f"Fetching fundamental & analyst data (TickerTape/Screener)..."})
        
    tt_data = await tt_crawler.crawl_stock(symbol)
    screener_data = await sc_crawler.crawl_stock(symbol)
    
    fundamentals = tt_data.get("metrics", {})
    checklist = tt_data.get("checklist", {})
    financials = tt_data.get("financials", {})
    
    # 3. Prepare Recommendation Request
    engine_signals = []
    # (Note: TradingView signals are now handled in the dynamic sentiment filtering loop below)
    
    # fuzzy matcher helper
    def find_match(tgt_symbol, recs_map):
        if not recs_map:
            return None
        # 1. Exact match
        if tgt_symbol in recs_map:
            return recs_map[tgt_symbol]
        
        # 2. Fuzzy / Normalization match
        # Normalize: remove spaces, special chars
        tgt_clean = re.sub(r'[^A-Z0-9]', '', tgt_symbol)
        
        for key, val in recs_map.items():
            key_clean = re.sub(r'[^A-Z0-9]', '', key)
            
            # Check contains (e.g. KOTAK in KOTAKBANK or KOTAKMAHINDRA)
            # This is risky, e.g. "TATA" in "TATAMOTORS" and "TATASTEEL".
            # Better check: Startswith or known variations.
            
            # Specific mappings/heuristics
            # KOTAKBANK matches KOTAKMAHINDRA
            if tgt_clean.startswith("KOTAK") and key_clean.startswith("KOTAK"):
                return val
            
            # M&M vs MANDM
            if tgt_clean == "MM" and (key_clean == "MANDM" or key_clean == "MAHINDRAEXC"):
                 return val

            # Simple contains if length is sufficient to avoid noise
            if len(tgt_clean) > 3 and (tgt_clean in key_clean or key_clean in tgt_clean):
                # Verify first 3 chars match to ensure same group
                if tgt_clean[:3] == key_clean[:3]:
                    return val
                    
        return None

    # Add 5paisa if present
    rec = find_match(symbol, five_paisa_recs)
    if rec:
        engine_signals.append({
            "source": "5paisa",
            "sentiment": 1.0 if rec["metadata"]["action"].upper() == "BUY" else -1.0,
            "relevance": 1.0,
            "confidence": 0.9,
            "freshness": calculate_freshness(rec.get("timestamp")),
            "raw_text": rec["content"]
        })
        if progress_callback:
            await progress_callback({"status": "processing", "symbol": symbol, "log": f"Found matching analyst recommendation on 5paisa: {rec['metadata']['action']}"})
    
    # Add Moneycontrol if present
    rec = find_match(symbol, mc_recs)
    if rec:
        engine_signals.append({
            "source": "Moneycontrol",
            "sentiment": 1.0 if rec["metadata"]["action"].upper() == "BUY" else (-1.0 if rec["metadata"]["action"].upper() == "SELL" else 0.0),
            "relevance": 1.0,
            "confidence": 0.9,
            "freshness": calculate_freshness(rec.get("timestamp")),
            "raw_text": rec["content"]
        })
        if progress_callback:
            await progress_callback({"status": "processing", "symbol": symbol, "log": f"Found matching analyst call on Moneycontrol: {rec['metadata']['action']}"})

    # Add Trendlyne if present
    rec = find_match(symbol, tl_recs)
    if rec:
        action = rec["metadata"]["action"].upper()
        sent = 0.0
        if "BUY" in action or "ADD" in action:
            sent = 1.0
        elif "SELL" in action or "REDUCE" in action:
            sent = -1.0
            
        engine_signals.append({
            "source": "Trendlyne",
            "sentiment": sent,
            "relevance": 1.0,
            "confidence": 0.9,
            "freshness": calculate_freshness(rec.get("timestamp")),
            "raw_text": rec["content"]
        })
        if progress_callback:
            await progress_callback({"status": "processing", "symbol": symbol, "log": f"Found matching research report on Trendlyne: {action}"})

    # Add RSI Technical signal
    rsi = market_data.get("rsi")
    if rsi and rsi is not None:
        try:
            rsi_val = float(rsi)
            if rsi_val > 70:
                engine_signals.append({
                    "source": "Technical",
                    "sentiment": -0.8,
                    "relevance": 0.8,
                    "confidence": 1.0,
                    "freshness": 1.0,
                    "raw_text": f"RSI Overbought: {rsi_val}"
                })
            elif rsi_val < 30:
                engine_signals.append({
                    "source": "Technical",
                    "sentiment": 0.8,
                    "relevance": 0.8,
                    "confidence": 1.0,
                    "freshness": 1.0,
                    "raw_text": f"RSI Oversold: {rsi_val}"
                })
        except Exception:
            pass

    # 4. Filter generic signals (Reddit, ValuePickr, TradingView) by symbol
    # (Since these are global feeds, we keep only relevant ones for the current symbol)
    tradingview_matches = []
    for sig in signals:
        content = sig.get("content", "")
        if is_symbol_in_text(symbol, content):
            tradingview_matches.append(sig)
    
    if tradingview_matches:
        # Aggregate sentiment and calculate confidence
        total_sent = 0
        valid_hits = 0
        for sig in tradingview_matches:
            sentiment, relevance = await analyze_sentiment(client, sig.get("content", ""), source_id="TradingView")
            if relevance > 0.4:
                total_sent += sentiment
                valid_hits += 1
        
        if valid_hits > 0:
            avg_sent = total_sent / valid_hits
            confidence = calculate_confidence("TradingView", valid_hits)
            
            engine_signals.append({
                "source": "TradingView",
                "sentiment": avg_sent,
                "relevance": 0.8,
                "confidence": confidence,
                "freshness": 1.0,
                "raw_text": f"Aggregated {valid_hits} relevant ideas on TradingView"
            })

    # 5. Add Reddit & ValuePickr signals if keyword matches
    global_signals = sig_context.get("global_signals", []) if sig_context else []
    
    # Categorize by source for aggregation
    source_matches = {"Reddit": [], "ValuePickr": []}
    for sig in global_signals:
        content = sig.get("content", "")
        if is_symbol_in_text(symbol, content):
            source = sig.get("source", "Reddit")
            if source in source_matches:
                source_matches[source].append(sig)

    for source, matches in source_matches.items():
        if matches:
            total_sent = 0
            valid_hits = 0
            for sig in matches:
                sentiment, relevance = await analyze_sentiment(client, sig.get("content", ""), source_id=source)
                if relevance > 0.4:
                    total_sent += sentiment
                    valid_hits += 1
            
            if valid_hits > 0:
                avg_sent = total_sent / valid_hits
                confidence = calculate_confidence(source, valid_hits)
                
                engine_signals.append({
                    "source": source,
                    "sentiment": avg_sent,
                    "relevance": 0.7,
                    "confidence": confidence,
                    "freshness": 1.0,
                    "raw_text": f"Aggregated {valid_hits} relevant mentions on {source}"
                })
    
    logger.info(f"Aggregated {len(engine_signals)} total signals for {symbol} (Analysts + Community + Tech)")
    
    logger.info(f"Aggregated {len(engine_signals)} total signals for {symbol} (Analysts + Community + Tech)")

    rec_request = {
        "symbol": symbol,
        "current_price": market_data["close"],
        "atr": market_data.get("atr", 0.0),
        "indicators": market_data,
        "signals": engine_signals,
        "fundamentals": fundamentals,
        "checklist": checklist,
        "financials": financials,
        "screener_analysis": screener_data,
        "tickertape_analysis": tt_data,
        "global_analysis": global_analysis
    }
    
    # 4. Generate Recommendation
    if progress_callback:
        await progress_callback({"status": "processing", "symbol": symbol, "log": f"Sending signal fusion to AI Recommendation Engine (Signals: {len(engine_signals)})..."})
    try:
        resp = await client.post(f"{REC_ENGINE_URL}/generate", json=rec_request)
        if resp.status_code == 200:
            res_json = resp.json()
            logger.info(f"Recommendation for {symbol}: {res_json.get('status')} - {res_json.get('id', 'N/A')}")
            if progress_callback:
                status_msg = f"Success: AI Signal Fusion complete for {symbol}."
                if res_json.get("status") == "published":
                    status_msg += " RECOMMENDATION GENERATED!"
                await progress_callback({"status": "processing", "symbol": symbol, "log": status_msg})
        else:
            logger.error(f"Failed to generate recommendation: {resp.status_code} - {resp.text}")
            if progress_callback:
                await progress_callback({"status": "processing", "symbol": symbol, "log": f"Error: AI Engine reported failure for {symbol} ({resp.status_code})."})
    except Exception as e:
        logger.error(f"Error calling recommendation engine: {e}")
        if progress_callback:
            await progress_callback({"status": "processing", "symbol": symbol, "log": f"Error: Data pipe to AI Engine broken for {symbol}."})

async def run_batch(limit=None, target_symbol=None, progress_callback=None):
    if not os.path.exists(STOCKS_CSV):
        logger.error(f"Stock CSV not found at {STOCKS_CSV}")
        if progress_callback:
            await progress_callback({"status": "error", "message": "Stocks CSV not found"})
        return

    df = pd.read_csv(STOCKS_CSV)
    symbols = df['Symbol'].tolist()
    
    if target_symbol:
        symbols = [s for s in symbols if s == target_symbol.upper()]
        if not symbols:
             # If exact match fails, try containment
             symbols = [s for s in df['Symbol'].tolist() if target_symbol.upper() in s]
    
    if limit and not target_symbol:
        symbols = symbols[:limit]
        
    total = len(symbols)
    logger.info(f"Starting batch job for {total} symbols.")
    
    if progress_callback:
        await progress_callback({"status": "starting", "total": total, "current": 0})
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check services
        try:
            await client.get(f"{MARKET_DATA_URL}/health")
            await client.get(f"{REC_ENGINE_URL}/health")
        except Exception:
            logger.warning("One or more services might be down. Proceeding anyway...")

        # --- RANKING LOGIC ---
        # Pre-screen stocks to find "interesting" ones (e.g. RSI at extremes)
        # This fulfills: "Implement a ranking mechanism for recommendations to prioritize the best signals"
        if total > limit if limit else total:
            logger.info("Ranking stocks based on technical interest...")
            if progress_callback:
                await progress_callback({"status": "ranking", "message": "Pre-screening stocks for best signals..."})
            
            scored_symbols = []
            for symbol in symbols:
                m_data = await fetch_market_data(client, symbol)
                if m_data and m_data.get("rsi"):
                    rsi = float(m_data["rsi"])
                    # Score: deviation from 50 (higher is more overbought/oversold, i.e. "interesting")
                    score = abs(rsi - 50)
                    scored_symbols.append((symbol, score))
                else:
                    scored_symbols.append((symbol, 0))
            
            # Sort by score descending
            scored_symbols.sort(key=lambda x: x[1], reverse=True)
            symbols = [s[0] for s in scored_symbols]
            
            if limit:
                symbols = symbols[:limit]
                total = len(symbols)
        # ---------------------

        five_paisa_recs = await fetch_5paisa_recommendations(client, progress_callback=progress_callback)
        mc_recs = await fetch_moneycontrol_recommendations(client, progress_callback=progress_callback)
        tl_recs = await fetch_trendlyne_recommendations(client, progress_callback=progress_callback)
        
        # Fetch community signals once
        reddit_signals = await fetch_reddit_signals(client, progress_callback=progress_callback)
        vp_signals = await fetch_valuepickr_signals(client, progress_callback=progress_callback)
        
        # Prepare context for community signals (tagged with source)
        global_signals = []
        for s in reddit_signals:
            s["source"] = "Reddit"
            global_signals.append(s)
        for s in vp_signals:
            s["source"] = "ValuePickr"
            global_signals.append(s)
            
        sig_context = {"global_signals": global_signals}
        if progress_callback:
            await progress_callback({"status": "processing", "log": f"Community Hub: Found {len(global_signals)} signals across Reddit & ValuePickr."})

        # Fetch global market context (VIX, indices) once for all symbols
        global_analysis = None
        try:
            global_data = await global_crawler.fetch_sentiment()
            if global_data and isinstance(global_data, dict):
                global_analysis = {
                    "global_summary": global_data.get("global_summary", ""),
                    "global_score": global_data.get("global_score", 0.0),
                    "vix": global_data.get("vix", 0.0),
                    "indices": global_data.get("indices", {})
                }
                logger.info(f"Global Market Context: VIX={global_analysis['vix']}, Score={global_analysis['global_score']}")
        except Exception as e:
            logger.warning(f"Could not fetch global market data: {e}")

        processed = 0
        for symbol in symbols:
            processed += 1
            if progress_callback:
                await progress_callback({
                    "status": "processing", 
                    "symbol": symbol, 
                    "current": processed, 
                    "total": total,
                    "percentage": round((processed / total) * 100, 2),
                    "log": f"Switching context to {symbol} ({processed}/{total})..."
                })
            
            await process_symbol(client, symbol, five_paisa_recs=five_paisa_recs, mc_recs=mc_recs, tl_recs=tl_recs, sig_context=sig_context, global_analysis=global_analysis, progress_callback=progress_callback)
            # await asyncio.sleep(0.1) # Rate limit protection

    if progress_callback:
        await progress_callback({"status": "completed", "total": total, "current": total, "percentage": 100.0})

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of stocks to process")
    parser.add_argument("--symbol", type=str, default=None, help="Process specific symbol")
    args = parser.parse_args()
    
    # Quick hack to filter symbols if arg provided
    asyncio.run(run_batch(limit=args.limit, target_symbol=args.symbol))

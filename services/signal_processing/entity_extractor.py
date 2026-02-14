import re
import os
import csv
from typing import List, Dict, Set

class EntityExtractor:
    def __init__(self):
        # Dynamically load all NSE symbols from CSV
        self.symbol_map = self._load_symbols()
        
        # Regex for $SYMBOL format (e.g., $RELIANCE, $TCS)
        self.cashtag_regex = re.compile(r'\$([A-Z][A-Z0-9&-]{1,})')

    def _load_symbols(self) -> Dict[str, str]:
        """Load symbols from nse_stocks.csv, building symbol and name aliases."""
        symbol_map = {}
        
        # Try multiple paths (works both locally and in Docker)
        csv_paths = [
            os.path.join(os.path.dirname(__file__), "../../data/nse_stocks.csv"),
            "/app/data/nse_stocks.csv",
            "data/nse_stocks.csv"
        ]
        
        csv_file = None
        for p in csv_paths:
            if os.path.exists(p):
                csv_file = p
                break
        
        if csv_file:
            try:
                with open(csv_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sym = row["Symbol"].strip().upper()
                        name = row.get("Name", "").strip().upper()
                        
                        # Map the symbol to itself
                        symbol_map[sym] = sym
                        
                        # Map the full name
                        if name:
                            symbol_map[name] = sym
                            
                            # Also map key parts of the name:
                            # "Reliance Industries Limited" -> "RELIANCE INDUSTRIES"
                            # Remove "Limited", "Ltd", etc.
                            short_name = name.replace(" LIMITED", "").replace(" LTD", "").strip()
                            if short_name and short_name != sym:
                                symbol_map[short_name] = sym
                            
                            # First word (e.g., "RELIANCE", "INFOSYS") if it's >= 3 chars
                            first_word = name.split()[0] if name.split() else ""
                            if len(first_word) >= 4 and first_word != sym:
                                symbol_map[first_word] = sym
            except Exception as e:
                print(f"[EntityExtractor] Warning: Could not load symbols from CSV: {e}")
        
        # Hardcoded common aliases that CSV can't capture
        aliases = {
            "RIL": "RELIANCE", "SBI": "SBIN", "STATE BANK": "SBIN",
            "HDFC": "HDFCBANK", "ICICI": "ICICIBANK", "TATA MOTORS": "TMCV",
            "HUL": "HINDUNILVR", "BAJAJ FINANCE": "BAJFINANCE",
            "MAHINDRA": "M&M", "ZOMATO": "ETERNAL", "DMART": "DMART",
            "AVENUE SUPERMARTS": "DMART", "TATA STEEL": "TATASTEEL",
            "JSW": "JSWSTEEL", "ADANI PORTS": "ADANIPORTS",
            "COAL INDIA": "COALINDIA", "KOTAK": "KOTAKBANK",
            "NESTLE": "NESTLEIND", "ASIAN PAINTS": "ASIANPAINT",
            "ULTRA CEMENT": "ULTRACEMCO", "ULTRATECH": "ULTRACEMCO",
            "POWER GRID": "POWERGRID", "BAJAJ AUTO": "BAJAJ-AUTO",
            "ADANI GREEN": "ADANIGREEN", "SBI LIFE": "SBILIFE",
            "INDUSIND": "INDUSINDBK", "BHARTI AIRTEL": "BHARTIARTL",
            "AIRTEL": "BHARTIARTL"
        }
        symbol_map.update(aliases)
        
        print(f"[EntityExtractor] Loaded {len(symbol_map)} symbol mappings")
        return symbol_map

    def extract_entities(self, text: str) -> List[str]:
        found_symbols: Set[str] = set()
        
        # 1. Cashtag extraction
        cashtags = self.cashtag_regex.findall(text.upper())
        for tag in cashtags:
            if tag in self.symbol_map:
                found_symbols.add(self.symbol_map[tag])
            # Check if tag itself is a valid value in map (direct symbol usage)
            elif tag in self.symbol_map.values():
                found_symbols.add(tag)

        # 2. Keyword matching
        text_upper = text.upper()
        for keyword, symbol in self.symbol_map.items():
            # word boundary check to avoid partial matches (e.g. "REL" in "RELEASE")
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_upper):
                found_symbols.add(symbol)
                
        return list(found_symbols)

# Singleton
entity_extractor = EntityExtractor()

import re
from typing import List, Dict, Set

class EntityExtractor:
    def __init__(self):
        # A small subset of NSE stocks for demonstration.
        # In a real system, this would be loaded from a CSV/Database.
        self.symbol_map = {
            "RELIANCE": "RELIANCE",
            "RIL": "RELIANCE",
            "TCS": "TCS",
            "INFOSYS": "INFY",
            "INFY": "INFY",
            "HDFC BANK": "HDFCBANK",
            "HDFCBANK": "HDFCBANK",
            "TATA MOTORS": "TATAMOTORS",
            "TATAMOTORS": "TATAMOTORS",
            "SBIN": "SBIN",
            "SBI": "SBIN",
            "STATE BANK OF INDIA": "SBIN",
            "ICICI BANK": "ICICIBANK",
            "ICICIBANK": "ICICIBANK",
            "ITC": "ITC",
            "WIPRO": "WIPRO"
        }
        
        # Regex for $SYMBOL format (e.g., $RELIANCE, $TCS)
        self.cashtag_regex = re.compile(r'\$([A-Z]{3,})')

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

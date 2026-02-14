import asyncio
import sys
import os
import json
import logging
from unittest.mock import MagicMock
import httpx

# Setup logging
logging.basicConfig(level=logging.ERROR) # Quiet logs

# Adjust path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "services/ingestion_service")))

# Capture
captured_payload = None

# Save original before patching
OriginalAsyncClient = httpx.AsyncClient

# Spy Class
class SpyClient:
    def __init__(self, *args, **kwargs):
        # Delegate to real client
        self.client = OriginalAsyncClient(*args, **kwargs)
        
    async def __aenter__(self):
        await self.client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
        
    async def get(self, url, **kwargs):
        # Pass through real GET
        # print(f"SpyClient: Fetching {url}")
        return await self.client.get(url, **kwargs)

    async def post(self, url, json=None, **kwargs):
        global captured_payload
        # Intercept Engine POST
        if "18004/generate" in str(url):
            print(f"\n[SpyClient] INTERCEPTED POST to {url}")
            captured_payload = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp
        else:
            return await self.client.post(url, json=json, **kwargs)

# Patch globally
httpx.AsyncClient = SpyClient

from pipeline_runner import PipelineRunner  # noqa: E402

async def main():
    runner = PipelineRunner()
    print("Running process_stock for RELIANCE...")
    stock = {"Symbol": "RELIANCE", "Name": "Reliance Industries"}
    await runner.process_stock(stock)
    
    if captured_payload:
        print("\n--- CAPTURED PAYLOAD (Subset) ---")
        subset = {
            "symbol": captured_payload.get("symbol"),
            "fundamentals": captured_payload.get("fundamentals"),
            "checklist": captured_payload.get("checklist"),
            "financials_summary": {
                "income_statement_count": len(captured_payload.get("financials", {}).get("income_statement", [])),
                "latest_revenue": captured_payload.get("financials", {}).get("income_statement", [])[-1].get("incTrev") if captured_payload.get("financials", {}).get("income_statement") else "N/A"
            }
        }
        print(json.dumps(subset, indent=2))
        
        # Verify specific fields
        fund = captured_payload.get("fundamentals", {})
        print("\n--- Data Check ---")
        print(f"PE Ratio Present: {fund.get('pe_ratio') is not None}")
        print(f"Valuation Score: {captured_payload.get('checklist', {}).get('valuation')}")
    else:
        print("No payload captured.")

if __name__ == "__main__":
    asyncio.run(main())

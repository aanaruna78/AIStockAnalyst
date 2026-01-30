import asyncio
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

async def test_trendlyne():
    url = "https://trendlyne.com/research-reports/buy/"
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    
    print(f"Fetching {url} with headers...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers, timeout=15.0)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("Successfully fetched page.")
                soup = BeautifulSoup(response.text, "lxml")
                
                # Try to find the table
                # Based on typical structures, look for tables
                tables = soup.find_all("table")
                print(f"Found {len(tables)} tables.")
                
                if tables:
                    # Inspect the first table rows
                    table = tables[0]
                    rows = table.find_all("tr")
                    print(f"Table has {len(rows)} rows.")
                    
                    # Print first few rows to see structure
                    for i, row in enumerate(rows[:5]):
                        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                        print(f"Row {i}: {cells}")
                else:
                    print("No tables found. Dumping first 500 chars of body:")
                    print(soup.body.get_text(strip=True)[:500] if soup.body else "No body")
            else:
                print("Failed to fetch page.")
                print(f"Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_trendlyne())

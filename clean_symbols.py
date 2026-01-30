import json
import os

REC_FILE = "data/recommendations.json"
PORTFOLIO_FILE = "data/paper_trades.json"

def clean_recommendations():
    if not os.path.exists(REC_FILE):
        print(f"{REC_FILE} not found.")
        return

    with open(REC_FILE, "r") as f:
        data = json.load(f)

    # Filter out TATAMOTORS and ZOMATO
    new_data = {k: v for k, v in data.items() if "TATAMOTORS" not in k and "ZOMATO" not in k and v.get("symbol") not in ["TATAMOTORS", "ZOMATO"]}
    
    removed = len(data) - len(new_data)
    
    with open(REC_FILE, "w") as f:
        json.dump(new_data, f, indent=2)
    
    print(f"Removed {removed} legacy entries from {REC_FILE}")

def clean_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        print(f"{PORTFOLIO_FILE} not found (might be empty or in different loc).")
        return

    with open(PORTFOLIO_FILE, "r") as f:
        data = json.load(f)

    # Clean active trades
    if "active_trades" in data:
        original_count = len(data["active_trades"])
        data["active_trades"] = [t for t in data["active_trades"] if t["symbol"] not in ["TATAMOTORS", "ZOMATO"]]
        print(f"Removed {original_count - len(data['active_trades'])} active trades from portfolio")

    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    clean_recommendations()
    clean_portfolio()

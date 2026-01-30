from typing import List, Optional
from pydantic import BaseModel
from enum import Enum

class SourceTier(int, Enum):
    TIER_1 = 1  # High Priority
    TIER_2 = 2  # Medium Priority
    TIER_3 = 3  # Low Weight
    TIER_4 = 4  # News & Editorial

class SourceMetadata(BaseModel):
    id: str
    name: str
    base_url: str
    tier: SourceTier
    rate_limit_seconds: int
    robots_url: Optional[str] = None
    description: str

SOURCE_REGISTRY: List[SourceMetadata] = [
    SourceMetadata(
        id="SRC-01",
        name="ValuePickr Forum",
        base_url="https://forum.valuepickr.com",
        tier=SourceTier.TIER_1,
        rate_limit_seconds=5,
        robots_url="https://forum.valuepickr.com/robots.txt",
        description="Company-specific discussion threads for long-term sentiment."
    ),
    SourceMetadata(
        id="SRC-03",
        name="TradingView Ideas",
        base_url="https://www.tradingview.com",
        tier=SourceTier.TIER_1,
        rate_limit_seconds=10,
        robots_url="https://www.tradingview.com/robots.txt",
        description="Public trading ideas for direction bias and breakout mentions."
    ),
    SourceMetadata(
        id="SRC-08",
        name="Reddit IndianStockMarket",
        base_url="https://www.reddit.com/r/IndianStockMarket",
        tier=SourceTier.TIER_2,
        rate_limit_seconds=2,
        description="Momentum sentiment and hype tracking."
    ),
    SourceMetadata(
        id="SRC-09",
        name="Reddit Stocks",
        base_url="https://www.reddit.com/r/stocks",
        tier=SourceTier.TIER_2,
        rate_limit_seconds=2,
        description="Global market sentiment and sector trends."
    ),
    SourceMetadata(
        id="SRC-05",
        name="5paisa Recommendations",
        base_url="https://www.5paisa.com/share-market-today/stocks-to-buy-or-sell-today",
        tier=SourceTier.TIER_2,
        rate_limit_seconds=10,
        description="Daily Buy/Sell recommendations from 5paisa."
    ),
    SourceMetadata(
        id="SRC-13",
        name="Economic Times Markets",
        base_url="https://economictimes.indiatimes.com/markets",
        tier=SourceTier.TIER_4,
        rate_limit_seconds=5,
        description="News headlines and sentiment shift."
    ),
    SourceMetadata(
        id="SRC-14",
        name="Moneycontrol Stock Ideas",
        base_url="https://www.moneycontrol.com/markets/stock-ideas/",
        tier=SourceTier.TIER_2,
        rate_limit_seconds=5,
        description="Curated stock selection and analyst calls from Moneycontrol."
    ),
    SourceMetadata(
        id="SRC-15",
        name="Trendlyne Research",
        base_url="https://trendlyne.com/research-reports/buy/",
        tier=SourceTier.TIER_2,
        rate_limit_seconds=10,
        description="Broker research reports and buy recommendations from Trendlyne."
    )
]

def get_source_by_id(source_id: str) -> Optional[SourceMetadata]:
    for source in SOURCE_REGISTRY:
        if source.id == source_id:
            return source
    return None

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Direction(str, Enum):
    STRONG_UP = "Strong Up"
    STRONG_DOWN = "Strong Down"

class MarketRegime(str, Enum):
    TRENDING = "trending"
    CHOP = "chop"
    VOLATILE = "volatile"

class RecommendationBase(BaseModel):
    symbol: str
    direction: Direction
    entry_range: str
    target_1: float
    target_2: float
    stop_loss: float
    validity_window: str
    confidence_score: float
    rationale: str
    timestamp: datetime = datetime.now()

class Recommendation(RecommendationBase):
    id: str

class Signal(BaseModel):
    source: str
    content: str
    sentiment: float
    relevance: float
    confidence: float = 1.0
    freshness: float = 1.0
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.now()

# EPIC 1: User & Auth Models
class RiskTolerance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class InvestmentHorizon(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"
    LONG_TERM = "long_term"

class UserPreferences(BaseModel):
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    investment_horizon: InvestmentHorizon = InvestmentHorizon.SWING
    preferred_sectors: List[str] = []
    max_allocation_per_trade: float = 0.1  # 10%

class BrokerType(str, Enum):
    NONE = "none"
    DHAN = "dhan"
    ANGELONE = "angelone"

class BrokerConfig(BaseModel):
    broker_type: BrokerType = BrokerType.NONE
    # Dhan credentials
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None
    # AngelOne credentials
    angelone_api_key: Optional[str] = None
    angelone_client_id: Optional[str] = None
    angelone_password: Optional[str] = None
    angelone_totp_secret: Optional[str] = None
    # Common
    is_active: bool = False  # User must explicitly enable live trading

class UserProfile(BaseModel):
    full_name: str
    email: str
    picture: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    preferences: UserPreferences = UserPreferences()
    onboarded: bool = False

class User(UserProfile):
    id: str
    hashed_password: Optional[str] = None
    google_id: Optional[str] = None
    login_history: List[dict] = []
    broker_config: BrokerConfig = BrokerConfig()

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str

class UserRegister(BaseModel):
    """Registration request with password confirmation."""
    email: str
    password: str
    confirm_password: str
    full_name: str

class OTPVerifyRequest(BaseModel):
    email: str
    otp: str

class OTPResendRequest(BaseModel):
    email: str

class LoginRequest(BaseModel):
    email: str
    password: str

class PendingUser(BaseModel):
    """User awaiting OTP verification."""
    email: str
    full_name: str
    hashed_password: str
    otp: str
    otp_created_at: datetime = datetime.now()
    last_resend_at: datetime = datetime.now()

# EPIC 3: Paper Trading Models
class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class TradeType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class Trade(BaseModel):
    id: str
    symbol: str
    type: TradeType
    status: TradeStatus
    entry_price: float
    quantity: int
    entry_time: datetime
    current_price: Optional[float] = None
    
    # Exit details (Optional until closed)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = 0.0
    pnl_percent: Optional[float] = 0.0
    
    # Strategy details
    target: float
    stop_loss: float
    conviction: float
    rationale_summary: Optional[str] = None

class Portfolio(BaseModel):
    cash_balance: float = 100000.0
    realized_pnl: float = 0.0
    active_trades: List[Trade] = []
    trade_history: List[Trade] = []
    last_updated: datetime = datetime.now()

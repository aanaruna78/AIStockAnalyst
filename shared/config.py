from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class GlobalConfig(BaseSettings):
    # Platform Info
    PLATFORM_NAME: str = "SignalForge"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Dhan API Configuration
    DHAN_CLIENT_ID: Optional[str] = None
    DHAN_ACCESS_TOKEN: Optional[str] = None
    DHAN_ENV: str = "production"

    # Auth Configuration
    JWT_SECRET: str = "your-super-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Email / OTP Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = "aanaruna@gmail.com"
    SMTP_PASSWORD: str = ""  # set via .env
    SMTP_FROM_NAME: str = "SignalForge"
    OTP_EXPIRE_MINUTES: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 30

    # Recommendation Thresholds (Control Section)
    MIN_CONFIDENCE_SCORE: float = 0.15  # 15% directional conviction (bidirectional: distance from neutral)
    MAX_TRADES_PER_DAY: int = 5
    DEFAULT_VALIDITY_MINUTES: int = 240  # 4 hours
    STRICT_STOP_LOSS: bool = True

    # Service Discovery & Ports
    API_GATEWAY_PORT: int = 8000
    REC_ENGINE_PORT: int = 18004
    INGESTION_SERVICE_PORT: int = 8002
    PREDICTION_SERVICE_PORT: int = 8001
    MARKET_DATA_SERVICE_PORT: int = 8003
    SIGNAL_PROCESSING_PORT: int = 8004
    TRADING_SERVICE_PORT: int = 8005
    FRONTEND_PORT: int = 3000

    # Service Discovery URLs (Internal)
    # When running in Docker, these are overridden via environment variables
    # to use Docker service names (e.g. http://ingestion-service:8000)
    API_GATEWAY_URL: str = "http://localhost:8000"
    INGESTION_SERVICE_URL: str = "http://localhost:8002"
    INGESTION_WS_URL: str = "ws://localhost:8002"
    PREDICTION_SERVICE_URL: str = "http://localhost:8001"
    REC_ENGINE_URL: str = "http://localhost:18004"
    REC_ENGINE_WS_URL: str = "ws://localhost:18004"
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    SIGNAL_PROCESSING_URL: str = "http://localhost:8004"
    TRADING_SERVICE_URL: str = "http://localhost:8005"
    AI_MODEL_SERVICE_URL: str = "http://localhost:18005"
    ALERT_SERVICE_URL: str = "http://localhost:18006"
    
    # Ingestion Settings
    DEFAULT_SCAN_INTERVAL: int = 10  # minutes

    # Scoring Weights
    BASE_WEIGHT_SENTIMENT: float = 0.20
    BASE_WEIGHT_TECHNICAL: float = 0.20
    BASE_WEIGHT_ML: float = 0.25
    BASE_WEIGHT_FUNDAMENTAL: float = 0.20
    BASE_WEIGHT_ANALYST: float = 0.15

    # Regime Thresholds
    REGIME_ADX_TRENDING: int = 25
    REGIME_ATR_RATIO_VOLATILE: float = 1.5
    REGIME_ATR_RATIO_RISK: float = 1.3

    # Indicator Thresholds
    RSI_OVERSOLD: int = 30
    RSI_OVERBOUGHT: int = 70

    # VIX Thresholds
    VIX_BASELINE: float = 15.0
    VIX_HIGH: float = 20.0
    VIX_EXTREME: float = 25.0

    # ML & AI thresholds
    ML_CONFIDENCE_FLOOR: float = 0.5
    ML_FETCH_TIMEOUT: float = 5.0
    
    # Analyst Thresholds (TickerTape)
    ANALYST_UPSIDE_MID: float = 10.0
    ANALYST_UPSIDE_HIGH: float = 20.0
    ANALYST_BUY_PERCENT_HIGH: int = 80
    ANALYST_BUY_PERCENT_MID: int = 50
    ANALYST_BUY_PERCENT_LOW: int = 30

    # UI Colors (Hex)
    COLOR_GREEN: str = "#27c93f"
    COLOR_RED: str = "#ff5f56"
    COLOR_ORANGE: str = "#ffbd2e"
    COLOR_CYAN: str = "#00e5ff"

    # Pipeline Constants
    STOCKS_FILE_PATH: str = "data/nse_stocks.csv"
    CRAWLER_DELAY_SECONDS: float = 2.0
    PIPELINE_BATCH_SIZE: int = 5
    PIPELINE_LOOP_INTERVAL_SECONDS: int = 10800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Singleton instance
settings = GlobalConfig()

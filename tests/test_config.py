"""Tests for shared/config.py — GlobalConfig defaults and overrides."""
from shared.config import GlobalConfig


class TestGlobalConfigDefaults:
    """Ensure all default values are sane."""

    def test_platform_name(self):
        cfg = GlobalConfig()
        assert cfg.PLATFORM_NAME == "SignalForge"

    def test_environment_default(self):
        cfg = GlobalConfig()
        assert cfg.ENVIRONMENT == "development"

    def test_debug_default(self):
        cfg = GlobalConfig()
        assert cfg.DEBUG is True

    def test_jwt_defaults(self):
        cfg = GlobalConfig()
        assert cfg.ALGORITHM == "HS256"
        assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24 * 7  # 1 week

    def test_recommendation_thresholds(self):
        cfg = GlobalConfig()
        assert 0 < cfg.MIN_CONFIDENCE_SCORE < 1
        assert cfg.MAX_TRADES_PER_DAY >= 1
        assert cfg.DEFAULT_VALIDITY_MINUTES > 0

    def test_scoring_weights_sum_to_one(self):
        cfg = GlobalConfig()
        total = (
            cfg.BASE_WEIGHT_SENTIMENT
            + cfg.BASE_WEIGHT_TECHNICAL
            + cfg.BASE_WEIGHT_ML
            + cfg.BASE_WEIGHT_FUNDAMENTAL
            + cfg.BASE_WEIGHT_ANALYST
        )
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_vix_thresholds_ordered(self):
        cfg = GlobalConfig()
        assert cfg.VIX_BASELINE < cfg.VIX_HIGH < cfg.VIX_EXTREME

    def test_rsi_thresholds_ordered(self):
        cfg = GlobalConfig()
        assert cfg.RSI_OVERSOLD < cfg.RSI_OVERBOUGHT

    def test_service_ports_unique(self):
        cfg = GlobalConfig()
        ports = [
            cfg.API_GATEWAY_PORT,
            cfg.REC_ENGINE_PORT,
            cfg.INGESTION_SERVICE_PORT,
            cfg.PREDICTION_SERVICE_PORT,
            cfg.MARKET_DATA_SERVICE_PORT,
            cfg.SIGNAL_PROCESSING_PORT,
            cfg.TRADING_SERVICE_PORT,
            cfg.FRONTEND_PORT,
        ]
        assert len(ports) == len(set(ports)), "Service ports must be unique"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_NAME", "TestForge")
        cfg = GlobalConfig()
        assert cfg.PLATFORM_NAME == "TestForge"

    def test_optional_fields_default_none(self):
        cfg = GlobalConfig()
        # These should be None when not set via env
        assert cfg.DHAN_CLIENT_ID is None or isinstance(cfg.DHAN_CLIENT_ID, str)
        assert cfg.DHAN_ACCESS_TOKEN is None or isinstance(cfg.DHAN_ACCESS_TOKEN, str)

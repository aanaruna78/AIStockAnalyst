"""Tests for services/ingestion_service/provenance.py — provenance tracking."""
from datetime import datetime
from services.ingestion_service.provenance import ProvenanceTracker


class TestProvenanceTracker:
    def test_create_provenance_basic(self):
        p = ProvenanceTracker.create_provenance(
            source_id="screener_in",
            url="https://screener.in/company/RELIANCE/",
        )
        assert p["source_id"] == "screener_in"
        assert p["url"] == "https://screener.in/company/RELIANCE/"
        assert p["confidence_adjustment"] == 0.0
        # ingested_at should be a valid ISO 8601 string
        dt = datetime.fromisoformat(p["ingested_at"])
        assert isinstance(dt, datetime)

    def test_create_provenance_with_delta(self):
        p = ProvenanceTracker.create_provenance(
            source_id="trendlyne",
            url="https://trendlyne.com/stock/123",
            confidence_delta=0.15,
        )
        assert p["confidence_adjustment"] == 0.15

    def test_create_provenance_negative_delta(self):
        p = ProvenanceTracker.create_provenance(
            source_id="unknown",
            url="https://example.com",
            confidence_delta=-0.1,
        )
        assert p["confidence_adjustment"] == -0.1

    def test_provenance_keys(self):
        p = ProvenanceTracker.create_provenance(source_id="test", url="http://test.com")
        expected_keys = {"source_id", "url", "ingested_at", "confidence_adjustment"}
        assert set(p.keys()) == expected_keys

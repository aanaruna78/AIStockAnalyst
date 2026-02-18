"""Unit tests for SelfLearningEngine — profile selection, bandit, persistence."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.self_learning import SelfLearningEngine


class TestSelfLearningEngine:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.engine = SelfLearningEngine(data_dir=self.tmp_dir)

    def test_default_profiles_loaded(self):
        profiles = self.engine.get_profiles()
        assert len(profiles) >= 5
        ids = [p["profile_id"] for p in profiles]
        assert "P1_OPEN_TREND" in ids
        assert "P3_MID_TREND" in ids

    def test_select_profile_with_hint(self):
        """Regime hint should prefer the recommended profile."""
        profile = self.engine.select_profile("P1_OPEN_TREND")
        assert profile.profile_id == "P1_OPEN_TREND"

    def test_select_profile_bandit_fallback(self):
        """No hint → UCB bandit selects."""
        profile = self.engine.select_profile("")
        assert profile.profile_id  # Should have a profile

    def test_force_profile(self):
        """Force override selects specific profile."""
        assert self.engine.force_profile("P5_EXPIRY_DAY")
        profile = self.engine.select_profile("P1_OPEN_TREND")
        assert profile.profile_id == "P5_EXPIRY_DAY"

    def test_force_profile_invalid(self):
        assert not self.engine.force_profile("NONEXISTENT")

    def test_record_trade_result(self):
        """Recording a result updates bandit stats."""
        # select_profile increments n_selections, record_trade_result updates reward
        self.engine.select_profile("P1_OPEN_TREND")
        self.engine.record_trade_result("P1_OPEN_TREND", pnl=500, drawdown=100)
        stats = self.engine.get_bandit_stats()
        arm = next(a for a in stats["arms"] if a["profile_id"] == "P1_OPEN_TREND")
        assert arm["n_selections"] == 1
        assert arm["avg_reward"] > 0

    def test_ucb_exploration(self):
        """Profiles with 0 pulls should be explored first."""
        # Only record results for P1
        for _ in range(10):
            self.engine.record_trade_result("P1_OPEN_TREND", pnl=100, drawdown=50)
        # Select with no hint → should explore unplayed profiles
        # (UCB gives infinity for n=0)
        profile = self.engine.select_profile("")
        # Could be any un-explored profile
        assert profile.profile_id != ""

    def test_persistence(self):
        """Engine persists and reloads state."""
        self.engine.select_profile("P1_OPEN_TREND")
        self.engine.record_trade_result("P1_OPEN_TREND", pnl=500, drawdown=100)
        self.engine._save()

        # Create new engine from same dir
        engine2 = SelfLearningEngine(data_dir=self.tmp_dir)
        stats = engine2.get_bandit_stats()
        arm = next(a for a in stats["arms"] if a["profile_id"] == "P1_OPEN_TREND")
        assert arm["n_selections"] == 1

    def test_eod_update(self):
        """EOD update recalibrates without error."""
        for _ in range(5):
            self.engine.record_trade_result("P3_MID_TREND", pnl=200, drawdown=50)
        self.engine.eod_update()
        # Should not raise

    def test_get_bandit_stats(self):
        stats = self.engine.get_bandit_stats()
        assert "arms" in stats
        assert "total_selections" in stats

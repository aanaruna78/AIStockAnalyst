"""Unit tests for PremiumSimulator — Greeks, tick, spread model."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.premium_simulator import PremiumSimulator


class TestPremiumSimulator:
    def test_ce_premium_positive(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                              days_to_expiry=3.0, iv=15.0)
        assert sim.premium > 0

    def test_pe_premium_positive(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="PE",
                              days_to_expiry=3.0, iv=15.0)
        assert sim.premium > 0

    def test_itm_ce_higher_than_otm(self):
        itm = PremiumSimulator(spot=23100, strike=23000, option_type="CE", days_to_expiry=3.0)
        otm = PremiumSimulator(spot=22900, strike=23000, option_type="CE", days_to_expiry=3.0)
        assert itm.premium > otm.premium

    def test_itm_pe_higher_than_otm(self):
        itm = PremiumSimulator(spot=22900, strike=23000, option_type="PE", days_to_expiry=3.0)
        otm = PremiumSimulator(spot=23100, strike=23000, option_type="PE", days_to_expiry=3.0)
        assert itm.premium > otm.premium

    def test_tick_increases_premium_on_spot_up_ce(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE", days_to_expiry=3.0)
        initial = sim.premium
        sim.tick(new_spot=23050, elapsed_seconds=60)
        assert sim.premium > initial

    def test_tick_decreases_premium_on_spot_down_ce(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE", days_to_expiry=3.0)
        initial = sim.premium
        sim.tick(new_spot=22950, elapsed_seconds=60)
        assert sim.premium < initial

    def test_tick_pe_inverse(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="PE", days_to_expiry=3.0)
        initial = sim.premium
        sim.tick(new_spot=22950, elapsed_seconds=60)
        assert sim.premium > initial  # PE gains when spot falls

    def test_theta_decay(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                              days_to_expiry=3.0, iv=15.0)
        initial = sim.premium
        # Tick with same spot, just time passes
        sim.tick(new_spot=23000, elapsed_seconds=3600)
        assert sim.premium < initial  # Theta decay

    def test_iv_increase_raises_premium(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                              days_to_expiry=3.0, iv=15.0)
        initial = sim.premium
        sim.tick(new_spot=23000, elapsed_seconds=60, iv_change=2.0)
        assert sim.premium > initial

    def test_breakout_iv_adjustment(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                              days_to_expiry=3.0, iv=15.0)
        initial_iv = sim.iv
        sim.tick(new_spot=23000, elapsed_seconds=60, is_breakout=True)
        assert sim.iv > initial_iv

    def test_chop_iv_adjustment(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                              days_to_expiry=3.0, iv=15.0)
        initial_iv = sim.iv
        sim.tick(new_spot=23000, elapsed_seconds=60, is_chop=True)
        assert sim.iv < initial_iv

    def test_greeks_structure(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE", days_to_expiry=3.0)
        g = sim.greeks
        assert hasattr(g, 'delta')
        assert hasattr(g, 'gamma')
        assert hasattr(g, 'theta')
        assert hasattr(g, 'vega')
        assert 0 < g.delta < 1  # CE delta between 0 and 1
        assert g.gamma > 0
        assert g.theta < 0  # Theta is negative (time decay)

    def test_to_dict(self):
        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE", days_to_expiry=3.0)
        d = sim.to_dict()
        assert "premium" in d
        assert "greeks" in d
        assert "spot" in d

    def test_premium_floor(self):
        """Premium should never go below 0.01."""
        sim = PremiumSimulator(spot=23000, strike=25000, option_type="CE",
                              days_to_expiry=0.1, iv=5.0)
        # Deep OTM should still have minimum premium
        assert sim.premium >= 0.01

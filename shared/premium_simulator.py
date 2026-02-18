"""
PremiumSimulator — Greeks-Based Option Premium Simulation
==========================================================
Realistic premium estimation using Delta/Gamma/Theta/Vega
for meaningful paper trading when real option ticks are unavailable.

Premium update per risk-loop tick::

    premium_t = premium_prev + Δ·ΔS + 0.5·Γ·(ΔS²) - Θ·Δt + Vega·ΔIV - spread_cost

Realistic behaviour:
  - Gamma increases as expiry approaches
  - Theta increases later in day
  - IV rises during breakouts, falls in chop
  - Spread widens when IV rises or volume drops
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class GreeksSnapshot:
    """Instantaneous greeks for an ATM option."""
    delta: float = 0.50       # ATM ≈ 0.50
    gamma: float = 0.002      # sensitivity of delta to spot move
    theta: float = -2.0       # time decay per day (₹)
    vega: float = 5.0         # premium change per 1% IV move
    iv: float = 15.0          # implied volatility (%)


@dataclass
class SpreadModel:
    """Bid-ask spread model tied to regime + volume."""
    base_spread_pct: float = 0.3      # 0.3% of premium in normal conditions
    iv_multiplier: float = 0.5        # spread widens 0.5× per 1% IV rise
    volume_floor: float = 0.5         # if vol_ratio < this, widen spread
    volume_widen_factor: float = 1.5  # spread × this when volume is low
    max_spread_pct: float = 2.0       # cap


class PremiumSimulator:
    """
    Simulates option premium dynamics for paper trading.

    Usage::

        sim = PremiumSimulator(spot=23000, strike=23000, option_type="CE",
                               days_to_expiry=3, iv=15.0)
        # Each tick (1–5s):
        premium = sim.tick(new_spot=23015, elapsed_seconds=5, iv_change=0.1)
    """

    def __init__(
        self,
        spot: float,
        strike: float,
        option_type: str = "CE",
        days_to_expiry: float = 3.0,
        iv: float = 15.0,
        lot_size: int = 65,
    ):
        self.spot = spot
        self.strike = strike
        self.option_type = option_type.upper()  # "CE" or "PE"
        self.dte = max(days_to_expiry, 0.01)
        self.iv = iv
        self.lot_size = lot_size

        # Initialise greeks
        self._greeks = self._compute_greeks()
        self.premium = self._bs_price()
        self._spread_model = SpreadModel()

    # ------------------------------------------------------------------
    # Public tick
    # ------------------------------------------------------------------

    def tick(
        self,
        new_spot: float,
        elapsed_seconds: float = 1.0,
        iv_change: float = 0.0,
        volume_ratio: float = 1.0,
        is_breakout: bool = False,
        is_chop: bool = False,
    ) -> float:
        """
        Advance simulation by one tick.  Returns updated premium.

        Parameters
        ----------
        new_spot : latest underlying spot
        elapsed_seconds : time since last tick
        iv_change : manual IV adjustment (±%)
        volume_ratio : current_vol / avg_vol
        is_breakout : if True, IV gets a bump
        is_chop : if True, IV drops slightly
        """
        ds = new_spot - self.spot
        dt_days = elapsed_seconds / 86400.0
        self.dte = max(self.dte - dt_days, 0.001)
        self.spot = new_spot

        # ── IV adjustment ──
        if is_breakout:
            iv_change += 0.5   # IV rises during breakouts
        if is_chop:
            iv_change -= 0.2   # IV compresses in chop
        self.iv = max(5.0, self.iv + iv_change)

        # ── Recompute greeks (they change with spot / dte / IV) ──
        self._greeks = self._compute_greeks()
        g = self._greeks

        # ── Premium update formula ──
        delta_component = g.delta * ds
        gamma_component = 0.5 * g.gamma * ds * ds
        theta_component = g.theta * dt_days
        vega_component = g.vega * iv_change

        # Spread cost (half spread per tick as slippage proxy)
        spread = self._compute_spread(volume_ratio)
        spread_cost = spread * 0.5  # half-spread cost

        new_premium = self.premium + delta_component + gamma_component + theta_component + vega_component - spread_cost
        self.premium = max(0.05, round(new_premium, 2))
        return self.premium

    # ------------------------------------------------------------------
    # Greeks computation (simplified Black-Scholes-like)
    # ------------------------------------------------------------------

    def _compute_greeks(self) -> GreeksSnapshot:
        s = self.spot
        k = self.strike
        t = self.dte / 365.0
        sigma = self.iv / 100.0
        is_call = self.option_type == "CE"

        if t <= 0 or sigma <= 0:
            # At or past expiry
            intrinsic = max(0, s - k) if is_call else max(0, k - s)
            return GreeksSnapshot(
                delta=1.0 if intrinsic > 0 else 0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                iv=self.iv,
            )

        sqrt_t = math.sqrt(t)
        d1 = (math.log(s / k) + (0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
        # d2 = d1 - sigma * sqrt_t

        # ── Delta ──
        nd1 = self._norm_cdf(d1)
        delta = nd1 if is_call else nd1 - 1.0

        # ── Gamma ── (same for call/put)
        nprime_d1 = self._norm_pdf(d1)
        gamma = nprime_d1 / (s * sigma * sqrt_t) if s > 0 else 0.0

        # ── Theta ── (per day, in premium terms)
        theta_annual = -(s * nprime_d1 * sigma) / (2 * sqrt_t)
        theta_daily = theta_annual / 365.0

        # ── Vega ── (per 1% IV change)
        vega = s * nprime_d1 * sqrt_t / 100.0  # per 1% IV

        return GreeksSnapshot(
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta=round(theta_daily, 2),
            vega=round(vega, 2),
            iv=round(self.iv, 2),
        )

    def _bs_price(self) -> float:
        """Black-Scholes price (simplified, no risk-free rate)."""
        s = self.spot
        k = self.strike
        t = self.dte / 365.0
        sigma = self.iv / 100.0
        is_call = self.option_type == "CE"

        if t <= 0 or sigma <= 0:
            return max(0, s - k) if is_call else max(0, k - s)

        sqrt_t = math.sqrt(t)
        d1 = (math.log(s / k) + (0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
        d2 = d1 - sigma * sqrt_t

        if is_call:
            price = s * self._norm_cdf(d1) - k * self._norm_cdf(d2)
        else:
            price = k * self._norm_cdf(-d2) - s * self._norm_cdf(-d1)

        return max(0.05, round(price, 2))

    # ------------------------------------------------------------------
    # Spread model
    # ------------------------------------------------------------------

    def _compute_spread(self, volume_ratio: float = 1.0) -> float:
        """Compute bid-ask spread in ₹."""
        m = self._spread_model
        base = self.premium * m.base_spread_pct / 100.0

        # IV-based widening
        iv_excess = max(0, self.iv - 15.0)
        iv_widen = iv_excess * m.iv_multiplier / 100.0 * self.premium

        # Volume-based widening
        vol_widen = 0.0
        if volume_ratio < m.volume_floor:
            vol_widen = base * m.volume_widen_factor

        spread = base + iv_widen + vol_widen
        max_spread = self.premium * m.max_spread_pct / 100.0
        return min(spread, max_spread)

    @property
    def spread_pct(self) -> float:
        """Current spread as % of premium."""
        if self.premium <= 0:
            return 0.0
        return round(self._compute_spread() / self.premium * 100, 3)

    @property
    def greeks(self) -> GreeksSnapshot:
        return self._greeks

    # ------------------------------------------------------------------
    # Normal distribution helpers (no scipy dependency)
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Cumulative distribution function for standard normal."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        """Probability density function for standard normal."""
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "spot": self.spot,
            "strike": self.strike,
            "option_type": self.option_type,
            "dte": round(self.dte, 4),
            "iv": self.iv,
            "premium": self.premium,
            "greeks": {
                "delta": self._greeks.delta,
                "gamma": self._greeks.gamma,
                "theta": self._greeks.theta,
                "vega": self._greeks.vega,
            },
            "spread_pct": self.spread_pct,
        }

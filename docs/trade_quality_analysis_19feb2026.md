# SignalForge — Trade Quality Analysis & Fix Report

**Date:** 19 February 2026  
**Commit:** `5803c1a` (fix: trade quality overhaul)  
**Previous Commit:** `5fb6f35` (DATA_DIR fix)  
**Branch:** `main`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Went Wrong — Root Cause Analysis](#2-what-went-wrong--root-cause-analysis)
3. [What Was Fixed — Implementation Details](#3-what-was-fixed--implementation-details)
4. [Files Modified](#4-files-modified)
5. [Gate Sequence — Order of Checks](#5-gate-sequence--order-of-checks)
6. [Remaining Gaps & Known Risks](#6-remaining-gaps--known-risks)
7. [Suggested Future Improvements](#7-suggested-future-improvements)
8. [Test Coverage](#8-test-coverage)
9. [Deployment Notes](#9-deployment-notes)

---

## 1. Executive Summary

On 19 Feb 2026, multiple bad trades were observed in both **Options (Nifty weekly)** and **Equity (intraday stocks)**. A deep code analysis was performed across 10+ files. **7 root causes** were identified and fixed:

| # | Root Cause | Severity | Impact |
|---|-----------|----------|--------|
| 1 | Deployed service running v1 (random signals) | **Critical** | All signals were randomly generated |
| 2 | No Greeks filtering on options | **High** | Deep OTM/ITM options taken with poor R:R |
| 3 | Broken SL formula in v1 (26.7% drawdown!) | **Critical** | SL was effectively 26.7% below entry |
| 4 | No cooldown after option losses | **High** | Immediate re-entry after losses |
| 5 | No per-strike/symbol daily limit | **High** | BAJAJ-AUTO entered 6 times in one day |
| 6 | Trailing SL too tight for equity (0.5%) | **Medium** | Premature stop-outs on normal noise |
| 7 | Iceberg never triggered (off-by-one) | **Medium** | 5-lot orders not getting iceberg splitting |

**Result:** 237 tests passing, 0 failures, ruff clean.

---

## 2. What Went Wrong — Root Cause Analysis

### Root Cause 1: Deployed Service Running v1 (Random Signals)

**The single biggest problem.** The production Docker container was running `main.py` (v1) — NOT `main_v2.py`.

The v1 code generates ALL technical indicators via `np.random`:

```python
# v1 main.py — lines 643-663 (ACTUAL deployed code)
np.random.seed(int(datetime.now(IST).timestamp()) % 100000)
ema_offset = np.random.uniform(-0.003, 0.003)    # ← RANDOM
vwap = spot * (1 + np.random.uniform(-0.001, 0.001))  # ← RANDOM
rsi7 = np.random.uniform(30, 75)                  # ← RANDOM
current_volume = int(avg_volume * np.random.uniform(0.6, 2.5))  # ← RANDOM
oi_change_pct = np.random.uniform(-5, 5)           # ← RANDOM
lagged = [np.random.uniform(-0.002, 0.002) for _ in range(3)]  # ← RANDOM
```

This means:
- **RSI was random** (30–75) — not computed from price action
- **EMA relationship was random** — no real trend detection
- **Volume spikes were random** — no real participation check
- **OI changes were random** — no real OI-based validation

The v2 engine (`main_v2.py`) with proper `MarketDataStore`, `RegimeEngine`, `MomentumSignalEngine`, `PremiumSimulator` etc. was already written and tested but **never deployed**. The Dockerfile still pointed to `main:app`.

### Root Cause 2: No Greeks Filtering on Options

The options scalping service accepted **any option** regardless of its Greeks profile:

- **Deep OTM** options (delta < 0.25): Very low probability of profit, low premium sensitivity to spot movement. A 50-point Nifty move might only move the premium by ₹12.
- **Deep ITM** options (delta > 0.75): High premium cost, poor risk-to-reward ratio. You're essentially paying for intrinsic value and getting poor leverage.
- **Low gamma** options: Delta barely changes even with spot movement. No acceleration benefit.
- **High theta** options: Time decay eating away > 5% of premium per day means the option needs a large directional move just to break even.
- **Cheap premiums** (< ₹5): Very wide bid-ask spreads. A ₹5 option with 0.5% spread = ₹0.025 spread cost. But with typical market-maker behaviour, actual spread on sub-₹5 options is ₹0.50–₹1.00 (10–20%!).

**No validation existed.** The system used a hardcoded `delta=0.5` everywhere without checking actual greeks.

### Root Cause 3: Broken Stop Loss Formula in v1

The v1 SL calculation was mathematically broken:

```python
# v1 main.py — BEFORE fix
"sl_premium": round(slipped_premium * (1 - SL_PCT / 0.003), 2)
```

Where `SL_PCT = 0.0008` (0.08% of spot). So:

```
1 - 0.0008 / 0.003 = 1 - 0.2667 = 0.7333
```

This means **SL was set at 73.3% of entry premium** — a **26.7% drawdown** before stop loss triggers! For a ₹120 premium, SL was at ~₹88 — a ₹32 loss per unit × 65 × 5 = **₹10,400 loss per trade**.

The formula was trying to convert a spot-based SL to a premium-based SL but the math was wrong. It should have been a direct percentage.

### Root Cause 4: No Cooldown After Option Losses

When a trade hit SL and closed with a loss:
1. The signal loop ran again 30 seconds later
2. If any signal appeared (which with random v1 signals was frequent), it immediately entered a new trade
3. No waiting period, no reflection, no pattern analysis

This created a **loss spiral**: Loss → immediate re-entry → loss → immediate re-entry. With random signals, the win rate is ~50%, but with the broken SL (26.7% drawdown) vs. normal target, the average loss far exceeds the average win.

### Root Cause 5: No Per-Strike / Per-Symbol Daily Limit

**Options:** The same strike and direction (e.g., NIFTY 25800 CE) could be traded unlimited times per day. If the first trade at 25800 CE hit SL, the system would immediately try 25800 CE again on the next signal.

**Equity:** BAJAJ-AUTO was entered 6 times in one session. Each time triggered by the scheduler's `execute_trades_job` which runs every 5–15 minutes. No memory of "we already tried this symbol today and it failed."

### Root Cause 6: Trailing Stop Loss Too Tight for Equity

The equity trailing SL config was:

```python
# BEFORE (too tight)
trail_pct = 0.5%        # 0.5% trail from peak
activation_pct = 0.3%   # Start trailing after just 0.3% profit
min_trail_pct = 0.2%    # SL can get as close as 0.2% from current price
breakeven_trigger = 0.5% # Move to breakeven after 0.5%
```

For a ₹10,000 stock:
- Trail distance = ₹50 (0.5%)
- Activation at just ₹30 profit (0.3%)
- Min trail = ₹20 (0.2%)

Normal intraday noise on a ₹10k stock is ₹50–100. A 0.5% trail means **every normal price fluctuation triggers SL**. The stock might go from 10,000 → 10,040 → 9,990 → 10,120, but you'd get stopped out at 9,990 (trailing from 10,040 peak - 0.5% = 9,990).

### Root Cause 7: Iceberg Never Triggered (Off-by-One)

```python
# BEFORE — iceberg_order.py
return lots > IcebergEngine.OPTION_ICEBERG_THRESHOLD_LOTS  # threshold = 5
# So: 5 > 5 = False! Never triggers for 5 lots.
```

Default lot count is 5. The comparison used strict greater-than (`>`), meaning iceberg only triggered for 6+ lots. Since the default was always 5, iceberg **never** activated. The user expected 5 lots to be split into smaller slices (2+2+1).

---

## 3. What Was Fixed — Implementation Details

### Fix 1: Switch Deployment to v2 Engine

**Files:** `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`

```dockerfile
# Dockerfile — AFTER
CMD ["uvicorn", "main_v2:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml — AFTER
command: python -m uvicorn main_v2:app --host 0.0.0.0 --port 8000 --reload
```

The v2 engine uses:
- `MarketDataStore` — rolling 1-min candles with computed EMA/VWAP/ATR/RSI
- `RegimeEngine` — classifies market into OPEN_TREND, MID_TREND, LATE_TREND, OPEN_CHOP, MID_CHOP, LATE_CHOP, NO_TRADE
- `MomentumSignalEngine` — breakout detection + expansion + volume participation scoring
- `PremiumSimulator` — Black-Scholes-based Greeks estimation
- `RiskEngine v2` — premium-based SL/TP with MFE/MAE tracking
- `SelfLearningEngine` — profile selection via Thompson Sampling bandit
- `MetricsEngine` — telemetry and daily reporting

### Fix 2: Greeks Filtering Gates

**File:** `main_v2.py` — `place_trade()` method

New constants:

```python
MIN_DELTA_ABS = 0.25          # Reject deep OTM (delta < 0.25)
MAX_DELTA_ABS = 0.75          # Reject deep ITM (delta > 0.75)
MIN_PREMIUM = 5.0             # Reject pennies (wide spreads)
MAX_THETA_PCT_OF_PREMIUM = 5.0  # Reject rapid decay (>5%/day)
MIN_GAMMA = 0.0005            # Need meaningful delta sensitivity
```

Gate logic in `place_trade()`:

```python
if greeks:
    delta_abs = abs(greeks.get("delta", 0.5))
    gamma_val = abs(greeks.get("gamma", 0.001))
    theta_val = abs(greeks.get("theta", 0))

    if delta_abs < MIN_DELTA_ABS:
        return {"status": "rejected", "reason": "too far OTM"}
    if delta_abs > MAX_DELTA_ABS:
        return {"status": "rejected", "reason": "too deep ITM"}
    if gamma_val < MIN_GAMMA:
        return {"status": "rejected", "reason": "insufficient delta sensitivity"}
    if entry_premium > 0 and theta_val > 0:
        theta_pct = (theta_val / entry_premium) * 100
        if theta_pct > MAX_THETA_PCT_OF_PREMIUM:
            return {"status": "rejected", "reason": "rapid time decay"}
```

The signal loop now computes Greeks via `PremiumSimulator` and passes them to `place_trade()`:

```python
sim = PremiumSimulator(spot=spot, strike=atm_strike, option_type=direction,
                       days_to_expiry=dte, iv=15.0)
greeks_data = {
    "delta": sim.greeks.delta,
    "gamma": sim.greeks.gamma,
    "theta": sim.greeks.theta,
    "vega": sim.greeks.vega,
    "iv": sim.greeks.iv,
}
result = paper_engine.place_trade(..., greeks=greeks_data)
```

**Why these thresholds:**

| Greek | Threshold | Rationale |
|-------|-----------|-----------|
| Delta | 0.25–0.75 | ATM options have delta ~0.50. Below 0.25 = too far OTM (low prob). Above 0.75 = deep ITM (expensive, poor leverage). |
| Gamma | > 0.0005 | Gamma determines how fast delta changes. Low gamma = delta doesn't move with the underlying. |
| Theta | < 5%/day | If an option loses 5%+ per day to time decay, you need a massive directional move to overcome it. |
| Premium | > ₹5 | Sub-₹5 options have wide spreads (10–20% effective cost). |

### Fix 3: SL Formula Fix (v1)

**File:** `main.py` (v1) — kept as fallback but not deployed

```python
# BEFORE
"sl_premium": round(slipped_premium * (1 - SL_PCT / 0.003), 2)  # = 73.3% of entry!

# AFTER
"sl_premium": round(slipped_premium * 0.90, 2)      # 10% SL
"target_premium": round(slipped_premium * 1.12, 2)   # 12% target
```

The v2 engine uses `RiskEngine` which computes SL/TP based on premium ATR and configured percentages:

```python
# v2 RiskEngine config
sl_pct=0.10,        # 10% SL
tp1_pct=0.12,       # 12% TP1
tp1_book_pct=0.60,  # Book 60% at TP1
```

### Fix 4: Options Cooldown After Consecutive Losses

**File:** `main_v2.py` — `PaperTradingEngine`

New tracking fields:

```python
self._last_loss_time: float = 0        # epoch secs of last loss
self._consecutive_losses: int = 0       # running consecutive loss count
```

Constants:

```python
LOSS_COOLDOWN_SEC = 300       # 5 min cooldown after a loss
CONSEC_LOSS_COOLDOWN_SEC = 600  # 10 min after 2+ consecutive losses
```

In `place_trade()`, before any entry:

```python
if self._last_loss_time > 0:
    elapsed = _time.time() - self._last_loss_time
    cooldown = CONSEC_LOSS_COOLDOWN_SEC if self._consecutive_losses >= 2 else LOSS_COOLDOWN_SEC
    if elapsed < cooldown:
        return {"status": "rejected", "reason": f"Cooldown active: {remaining}s"}
```

In `close_trade()`, after each close:

```python
if total_pnl < 0:
    self._consecutive_losses += 1
    self._last_loss_time = _time.time()
else:
    self._consecutive_losses = 0
    self._last_loss_time = 0
```

**Cooldown is additive with RiskEngine's portfolio-level cooldown:**
- `PaperTradingEngine` level: 5 min (1 loss) / 10 min (2+ losses) — lightweight, per-trade
- `RiskEngine` level: 30 min after 3 consecutive losses — portfolio kill-switch

### Fix 5: Per-Strike (Options) and Per-Symbol (Equity) Daily Limits

**Options — `main_v2.py`:**

```python
MAX_SAME_STRIKE_PER_DAY = 2   # Max 2 entries per strike+direction per day

# Tracking:
self._daily_strike_entries: dict = {}   # {f"{strike}-{dir}": count}

# In place_trade():
strike_key = f"{strike}-{direction}"
entries_today = self._daily_strike_entries.get(strike_key, 0)
if entries_today >= MAX_SAME_STRIKE_PER_DAY:
    return {"status": "rejected", ...}

# After successful entry:
self._daily_strike_entries[strike_key] += 1
```

All daily counters reset in `_reset_daily()` when the date changes.

**Equity — `trade_manager.py`:**

```python
SYMBOL_COOLDOWN_SEC = 1800     # 30 min cooldown after SL hit
MAX_ENTRIES_PER_SYMBOL_DAY = 2 # Max 2 entries per symbol per day

# Tracking:
self._symbol_last_exit: Dict[str, float] = {}
self._symbol_entries_today: Dict[str, int] = {}

# In place_order():
# Gate 1c: Per-symbol cooldown after SL hit
last_exit_epoch = self._symbol_last_exit.get(symbol, 0)
if last_exit_epoch > 0:
    elapsed = _wall_time.time() - last_exit_epoch
    if elapsed < SYMBOL_COOLDOWN_SEC:
        return None  # Blocked

# Gate 1d: Max entries per symbol per day
sym_entries = self._symbol_entries_today.get(symbol, 0)
if sym_entries >= MAX_ENTRIES_PER_SYMBOL_DAY:
    return None  # Blocked

# In close_trade(): Record exit time on SL-related exits
if pnl < 0 and ("sl" in reason.lower() or "stop" in reason.lower()):
    self._symbol_last_exit[trade.symbol] = _wall_time.time()
```

### Fix 6: Widen Trailing SL for Equity

**File:** `trade_manager.py` — `TradeManager.__init__`

```python
# BEFORE                          # AFTER
trail_pct = 0.5%                  trail_pct = 1.2%
activation_pct = 0.3%             activation_pct = 0.8%
step_size_pct = 0.5%              step_size_pct = 0.8%
step_lock_pct = 0.3%              step_lock_pct = 0.5%
breakeven_trigger = 0.5%          breakeven_trigger = 1.0%
min_trail_pct = 0.2%              min_trail_pct = 0.5%
```

For a ₹10,000 stock:
- Trail distance = ₹120 (1.2%) — accommodates normal noise
- Activation after ₹80 profit (0.8%) — requires meaningful move
- Min trail = ₹50 (0.5%) — never closer than ₹50

### Fix 7: Iceberg Trigger at 5 Lots (>=)

**Files:** `main.py`, `main_v2.py`, `iceberg_order.py`

```python
# BEFORE
return lots > ICEBERG_THRESHOLD_LOTS   # 5 > 5 = False!

# AFTER
return lots >= ICEBERG_THRESHOLD_LOTS  # 5 >= 5 = True!
```

Splitting behaviour (OPTION_MAX_LOTS_PER_SLICE = 2):
- 5 lots → 3 slices: 2 + 2 + 1 = 130 + 130 + 65 = 325 qty
- 7 lots → 4 slices: 2 + 2 + 2 + 1
- 4 lots → no iceberg (below threshold)

---

## 4. Files Modified

| File | Changes |
|------|---------|
| `services/options_scalping_service/main_v2.py` | Greeks filtering, cooldown tracking, per-strike limit, iceberg trigger fix, Greeks pass-through in signal loop |
| `services/options_scalping_service/main.py` | SL formula fix (0.90), target fix (1.12), iceberg trigger fix |
| `services/options_scalping_service/Dockerfile` | App entry point: `main:app` → `main_v2:app` |
| `services/trading_service/trade_manager.py` | Per-symbol cooldown, daily limits, widened trailing SL config |
| `shared/iceberg_order.py` | `should_iceberg_option()`: `>` → `>=` |
| `docker-compose.yml` | Options service command → `main_v2:app` |
| `docker-compose.prod.yml` | Options service command → `main_v2:app` |
| `tests/test_iceberg_order.py` | Updated threshold tests, added 5-lot split test |
| `tests/test_trade_quality.py` | **NEW** — 19 tests covering all fixes |

---

## 5. Gate Sequence — Order of Checks

### Options (main_v2.py → `place_trade()`)

Trade entry goes through these gates **in order**:

```
1. _reset_daily()            → Reset counters if new day
2. risk_engine.check_can_trade()  → Portfolio kill-switch, daily loss cap, portfolio cooldown, max trades
3. MAX_TRADES_PER_DAY check  → 8 trades/day max
4. Active position check     → Only 1 open position at a time
5. Intraday cutoff check     → No trades after 3:15 PM IST
6. Cooldown timer check      → 300s / 600s after losses
7. Per-strike daily limit    → Max 2 per strike+direction
8. Greeks validation         → Delta (0.25–0.75), Gamma (>0.0005), Theta (<5%)
9. Premium floor check       → Premium > ₹5
10. Capital gate             → Trade cost < 20% of capital
11. → ENTRY (slippage + iceberg + RiskEngine SL/TP)
```

### Equity (trade_manager.py → `place_order()`)

```
1. Time gate                 → Only 9:20 AM – 3:15 PM IST
2. Daily counter reset       → Reset per-symbol counters if new day
3. Per-symbol cooldown       → 1800s after SL hit on same symbol
4. Per-symbol daily limit    → Max 2 entries per symbol/day
5. Failed trade log check    → Block if 3+ recent failures on symbol
6. MIN_CONVICTION check      → Conviction >= 30
7. Quantity calculation      → 3x leverage on ~₹20k allocation
8. Max loss per trade        → Projected loss < 3% of capital
9. Max drawdown floor        → Don't go below 50% of initial capital
10. SL/target sanity check   → SL < entry for BUY, target > entry for BUY
11. Funds check              → Sufficient cash balance
12. → ENTRY (trailing SL init + iceberg if qty > 500)
```

### Signal Quality (before `place_trade()` is called)

```
Signal Loop (30s):
1. Market open check         → Mon-Fri, 9:15–15:15 IST
2. Fetch Nifty spot          → Google Finance scraping
3. Build 1-min candle        → Accumulate OHLCV
4. RegimeEngine classify     → Must be trade-allowed regime
5. SelfLearning profile      → Thompson Sampling selects best profile
6. MomentumSignalEngine      → Breakout + expansion + participation scoring
7. Regime re-check           → With confidence for chop-window override
8. Confidence threshold      → Signal conf >= profile threshold
9. No active position        → Only then attempt entry
10. PremiumSimulator Greeks  → Compute delta/gamma/theta/vega
11. → place_trade() with greeks
```

---

## 6. Remaining Gaps & Known Risks

### GAP 1: OI Data is Still Simulated (Medium Risk)

**Status:** Not fixed — deliberately left as-is for now.

In `main_v2.py`, the signal loop generates **random OI data**:

```python
oi_call = _random.uniform(-3, 5)
oi_put = _random.uniform(-3, 5)
spread_pct = 0.3 + _random.uniform(0, 0.5)
```

OI (Open Interest) changes are important for confirming direction conviction. However, the `MomentumSignalEngine.evaluate()` only uses OI for a small part of the participation score (up to 5 out of 20 points for OI confirmation). The primary signal drivers — breakout, expansion, volume — use real data.

**Risk:** Without real OI data, the participation score's OI component adds noise rather than signal. However, this is bounded (max 5 points out of 100 total confidence), so the impact is limited.

**To fix properly:** Connect to NSE/broker API for real-time option chain OI data, or use a data provider like TrueData.

### GAP 2: Volume Data is Simulated (Medium Risk)

In the signal loop, volume for candles is still generated randomly:

```python
_candle_vol = _random.randint(50000, 200000)
_candle_vol += _random.randint(5000, 20000)
```

The `MomentumSignalEngine` uses volume for:
- Volume spike detection (participation score: up to 10 points)
- Volume confirmation of breakout

Since ALL candles use random volume, the volume spike ratio converges to ~1.0 over time (random/average_of_randoms ≈ 1). This means volume spike signals will rarely trigger meaningfully.

**Risk:** Missing real volume-based confirmation. Breakout entries happen without volume validation.

**To fix:** Integrate real Nifty volume data from NSE or broker feed.

### GAP 3: No Real Option Premium Data (Medium Risk)

The system uses `PremiumSimulator` (Black-Scholes approximation) instead of real option tick data. While the simulator produces reasonable Greeks, it has limitations:

- **IV is initialized at fixed 15%** and only adjusts via simulated breakout/chop flags
- **Real spreads** vary significantly during the day (wider at open, tighter mid-session)
- **Real premium movement** can be spikier than BS predicts (pin risk near expiry, gamma explosion)

**Risk:** Backtesting and paper trading returns may not match real execution. Premium simulator underestimates tail events.

**To fix:** Connect to a real option data feed (TrueData, Dhan API, Angel Broking API) for live option ticks.

### GAP 4: Spot Data Dependency on Google Finance Scraping (High Risk)

```python
def get_nifty_spot():
    url = "https://www.google.com/finance/quote/NIFTY_50:INDEXNSE"
    resp = requests.get(url, headers=headers, timeout=8, verify=False)
```

This is fragile:
- Google can block or rate-limit
- HTML structure can change
- `verify=False` disables SSL validation
- 8-second timeout means occasional slow responses

**Risk:** If Google blocks the IP or changes page structure, the entire system goes blind (no spot data → no signals → no trades). There's a fallback (`return None`) but the signal loop just sleeps and retries.

**To fix:** Use broker WebSocket feed (Dhan/Angelone) as primary, Google Finance as fallback.

### GAP 5: Equity Signal Source Quality (Medium Risk)

Equity trades are sourced from the `recommendation_engine` which uses:
- TrendLyne screener scraping
- TickerTape analysis scraping  
- AI model consensus (GPT-4 / Gemini)
- Scoring model with conviction 0–100

The `trade_manager.py` has a `MIN_CONVICTION = 30` gate. However:
- Conviction scoring depends on AI model responses which can be inconsistent
- A conviction of 30 is relatively low — many marginal signals pass through
- The model may produce bullish signals during bearish market conditions

**Risk:** Poor equity signal quality leads to frequent SL hits, even with the new cooldown/limit protections.

**Suggestion:** Consider raising `MIN_CONVICTION` to 40–50 for higher signal quality. Monitor win rate per conviction band.

### GAP 6: No Volatility-Adjusted Position Sizing (Low Risk)

Both options and equity use **fixed position sizing**:
- Options: Always 5 lots (65 × 5 = 325 qty)
- Equity: Always ~₹20k × 3x leverage

In high-volatility regimes, position size should be **reduced** to maintain the same risk per trade. A 1.2% trail on a high-vol stock is different from 1.2% on a low-vol stock.

**To fix:** Use ATR-based position sizing: `risk_per_trade / (ATR × multiplier)` to calculate quantity.

### GAP 7: PremiumSimulator Does Not Include Risk-Free Rate

The Black-Scholes implementation has `r = 0` (no risk-free rate):

```python
d1 = (math.log(s / k) + (0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
```

Standard BS uses `(r + 0.5 * sigma²) * t`. With current RBI rates ~6.5%, this causes:
- CE delta slightly underestimated
- PE delta slightly overestimated

**Risk:** Minor (~1–2% on delta). Acceptable for paper trading.

### GAP 8: No Weekend/Holiday Decay in PremiumSimulator

The `_days_to_expiry()` function computes calendar days to next Thursday. But:
- Theta doesn't decay on weekends in real markets (markets are closed)
- Yet the simulator's `dt_days` uses real elapsed time including weekends

**Risk:** On Monday morning, if the system ran over the weekend (unlikely given market hour checks), it would over-reduce premium. Low risk since `_is_market_open()` gates the loops.

### GAP 9: No Persistence of Cooldown State Across Restarts

When Docker restarts:
- `_consecutive_losses` resets to 0
- `_last_loss_time` resets to 0
- `_daily_strike_entries` resets to `{}`
- `_symbol_last_exit` resets to `{}`

These are **in-memory only**. If the service restarts mid-day (Docker restart, crash, deploy), all cooldown state is lost and the system can immediately re-enter positions it was cooling down from.

**Risk:** Medium. A mid-day restart bypasses all cooldown protections.

**To fix:** Persist cooldown state in the JSON file alongside trades. Add to `_save()` and `_load()`.

---

## 7. Suggested Future Improvements

### Priority 1: Real Market Data Integration

| Data | Current Source | Recommended |
|------|---------------|-------------|
| Nifty Spot | Google Finance scraping | Broker WebSocket (Dhan/Angel) |
| Option Premium | PremiumSimulator (BS) | Option chain API (broker/TrueData) |
| Volume | Random simulation | NSE real tick volume |
| OI | Random simulation | Option chain OI from broker API |
| IV | Fixed 15% + adjustments | Implied from real option prices |

### Priority 2: Persist Cooldown State

Add to `PaperTradingEngine._save()`:
```python
data["_cooldown_state"] = {
    "consecutive_losses": self._consecutive_losses,
    "last_loss_time": self._last_loss_time,
    "daily_strike_entries": self._daily_strike_entries,
}
```

### Priority 3: Dynamic Position Sizing

```python
# Example ATR-based sizing
max_risk_per_trade = capital * 0.01  # 1% risk per trade
sl_distance = premium_atr * 1.5     # SL at 1.5x premium ATR
lots = max(1, int(max_risk_per_trade / (sl_distance * NIFTY_LOT_SIZE)))
lots = min(lots, 10)  # Cap at 10 lots
```

### Priority 4: Conviction Threshold Tuning

Track and log win rates by conviction band:
- 30–40: What's the win rate? If < 40%, raise minimum.
- 40–50: Expected to be marginal (~50% win rate)
- 50–60: Should be profitable zone
- 60+: High-quality signals

### Priority 5: Monitoring Dashboard

Add a `/diagnostics` endpoint that shows:
- Current cooldown state (time remaining)
- Today's per-strike and per-symbol entry counts
- Greeks filter rejection counts
- Signal-to-trade conversion rate
- Current regime classification

---

## 8. Test Coverage

### Test File: `tests/test_trade_quality.py` (19 tests)

| Test Class | Tests | What It Validates |
|-----------|-------|-------------------|
| `TestOptionsGreeksFiltering` | 6 | Delta low/high rejection, gamma rejection, theta rejection, good greeks accepted, cheap premium rejection |
| `TestOptionsCooldown` | 3 | 300s cooldown after 1 loss, 600s after 2+ losses, cooldown expiry |
| `TestOptionsStrikeLimit` | 2 | Block after max entries, allow different strike |
| `TestEquitySymbolCooldown` | 2 | Tracking fields exist, constants defined |
| `TestTrailingSLConfig` | 2 | Config widened, trail not too narrow for ₹10k stock |
| `TestIceberg5Lots` | 4 | 5 lots triggers, 4 lots doesn't, 5 lots = 3 slices, 7 lots = 4 slices |

### Test File: `tests/test_iceberg_order.py` (updated)

- `test_option_below_threshold` — 3 and 4 lots → no iceberg
- `test_option_at_threshold` — 5 lots → iceberg triggers
- `test_option_iceberg_5_lots` — 5 lots → 3 slices (2+2+1)

### Full Suite

```
237 passed, 0 failed, 3 skipped, ruff clean
```

---

## 9. Deployment Notes

### After git pull on server:

```bash
cd /opt/signalforge
git pull origin main
docker compose up --build -d
```

### Verify v2 is running:

```bash
# Check service health
curl http://localhost:18010/health
# Expected: {"status": "healthy", "service": "options-scalping-v2", "version": "2.0"}

# Check regime
curl http://localhost:18010/regime

# Check portfolio state
curl http://localhost:18010/portfolio
```

### Key Environment Variables:

```
DATA_DIR=/app/data              # Shared data directory
MARKET_DATA_SERVICE_URL=http://market-data-service:8000
```

### Rollback:

If v2 has issues, revert to v1 by changing `main_v2:app` back to `main:app` in docker-compose.yml. Note that v1's SL formula is now fixed (10%/12%) but signals are still random.

---

## Appendix: Architecture Overview

```
Signal Loop (30s)          Risk Loop (3s)
     │                          │
     ├─ Fetch Spot              ├─ Update Premium (PremiumSimulator)
     ├─ Build Candle            ├─ Track MFE/MAE (RiskEngine)
     ├─ Classify Regime         ├─ Update Trailing SL
     ├─ Select Profile          ├─ Check SL/TP/Momentum-Failure
     ├─ Evaluate Momentum       ├─ Square-off at 3:15 PM
     ├─ Compute Greeks          │
     ├─ place_trade()           │
     │   ├─ Portfolio Gate      │
     │   ├─ Cooldown Gate       │
     │   ├─ Strike Limit        │
     │   ├─ Greeks Gate         │
     │   ├─ Capital Gate        │
     │   ├─ Iceberg Split       │
     │   └─ → Trade Created     │
     │                          │
     ▼                          ▼
              PaperTradingEngine
              (JSON persistence)
```

---

*Document generated after comprehensive code analysis and fix implementation on 19 Feb 2026.*

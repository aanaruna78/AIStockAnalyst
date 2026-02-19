# SignalForge — AI-Powered Stock Intelligence Platform

## Comprehensive Platform Overview, Business Value & Benefits

**Version:** 2.0 | **Date:** 19 February 2026  
**Platform:** AIStockAnalyst (SignalForge)  
**Author:** ThinkHive Labs  
**Audience:** Founders, Product Leaders, Investment Advisory Teams, Engineering, FinOps

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Problem](#2-business-problem)
3. [Platform Overview](#3-platform-overview)
4. [Architecture & Services](#4-architecture--services)
5. [Core Intelligence Engines](#5-core-intelligence-engines)
6. [Trading & Execution](#6-trading--execution)
7. [Risk Management Framework](#7-risk-management-framework)
8. [Frontend & User Experience](#8-frontend--user-experience)
9. [Data Sources & Ingestion](#9-data-sources--ingestion)
10. [Shared Engine Library](#10-shared-engine-library)
11. [Testing & Quality Assurance](#11-testing--quality-assurance)
12. [Deployment & Infrastructure](#12-deployment--infrastructure)
13. [Strategic Business Values](#13-strategic-business-values)
14. [Quantifiable Benefits](#14-quantifiable-benefits)
15. [Competitive Differentiators](#15-competitive-differentiators)
16. [Adoption Roadmap](#16-adoption-roadmap)
17. [Technology Stack Summary](#17-technology-stack-summary)

---

## 1. Executive Summary

SignalForge is an **AI-powered stock intelligence and autonomous trading platform** designed for the Indian equity and derivatives market (NSE). It combines technical indicators, multi-source sentiment analysis, fundamental metrics, and machine learning into a unified **conviction scoring model (S.T.A.F.A)** — producing explainable, multi-factor BUY/SELL recommendations with automated trade execution.

The platform operates as **13 independent microservices** orchestrated via Docker Compose, with a React-based enterprise dashboard, fully autonomous intraday trading agent, and a dedicated Nifty options scalping engine. It runs 24/7 on DigitalOcean infrastructure with automated deployment pipelines.

**Key Numbers at a Glance:**

| Metric | Value |
|--------|-------|
| Microservices | 13 (+ Kafka optional) |
| Data Sources | 9 crawlers across 15+ financial platforms |
| NSE Stocks Covered | Full NSE universe (CSV-driven) |
| Test Coverage | 240 tests across 20 test files |
| Shared Engines | 12 specialized modules |
| Frontend Pages | 20 pages/views |
| Lines of Code | ~15,000+ (Python + React) |
| Deployment | Docker Compose on DigitalOcean |

---

## 2. Business Problem

Traditional equity analysis workflows face four recurring constraints:

### Fragmented Data Sources
Technical indicators, sentiment signals, analyst reports, and fundamental data sit in separate tools — TradingView for charts, ValuePickr for discussions, Screener for fundamentals, broker platforms for execution. Analysts spend more time switching contexts than analyzing opportunities.

### Slow Analysis Cycles
Manual data collection, reconciliation, and cross-referencing across tools creates a 30–60 minute cycle per stock. In fast-moving intraday markets, this lag means missed entries and exits.

### Inconsistent Decision-Making
Human-only interpretation produces variable outcomes. Two analysts looking at the same stock may reach opposite conclusions based on which data they weight most heavily. No standardized scoring framework exists.

### Scaling Limitations
Manual processes don't scale. Covering 50 stocks with the same depth as 10 requires 5x analyst headcount. There is no leverage mechanism for research throughput.

**These constraints compound**: higher cost per insight, delayed actionability, inconsistent recommendations, and limited coverage breadth.

---

## 3. Platform Overview

SignalForge addresses these constraints through five integrated capability layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React/Vite)                       │
│   Dashboard │ Portfolio │ Options │ Agent │ Reports │ Admin      │
├─────────────────────────────────────────────────────────────────┤
│                     API GATEWAY (FastAPI)                         │
│          Auth │ Rate Limiting │ CORS │ Routing                   │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┤
│Ingest│Signal│Market│ Rec  │  AI  │Alert │Pred  │Chart │Options │
│  ion │ Proc │ Data │Engine│Model │  Svc │  Svc │Anlys │Scalp   │
├──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴────────┤
│               TRADING SERVICE  │  INTRADAY AGENT                 │
│     Portfolio │ Risk │ Margin  │  Autonomous │ Trailing SL        │
├─────────────────────────────────────────────────────────────────┤
│                   SHARED ENGINE LIBRARY                           │
│ Risk │ Trailing SL │ Iceberg │ Regime │ Momentum │ Metrics       │
│ Self-Learning │ Premium Sim │ Market Data Store │ Broker Iface   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Architecture & Services

SignalForge runs **13 microservices** plus an optional Kafka cluster, each independently deployable with health checks and auto-restart.

### Service Catalog

| # | Service | Port | Purpose | Health Check |
|---|---------|------|---------|--------------|
| 1 | **API Gateway** | 8000 | Central routing, auth, rate limiting | ✅ |
| 2 | **Frontend** | 3000 | React dashboard (Vite dev server) | — |
| 3 | **Ingestion Service** | 8001 | Multi-source web crawling & signal aggregation | ✅ |
| 4 | **Signal Processing** | 8002 | NLP pipeline — entity extraction, sentiment, relevance | ✅ |
| 5 | **Market Data Service** | 18003 | Live quotes, OHLC, technical indicators, calendar | ✅ |
| 6 | **Recommendation Engine** | 18004 | S.T.A.F.A scoring, level calculation, lifecycle | ✅ |
| 7 | **AI Model Service** | 18005 | Multi-model AI inference & consensus | ✅ |
| 8 | **Alert Service** | 18006 | Price monitoring & notification management | ✅ |
| 9 | **Prediction Service** | 18007 | ML-based movement prediction (XGBoost) | ✅ |
| 10 | **Trading Service** | 8005 | Paper/live trading, portfolio, risk controls | ✅ |
| 11 | **Intraday Agent** | 18008 | Fully autonomous intraday trading agent | ✅ |
| 12 | **Chart Analysis Service** | 18009 | Technical charting, patterns, multi-indicator analysis | ✅ |
| 13 | **Options Scalping Service** | 18010 | Nifty weekly options momentum trading | ✅ |

### Inter-Service Communication

```
                    ┌──────────┐
         ┌──────────│  Frontend │──────────┐
         │          └──────────┘          │
         ▼                                ▼
  ┌─────────────┐                  ┌─────────────┐
  │ API Gateway │◄─────────────────│   Alerts    │
  └──────┬──────┘                  └─────────────┘
         │
    ┌────┼────┬──────┬──────┬──────┬──────┐
    ▼    ▼    ▼      ▼      ▼      ▼      ▼
 Ingest Signal  Market  Rec    AI    Pred  Chart
  Svc   Proc   Data   Engine Model  Svc   Anlys
    │    │      │      │      │      │      │
    └────┴──────┴──────┴──────┴──────┴──────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         Trading   Intraday  Options
         Service    Agent    Scalping
```

All services communicate via **REST (HTTP)** with Docker-internal DNS. Optional **Kafka** streaming (topics: `trades.request`, `trades.status`, `trades.trailing_sl`) with automatic in-memory queue fallback.

---

## 5. Core Intelligence Engines

### 5.1 S.T.A.F.A Scoring Model

The proprietary **S.T.A.F.A** (Sentiment, Technical, AI, Fundamental, Analyst) scoring model is the platform's decision backbone. It produces a unified conviction score (0–100%) from five weighted signal layers:

| Factor | Weight | Data Sources | Signal Type |
|--------|--------|-------------|-------------|
| **S**entiment | 20% | Reddit, ValuePickr, TradingView, News | Social media NLP polarity |
| **T**echnical | 20% | RSI, MACD, Bollinger, ADX, EMA, VWAP | Indicator-based directional bias |
| **A**I Model | 25% | XGBoost, Gemini AI | ML probability + LLM consensus |
| **F**undamental | 20% | ROCE, PE, PB, Revenue Growth, Net Margin | Valuation & profitability |
| **A**nalyst | 15% | TickerTape, 5paisa, Moneycontrol, Trendlyne | Professional consensus |

**Dynamic Weight Gating:**
- **Trending market** → Technical weight boosted
- **Choppy market** → ML/AI weight boosted
- Confidence × Freshness gating per layer — stale signals decay automatically

**Output:** Directional recommendation (UP/DOWN) + conviction percentage + multi-paragraph HTML rationale with color-coded indicators.

### 5.2 Level Calculator (ATR-Based)

Every recommendation includes precise entry, target, and stop-loss levels computed via ATR (Average True Range):

| Mode | Stop Loss | Target 1 | Target 2 | R:R Minimum |
|------|-----------|----------|----------|-------------|
| **Intraday** | 0.4 × ATR | 0.8 × ATR | 1.2 × ATR | 2:1 |
| **Swing** | 1.0 × ATR | 2.0 × ATR | 3.0 × ATR | 2:1 |

**VIX-Aware Scaling:**
- VIX > 20 → Levels widened by 1.2×
- VIX > 25 → Levels widened by 1.5×

### 5.3 Regime Detection Engine

The platform classifies market state in real-time across six regimes:

| Regime | Time Window | Characteristics |
|--------|-------------|-----------------|
| `OPEN_TREND` | 9:15–10:30 | Strong directional move from open |
| `OPEN_CHOP` | 9:15–10:30 | Indecisive opening, whipsaws |
| `MID_CHOP` | 11:00–13:15 | Lunch-hour range-bound |
| `MID_TREND` | 10:30–14:00 | Sustained mid-day trend |
| `LATE_TREND` | 14:00–15:15 | End-of-day positioning |
| `EVENT_SPIKE` | Any | News/event-driven volatility |

Features VWAP magnet detection and time-of-day awareness. The regime gates both the options engine (mandatory check before any trade) and the intraday agent.

### 5.4 Momentum Signal Engine

Multi-component momentum scoring combining:

| Component | Weight | Description |
|-----------|--------|-------------|
| Breakout Detection | High | Price closing above/below range with confirmation |
| Range Expansion | Medium | ATR expansion relative to rolling average |
| Volume Participation | Medium | Volume spike vs 20-bar average |
| Trend Alignment | Medium | EMA slope + RSI direction agreement |
| VWAP Confirmation | Low | Price position relative to VWAP |

**Entry Modes:**
- `BREAKOUT_CONFIRM` — Requires 2 consecutive closes beyond level
- `BREAKOUT_RETEST` — Entry on pullback to breakout level

Produces confidence score 0–100 with per-component breakdown.

### 5.5 Chart Analysis Engine

Full technical analysis suite computing 7 indicators with composite signal scoring:

**Indicators Computed:**
- RSI (14-period) with overbought/oversold zones
- MACD (12/26/9) with crossover and histogram analysis
- Bollinger Bands (20-period, 2σ) with %B and bandwidth
- VWAP (Volume-Weighted Average Price)
- ADX (14-period) with +DI/-DI and trend strength classification
- EMA (configurable span)
- ATR (14-period)

**Composite Signal:** Aggregates all indicators into `STRONG_BUY`, `BUY`, `NEUTRAL`, `SELL`, `STRONG_SELL` with numeric score 0–100.

**Pattern Recognition:** Candlestick patterns (Doji, Engulfing, Stars, etc.) and support/resistance level detection.

---

## 6. Trading & Execution

### 6.1 Trading Service (Paper + Live)

Full portfolio management with multi-layer safety controls:

| Feature | Detail |
|---------|--------|
| Initial Capital | ₹1,00,000 paper trading |
| Leverage | 3× intraday margin |
| Order Types | Market, Limit, SL, SL-M |
| Iceberg Orders | Auto-split for quantities > 500 shares |
| State Persistence | JSON-based with backup and restore |
| Price Monitoring | Every 5 seconds via 3-tier fallback (Yahoo → Google → Dhan) |

**Key Endpoints (18 routes):**
- Portfolio management (view, reset, clear history)
- Trade execution (manual, signal-based, close by ID/symbol/all)
- Trailing SL management (update, status view)
- Model reports (daily AI performance, feedback, failed trade log)
- Risk & metrics dashboards

### 6.2 Intraday Agent (Fully Autonomous)

An AI-driven agent that autonomously trades during Indian market hours:

| Parameter | Value |
|-----------|-------|
| Trading Window | 9:20 AM – 3:15 PM IST |
| Auto Square-off | 3:10 PM (5 min before close) |
| Loop Interval | 15 seconds |
| Max Positions | 5 concurrent |
| Max Capital / Trade | ₹15,000 (margin) |
| Min Conviction | 40% |
| Max SL Risk / Trade | ₹2,500 |
| Leverage | 3× intraday |

**Autonomous Workflow:**
1. **Signal Fetch** — Polls Recommendation Engine `/active` for live signals
2. **Chart Validation** — Cross-references with Chart Analysis Service
3. **Conviction Filter** — Applies minimum conviction threshold
4. **Risk-Based Sizing** — Caps quantity so SL loss ≤ ₹2,500 per trade
5. **Order Placement** — Limit orders at LTP ± 0.1% via Trading Service
6. **Position Management** — Monitors trailing SL, manages positions
7. **EOD Square-off** — Closes all positions at 3:10 PM

### 6.3 Options Scalping Engine (Nifty Weeklies)

Momentum-first options trading with advanced risk management:

| Parameter | Value |
|-----------|-------|
| Underlying | NIFTY 50 Index |
| Lot Size | 65 (5 lots default) |
| Initial Capital | ₹1,00,000 |
| Max Trades/Day | 8 |
| Signal Loop | 30 seconds |
| Risk Loop | 3 seconds |

**Options-Specific Features:**
- Greeks filtering (Delta: 0.25–0.75, min premium ₹5, max theta 5%)
- Black-Scholes premium simulation with spread modeling
- Cooldown: 5 min after loss, 10 min after 2+ consecutive losses
- Max 2 entries per strike/direction/day
- Auto square-off at 3:15 PM

**Self-Learning (UCB Bandit):**
Five preset trading profiles automatically selected based on performance:

| Profile | Optimal For |
|---------|-------------|
| Open Trend | Strong directional opens |
| Open Chop | Indecisive morning sessions |
| Mid Trend | Sustained mid-day moves |
| High IV | High-volatility events |
| Expiry Day | Thursday expiry dynamics |

The bandit recalibrates after every 25 trades or at end of day, using reward = PnL − drawdown penalty.

---

## 7. Risk Management Framework

### 7.1 Multi-Layer Safety Gates (Equity Trading)

Every trade passes through **6 sequential safety gates** before execution:

| Gate | Rule | Purpose |
|------|------|---------|
| **Time Gate** | 9:20 AM – 3:15 PM IST only | Prevent off-hours trades |
| **Cooldown Gate** | 30 min after SL hit, max 2 entries/symbol/day | Prevent revenge trading |
| **Feedback Gate** | Block after 3 recent failures on same symbol | Avoid weak-signal symbols |
| **Conviction Gate** | Minimum 45% conviction required | Filter ambiguous signals |
| **Loss Cap Gate** | Max 3% of initial capital per trade | Limit single-trade downside |
| **Drawdown Floor** | Don't breach 50% of initial capital | Catastrophic loss protection |
| **SL Sanity** | Auto-correct inverted SL/target levels | Prevent misconfigured trades |

### 7.2 Trailing Stop-Loss Engine

Four strategies available, configurable per trade:

| Strategy | Description |
|----------|-------------|
| **Percentage** | Trail by fixed % from high-water mark |
| **ATR-Based** | Trail by ATR multiple, adapts to volatility |
| **Step Trail** | Lock profits in discrete steps (e.g., every 0.5%) |
| **Hybrid** | Combines percentage + step + breakeven trigger |

Features breakeven trigger (auto-raise SL to entry after X% profit), cost-aware adjustments, and full audit trail.

### 7.3 Risk Engine (Dual Mode)

| Mode | Used By | Stop Loss | Take Profit 1 | Book % | Runner Trail |
|------|---------|-----------|----------------|--------|--------------|
| **Premium PCT** | Options | 10% of premium | 12% of premium | 60% | 6% trail |
| **Equity ATR** | Stocks | 1.0 × ATR | 1.2 × ATR | 55% | 1.0 × ATR |

Additional controls:
- Daily loss cap: 2% of capital
- Consecutive loss limit: 3 (then cooldown)
- MFE/MAE tracking per trade
- Momentum-failure exit detection

---

## 8. Frontend & User Experience

### Technology Stack
- **React 18** + **Vite** (instant HMR)
- **Material UI (MUI)** component library
- **React Router v6** for SPA navigation
- **Google One-Tap SSO** for authentication
- Dark/light mode with persistent preference

### Pages & Views (20 screens)

| Page | Description |
|------|-------------|
| **Dashboard** | Live recommendations, market overview, ticker bar with Nifty 50, VIX, headlines |
| **Recommendation Detail** | Full signal breakdown — rationale, chart, entry/target/SL levels, conviction |
| **Watchlist** | User-curated symbols with real-time price tracking |
| **Alerts** | Alert center with price-level monitoring and notification history |
| **Portfolio** | Paper trading portfolio — active trades, P&L, trade history with analytics |
| **Agent Dashboard** | Intraday agent monitoring — status, action log, trade count, force-cycle |
| **Options Scalping** | Nifty options trading — chain, signals, paper trades, Greeks, P&L |
| **Trade Reports** | Daily model performance, win rates, conviction accuracy |
| **Profile** | User settings and preferences |
| **Broker Config** | Dhan / AngelOne API key configuration |
| **Admin Panel** | System administration and monitoring |
| **Admin Model Report** | Model performance analytics for administrators |
| **Admin Options Report** | Options scalping analytics for administrators |
| **Login / Register** | Email + Google SSO authentication |
| **Onboarding** | First-time user setup wizard |

### Real-Time Features
- 30-second alert polling with toast notifications
- Bullish/bearish signal toast indicators (green/red pulsing)
- WebSocket connections for live ingestion progress
- Streaming recommendation updates
- Live market ticker with Nifty 50, VIX, and financial headlines

---

## 9. Data Sources & Ingestion

### Crawler Network

The Ingestion Service operates **9 specialized crawlers** across 15+ financial platforms:

| Crawler | Sources | Data Type | Tier |
|---------|---------|-----------|------|
| **ValuePickr** | Forum threads | Long-term fundamental sentiment | Tier 1 |
| **TradingView** | Community ideas | Direction bias, breakout mentions | Tier 1 |
| **Reddit** | r/IndianStockMarket, r/Stocks | Momentum sentiment, hype detection | Tier 2 |
| **5paisa** | Analyst section | Professional recommendations | — |
| **Moneycontrol** | Research reports | Analyst consensus | — |
| **Trendlyne** | Research platform | Target prices, ratings | — |
| **Screener** | Financial data | Fundamental metrics (PE, ROCE, ROE) | — |
| **TickerTape** | Analysis platform | Analyst forecasts, upside potential | — |
| **GlobalMarket** | International indices | Global outlook, USD/INR, ADRs | — |

### Ingestion Pipeline Features

| Feature | Description |
|---------|-------------|
| **Deduplication** | Content hashing prevents duplicate signals from entering the pipeline |
| **Provenance Tracking** | Full audit trail for every signal — source, timestamp, original content |
| **Scheduled Scanning** | APScheduler runs automated scans (configurable, default 10 min) |
| **Real-Time Progress** | WebSocket broadcasting for live crawl status updates |
| **Health Monitoring** | Per-source success/failure tracking with health endpoints |
| **Batch Pipeline** | `pipeline_runner.py` orchestrates full ingestion → processing → recommendation |

### Market Data (3-Tier Price Fetching)

Live prices are fetched with automatic failover:

1. **yfinance** (primary) — Fast info → History fallback, circuit breaker after 2 failures
2. **Google Finance** (secondary) — Regex-based scraper, no API key required
3. **Dhan API** (tertiary) — Broker API when configured
4. **Mock mode** — Development fallback with realistic synthetic data

Index-specific routing: NIFTY_50 → `^NSEI`, NIFTY_BANK → `^NSEBANK`, India VIX → `^INDIAVIX`

---

## 10. Shared Engine Library

SignalForge's intelligence is built on **12 shared modules** used across multiple services:

| Module | Lines | Services Using It | Purpose |
|--------|-------|-------------------|---------|
| **models.py** | 161 | All | Core data models (Trade, Portfolio, Recommendation, Signal, User) |
| **config.py** | 123 | All | Global configuration via Pydantic BaseSettings |
| **trailing_sl.py** | 348 | Trading, Agent, Options | 4 trailing SL strategies with audit trail |
| **iceberg_order.py** | 417 | Trading, Agent, Options | Large order splitting with delay/price improvement |
| **risk_engine.py** | 477 | Trading, Options | Dual-mode risk engine (Premium + ATR) |
| **metrics_engine.py** | 328 | Trading, Options | Trade telemetry, daily reports, win rate, profit factor |
| **self_learning.py** | 389 | Options | UCB Bandit profile selection with reward optimization |
| **regime_engine.py** | 214 | Trading, Options | 6-regime market state classifier |
| **momentum_signal.py** | 301 | Trading, Options | Multi-component momentum scoring |
| **premium_simulator.py** | 281 | Options | Black-Scholes Greeks simulation with spread modeling |
| **market_data_store.py** | 327 | Trading, Options | Rolling 1-min candle store (120 bars) with derived indicators |
| **broker_interface.py** | 745 | Trading | Unified broker abstraction (Paper/Dhan/AngelOne) |
| **trade_stream.py** | 326 | Trading | Kafka trade streaming with in-memory fallback |

**Total shared library:** ~4,400 lines of battle-tested, unit-tested engine code.

---

## 11. Testing & Quality Assurance

### Test Suite: 240 Tests Across 20 Files

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| test_trailing_sl.py | 21 | 4 trailing SL strategies, breakeven, audit |
| test_broker_interface.py | 20 | Broker routing, order types, Paper/Dhan/Angel |
| test_trade_quality.py | 19 | Greeks filtering, cooldown, strike limits, equity gates |
| test_iceberg_order.py | 19 | Order splitting, fill simulation, edge cases |
| test_premium_simulator.py | 14 | Black-Scholes, premium dynamics, spread |
| test_models.py | 14 | Data model serialization, validation |
| test_market_data_store.py | 14 | Candle store, derived indicators, thread safety |
| test_level_calculator.py | 14 | ATR levels, VIX scaling, R:R guardrails |
| test_trade_stream.py | 12 | Kafka streaming, in-memory fallback |
| test_risk_engine.py | 12 | Dual-mode risk, loss caps, cooldown |
| test_config.py | 11 | Configuration loading, env vars |
| test_self_learning.py | 10 | UCB Bandit, profile selection, rewards |
| test_regime_engine.py | 10 | 6 regime classifications, time windows |
| test_schemas.py | 9 | API request/response schemas |
| test_auth_utils.py | 9 | JWT tokens, Google OAuth, OTP |
| test_momentum_signal.py | 8 | Breakout detection, confirmation modes |
| test_e2e_integration.py | 8 | End-to-end pipeline integration |
| test_scenarios.py | 6 | Real-world trading scenarios |
| test_metrics_engine.py | 6 | Trade telemetry, daily reports |
| test_provenance.py | 4 | Data lineage, audit trail |

### CI/CD Pipeline
- **GitHub Actions** — Automated on every push
- Python 3.11 test environment
- Full test suite execution with `pytest`
- Clock-mocked tests for time-dependent logic (market hours bypass)
- Zero external dependencies for test execution

---

## 12. Deployment & Infrastructure

### Production Stack

| Component | Technology |
|-----------|------------|
| Cloud Provider | DigitalOcean |
| Droplet | Ubuntu 24.04 LTS (2 vCPU, 2 GB) |
| Container Runtime | Docker + Docker Compose |
| Reverse Proxy | Nginx |
| Domain | sf.thinkhivelabs.com |
| SSL | Let's Encrypt (via Certbot) |
| Auto-Deploy | systemd service + git pull |

### Container Architecture

```
┌──────────────────────────────────────────┐
│           DigitalOcean Droplet           │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │         Nginx (SSL/Proxy)         │  │
│  └─────────┬──────────────────┬──────┘  │
│            │                  │          │
│  ┌─────────▼────┐   ┌────────▼───────┐  │
│  │ Frontend     │   │  API Gateway   │  │
│  │ :3000        │   │  :8000         │  │
│  └──────────────┘   └───────┬────────┘  │
│                             │            │
│  ┌──────────────────────────▼─────────┐  │
│  │      11 Backend Services          │  │
│  │  (ports 8001-18010)               │  │
│  │  Health-checked, auto-restart     │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  Persistent Volumes               │  │
│  │  paper_trades.json, options, etc. │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/startup.sh` | Start full stack (with `--build --logs` options) |
| `scripts/shutdown.sh` | Graceful shutdown (with `--volumes` for cleanup) |
| `scripts/deploy.sh` | Build + recreate (with `--pull --prune --logs`) |
| `scripts/auto_deploy.sh` | Auto-deploy on git push |
| `scripts/git_pull_deploy.sh` | Pull latest and redeploy |
| `signalforge-autodeploy.service` | systemd auto-deploy service |

### Data Persistence

| File | Purpose | Location |
|------|---------|----------|
| `paper_trades.json` | Equity portfolio state | `/app/data/` |
| `options_paper_trades.json` | Options portfolio state | `/app/data/` |
| `recommendations.json` | Active recommendations | `/app/data/` |
| `model_daily_report.json` | Cached performance report | `/app/data/` |
| `model_feedback.json` | User model feedback | `/app/data/` |
| `nse_stocks.csv` | Master stock universe | `/app/data/` |

---

## 13. Strategic Business Values

### Value 1: Faster Time-to-Decision

**Before:** 30–60 minutes per stock to manually gather data from 5+ sources, reconcile indicators, and form a view.

**After:** Unified conviction score generated in seconds. Recommendations arrive with entry, target, SL, and full rationale — ready for immediate action.

**Impact:** 10–50× compression in analysis cycle time.

### Value 2: Higher Decision Consistency

**Before:** Analyst-to-analyst variance; same stock, different conclusions based on personal methodology.

**After:** Standardized 5-factor scoring model applies identical methodology every time. Conviction scores are comparable across stocks, sectors, and time periods.

**Impact:** Repeatable, defensible decision framework.

### Value 3: Research Throughput Multiplication

**Before:** 10–15 stocks per analyst per day at current depth.

**After:** Full NSE universe scanned automatically on schedule. Analysts focus on the highest-conviction opportunities rather than raw data collection.

**Impact:** 10× coverage expansion with zero headcount increase.

### Value 4: Autonomous Execution

**Before:** Manual order entry, constant monitoring, missed exits, emotional decision-making.

**After:** Intraday agent executes trades autonomously with safety gates, trailing SL, and risk caps. Options engine runs self-learning strategies that adapt to market conditions.

**Impact:** 24/5 market coverage without human fatigue or emotional bias.

### Value 5: Operational Resilience

**Before:** Monolithic trading scripts with single points of failure.

**After:** 13 independent microservices — one service failing doesn't crash the platform. Health checks + auto-restart ensure high availability.

**Impact:** Production-grade reliability with sub-minute recovery.

### Value 6: Explainability & Trust

**Before:** Black-box algorithms producing unexplained buy/sell signals.

**After:** Every recommendation includes a structured rationale: market context, sentiment analysis, fundamental metrics, technical indicators, analyst consensus — all color-coded for instant comprehension.

**Impact:** Defensible decision trail for internal review and client communication.

---

## 14. Quantifiable Benefits

### Efficiency Metrics

| KPI | Measurement Method |
|-----|-------------------|
| Mean time: event → recommendation | Timestamp from ingestion → recommendation generation |
| Analysis turnaround per symbol | End-to-end pipeline timing |
| Automated scan completion rate | Successful scans / total scheduled |
| Analyst hours saved per week | Before/after comparison |
| Cost per analyzed symbol | Total operating cost / symbols covered |

### Quality Metrics

| KPI | Measurement Method |
|-----|-------------------|
| Recommendation hit rate | Directional accuracy (target reached vs. SL hit) |
| Conviction accuracy | High-conviction hit rate vs. low-conviction |
| Win rate (paper trading) | Winning trades / total trades |
| Profit factor | Gross profit / gross loss |
| Expectancy | Average PnL per trade |
| MFE/MAE ratio | Maximum favorable vs. adverse excursion |

### Platform Reliability

| KPI | Measurement Method |
|-----|-------------------|
| Service uptime | Health check pass rate |
| Data freshness | Time since last successful crawl per source |
| Deployment success rate | Successful deploys / total attempts |
| Test pass rate | CI pipeline green/red ratio |

### Financial Impact Model

$$
\text{Annual Net Value} = (\text{Productivity Savings} + \text{Decision Uplift} + \text{Risk Avoidance}) - \text{Platform Cost}
$$

**Illustrative Example (10-person advisory team):**

| Component | Conservative Estimate |
|-----------|----------------------|
| Productivity savings (5 hrs/analyst/week × 50 weeks) | ₹12,50,000/year |
| Decision uplift (2% improvement on ₹10Cr AUM) | ₹20,00,000/year |
| Risk avoidance (fewer SL hits, tighter exits) | ₹5,00,000/year |
| Platform cost (DigitalOcean + API keys) | ₹(1,20,000)/year |
| **Net annual value** | **₹36,30,000/year** |

---

## 15. Competitive Differentiators

| Differentiator | SignalForge | Typical Tools |
|---|---|---|
| **Multi-factor scoring** | 5-factor S.T.A.F.A with dynamic gating | Single-factor or 2-factor |
| **Regime awareness** | 6-regime classifier adapts strategy | Regime-blind |
| **Autonomous trading** | Fully autonomous agent + options engine | Manual execution |
| **Self-learning** | UCB Bandit auto-selects optimal strategy | Static parameters |
| **Explainability** | Full HTML rationale with every recommendation | Numeric score only |
| **Risk framework** | 6-gate safety + trailing SL + loss caps | Basic SL only |
| **Architecture** | 13 independent microservices | Monolithic |
| **Data sources** | 9 crawlers, 15+ platforms | 1-2 APIs |
| **Indian market focus** | NSE-native, IST-aware, India holidays | Global/generic |

---

## 16. Adoption Roadmap

### Phase 1: Pilot (Weeks 1–4)
- Deploy on DigitalOcean (single droplet)
- Configure data sources and API keys
- Run paper trading with ₹1,00,000 virtual capital
- Baseline current analysis cycle time
- Validate recommendation quality against manual analysis

### Phase 2: Controlled Scale (Weeks 5–8)
- Expand stock universe coverage
- Enable autonomous intraday agent
- Activate options scalping engine
- Establish KPI dashboards (win rate, profit factor, coverage)
- Tune conviction thresholds and risk parameters

### Phase 3: Production (Weeks 9–12)
- Configure broker integration (Dhan / AngelOne)
- Enable live execution (small capital scale)
- Set up alert-driven workflows
- Formalize governance for model tuning and parameter changes

### Phase 4: Full Operationalization (Ongoing)
- Integrate with team research and review processes
- Monitor and optimize based on performance KPIs
- Scale infrastructure as coverage grows
- Continuous improvement via self-learning engine data

---

## 17. Technology Stack Summary

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | React 18, Vite, Material UI, React Router v6 |
| **ML/AI** | XGBoost, Google Gemini AI, LiteLLM |
| **Data** | yfinance, Google Finance, Dhan API, Web Scraping |
| **NLP** | Custom entity extraction, sentiment analysis, relevance scoring |
| **Streaming** | Apache Kafka (optional, with in-memory fallback) |
| **Containers** | Docker, Docker Compose |
| **Infrastructure** | DigitalOcean, Nginx, Let's Encrypt |
| **CI/CD** | GitHub Actions, systemd auto-deploy |
| **Auth** | JWT, Google OAuth 2.0, OTP |
| **Testing** | pytest (240 tests, 20 files) |
| **Monitoring** | Health checks, per-source crawl health, risk engine status |

---

<div align="center">

**SignalForge** — *From fragmented analysis to intelligent, autonomous trading.*

Built by **ThinkHive Labs** | [sf.thinkhivelabs.com](https://sf.thinkhivelabs.com)

</div>

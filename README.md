# SignalForge: AI Stock Analyst Dashboard

SignalForge is a multi-layered AI stock analysis platform that fuses technical indicators, sentiment analysis (Reddit, ValuePickr, News), fundamental metrics, and machine learning (XGBoost) into a single "Conviction Score" for stock recommendations.

![Dashboard Preview](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/dark_mode_dashboard_1769793645886.png)

## 🚀 Key Features

- **S.T.A.F.A Scoring Engine**: A proprietary fusion model combining:
  - **S**entiment (Social Media/News)
  - **T**echnical (RSI, MA Trends, Volatility)
  - **A**I Model (XGBoost Probabilities)
  - **F**undamental (ROCE, PE, PB, Profit Growth)
  - **A**nalyst (TickerTape Upside/Buy Consensus)
- **Live Market Ticker**: Real-time scrolling bar with Nifty 50, VIX, and headlines from LiveMint & yfinance.
- **Dynamic Regime Detection**: Adapts analysis based on market state (Trending, Chop, or Volatile).
- **Automated Scanning**: Scheduled market scans and custom symbol deep-dives via `pipeline_runner.py`.
- **Enterprise UI**: Beautiful React-based dashboard with light/dark mode support and real-time logs terminal.

## 🏗️ Architecture Overview

The system follows a microservices-oriented architecture:
- **FastAPI API Gateway**: Central routing and rate limiting.
- **Ingestion Service**: Distributed crawlers for web scraping and API data.
- **Recommendation Engine**: The brain that executes the Scoring Model.
- **Prediction Service**: Hosts the ML models for quantitative analysis.
- **React Frontend**: Interactive dashboard with real-time UI components.

For a detailed breakdown, see the [Technical Specification](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/technical_specification.md).

## 🛠️ Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- Docker (Optional, for containerized deployment)

### Setup
1. **Clone the repository**
2. **Install Project Dependencies**
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install
   ```
3. **Configure Environment**
   Create a `.env` file in the root using `.env.template` as a guide.

### Running the Platform
Use the provided management script for easy service control:

```bash
# Start all services
./manage_services.sh start all

# Stop all services
./manage_services.sh stop all

# Restart a specific service (e.g. Ingestion)
./manage_services.sh restart ingestion
```

Or use Docker-based lifecycle scripts:

```bash
# Start the full stack
./scripts/startup.sh

# Start with rebuild and stream logs
./scripts/startup.sh --build --logs

# Graceful shutdown
./scripts/shutdown.sh

# Shutdown and remove named volumes
./scripts/shutdown.sh --volumes

# Deploy (rebuild and recreate containers)
./scripts/deploy.sh

# Deploy with latest pulls, prune dangling images, and stream logs
./scripts/deploy.sh --pull --prune --logs
```

## 📈 Deployment Strategy

SignalForge supports two primary deployment paths:
- **Local Dev**: Use `./manage_services.sh` for hot-reloading and direct script management.
- **Containerized**: Use `docker-compose up -d` for a scalable, production-ready environment.

See [technical_specification.md#deployment-strategy](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/technical_specification.md#5-deployment-strategy) for more details.

## 📄 Documentation
- [Technical Specification](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/technical_specification.md)
- [Project Walkthrough](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/walkthrough.md)
- [PDF - Technical Spec](file:///Users/arunachalam/.gemini/antigravity/brain/6b10e4f9-1dfb-4c82-af40-9f04d8a9008f/technical_specification.pdf)
- [DigitalOcean Deployment Guide](docs/deployment_digitalocean.md)

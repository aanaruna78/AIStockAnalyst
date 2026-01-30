#!/bin/bash

# Kill existing processes on ports 8000, 8001, 8002, 8003, 8004, 18004
echo "Stopping existing services..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:8001 | xargs kill -9 2>/dev/null
lsof -ti:8002 | xargs kill -9 2>/dev/null
lsof -ti:8003 | xargs kill -9 2>/dev/null
lsof -ti:8004 | xargs kill -9 2>/dev/null
lsof -ti:18004 | xargs kill -9 2>/dev/null

# Wait a moment
sleep 2

# Start services
echo "Starting Prediction Service (8001)..."
nohup python3 services/prediction_service/main.py > prediction_service.log 2>&1 &

echo "Starting Ingestion Service (8002)..."
nohup python3 services/ingestion_service/main.py > ingestion_service.log 2>&1 &

echo "Starting Market Data Service (8003)..."
nohup python3 services/market_data_service/main.py > market_data_service.log 2>&1 &

echo "Starting Signal Processing Service (8004)..."
nohup python3 services/signal_processing/main.py > signal_processing.log 2>&1 &

echo "Starting Recommendation Engine (18004)..."
nohup python3 services/recommendation_engine/main.py > recommendation_engine.log 2>&1 &

# Give backends time to initialize
sleep 5

echo "Starting API Gateway (8000)..."
nohup python3 services/api_gateway/main.py > api_gateway.log 2>&1 &

echo "All services started!"
lsof -i :8000 -i :8001 -i :8002 -i :8003 -i :8004 -i :18004

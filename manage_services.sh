#!/bin/bash

# Configuration
PYTHON_CMD="/Users/arunachalam/smartai/AIStockAnalyst/venv/bin/python3"
LOG_DIR="logs"
export PYTHONPATH=$PYTHONPATH:.


# Ensure log directory exists
mkdir -p $LOG_DIR

# --- Helper Functions ---

function kill_on_port {
    local PORT=$1
    local NAME=$2
    local PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "   - Stopping $NAME on port $PORT (PID: $PID)..."
        kill -9 $PID 2>/dev/null
    else
        echo "   - $NAME (Port $PORT) is not running."
    fi
}

function start_python_service {
    local SCRIPT=$1
    local PORT=$2
    local LOG_FILE=$3
    local NAME=$4
    
    echo "   - Starting $NAME ($PORT)..."
    nohup $PYTHON_CMD $SCRIPT > $LOG_DIR/$LOG_FILE 2>&1 &
}

# --- Service Definitions ---

function manage_docker {
    local ACTION=$1
    if docker info > /dev/null 2>&1; then
        if [ "$ACTION" == "stop" ]; then
            echo "   - Stopping Docker containers..."
            docker-compose down 2>/dev/null || echo "     (No docker-compose active)"
        elif [ "$ACTION" == "start" ]; then
             echo "   - Starting Docker containers..."
             docker-compose up -d
        fi
    else
        echo "   - Docker daemon not running, skipping containers."
    fi
}

function service_api_gateway {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8000 "API Gateway"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/api_gateway/main.py" 8000 "api_gateway.log" "API Gateway"
    fi
}

function service_prediction {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8001 "Prediction Service"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/prediction_service/main.py" 8001 "prediction_service.log" "Prediction Service"
    fi
}

function service_ingestion {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8002 "Ingestion Service"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/ingestion_service/main.py" 8002 "ingestion_service.log" "Ingestion Service"
    fi
}

function service_market_data {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8003 "Market Data Service"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/market_data_service/main.py" 8003 "market_data_service.log" "Market Data Service"
    fi
}

function service_signal_processing {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8004 "Signal Processing"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/signal_processing/main.py" 8004 "signal_processing.log" "Signal Processing"
    fi
}

function service_recommendation {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 18004 "Recommendation Engine"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/recommendation_engine/main.py" 18004 "recommendation_engine.log" "Recommendation Engine"
    fi
}

function service_trading {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 8005 "Trading Service"
    elif [ "$ACTION" == "start" ]; then
        start_python_service "services/trading_service/main.py" 8005 "trading_service.log" "Trading Service"
    fi
}

function service_frontend {
    local ACTION=$1
    if [ "$ACTION" == "stop" ]; then
        kill_on_port 3000 "Frontend"
    elif [ "$ACTION" == "start" ]; then
        echo "   - Starting Frontend (3000)..."
        cd frontend
        nohup npm run dev -- --host 0.0.0.0 > ../$LOG_DIR/frontend.log 2>&1 &
        cd ..
    fi
}

# --- Main Logic ---

ACTION=$1
TARGET=$2

if [ -z "$ACTION" ]; then
    echo "Usage: ./manage_services.sh [start|stop|restart] [all|api_gateway|prediction|ingestion|market_data|signal_processing|recommendation|frontend]"
    exit 1
fi

if [ -z "$TARGET" ]; then
    TARGET="all"
fi

echo "=================================================="
echo "Command: $ACTION $TARGET"
echo "=================================================="

# Stop Logic
if [ "$ACTION" == "stop" ] || [ "$ACTION" == "restart" ]; then
    case $TARGET in
        all)
            manage_docker stop
            service_frontend stop
            service_api_gateway stop
            service_recommendation stop
            service_signal_processing stop
            service_market_data stop
            service_ingestion stop
            service_prediction stop
            service_trading stop
            ;;
        api_gateway) service_api_gateway stop ;;
        prediction) service_prediction stop ;;
        ingestion) service_ingestion stop ;;
        market_data) service_market_data stop ;;
        signal_processing) service_signal_processing stop ;;
        recommendation) service_recommendation stop ;;
        trading) service_trading stop ;;
        frontend) service_frontend stop ;;
        *) echo "Unknown target: $TARGET"; exit 1 ;;
    esac
fi

if [ "$ACTION" == "restart" ]; then
    echo "Waiting for ports to clear..."
    sleep 2
fi

# Start Logic
if [ "$ACTION" == "start" ] || [ "$ACTION" == "restart" ]; then
    case $TARGET in
        all)
            manage_docker start
            service_prediction start
            service_ingestion start
            service_market_data start
            service_signal_processing start
            service_recommendation start
            service_trading start
            
            # Brief pause for backends to init before gateway
            sleep 2
            
            service_api_gateway start
            service_frontend start
            ;;
        api_gateway) service_api_gateway start ;;
        prediction) service_prediction start ;;
        ingestion) service_ingestion start ;;
        market_data) service_market_data start ;;
        signal_processing) service_signal_processing start ;;
        recommendation) service_recommendation start ;;
        trading) service_trading start ;;
        frontend) service_frontend start ;;
        *) echo "Unknown target: $TARGET"; exit 1 ;;
    esac
fi

echo "=================================================="
echo "✅ Done."
if [ "$TARGET" == "all" ] || [ "$TARGET" == "api_gateway" ]; then
    echo "Checking Status..."
    lsof -i :8000 -i :8001 -i :8002 -i :8003 -i :8004 -i :18004 -i :8005 -i :3000
fi

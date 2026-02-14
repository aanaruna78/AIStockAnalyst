#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
PROD_COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
ENV_FILE=""

PULL=false
PRUNE=false
LOGS=false
WAIT=false
TIMEOUT_SECONDS=120
SKIP_BUILD=false
BUILD_ONLY=false
HEALTH_URL=""
PROD_MODE=false

usage() {
  cat <<EOF
Usage: scripts/deploy.sh [options]

Options:
  --pull       Pull latest image tags before deployment
  --prune      Remove dangling images after deployment
  --logs       Follow logs after deployment
  --wait       Wait for services to become healthy/running
  --timeout N  Max seconds to wait when --wait is used (default: 120)
  --env-file F Use a specific env file for docker compose
  --skip-build Skip image rebuild and recreate containers only
  --build-only Build images and exit (no container restart)
  --health-url Check URL after deployment (example: http://localhost:8000/health)
  --prod       Use docker-compose.prod.yml overrides (recommended for servers)
  -h, --help   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull)
      PULL=true
      shift
      ;;
    --prune)
      PRUNE=true
      shift
      ;;
    --logs)
      LOGS=true
      shift
      ;;
    --wait)
      WAIT=true
      shift
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        echo "--timeout requires a numeric value in seconds."
        usage
        exit 1
      fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then
        echo "Invalid timeout value: $2"
        usage
        exit 1
      fi
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --env-file)
      if [[ $# -lt 2 ]]; then
        echo "--env-file requires a file path."
        usage
        exit 1
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --build-only)
      BUILD_ONLY=true
      shift
      ;;
    --health-url)
      if [[ $# -lt 2 ]]; then
        echo "--health-url requires a URL value."
        usage
        exit 1
      fi
      HEALTH_URL="$2"
      shift 2
      ;;
    --prod)
      PROD_MODE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Compose file not found: $COMPOSE_FILE"
  exit 1
fi

if [ "$PROD_MODE" = true ] && [ ! -f "$PROD_COMPOSE_FILE" ]; then
  echo "Production compose file not found: $PROD_COMPOSE_FILE"
  exit 1
fi

if [ -n "$ENV_FILE" ] && [ ! -f "$ENV_FILE" ]; then
  echo "Env file not found: $ENV_FILE"
  exit 1
fi

if [ "$BUILD_ONLY" = true ] && [ "$LOGS" = true ]; then
  echo "--logs cannot be used with --build-only."
  exit 1
fi

cd "$ROOT_DIR"

COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
if [ "$PROD_MODE" = true ]; then
  COMPOSE_CMD+=(-f "$PROD_COMPOSE_FILE")
fi
if [ -n "$ENV_FILE" ]; then
  COMPOSE_CMD+=(--env-file "$ENV_FILE")
fi

echo "Deploying application stack..."

if [ "$PULL" = true ]; then
  echo "Pulling latest images..."
  "${COMPOSE_CMD[@]}" pull
fi

if [ "$BUILD_ONLY" = true ]; then
  echo "Building images only..."
  "${COMPOSE_CMD[@]}" build
  echo "Build completed."
  exit 0
fi

echo "Recreating containers..."
UP_ARGS=(up -d --remove-orphans)
if [ "$SKIP_BUILD" = false ]; then
  UP_ARGS+=(--build)
fi
"${COMPOSE_CMD[@]}" "${UP_ARGS[@]}"

if [ "$WAIT" = true ]; then
  TOTAL_SERVICES=$("${COMPOSE_CMD[@]}" config --services | wc -l | tr -d ' ')
  START_TIME=$(date +%s)

  echo
  echo "Waiting for services to become healthy/running (timeout: ${TIMEOUT_SECONDS}s)..."

  while true; do
    RUNNING_SERVICES=$("${COMPOSE_CMD[@]}" ps --status running --services | wc -l | tr -d ' ')
    PS_OUTPUT=$("${COMPOSE_CMD[@]}" ps)

    if echo "$PS_OUTPUT" | grep -qi "unhealthy"; then
      echo
      echo "Deployment failed: one or more services are unhealthy."
      "${COMPOSE_CMD[@]}" ps
      exit 1
    fi

    if echo "$PS_OUTPUT" | grep -qi "Exit\|Restarting\|Dead"; then
      echo
      echo "Deployment failed: one or more services exited or are restarting."
      "${COMPOSE_CMD[@]}" ps
      exit 1
    fi

    STARTING_COUNT=$(echo "$PS_OUTPUT" | grep -ic "health: starting" || true)

    if [ "$RUNNING_SERVICES" -eq "$TOTAL_SERVICES" ] && [ "$STARTING_COUNT" -eq 0 ]; then
      echo "All services are healthy/running."
      break
    fi

    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TIME))

    if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
      echo
      echo "Deployment timed out after ${TIMEOUT_SECONDS}s while waiting for health checks."
      "${COMPOSE_CMD[@]}" ps
      exit 1
    fi

    sleep 3
  done
fi

echo
echo "Deployment complete. Current service status:"
"${COMPOSE_CMD[@]}" ps

if [ -n "$HEALTH_URL" ]; then
  echo
  echo "Checking deployment endpoint: $HEALTH_URL"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error "$HEALTH_URL" >/dev/null
  else
    python3 - <<PY
import urllib.request
urllib.request.urlopen("$HEALTH_URL", timeout=15)
PY
  fi
  echo "Health check succeeded."
fi

if [ "$PRUNE" = true ]; then
  echo
  echo "Cleaning dangling Docker images..."
  docker image prune -f
fi

if [ "$LOGS" = true ]; then
  echo
  echo "Streaming logs (Ctrl+C to stop viewing logs; containers keep running)..."
  "${COMPOSE_CMD[@]}" logs -f
fi

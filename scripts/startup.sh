#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

BUILD=false
LOGS=false
DETACH=true

usage() {
  cat <<EOF
Usage: scripts/startup.sh [options]

Options:
  --build      Build images before starting containers
  --logs       Follow logs after startup (non-detached)
  -h, --help   Show this help
EOF
}

for arg in "$@"; do
  case "$arg" in
    --build)
      BUILD=true
      ;;
    --logs)
      LOGS=true
      DETACH=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
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

cd "$ROOT_DIR"

CMD=(docker compose -f "$COMPOSE_FILE" up)

if [ "$BUILD" = true ]; then
  CMD+=(--build)
fi

if [ "$DETACH" = true ]; then
  CMD+=(-d)
fi

echo "Starting application stack..."
"${CMD[@]}"

echo
echo "Services status:"
docker compose -f "$COMPOSE_FILE" ps

if [ "$LOGS" = true ]; then
  echo
  echo "Streaming logs (Ctrl+C to stop viewing logs; containers keep running)..."
  docker compose -f "$COMPOSE_FILE" logs -f
fi

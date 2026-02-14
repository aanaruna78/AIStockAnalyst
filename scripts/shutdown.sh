#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
REMOVE_VOLUMES=false

usage() {
  cat <<EOF
Usage: scripts/shutdown.sh [options]

Options:
  --volumes    Remove named volumes while shutting down
  -h, --help   Show this help
EOF
}

for arg in "$@"; do
  case "$arg" in
    --volumes)
      REMOVE_VOLUMES=true
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
  echo "Docker daemon is not running."
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Compose file not found: $COMPOSE_FILE"
  exit 1
fi

cd "$ROOT_DIR"

CMD=(docker compose -f "$COMPOSE_FILE" down)
if [ "$REMOVE_VOLUMES" = true ]; then
  CMD+=(--volumes)
fi

echo "Stopping application stack..."
"${CMD[@]}"

echo
echo "Stack stopped successfully."

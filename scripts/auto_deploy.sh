#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# auto_deploy.sh — Auto-deploy on DigitalOcean when new commits land
#
# This script checks for new commits on the remote branch every N
# seconds and automatically runs git pull + deploy when changes are
# detected.
#
# SETUP (run once on DigitalOcean droplet):
#   # Option 1: Run as a background service (recommended)
#   sudo cp scripts/signalforge-autodeploy.service /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable signalforge-autodeploy
#   sudo systemctl start signalforge-autodeploy
#
#   # Option 2: Run manually in a tmux/screen session
#   bash scripts/auto_deploy.sh
#
#   # Option 3: Cron (check every 2 minutes)
#   crontab -e
#   */2 * * * * /path/to/AIStockAnalyst/scripts/auto_deploy.sh --once >> /var/log/signalforge-deploy.log 2>&1
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="${GIT_BRANCH:-main}"
CHECK_INTERVAL="${DEPLOY_INTERVAL:-120}"  # seconds between checks (default 2 min)
LOG_FILE="${ROOT_DIR}/logs/auto_deploy.log"
LOCK_FILE="/tmp/signalforge-deploy.lock"
RUN_ONCE=false

# Parse args
for arg in "$@"; do
  case "$arg" in
    --once) RUN_ONCE=true ;;
  esac
done

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Prevent concurrent deployments
acquire_lock() {
  if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || true)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
      log "⏳ Deploy already in progress (PID $LOCK_PID), skipping."
      exit 0
    fi
    rm -f "$LOCK_FILE"
  fi
  echo $$ > "$LOCK_FILE"
}

release_lock() {
  rm -f "$LOCK_FILE"
}

trap release_lock EXIT

check_and_deploy() {
  # Fetch remote without merging
  git fetch origin "$BRANCH" --quiet 2>/dev/null

  LOCAL_HEAD=$(git rev-parse HEAD)
  REMOTE_HEAD=$(git rev-parse "origin/${BRANCH}")

  if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    return 1  # no changes
  fi

  log "🔄 New commits detected: ${LOCAL_HEAD:0:7} → ${REMOTE_HEAD:0:7}"
  log "   $(git log --oneline "${LOCAL_HEAD}..origin/${BRANCH}" | head -5)"

  acquire_lock

  log "▶ Pulling changes..."
  git reset --hard "origin/${BRANCH}"
  log "✓ Code updated to $(git rev-parse --short HEAD)"

  log "▶ Rebuilding & restarting services..."
  bash "$ROOT_DIR/scripts/deploy.sh" --prod --wait --prune 2>&1 | tee -a "$LOG_FILE"

  log "✅ Deployment complete"
  release_lock
  return 0
}

# ─── Main ─────────────────────────────────────────────────────────

if [ "$RUN_ONCE" = true ]; then
  # Single check (for cron usage)
  check_and_deploy || true
  exit 0
fi

# Continuous watcher loop
log "═══════════════════════════════════════════════════════════"
log "  SignalForge Auto-Deploy Watcher"
log "  Branch: ${BRANCH} | Check interval: ${CHECK_INTERVAL}s"
log "═══════════════════════════════════════════════════════════"

while true; do
  if check_and_deploy; then
    log "⏳ Next check in ${CHECK_INTERVAL}s..."
  fi
  sleep "$CHECK_INTERVAL"
done

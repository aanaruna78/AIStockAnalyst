#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# git_pull_deploy.sh — Pull latest code and redeploy on DigitalOcean
#
# Usage:
#   bash scripts/git_pull_deploy.sh              # normal deploy
#   bash scripts/git_pull_deploy.sh --prod       # production mode
#   bash scripts/git_pull_deploy.sh --logs       # follow logs after
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="${GIT_BRANCH:-main}"
DEPLOY_ARGS=("$@")

echo "═══════════════════════════════════════════════════════════"
echo "  SignalForge — Git Pull & Deploy"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

# ─── 1. Git pull ──────────────────────────────────────────────────
echo ""
echo "▶ Pulling latest changes from origin/${BRANCH}..."
git fetch origin "$BRANCH"
git reset --hard "origin/${BRANCH}"
echo "✓ Code updated to $(git rev-parse --short HEAD)"

# ─── 2. Deploy ───────────────────────────────────────────────────
echo ""
echo "▶ Running deploy.sh ${DEPLOY_ARGS[*]:-}..."
bash "$ROOT_DIR/scripts/deploy.sh" --prod --wait --prune "${DEPLOY_ARGS[@]}" 2>&1

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Deployment complete — $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

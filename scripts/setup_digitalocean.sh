#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# SignalForge — DigitalOcean Setup & Deploy Script
# ──────────────────────────────────────────────────────────────────
# Run on a fresh Ubuntu 24.04 droplet as root:
#
#   FIRST TIME (from anywhere):
#     curl -sL https://raw.githubusercontent.com/aanaruna78/AIStockAnalyst/main/scripts/setup_digitalocean.sh | bash
#
#   OR clone first, then:
#     bash scripts/setup_digitalocean.sh
#
#   SUBSEQUENT DEPLOYS:
#     bash /opt/apps/AIStockAnalyst/scripts/setup_digitalocean.sh
#
# The script is idempotent — safe to run multiple times.
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────
REPO_URL="https://github.com/aanaruna78/AIStockAnalyst.git"
APP_DIR="/opt/apps/AIStockAnalyst"
DOMAIN="sf.thinkhivelabs.com"
BRANCH="main"
ADMIN_EMAIL="admin@thinkhivelabs.com"

# ── Colors ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }
step() { echo -e "\n${CYAN}═══ $* ═══${NC}"; }

# ──────────────────────────────────────────────────────────────────
# STEP 1: System packages
# ──────────────────────────────────────────────────────────────────
install_system_packages() {
  step "Step 1/8: System Packages"

  if command -v docker &>/dev/null && command -v nginx &>/dev/null && command -v git &>/dev/null; then
    log "Docker, Nginx, Git already installed — skipping system install."
    return
  fi

  log "Updating system packages..."
  apt update -qq && apt upgrade -y -qq

  log "Installing base packages..."
  apt install -y -qq ca-certificates curl gnupg lsb-release git nginx ufw certbot python3-certbot-nginx

  # Docker Engine
  if ! command -v docker &>/dev/null; then
    log "Installing Docker Engine..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt update -qq
    apt install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    log "Docker installed: $(docker --version)"
  else
    log "Docker already installed: $(docker --version)"
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 2: Clone or pull repo
# ──────────────────────────────────────────────────────────────────
clone_or_pull() {
  step "Step 2/8: Git Repository"

  if [ -d "$APP_DIR/.git" ]; then
    log "Repo exists at $APP_DIR — pulling latest from $BRANCH..."
    cd "$APP_DIR"
    git fetch origin "$BRANCH" --quiet
    LOCAL_HEAD=$(git rev-parse HEAD)
    REMOTE_HEAD=$(git rev-parse "origin/${BRANCH}")
    if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
      log "Already up to date (${LOCAL_HEAD:0:7})."
    else
      log "Updating: ${LOCAL_HEAD:0:7} → ${REMOTE_HEAD:0:7}"
      git log --oneline "${LOCAL_HEAD}..origin/${BRANCH}" | head -5
      git reset --hard "origin/${BRANCH}"
      log "Updated to $(git rev-parse --short HEAD)"
    fi
  else
    log "Cloning $REPO_URL → $APP_DIR ..."
    mkdir -p "$(dirname "$APP_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
    log "Cloned successfully."
  fi

  cd "$APP_DIR"
}

# ──────────────────────────────────────────────────────────────────
# STEP 3: Environment files
# ──────────────────────────────────────────────────────────────────
setup_env_files() {
  step "Step 3/8: Environment Files"

  # Root .env
  if [ -f "$APP_DIR/.env" ]; then
    log ".env already exists — keeping existing values."
  else
    warn "Creating .env template — EDIT WITH YOUR REAL KEYS!"
    cat > "$APP_DIR/.env" <<'ENVEOF'
# ── Broker / API Keys ──
DHAN_CLIENT_ID=your_dhan_client_id
DHAN_ACCESS_TOKEN=your_dhan_access_token
GOOGLE_API_KEY=your_google_api_key

# ── Google OAuth ──
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# ── SMTP (optional) ──
SMTP_PASSWORD=

# ── Admin ──
ADMIN_EMAILS=you@example.com
ENVEOF
    warn ">>> IMPORTANT: Edit $APP_DIR/.env with real credentials before accessing the app."
  fi

  # Frontend .env
  if [ -f "$APP_DIR/frontend/.env" ]; then
    log "frontend/.env already exists — keeping existing values."
  else
    cat > "$APP_DIR/frontend/.env" <<FENVEOF
VITE_API_BASE_URL=https://${DOMAIN}/api/v1
VITE_WS_BASE_URL=wss://${DOMAIN}/api/v1
VITE_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
FENVEOF
    warn ">>> IMPORTANT: Edit $APP_DIR/frontend/.env with your Google Client ID."
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 4: Build & deploy containers
# ──────────────────────────────────────────────────────────────────
deploy_containers() {
  step "Step 4/8: Docker Build & Deploy"

  cd "$APP_DIR"

  log "Building and starting all services..."
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file .env \
    up --build -d --remove-orphans 2>&1 | tail -20

  log "Waiting for services to start (max 240s)..."
  local start_time
  start_time=$(date +%s)
  local timeout=240

  while true; do
    local running
    running=$(docker compose ps --status running --services 2>/dev/null | wc -l | tr -d ' ')
    local total
    total=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services 2>/dev/null | wc -l | tr -d ' ')
    local ps_output
    ps_output=$(docker compose ps 2>/dev/null || true)

    # Check for fatal failures
    if echo "$ps_output" | grep -qi "unhealthy\|Exit\|Dead"; then
      warn "Some services have issues:"
      docker compose ps
      warn "Check logs: docker compose logs -f <service-name>"
      break
    fi

    if [ "$running" -ge "$total" ] 2>/dev/null; then
      log "All $total services are running!"
      break
    fi

    local now
    now=$(date +%s)
    if [ $((now - start_time)) -ge $timeout ]; then
      warn "Timed out after ${timeout}s. Current status:"
      docker compose ps
      break
    fi

    sleep 5
  done

  echo ""
  docker compose ps
}

# ──────────────────────────────────────────────────────────────────
# STEP 5: Nginx reverse proxy
# ──────────────────────────────────────────────────────────────────
setup_nginx() {
  step "Step 5/8: Nginx Reverse Proxy"

  local conf="/etc/nginx/sites-available/${DOMAIN}"

  if [ -f "$conf" ]; then
    log "Nginx config for $DOMAIN already exists — keeping."
  else
    log "Creating Nginx config for $DOMAIN..."
    cat > "$conf" <<NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 20m;

    # API Gateway
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # WebSocket support
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
NGINXEOF
  fi

  # Enable site
  ln -sf "$conf" /etc/nginx/sites-enabled/${DOMAIN}

  # Remove default site if it exists
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

  # Test and reload
  if nginx -t 2>/dev/null; then
    systemctl reload nginx
    log "Nginx configured and reloaded."
  else
    err "Nginx config test failed! Check: nginx -t"
    nginx -t
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 6: SSL / HTTPS
# ──────────────────────────────────────────────────────────────────
setup_ssl() {
  step "Step 6/8: HTTPS (Let's Encrypt)"

  if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    log "SSL certificate already exists for $DOMAIN."
    certbot renew --dry-run --quiet 2>/dev/null && log "Certificate renewal check passed." || true
  else
    log "Requesting SSL certificate for $DOMAIN..."
    if certbot --nginx -d "$DOMAIN" --redirect --agree-tos -m "$ADMIN_EMAIL" -n 2>/dev/null; then
      log "SSL certificate installed and auto-redirect enabled."
    else
      warn "SSL setup failed. Ensure DNS A record points $DOMAIN to this server's IP."
      warn "You can retry later: certbot --nginx -d $DOMAIN --redirect --agree-tos -m $ADMIN_EMAIL -n"
    fi
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 7: Firewall
# ──────────────────────────────────────────────────────────────────
setup_firewall() {
  step "Step 7/8: Firewall (UFW)"

  if ufw status 2>/dev/null | grep -q "Status: active"; then
    log "Firewall already active."
    ufw status | grep -E "ALLOW|DENY" | head -10
  else
    log "Enabling firewall..."
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable
    log "Firewall enabled."
    ufw status
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 8: Auto-deploy service (optional)
# ──────────────────────────────────────────────────────────────────
setup_autodeploy() {
  step "Step 8/8: Auto-Deploy Service (optional)"

  local service_file="/etc/systemd/system/signalforge-autodeploy.service"

  if [ -f "$service_file" ]; then
    log "Auto-deploy service already installed."
    systemctl is-active --quiet signalforge-autodeploy && \
      log "Service is running." || \
      warn "Service exists but is not running. Start with: systemctl start signalforge-autodeploy"
  else
    if [ -f "$APP_DIR/scripts/signalforge-autodeploy.service" ]; then
      log "Installing auto-deploy systemd service..."
      cp "$APP_DIR/scripts/signalforge-autodeploy.service" "$service_file"
      systemctl daemon-reload
      systemctl enable signalforge-autodeploy
      systemctl start signalforge-autodeploy
      log "Auto-deploy watcher is now running (checks every 2 min)."
    else
      warn "Auto-deploy service file not found — skipping."
      warn "You can manually redeploy with: cd $APP_DIR && git pull && bash scripts/deploy.sh --prod --wait"
    fi
  fi
}

# ──────────────────────────────────────────────────────────────────
# STEP 9: Health check & summary
# ──────────────────────────────────────────────────────────────────
health_check_and_summary() {
  step "Deployment Complete!"

  echo ""
  log "Running health checks..."

  # Local health
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    log "API Gateway:  http://localhost:8000/health ✓"
  else
    warn "API Gateway not responding yet — may still be starting."
  fi

  # Public health (if DNS is set up)
  if curl -sf "https://${DOMAIN}/health" >/dev/null 2>&1; then
    log "Public HTTPS: https://${DOMAIN}/health ✓"
  elif curl -sf "http://${DOMAIN}/health" >/dev/null 2>&1; then
    log "Public HTTP:  http://${DOMAIN}/health ✓ (HTTPS may not be configured)"
  else
    warn "Public endpoint not reachable — check DNS and Nginx config."
  fi

  echo ""
  echo -e "${CYAN}┌──────────────────────────────────────────────────────────┐${NC}"
  echo -e "${CYAN}│${NC}  SignalForge deployed on DigitalOcean                     ${CYAN}│${NC}"
  echo -e "${CYAN}├──────────────────────────────────────────────────────────┤${NC}"
  echo -e "${CYAN}│${NC}  App Dir:    ${APP_DIR}                ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}  Frontend:   https://${DOMAIN}               ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}  API:        https://${DOMAIN}/api/v1        ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}  Health:     https://${DOMAIN}/health        ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}  Git:        $(git rev-parse --short HEAD) (${BRANCH})                          ${CYAN}│${NC}"
  echo -e "${CYAN}├──────────────────────────────────────────────────────────┤${NC}"
  echo -e "${CYAN}│${NC}  Useful commands:                                        ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}    docker compose ps                                      ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}    docker compose logs -f                                 ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}    docker compose logs -f api-gateway                     ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}    tail -f /var/log/nginx/error.log                       ${CYAN}│${NC}"
  echo -e "${CYAN}├──────────────────────────────────────────────────────────┤${NC}"
  echo -e "${CYAN}│${NC}  To redeploy after code changes:                          ${CYAN}│${NC}"
  echo -e "${CYAN}│${NC}    cd $APP_DIR && git pull && bash scripts/setup_digitalocean.sh ${CYAN}│${NC}"
  echo -e "${CYAN}└──────────────────────────────────────────────────────────┘${NC}"

  if [ ! -f "$APP_DIR/.env" ] || grep -q "your_dhan_client_id" "$APP_DIR/.env" 2>/dev/null; then
    echo ""
    warn "╔══════════════════════════════════════════════════════════╗"
    warn "║  ACTION REQUIRED: Edit .env files with your real keys!  ║"
    warn "║    nano $APP_DIR/.env"
    warn "║    nano $APP_DIR/frontend/.env"
    warn "║  Then restart: docker compose restart                   ║"
    warn "╚══════════════════════════════════════════════════════════╝"
  fi
}

# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────
main() {
  echo -e "${CYAN}"
  echo "  ╔═══════════════════════════════════════════════════════╗"
  echo "  ║   SignalForge — DigitalOcean Deployment Script       ║"
  echo "  ║   $(date '+%Y-%m-%d %H:%M:%S')                                  ║"
  echo "  ╚═══════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  install_system_packages
  clone_or_pull
  setup_env_files
  deploy_containers
  setup_nginx
  setup_ssl
  setup_firewall
  setup_autodeploy
  health_check_and_summary
}

main "$@"

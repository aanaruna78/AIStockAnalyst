# Deployment Guide (DigitalOcean + `sf.thinkhivelabs.com`)

This guide deploys AIStockAnalyst on your DigitalOcean droplet:
- Droplet: `ubuntu-s-2vcpu-2gb-amd-blr1-01`
- OS: Ubuntu 24.04 LTS
- Domain target: `sf.thinkhivelabs.com`

## 1) DNS Setup (ThinkHiveLabs Domain)

In your DNS provider for `thinkhivelabs.com`:

1. Create an **A record**:
   - Host/Name: `sf`
   - Value: `<YOUR_DROPLET_PUBLIC_IP>`
   - TTL: Auto/default
2. Wait for propagation (usually a few minutes, sometimes longer).
3. Verify:

```bash
nslookup sf.thinkhivelabs.com
```

## 2) Server Bootstrap (Ubuntu 24.04)

SSH into droplet:

```bash
ssh root@<YOUR_DROPLET_PUBLIC_IP>
```

Install base packages:

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg lsb-release git nginx ufw
```

Install Docker Engine + Compose plugin:

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
```

(Optional but recommended) create app user:

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
```

## 3) Clone Project + Env Setup

```bash
mkdir -p /opt/apps
cd /opt/apps
git clone <YOUR_REPO_URL> AIStockAnalyst
cd AIStockAnalyst
```

Create `.env` in project root (same folder as `docker-compose.yml`):

```bash
cat > .env <<'EOF'
# ── Broker / API Keys ──
DHAN_CLIENT_ID=your_dhan_client_id
DHAN_ACCESS_TOKEN=your_dhan_access_token
GOOGLE_API_KEY=your_google_api_key

# ── Google OAuth (required for login) ──
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# ── Admin (comma-separated emails that get admin console access) ──
ADMIN_EMAILS=you@example.com
EOF
```

Create `frontend/.env` for the Vite build:

```bash
cat > frontend/.env <<'EOF'
VITE_API_BASE_URL=https://sf.thinkhivelabs.com/api/v1
VITE_WS_BASE_URL=wss://sf.thinkhivelabs.com/api/v1
VITE_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
EOF
```

> **Note:** Never commit `.env` files. Templates are in `.env.template` and `frontend/.env.example`.

## 4) Deploy Using Script

From project root:

```bash
bash scripts/deploy.sh --prod --env-file .env --wait --timeout 240 --health-url http://localhost:8000/health
```

Useful variants:

```bash
# Pull upstream images first
bash scripts/deploy.sh --prod --env-file .env --pull --wait

# Build only (no restart)
bash scripts/deploy.sh --prod --env-file .env --build-only

# Restart without image rebuild
bash scripts/deploy.sh --prod --env-file .env --skip-build --wait
```

## 5) Nginx Reverse Proxy for `sf.thinkhivelabs.com`

Create site config:

```bash
cat > /etc/nginx/sites-available/sf.thinkhivelabs.com <<'EOF'
server {
    listen 80;
    server_name sf.thinkhivelabs.com;

    client_max_body_size 20m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # WebSocket support (for scan progress, live recommendations)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF
```

Enable + reload:

```bash
ln -sf /etc/nginx/sites-available/sf.thinkhivelabs.com /etc/nginx/sites-enabled/sf.thinkhivelabs.com
nginx -t
systemctl restart nginx
```

## 6) Enable HTTPS (Let’s Encrypt)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d sf.thinkhivelabs.com --redirect --agree-tos -m you@thinkhivelabs.com -n
```

Verify:

```bash
curl -I https://sf.thinkhivelabs.com
curl -I https://sf.thinkhivelabs.com/health
```

## 7) Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status
```

## 8) Update / Redeploy Flow

```bash
cd /opt/apps/AIStockAnalyst
git pull
bash scripts/deploy.sh --prod --env-file .env --wait --timeout 240 --health-url http://localhost:8000/health
```

## 9) Logs and Troubleshooting

```bash
# Compose service status
docker compose ps

# Full logs
docker compose logs -f

# API gateway only
docker compose logs -f api-gateway

# Nginx logs
tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

If frontend loads but API calls fail:
- Verify Nginx `location /api/` block exists and reload Nginx.
- Verify API gateway is healthy on `localhost:8000/health`.
- Confirm DNS points `sf.thinkhivelabs.com` to the droplet IP.

## 10) Code Quality / Linting

Backend (Python) — uses **ruff**:

```bash
pip install ruff
ruff check .                  # Check for errors
ruff check --fix .            # Auto-fix safe issues
ruff check --fix --unsafe-fixes .  # Auto-fix all
```

Frontend (React) — uses **ESLint** (via Vite):

```bash
cd frontend
npx eslint src/               # Check for errors
```

Both are configured to catch unused imports, bare excepts, ambiguous variables, and React hooks issues.

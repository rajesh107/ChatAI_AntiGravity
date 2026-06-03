#!/usr/bin/env bash
# Redeploy script — run on the EC2 instance from the app directory.
# Usage:  bash deploy.sh [branch]
# Default branch: main
set -euo pipefail

APP_DIR="/home/ubuntu/chatbot"
SERVICE="chatbot"
REPO="https://github.com/rajesh107/ChatAI_AntiGravity.git"
BRANCH="${1:-main}"

echo "========================================"
echo " ChatAI AntiGravity — Deploy"
echo " Branch : $BRANCH"
echo " Dir    : $APP_DIR"
echo "========================================"

# ── 1. Pull latest code ──────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
    echo "==> Pulling latest code from $BRANCH"
    cd "$APP_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    echo "==> Cloning repo into $APP_DIR"
    git clone --branch "$BRANCH" "$REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# ── 2. Virtual environment ───────────────────────────────────────────────────
echo "==> Setting up virtualenv"
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
source "$APP_DIR/venv/bin/activate"

# ── 3. Install dependencies ──────────────────────────────────────────────────
echo "==> Upgrading pip"
pip install --upgrade pip --quiet

echo "==> Installing requirements"
pip install -r requirements.txt --quiet

# Pin bcrypt to 4.x — passlib is incompatible with bcrypt 5.x
pip install "bcrypt==4.0.1" --quiet

echo "==> Dependencies installed"

# ── 4. Validate .env exists ──────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "ERROR: .env file not found at $APP_DIR/.env"
    echo "       Copy .env.example to .env and fill in the values."
    exit 1
fi

# ── 5. Install / refresh systemd service ─────────────────────────────────────
echo "==> Installing systemd service"
sudo cp "$APP_DIR/chatbot.service" /etc/systemd/system/${SERVICE}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE}

# ── 6. Restart service ───────────────────────────────────────────────────────
echo "==> Restarting service"
sudo systemctl restart ${SERVICE}
sleep 2

# ── 7. Status check ──────────────────────────────────────────────────────────
echo "==> Service status:"
sudo systemctl --no-pager status ${SERVICE} | head -20

echo ""
echo "========================================"
echo " Done."
echo " Tail logs : journalctl -u ${SERVICE} -f"
echo " API docs  : http://<server-ip>:8000/docs"
echo "========================================"

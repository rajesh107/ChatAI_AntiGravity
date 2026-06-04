#!/usr/bin/env bash
# deploy_tarball.sh — Deploy ChatAI AntiGravity from a tar.gz archive.
# Usage:  bash deploy_tarball.sh <archive.tar.gz>
# Run on the EC2 instance after uploading the archive via scp.
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
APP_DIR="/home/ubuntu/chatbot"
SERVICE="chatbot"
BACKUP_DIR="/home/ubuntu/chatbot_backups"

# ── Args ─────────────────────────────────────────────────────────────────────
ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
    echo "Usage: bash deploy_tarball.sh <archive.tar.gz>"
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: Archive not found: $ARCHIVE"
    exit 1
fi

echo "========================================"
echo " ChatAI AntiGravity — Tarball Deploy"
echo " Archive : $ARCHIVE"
echo " App dir : $APP_DIR"
echo "========================================"

# ── 1. Backup current deployment ─────────────────────────────────────────────
if [ -d "$APP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    echo "==> Backing up current deployment -> $BACKUP_DIR/$BACKUP_NAME"
    tar -czf "$BACKUP_DIR/$BACKUP_NAME" -C "$(dirname $APP_DIR)" "$(basename $APP_DIR)" \
        --exclude="$(basename $APP_DIR)/venv" \
        --exclude="$(basename $APP_DIR)/__pycache__"
fi

# ── 2. Stop service ───────────────────────────────────────────────────────────
echo "==> Stopping service"
sudo systemctl stop ${SERVICE} 2>/dev/null || true

# ── 3. Extract archive ────────────────────────────────────────────────────────
echo "==> Extracting $ARCHIVE"
TEMP_DIR=$(mktemp -d)
tar -xzf "$ARCHIVE" -C "$TEMP_DIR"

# Archive contains a single top-level folder named 'chatbot'
EXTRACTED=$(ls "$TEMP_DIR")
SRC="$TEMP_DIR/$EXTRACTED"

# Create app dir if it doesn't exist
mkdir -p "$APP_DIR"

# Copy extracted files (preserve .env if it already exists on server)
echo "==> Syncing files to $APP_DIR"
rsync -a --exclude='.env' "$SRC/" "$APP_DIR/"
echo "   Files synced (existing .env preserved)"

# Cleanup temp
rm -rf "$TEMP_DIR"

# ── 4. Check .env ─────────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo ""
    echo "  WARNING: .env not found at $APP_DIR/.env"
    echo "  Copy it manually before starting the service:"
    echo "    scp .env ubuntu@<server-ip>:$APP_DIR/.env"
    echo ""
fi

# ── 5. Virtualenv + dependencies ─────────────────────────────────────────────
echo "==> Setting up virtualenv"
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
source "$APP_DIR/venv/bin/activate"

echo "==> Installing dependencies"
pip install --upgrade pip --quiet
pip install -r "$APP_DIR/requirements.txt" --quiet

# Pin bcrypt — passlib is incompatible with bcrypt 5.x
pip install "bcrypt==4.0.1" --quiet
echo "   Dependencies installed"

# ── 6. Install systemd service ───────────────────────────────────────────────
echo "==> Installing systemd service"
sudo cp "$APP_DIR/chatbot.service" /etc/systemd/system/${SERVICE}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE}

# ── 7. Start service ──────────────────────────────────────────────────────────
echo "==> Starting service"
sudo systemctl start ${SERVICE}
sleep 3

# ── 8. Health check ───────────────────────────────────────────────────────────
echo "==> Service status:"
sudo systemctl --no-pager status ${SERVICE} | head -20

echo ""
echo "==> Quick API health check:"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs | grep -q "200"; then
    echo "   API is UP — http://localhost:8000/docs"
else
    echo "   WARNING: API did not respond on port 8000"
    echo "   Check logs: journalctl -u ${SERVICE} -f"
fi

echo ""
echo "========================================"
echo " Deploy complete."
echo " Tail logs : journalctl -u ${SERVICE} -f"
echo " Rollback  : bash deploy_tarball.sh $BACKUP_DIR/<backup>.tar.gz"
echo "========================================"

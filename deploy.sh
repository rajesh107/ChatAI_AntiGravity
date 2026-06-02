#!/usr/bin/env bash
# Redeploy script — run on the EC2 instance from the app directory.
# Usage:  bash deploy.sh
set -euo pipefail

APP_DIR="/home/ubuntu/chatbot"
SERVICE="chatbot"

cd "$APP_DIR"

echo "==> Creating/activating virtualenv"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate

echo "==> Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Installing/refreshing systemd service"
sudo cp chatbot.service /etc/systemd/system/${SERVICE}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE}

echo "==> Restarting service"
sudo systemctl restart ${SERVICE}

echo "==> Status:"
sudo systemctl --no-pager status ${SERVICE} | head -n 15

echo "==> Done. Tail logs with:  journalctl -u ${SERVICE} -f"

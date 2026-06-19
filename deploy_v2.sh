#!/usr/bin/env bash
# deploy_v2.sh — Deploy ChatAI AntiGravity to the chatbot-v2 service.
#
# Targets /home/ubuntu/chatbot-v2 and the chatbot-v2 systemd unit (gunicorn,
# port 8001). Keeps the existing chatbot-v2.service unit (does NOT overwrite it
# with the repo's chatbot.service) and preserves the existing .env.
#
# Usage:  bash deploy_v2.sh <archive.tar.gz>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="/home/ubuntu/chatbot-v2" \
SERVICE="chatbot-v2" \
BACKUP_DIR="/home/ubuntu/chatbot-v2_backups" \
PORT="8001" \
SKIP_SERVICE_INSTALL="1" \
    bash "$SCRIPT_DIR/deploy_tarball.sh" "$@"

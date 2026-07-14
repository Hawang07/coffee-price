#!/usr/bin/env bash
# อัปเดต code บน VPS (git pull + restart)
# ใช้: bash deploy/deploy.sh
set -euo pipefail

APP_DIR=/var/www/coffee-price
APP_USER=coffee

echo "=== pull latest code ==="
sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only

echo "=== install/update deps ==="
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "=== restart service ==="
systemctl restart coffee-price
systemctl is-active --quiet coffee-price && echo "service OK" || echo "service FAILED — check: journalctl -u coffee-price -n 50"

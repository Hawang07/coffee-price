#!/usr/bin/env bash
# รัน 1 ครั้งบน VPS ใหม่ (Ubuntu 22.04 / 24.04)
# ใช้: sudo bash deploy/setup.sh
set -euo pipefail

APP_DIR=/var/www/coffee-price
APP_USER=coffee
REPO_URL="https://github.com/Hawang07/coffee-price.git"

echo "=== 1. system packages ==="
apt-get update -q
apt-get install -y python3.12 python3.12-venv python3-pip git curl

echo "=== 2. install Caddy ==="
if ! command -v caddy &>/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q
    apt-get install -y caddy
fi

echo "=== 3. create app user ==="
id "$APP_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"

echo "=== 4. clone repo ==="
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "=== 5. python venv + deps ==="
sudo -u "$APP_USER" python3.12 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "=== 6. .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo ">>> แก้ไข $APP_DIR/.env ก่อน start service <<<"
    echo "    nano $APP_DIR/.env"
fi

echo "=== 7. seed DB ==="
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m app.seed

echo "=== 8. install systemd service ==="
cp "$APP_DIR/deploy/coffee-price.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable coffee-price
systemctl start coffee-price

echo "=== 9. Caddy ==="
mkdir -p /var/log/caddy
cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
echo ""
echo ">>> แก้ domain ใน /etc/caddy/Caddyfile ก่อน reload <<<"
echo "    nano /etc/caddy/Caddyfile && systemctl reload caddy"

echo ""
echo "=== setup เสร็จ ==="
echo "    systemctl status coffee-price"
echo "    journalctl -u coffee-price -f"

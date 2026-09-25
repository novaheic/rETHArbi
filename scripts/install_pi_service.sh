#!/usr/bin/env bash
# Install systemd services: research daemon + LAN check-in dashboard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "No .venv found. Run ./scripts/setup_pi.sh first."
  exit 1
fi

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/reports"

install_unit() {
  local src="$1"
  local name="$2"
  local dst="/etc/systemd/system/${name}.service"
  local tmp
  tmp="$(mktemp)"
  sed \
    -e "s|REPLACE_USER|$USER_NAME|g" \
    -e "s|REPLACE_ROOT|$ROOT|g" \
    "$src" > "$tmp"
  echo "==> Installing systemd unit as $dst"
  sudo cp "$tmp" "$dst"
  rm -f "$tmp"
  sudo systemctl enable "${name}.service"
  sudo systemctl restart "${name}.service"
}

install_unit "$ROOT/scripts/reth-basis.service.in" "reth-basis"
install_unit "$ROOT/scripts/reth-dashboard.service.in" "reth-dashboard"

sudo systemctl daemon-reload

sleep 2
sudo systemctl --no-pager --full status reth-basis.service || true
echo
sudo systemctl --no-pager --full status reth-dashboard.service || true

PORT="$(grep -E '^DASHBOARD_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- || true)"
PORT="${PORT:-8080}"

cat <<EOF

Services installed.

Daemon:
  sudo systemctl status reth-basis
  tail -f $ROOT/logs/daemon.log

Dashboard (LAN check-in, no auth):
  sudo systemctl status reth-dashboard
  Open from your PC/phone:  http://$(hostname).local:${PORT}
  Or:                       http://<pi-ip>:${PORT}
  Manual run:               source .venv/bin/activate && python -m src.dashboard

EOF

#!/usr/bin/env bash
# Install systemd service so the daemon starts on boot and restarts on crash.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
UNIT_SRC="$ROOT/scripts/reth-basis.service.in"
UNIT_DST="/etc/systemd/system/reth-basis.service"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "No .venv found. Run ./scripts/setup_pi.sh first."
  exit 1
fi

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/reports"

TMP="$(mktemp)"
sed \
  -e "s|REPLACE_USER|$USER_NAME|g" \
  -e "s|REPLACE_ROOT|$ROOT|g" \
  "$UNIT_SRC" > "$TMP"

echo "==> Installing systemd unit as $UNIT_DST"
sudo cp "$TMP" "$UNIT_DST"
rm -f "$TMP"

sudo systemctl daemon-reload
sudo systemctl enable reth-basis.service
sudo systemctl restart reth-basis.service

sleep 2
sudo systemctl --no-pager --full status reth-basis.service || true

cat <<EOF

Service installed.

Useful commands:
  sudo systemctl status reth-basis     # is it running?
  sudo journalctl -u reth-basis -f     # live logs
  tail -f $ROOT/logs/daemon.log        # app log
  sudo systemctl stop reth-basis       # stop
  sudo systemctl start reth-basis      # start
  sudo systemctl restart reth-basis    # restart after .env changes

EOF

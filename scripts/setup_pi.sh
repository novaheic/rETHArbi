#!/usr/bin/env bash
# One-time setup for Raspberry Pi (Debian / Raspberry Pi OS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing system packages (needs sudo)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  git \
  libopenblas-dev \
  gfortran

PY="$(command -v python3)"
echo "==> Using $PY ($("$PY" --version))"

echo "==> Creating virtual environment..."
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
  echo "    Edit .env and set ETH_RPC_HTTP if you have a reliable RPC URL."
else
  echo "==> .env already exists — leaving it alone"
fi

mkdir -p data reports logs

echo "==> Running a single test observation..."
export PYTHONPATH="$ROOT"
python -m src.main --once

cat <<EOF

Setup complete.

Next steps:
  1. (Optional) Edit .env:  nano .env
  2. Install auto-start (daemon + dashboard):
       sudo ./scripts/install_pi_service.sh
  3. Open the check-in dashboard from your PC:
       http://$(hostname).local:8080
  4. Or run manually:
       source .venv/bin/activate
       python -m src.main

EOF

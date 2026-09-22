#!/usr/bin/env bash
# Run a single live observation cycle against Ethereum mainnet.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH=.
python -m src.main --once "$@"

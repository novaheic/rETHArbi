# rETH Basis Research Daemon

Passive, **read-only** research system for the Rocket Pool rETH/ETH basis on Ethereum mainnet.

> Measure first. Trade later.
> No private keys. No automated trading.

## What it does

Continuously observes:

1. rETH protocol-implied ETH value (`getExchangeRate` on the official contract)
2. Executable rETH/ETH prices on Uniswap V3, Curve, and Balancer
3. Basis, liquidity curves, gas, and net edge after realistic costs
4. Paper portfolios for €500 / €1,000 (and liquidity quotes up to €10,000)
5. Hypothetical P&amp;L under Strategies A–D (mean reversion, fixed-time exit, etc.)

End goal of this phase: a dataset + backtest that answers whether a systematic rETH basis strategy made money after slippage, gas, fees, and execution assumptions.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set ETH_RPC_HTTP to your Ethereum mainnet endpoint

# single observation (vertical slice)
python -m src.main --once

# continuous daemon (default 15s poll)
python -m src.main

# offline synthetic feed
python -m src.main --demo --once
```

### Raspberry Pi (always-on)

See **[docs/RASPBERRY_PI.md](docs/RASPBERRY_PI.md)** for beginner steps:
`setup_pi.sh` + systemd auto-start on boot.

## Environment

| Variable | Purpose |
|---|---|
| `ETH_RPC_HTTP` | Ethereum JSON-RPC (required unless `DEMO_MODE`) |
| `ETH_RPC_WS` | Optional WebSocket RPC |
| `DATABASE_URL` | `sqlite+aiosqlite:///...` or `postgresql+asyncpg://...` |
| `POLL_INTERVAL_SECONDS` | Market quote interval (default 15) |
| `CAPITAL_EUR_1` / `CAPITAL_EUR_2` | Paper capital (€500 / €1,000) |
| `TRADE_SIZES_EUR` | Liquidity curve sizes |
| `DEMO_MODE` | Synthetic data, no RPC |

Official rETH contract (hard-coded from Rocket Pool docs):

`0xae78736Cd615f374D3085123A210448E74Fc6393`

## Architecture

```
src/
  main.py                 # daemon loop
  collectors/             # ethereum, rocketpool, uniswap, curve, balancer, gas
  models/                 # pydantic domain models
  strategy/               # basis math, paper portfolio, simulator
  storage/                # SQLAlchemy async (SQLite / PostgreSQL)
  analytics/              # statistics, backtest, reports
  monitoring/             # health + informational alerts
```

## Database

Tables: `blocks`, `protocol_rates`, `dex_quotes`, `gas_prices`, `basis_observations`,
`simulated_trades`, `portfolio_snapshots`, `strategy_results`.

SQLite is fine for the first vertical slice. For 30–90 day continuous runs, prefer PostgreSQL:

```bash
cd docker && docker compose up -d db
# DATABASE_URL=postgresql+asyncpg://reth:reth@localhost:5432/reth_basis
```

## Reports

After each cycle:

- `reports/dashboard.html` — live snapshot
- `reports/daily_report.txt` — text daily report

## Tests

```bash
pytest -q
```

## Security

- Read-only Ethereum access
- **Never** put a private key in `.env`, source, Docker image, DB, or logs
- Alerts are informational only — they do not trade

## Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | rETH contract rate reader | implemented |
| 2 | DEX executable quotes (Uni/Curve/Balancer) | implemented |
| 3 | Persist observations | implemented |
| 4 | Basis + net edge engine | implemented |
| 5 | Paper portfolio simulator | implemented |
| 6 | Historical backtest (Mode 1) | implemented |
| 7 | 30-day live observation | run the daemon |
| 8 | 90-day research dataset | run + analyze |

## Principle

If the research shows insufficient edge after pessimistic costs and out-of-sample testing, that is a successful outcome — it saves building an automated loss machine.

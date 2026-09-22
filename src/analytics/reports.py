"""Daily HTML/text report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from src.models import BasisObservation, ProtocolRate


def daily_text_report(
    protocol: ProtocolRate,
    sell_obs: Optional[BasisObservation],
    basis_24h: Sequence[float],
    signals_today: int,
    trades_today: int,
    pnl_today: float,
    pnl_cum: float,
    size_500: Optional[BasisObservation] = None,
    size_1000: Optional[BasisObservation] = None,
) -> str:
    market = sell_obs.market_rate if sell_obs else float("nan")
    basis = sell_obs.basis_bps if sell_obs else float("nan")
    bmin = min(basis_24h) if basis_24h else float("nan")
    bmax = max(basis_24h) if basis_24h else float("nan")
    period = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""rETH BASIS REPORT
=================
Period:
{period}
Protocol rate:
{protocol.reth_rate:.10f} ETH/rETH
Market rate:
{market:.10f} ETH/rETH
Current basis:
{basis:+.2f} bp
24h minimum:
{bmin:+.2f} bp
24h maximum:
{bmax:+.2f} bp
€500 executable basis:
{(size_500.basis_bps if size_500 else float('nan')):+.2f} bp
€1,000 executable basis:
{(size_1000.basis_bps if size_1000 else float('nan')):+.2f} bp
Signals today:
{signals_today}
Hypothetical trades:
{trades_today}
Hypothetical P&L:
€{pnl_today:+.2f}
Cumulative P&L:
€{pnl_cum:+.2f}
"""


def write_html_dashboard(
    path: Path,
    protocol: ProtocolRate,
    observations: Sequence[BasisObservation],
    gas_eur: float,
    portfolio_value: float,
    portfolio_pnl: float,
    signals: int,
    completed_trades: int,
) -> Path:
    sell = [o for o in observations if o.direction.value == "sell_reth"]
    best = sell[0] if sell else None
    rows = "".join(
        f"<tr><td>{o.venue}</td><td>€{o.trade_size_eur:.0f}</td>"
        f"<td>{o.basis_bps:+.2f}</td><td>{o.net_edge_bps:+.2f}</td>"
        f"<td>{o.market_rate:.6f}</td></tr>"
        for o in sell
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>rETH Basis Daemon</title>
<style>
body {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 2rem; background: #0f1419; color: #e7ecf1; }}
h1 {{ color: #f2a900; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
.card {{ background: #1a2332; padding: 1rem; border-radius: 8px; }}
.metric {{ font-size: 1.4rem; color: #7dd3fc; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #2a3544; }}
</style></head><body>
<h1>rETH Basis Research Daemon</h1>
<p>Updated {protocol.timestamp.isoformat()} · block {protocol.block_number}</p>
<div class="grid">
  <div class="card"><div>Protocol rate</div><div class="metric">{protocol.reth_rate:.8f}</div></div>
  <div class="card"><div>Market rate</div><div class="metric">{(best.market_rate if best else float('nan')):.8f}</div></div>
  <div class="card"><div>Basis</div><div class="metric">{(best.basis_bps if best else float('nan')):+.2f} bp</div></div>
  <div class="card"><div>Gas</div><div class="metric">€{gas_eur:.3f}</div></div>
  <div class="card"><div>Portfolio</div><div class="metric">€{portfolio_value:.2f}</div></div>
  <div class="card"><div>P&amp;L</div><div class="metric">€{portfolio_pnl:+.2f}</div></div>
  <div class="card"><div>Signals</div><div class="metric">{signals}</div></div>
  <div class="card"><div>Trades</div><div class="metric">{completed_trades}</div></div>
</div>
<table>
<thead><tr><th>Venue</th><th>Size</th><th>Basis bp</th><th>Net edge bp</th><th>Exec rate</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<p style="margin-top:2rem;opacity:0.6">Measure first. Trade later. Read-only · no private keys.</p>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path

"""Render the check-in dashboard HTML with Chart.js."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote


WINDOWS = ("24h", "7d", "30d", "all")


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def _fmt_signed(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:+.{digits}f}{suffix}"
    return str(value)


def render_dashboard(payload: dict[str, Any]) -> str:
    window = payload.get("window", "7d")
    header = payload.get("header") or {}
    board = payload.get("strategy_leaderboard") or []
    trades = payload.get("recent_trades") or []
    venues = payload.get("venue_stats") or []
    data_json = json.dumps(payload, default=str)

    window_links = " ".join(
        f'<a class="chip{" active" if w == window else ""}" href="/?window={quote(w)}">{w}</a>'
        for w in WINDOWS
    )

    board_rows = "".join(
        "<tr>"
        f"<td class='mono'>{b['strategy']}</td>"
        f"<td>{b['n_trades']}</td>"
        f"<td class='{'pos' if b['total_pnl'] >= 0 else 'neg'}'>{b['total_pnl']:+.2f}</td>"
        f"<td class='{'pos' if b['avg_pnl'] >= 0 else 'neg'}'>{b['avg_pnl']:+.2f}</td>"
        f"<td>{100.0 * b['win_rate']:.0f}%</td>"
        f"<td>{b['avg_hold_h']:.1f}h</td>"
        "</tr>"
        for b in board
    ) or "<tr><td colspan='6'>No closed paper trades in this window yet.</td></tr>"

    trade_rows = "".join(
        "<tr>"
        f"<td class='mono'>{t['strategy']}</td>"
        f"<td>{(t.get('exit_timestamp') or '')[:19]}</td>"
        f"<td>{_fmt_signed(t.get('entry_basis_bps'), 1)}</td>"
        f"<td>{_fmt_signed(t.get('exit_basis_bps'), 1)}</td>"
        f"<td class='{'pos' if (t.get('net_pnl_eur') or 0) >= 0 else 'neg'}'>"
        f"{_fmt_signed(t.get('net_pnl_eur'), 2)}</td>"
        f"<td>{((t.get('holding_seconds') or 0) / 3600):.1f}h</td>"
        "</tr>"
        for t in trades
    ) or "<tr><td colspan='6'>No closed trades yet.</td></tr>"

    venue_rows = "".join(
        "<tr>"
        f"<td>{v['venue']}</td>"
        f"<td>€{v['trade_size_eur']:.0f}</td>"
        f"<td>{v['n']}</td>"
        f"<td>{v['avg_basis_bps']:+.2f}</td>"
        f"<td class='{'pos' if v['avg_net_edge_bps'] >= 0 else 'neg'}'>"
        f"{v['avg_net_edge_bps']:+.2f}</td>"
        f"<td>{v['pct_positive_net']:.1f}%</td>"
        "</tr>"
        for v in venues
    ) or "<tr><td colspan='6'>No basis observations yet.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>rETH Basis Research Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #0c1117;
  --panel: #151c27;
  --line: #243044;
  --text: #e8eef6;
  --muted: #8b9bb0;
  --accent: #f0b429;
  --cyan: #5ec8f8;
  --pos: #3dd68c;
  --neg: #f07178;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, monospace;
  background:
    radial-gradient(1200px 600px at 10% -10%, #1a2738 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #1c1a14 0%, transparent 50%),
    var(--bg);
  color: var(--text);
  min-height: 100vh;
}}
header {{
  padding: 1.5rem 1.75rem 0.75rem;
  border-bottom: 1px solid var(--line);
}}
header h1 {{
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.02em;
}}
.sub {{
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.45;
}}
.disclaimer {{
  display: inline-block;
  margin-top: 0.65rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid #3a3420;
  background: #1c190f;
  color: #e6c86c;
  font-size: 0.78rem;
}}
.wrap {{ padding: 1.25rem 1.75rem 2.5rem; max-width: 1280px; margin: 0 auto; }}
.toolbar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 1.25rem;
}}
.chip {{
  color: var(--muted);
  text-decoration: none;
  border: 1px solid var(--line);
  padding: 0.3rem 0.65rem;
  border-radius: 4px;
  font-size: 0.8rem;
}}
.chip.active, .chip:hover {{
  color: var(--text);
  border-color: var(--cyan);
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}}
.card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.85rem 1rem;
}}
.card .label {{ color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }}
.card .metric {{ margin-top: 0.35rem; font-size: 1.25rem; color: var(--cyan); }}
.charts {{
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}}
@media (min-width: 960px) {{
  .charts {{ grid-template-columns: 1fr 1fr; }}
  .charts .wide {{ grid-column: 1 / -1; }}
}}
.chart-card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.85rem 1rem 1rem;
}}
.chart-card h2 {{
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--muted);
}}
.chart-wrap {{ position: relative; height: 260px; }}
.chart-wrap.tall {{ height: 300px; }}
section {{
  margin-bottom: 1.5rem;
}}
section h2 {{
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  color: var(--accent);
  font-weight: 500;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
  font-size: 0.8rem;
}}
th, td {{
  text-align: left;
  padding: 0.45rem 0.65rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}}
th {{ color: var(--muted); font-weight: 500; }}
.mono {{ font-size: 0.72rem; word-break: break-all; }}
.pos {{ color: var(--pos); }}
.neg {{ color: var(--neg); }}
.scroll {{ overflow-x: auto; }}
footer {{
  color: var(--muted);
  font-size: 0.75rem;
  margin-top: 1rem;
}}
</style>
</head>
<body>
<header>
  <h1>rETH Basis Research Dashboard</h1>
  <div class="sub">
    Measure first. Trade later. Window <strong>{window}</strong> ·
    generated {payload.get("generated_at", "")[:19]} UTC ·
    auto-refresh 60s
  </div>
  <div class="disclaimer">{payload.get("paper_disclaimer", "Paper / hypothetical only.")}</div>
</header>
<div class="wrap">
  <div class="toolbar">{window_links}</div>

  <div class="grid">
    <div class="card"><div class="label">Protocol rate</div><div class="metric">{_fmt(header.get("protocol_rate"), 8)}</div></div>
    <div class="card"><div class="label">Market rate</div><div class="metric">{_fmt(header.get("market_rate"), 8)}</div></div>
    <div class="card"><div class="label">Basis</div><div class="metric">{_fmt_signed(header.get("basis_bps"), 2, " bp")}</div></div>
    <div class="card"><div class="label">Net edge</div><div class="metric">{_fmt_signed(header.get("net_edge_bps"), 2, " bp")}</div></div>
    <div class="card"><div class="label">Gas</div><div class="metric">€{_fmt(header.get("gas_eur"), 3)}</div></div>
    <div class="card"><div class="label">Observations</div><div class="metric">{_fmt(header.get("observation_count"), 0)}</div></div>
    <div class="card"><div class="label">Closed paper trades</div><div class="metric">{_fmt(header.get("closed_trade_count"), 0)}</div></div>
    <div class="card"><div class="label">Last DB write</div><div class="metric" style="font-size:0.95rem">{(header.get("last_write") or "—")[:19]}</div></div>
  </div>

  <div class="charts">
    <div class="chart-card wide">
      <h2>Basis over time (Uniswap sell)</h2>
      <div class="chart-wrap tall"><canvas id="chartBasis"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Protocol vs market rate</h2>
      <div class="chart-wrap"><canvas id="chartRates"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Net edge after costs (bp)</h2>
      <div class="chart-wrap"><canvas id="chartNetEdge"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Cumulative paper P&amp;L (top strategies)</h2>
      <div class="chart-wrap"><canvas id="chartCumPnl"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Portfolio value (key paper books)</h2>
      <div class="chart-wrap"><canvas id="chartPortfolio"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Basis histogram</h2>
      <div class="chart-wrap"><canvas id="chartHist"></canvas></div>
    </div>
  </div>

  <section>
    <h2>Strategy leaderboard (closed paper trades)</h2>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Strategy</th><th>N</th><th>Total €</th><th>Avg €</th><th>Win%</th><th>Avg hold</th>
        </tr></thead>
        <tbody>{board_rows}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Venue comparison</h2>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Venue</th><th>Size</th><th>N</th><th>Avg basis bp</th><th>Avg net edge bp</th><th>% net &gt; 0</th>
        </tr></thead>
        <tbody>{venue_rows}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Recent closed paper trades</h2>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Strategy</th><th>Exit</th><th>Entry bp</th><th>Exit bp</th><th>Net €</th><th>Hold</th>
        </tr></thead>
        <tbody>{trade_rows}</tbody>
      </table>
    </div>
  </section>

  <footer>LAN only · no auth · read-only SQLite · block {header.get("block_number") or "—"}</footer>
</div>

<script>
const DATA = {data_json};
const series = DATA.basis_series || [];
const bySize = {{}};
for (const row of series) {{
  const key = String(row.trade_size_eur);
  if (!bySize[key]) bySize[key] = [];
  bySize[key].push(row);
}}

const colors = ["#5ec8f8", "#f0b429", "#3dd68c", "#c792ea", "#f07178", "#82aaff"];
const commonOpts = {{
  responsive: true,
  maintainAspectRatio: false,
  interaction: {{ mode: "index", intersect: false }},
  plugins: {{
    legend: {{ labels: {{ color: "#8b9bb0", boxWidth: 12, font: {{ size: 11 }} }} }},
  }},
  scales: {{
    x: {{
      ticks: {{ color: "#8b9bb0", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }},
      grid: {{ color: "rgba(36,48,68,0.7)" }},
    }},
    y: {{
      ticks: {{ color: "#8b9bb0" }},
      grid: {{ color: "rgba(36,48,68,0.7)" }},
    }},
  }},
}};

function labelsFor(rows) {{
  return rows.map(r => (r.timestamp || "").slice(5, 16).replace("T", " "));
}}

const sizeKeys = Object.keys(bySize).sort((a,b) => Number(a)-Number(b));
const primary = bySize["1000"] || bySize[sizeKeys[0]] || [];

new Chart(document.getElementById("chartBasis"), {{
  type: "line",
  data: {{
    labels: labelsFor(primary.length ? primary : series),
    datasets: sizeKeys.map((k, i) => ({{
      label: "€" + k,
      data: (bySize[k] || []).map(r => r.basis_bps),
      borderColor: colors[i % colors.length],
      backgroundColor: "transparent",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.15,
    }})).concat([{{
      label: "0 bp",
      data: (primary.length ? primary : series).map(() => 0),
      borderColor: "#64748b",
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
    }}]),
  }},
  options: commonOpts,
}});

new Chart(document.getElementById("chartRates"), {{
  type: "line",
  data: {{
    labels: labelsFor(primary),
    datasets: [
      {{
        label: "protocol",
        data: primary.map(r => r.protocol_rate),
        borderColor: "#f0b429",
        pointRadius: 0,
        borderWidth: 1.6,
        tension: 0.15,
      }},
      {{
        label: "market",
        data: primary.map(r => r.market_rate),
        borderColor: "#5ec8f8",
        pointRadius: 0,
        borderWidth: 1.4,
        tension: 0.15,
      }},
    ],
  }},
  options: commonOpts,
}});

new Chart(document.getElementById("chartNetEdge"), {{
  type: "line",
  data: {{
    labels: labelsFor(primary),
    datasets: [{{
      label: "net edge bp (€1000)",
      data: primary.map(r => r.net_edge_bps),
      borderColor: "#3dd68c",
      pointRadius: 0,
      borderWidth: 1.5,
      tension: 0.15,
    }}, {{
      label: "0",
      data: primary.map(() => 0),
      borderColor: "#64748b",
      borderWidth: 1,
      borderDash: [4,4],
      pointRadius: 0,
    }}],
  }},
  options: commonOpts,
}});

const cum = DATA.cumulative_pnl || {{}};
const cumNames = Object.keys(cum);
new Chart(document.getElementById("chartCumPnl"), {{
  type: "line",
  data: {{
    labels: cumNames.length ? labelsFor(cum[cumNames[0]]) : [],
    datasets: cumNames.map((name, i) => ({{
      label: name,
      data: (cum[name] || []).map(p => p.cum_pnl),
      borderColor: colors[i % colors.length],
      pointRadius: 0,
      borderWidth: 1.4,
      tension: 0.15,
    }})),
  }},
  options: commonOpts,
}});

const ports = DATA.portfolio_series || {{}};
const portNames = Object.keys(ports);
new Chart(document.getElementById("chartPortfolio"), {{
  type: "line",
  data: {{
    labels: portNames.length ? labelsFor(ports[portNames[0]]) : [],
    datasets: portNames.map((name, i) => ({{
      label: name,
      data: (ports[name] || []).map(p => p.total_eur),
      borderColor: colors[i % colors.length],
      pointRadius: 0,
      borderWidth: 1.4,
      tension: 0.15,
    }})),
  }},
  options: commonOpts,
}});

const histSource = (bySize["1000"] || primary).map(r => r.basis_bps).filter(v => v !== null && v !== undefined);
const bins = 40;
let histLabels = [];
let histCounts = [];
if (histSource.length) {{
  const min = Math.min(...histSource);
  const max = Math.max(...histSource);
  const width = (max - min) / bins || 1;
  histCounts = Array(bins).fill(0);
  for (const v of histSource) {{
    let idx = Math.floor((v - min) / width);
    if (idx >= bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    histCounts[idx] += 1;
  }}
  histLabels = Array.from({{length: bins}}, (_, i) => (min + (i + 0.5) * width).toFixed(1));
}}
new Chart(document.getElementById("chartHist"), {{
  type: "bar",
  data: {{
    labels: histLabels,
    datasets: [{{
      label: "count",
      data: histCounts,
      backgroundColor: "rgba(94, 200, 248, 0.65)",
      borderWidth: 0,
    }}],
  }},
  options: {{
    ...commonOpts,
    plugins: {{ legend: {{ display: false }} }},
  }},
}});
</script>
</body>
</html>
"""

"""Statistical helpers and research question summaries."""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd


def basis_probabilities(basis_bps: Sequence[float], thresholds: Iterable[float]) -> dict[str, float]:
    arr = np.asarray(list(basis_bps), dtype=float)
    if len(arr) == 0:
        return {f"P(basis<{t:.0f}bp)": float("nan") for t in thresholds}
    return {f"P(basis<{t:.0f}bp)": float(np.mean(arr < t)) for t in thresholds}


def trade_metrics(pnls: Sequence[float], holding_seconds: Sequence[float], capital: float) -> dict:
    arr = np.asarray(list(pnls), dtype=float)
    holds = np.asarray(list(holding_seconds), dtype=float)
    if len(arr) == 0:
        return {"n_trades": 0}

    wins = arr[arr > 0]
    losses = arr[arr < 0]
    total_return = float(arr.sum())
    avg_hold_days = float(holds.mean() / 86400) if len(holds) else 0.0
    deployed_days = float(holds.sum() / 86400)

    return {
        "n_trades": int(len(arr)),
        "total_return": total_return,
        "win_rate": float(len(wins) / len(arr)),
        "avg_trade": float(arr.mean()),
        "median_trade": float(np.median(arr)),
        "best_trade": float(arr.max()),
        "worst_trade": float(arr.min()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf"),
        "avg_holding_seconds": float(holds.mean()) if len(holds) else 0.0,
        "median_holding_seconds": float(np.median(holds)) if len(holds) else 0.0,
        "return_per_trade": total_return / len(arr),
        "return_per_day_capital": (total_return / capital / deployed_days) if deployed_days > 0 else 0.0,
        "return_per_year_capital": (
            (total_return / capital / deployed_days) * 365 if deployed_days > 0 else 0.0
        ),
        "avg_hold_days": avg_hold_days,
    }


def max_drawdown(equity: Sequence[float]) -> float:
    eq = np.asarray(list(equity), dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return float(dd.min())


def sharpe_ratio(returns: Sequence[float], periods_per_year: float = 365.0) -> float:
    r = np.asarray(list(returns), dtype=float)
    if len(r) < 2 or r.std() == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * r.mean() / r.std())


def sortino_ratio(returns: Sequence[float], periods_per_year: float = 365.0) -> float:
    r = np.asarray(list(returns), dtype=float)
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * r.mean() / downside.std())


def observations_frame(rows) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": r.timestamp,
                "venue": r.venue,
                "trade_size_eur": r.trade_size_eur,
                "basis_bps": r.basis_bps,
                "net_edge_bps": r.net_edge_bps,
                "protocol_rate": r.protocol_rate,
                "market_rate": r.market_rate,
            }
            for r in rows
        ]
    )

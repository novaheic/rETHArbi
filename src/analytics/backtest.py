"""Historical backtest engine (Mode 1: price series; Mode 2 stub for pool reconstruct)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence

import pandas as pd

from src.analytics.statistics import max_drawdown, sharpe_ratio, sortino_ratio, trade_metrics
from src.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    strategy: str
    mode: str
    metrics: dict
    equity_curve: List[float]
    trades: List[dict]


class HistoricalBacktester:
    """
    Mode 1 — Historical price backtest using stored basis_observations.
    Mode 2 — Placeholder for pool-state reconstruction (future).
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def mode1_from_frame(
        self,
        df: pd.DataFrame,
        entry_bps: float,
        exit_bps: float,
        capital: float,
        venue: str = "uniswap_v3",
        trade_size_eur: Optional[float] = None,
    ) -> BacktestResult:
        """Walk-forward, no look-ahead mean-reversion on stored sell basis."""
        trade_size_eur = trade_size_eur or capital
        sub = df[(df["venue"] == venue) & (df["direction"] == "sell_reth")].copy()
        if trade_size_eur:
            sub = sub[sub["trade_size_eur"] == trade_size_eur]
        sub = sub.sort_values("timestamp")

        cash = capital
        position = 0.0
        entry_rate = 0.0
        entry_protocol = 0.0
        entry_ts = None
        entry_basis = 0.0
        equity = [capital]
        trades: List[dict] = []
        costs_rt_bps = 10.0  # rough stand-in when gas not in frame; prefer live sim

        for _, row in sub.iterrows():
            basis = row["basis_bps"]
            protocol = row["protocol_rate"]
            market = row["market_rate"]
            ts = row["timestamp"]

            if position == 0 and basis <= entry_bps:
                # Enter
                position = cash
                cash = 0.0
                entry_rate = market
                entry_protocol = protocol
                entry_ts = ts
                entry_basis = basis
            elif position > 0 and basis >= exit_bps:
                # Exit
                staking = position * (protocol / entry_protocol - 1.0)
                # Basis recovery approx
                basis_pnl = position * ((basis - entry_basis) / 10_000)
                cost = position * (costs_rt_bps / 10_000)
                net = basis_pnl + staking - cost
                cash = position + net
                hold = (ts - entry_ts).total_seconds() if entry_ts is not None else 0
                trades.append(
                    {
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "entry_basis": entry_basis,
                        "exit_basis": basis,
                        "net_pnl": net,
                        "staking_carry": staking,
                        "holding_seconds": hold,
                    }
                )
                position = 0.0

            equity.append(cash + position)

        pnls = [t["net_pnl"] for t in trades]
        holds = [t["holding_seconds"] for t in trades]
        metrics = trade_metrics(pnls, holds, capital)
        metrics["max_drawdown"] = max_drawdown(equity)
        rets = pd.Series(equity).pct_change().dropna()
        metrics["sharpe"] = sharpe_ratio(rets.tolist())
        metrics["sortino"] = sortino_ratio(rets.tolist())
        metrics["final_equity"] = equity[-1] if equity else capital

        return BacktestResult(
            strategy=f"A_entry{entry_bps:.0f}_exit{exit_bps:.0f}",
            mode="historical_price",
            metrics=metrics,
            equity_curve=equity,
            trades=trades,
        )

    def mode2_pool_reconstruct(self, *args, **kwargs) -> BacktestResult:
        raise NotImplementedError(
            "Mode 2 (pool-state reconstruction) will be implemented once "
            "sufficient on-chain snapshots are collected."
        )

    def walk_forward(
        self,
        df: pd.DataFrame,
        train_days: int = 30,
        test_days: int = 15,
        capital: float = 1000.0,
    ) -> List[BacktestResult]:
        """Optimize on train window, evaluate on test window; repeat."""
        if df.empty:
            return []
        df = df.sort_values("timestamp")
        start = df["timestamp"].min()
        results: List[BacktestResult] = []
        cursor = start
        entries = self.settings.entry_thresholds()
        exits = self.settings.exit_thresholds()

        while True:
            train_end = cursor + pd.Timedelta(days=train_days)
            test_end = train_end + pd.Timedelta(days=test_days)
            train = df[(df["timestamp"] >= cursor) & (df["timestamp"] < train_end)]
            test = df[(df["timestamp"] >= train_end) & (df["timestamp"] < test_end)]
            if train.empty or test.empty:
                break

            best_score = float("-inf")
            best_params = (entries[0], exits[0])
            for e in entries:
                for x in exits:
                    r = self.mode1_from_frame(train, e, x, capital)
                    score = r.metrics.get("total_return", 0.0)
                    if score > best_score:
                        best_score = score
                        best_params = (e, x)

            oos = self.mode1_from_frame(test, best_params[0], best_params[1], capital)
            oos.strategy = f"WF_entry{best_params[0]:.0f}_exit{best_params[1]:.0f}"
            oos.metrics["train_score"] = best_score
            oos.metrics["window_start"] = str(cursor)
            oos.metrics["window_end"] = str(test_end)
            results.append(oos)
            cursor = test_end

        return results

"""Generate research charts from stored observations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def generate_charts(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    """
    Chart 1: protocol vs market
    Chart 2: basis over time
    Chart 3: basis histogram
    Chart 4–6: placeholders when columns available
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    if df.empty:
        return paths

    sell = df[df.get("direction", "sell_reth") == "sell_reth"].copy() if "direction" in df.columns else df.copy()
    if sell.empty:
        sell = df

    # Chart 1
    if {"protocol_rate", "market_rate", "timestamp"}.issubset(sell.columns):
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(sell["timestamp"], sell["protocol_rate"], label="protocol", linewidth=1.5)
        ax.plot(sell["timestamp"], sell["market_rate"], label="market", linewidth=1.2, alpha=0.85)
        ax.set_title("rETH protocol value vs market price")
        ax.set_ylabel("ETH per rETH")
        ax.legend()
        fig.autofmt_xdate()
        p = out_dir / "chart1_protocol_vs_market.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    # Chart 2
    if {"basis_bps", "timestamp"}.issubset(sell.columns):
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(sell["timestamp"], sell["basis_bps"], color="#2563eb", linewidth=1.0)
        ax.axhline(0, color="#64748b", linewidth=0.8)
        ax.set_title("rETH basis over time")
        ax.set_ylabel("basis (bp)")
        fig.autofmt_xdate()
        p = out_dir / "chart2_basis_over_time.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

        # Chart 3
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(sell["basis_bps"].dropna(), bins=40, color="#0ea5e9", edgecolor="white")
        ax.set_title("Basis histogram")
        ax.set_xlabel("basis (bp)")
        p = out_dir / "chart3_basis_histogram.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    # Chart 4: basis vs ETH volatility (if present)
    if {"basis_bps", "eth_vol_1h"}.issubset(sell.columns):
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(sell["eth_vol_1h"], sell["basis_bps"], alpha=0.4, s=12)
        ax.set_title("Basis vs ETH volatility")
        ax.set_xlabel("ETH 1h vol")
        ax.set_ylabel("basis (bp)")
        p = out_dir / "chart4_basis_vs_vol.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    # Chart 5: basis vs liquidity
    if {"basis_bps", "liquidity"}.issubset(sell.columns):
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(sell["liquidity"], sell["basis_bps"], alpha=0.4, s=12)
        ax.set_title("Basis vs liquidity")
        ax.set_xlabel("liquidity")
        ax.set_ylabel("basis (bp)")
        p = out_dir / "chart5_basis_vs_liquidity.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    # Chart 6: portfolio
    if {"portfolio_value", "timestamp"}.issubset(df.columns):
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df["timestamp"], df["portfolio_value"], color="#16a34a")
        ax.set_title("Simulated portfolio value")
        ax.set_ylabel("EUR")
        fig.autofmt_xdate()
        p = out_dir / "chart6_portfolio.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    return paths

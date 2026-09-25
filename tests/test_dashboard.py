"""Dashboard payload + HTML rendering tests (DEMO_MODE / temp SQLite)."""

from __future__ import annotations

import pytest

from src.config import Settings
from src.dashboard.html import render_dashboard
from src.main import Daemon
from src.storage import Database


@pytest.mark.asyncio
async def test_dashboard_payload_and_html(tmp_path):
    settings = Settings(
        DEMO_MODE=True,
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'dash.db'}",
        REPORTS_DIR=str(tmp_path / "reports"),
        POLL_INTERVAL_SECONDS=1,
        ENTRY_THRESHOLDS_BPS="-20,-30",
        EXIT_THRESHOLDS_BPS="0,-5",
        MAX_HOLDING_SECONDS="3600,86400",
        TRADE_SIZES_EUR="500,1000",
        CAPITAL_EUR_1=500,
        CAPITAL_EUR_2=1000,
    )
    daemon = Daemon(settings)
    await daemon.run(once=True)

    db = Database(settings)
    await db.init()
    try:
        payload = await db.load_dashboard_payload(window="all")
    finally:
        await db.close()

    assert payload["header"]["observation_count"] >= 1
    assert payload["header"]["protocol_rate"] is not None
    assert isinstance(payload["basis_series"], list)
    assert len(payload["basis_series"]) >= 1

    html = render_dashboard(payload)
    assert "rETH Basis Research Dashboard" in html
    assert "chartBasis" in html
    assert "Paper / hypothetical" in html
    assert "const DATA =" in html


@pytest.mark.asyncio
async def test_portfolio_snapshots_persisted(tmp_path):
    settings = Settings(
        DEMO_MODE=True,
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'port.db'}",
        REPORTS_DIR=str(tmp_path / "reports"),
        ENTRY_THRESHOLDS_BPS="-20",
        EXIT_THRESHOLDS_BPS="0",
        MAX_HOLDING_SECONDS="3600",
        TRADE_SIZES_EUR="500,1000",
        CAPITAL_EUR_1=500,
        CAPITAL_EUR_2=1000,
    )
    daemon = Daemon(settings)
    await daemon.run(once=True)

    db = Database(settings)
    await db.init()
    try:
        series = await db.portfolio_series(window="all")
    finally:
        await db.close()

    assert any("A_entry-30_exit0" in k or "hold_eth" in k or "hold_reth" in k for k in series)

"""Integration-style tests using DEMO_MODE (no RPC)."""

from __future__ import annotations

import pytest

from src.config import Settings
from src.main import Daemon


@pytest.mark.asyncio
async def test_demo_once(tmp_path):
    settings = Settings(
        DEMO_MODE=True,
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
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
    assert (tmp_path / "reports" / "dashboard.html").exists()
    assert (tmp_path / "reports" / "daily_report.txt").exists()
    assert daemon.health.status.observations == 1

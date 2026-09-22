"""Health and informational alerts (no trading)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from src.models import BasisObservation, ProtocolRate

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    observations: int = 0
    signals: int = 0
    alerts: List[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.consecutive_failures < 5


class HealthMonitor:
    def __init__(self, signal_basis_bps: float = -20.0):
        self.status = HealthStatus()
        self.signal_basis_bps = signal_basis_bps

    def record_success(self) -> None:
        self.status.last_success = datetime.now(timezone.utc)
        self.status.consecutive_failures = 0
        self.status.observations += 1

    def record_failure(self, exc: Exception) -> None:
        self.status.consecutive_failures += 1
        self.status.last_error = str(exc)[:500]
        logger.error("Collector failure (%s): %s", self.status.consecutive_failures, exc)

    def maybe_alert(
        self,
        protocol: ProtocolRate,
        obs: BasisObservation,
    ) -> Optional[str]:
        """Informational alert only — never triggers trades."""
        if obs.basis_bps > self.signal_basis_bps:
            return None
        if obs.net_edge_bps <= 0:
            return None

        self.status.signals += 1
        msg = (
            f"rETH basis signal\n"
            f"Venue: {obs.venue}\n"
            f"Size: €{obs.trade_size_eur:.0f}\n"
            f"Basis: {obs.basis_bps:.1f} bp\n"
            f"Estimated net edge: {obs.net_edge_bps:+.1f} bp\n"
            f"Protocol rate:\n{protocol.reth_rate:.6f} ETH/rETH\n"
            f"Executable market rate:\n{obs.market_rate:.6f} ETH/rETH\n"
            f"Gas:\n€{obs.gas_eur:.2f}"
        )
        self.status.alerts.append(msg)
        logger.warning("ALERT (informational only — no trade):\n%s", msg)
        return msg

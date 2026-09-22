"""Strategy C — exchange-rate update reaction analysis.

Records every protocol rate change and samples market prices at
configured block/time offsets afterward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


BLOCK_OFFSETS = (1, 10, 50, 100, 500)
TIME_OFFSETS = (
    ("1h", timedelta(hours=1)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
)


@dataclass
class RateUpdateEvent:
    update_timestamp: datetime
    update_block: int
    old_rate: float
    new_rate: float
    rate_change_bps: float
    market_before: Optional[float] = None
    samples: Dict[str, Optional[float]] = field(default_factory=dict)


class RewardUpdateTracker:
    def __init__(self) -> None:
        self.last_rate: Optional[float] = None
        self.events: List[RateUpdateEvent] = []
        self._pending: List[RateUpdateEvent] = []

    def on_protocol_rate(
        self,
        rate: float,
        block: int,
        ts: datetime,
        market_mid: Optional[float],
    ) -> Optional[RateUpdateEvent]:
        if self.last_rate is None:
            self.last_rate = rate
            return None
        if rate == self.last_rate:
            return None

        change_bps = (rate / self.last_rate - 1.0) * 10_000
        event = RateUpdateEvent(
            update_timestamp=ts,
            update_block=block,
            old_rate=self.last_rate,
            new_rate=rate,
            rate_change_bps=change_bps,
            market_before=market_mid,
        )
        self.last_rate = rate
        self.events.append(event)
        self._pending.append(event)
        return event

    def on_market_tick(
        self,
        block: int,
        ts: datetime,
        market_mid: float,
    ) -> None:
        """Fill post-update samples when offsets are reached (no look-ahead at decision time)."""
        still_pending: List[RateUpdateEvent] = []
        for event in self._pending:
            done = True
            for offset in BLOCK_OFFSETS:
                key = f"{offset}_blocks"
                if key not in event.samples:
                    if block >= event.update_block + offset:
                        event.samples[key] = market_mid
                    else:
                        done = False
            for label, delta in TIME_OFFSETS:
                key = label
                if key not in event.samples:
                    if ts >= event.update_timestamp + delta:
                        event.samples[key] = market_mid
                    else:
                        done = False
            if not done:
                still_pending.append(event)
        self._pending = still_pending

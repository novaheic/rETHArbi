"""Strategy D — ETH volatility / liquidity stress features."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import log, sqrt
from typing import Deque, Optional, Tuple


@dataclass
class VolSnapshot:
    timestamp: datetime
    vol_5m: Optional[float]
    vol_1h: Optional[float]
    vol_6h: Optional[float]
    vol_24h: Optional[float]


class VolatilityTracker:
    """Rolling log-return volatility from ETH/EUR (or ETH mid) samples."""

    def __init__(self, max_age: timedelta = timedelta(hours=25)):
        self._samples: Deque[Tuple[datetime, float]] = deque()
        self.max_age = max_age

    def add(self, ts: datetime, price: float) -> VolSnapshot:
        self._samples.append((ts, price))
        cutoff = ts - self.max_age
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        return VolSnapshot(
            timestamp=ts,
            vol_5m=self._vol(ts, timedelta(minutes=5)),
            vol_1h=self._vol(ts, timedelta(hours=1)),
            vol_6h=self._vol(ts, timedelta(hours=6)),
            vol_24h=self._vol(ts, timedelta(hours=24)),
        )

    def _vol(self, now: datetime, window: timedelta) -> Optional[float]:
        start = now - window
        pts = [(t, p) for t, p in self._samples if t >= start]
        if len(pts) < 3:
            return None
        rets = []
        for i in range(1, len(pts)):
            if pts[i - 1][1] > 0 and pts[i][1] > 0:
                rets.append(log(pts[i][1] / pts[i - 1][1]))
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        # annualize roughly from sample cadence (~15s → 5760/day)
        return sqrt(var) * sqrt(365 * 24 * 60 * 4)

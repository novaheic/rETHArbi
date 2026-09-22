"""Placeholder for future CowSwap / aggregator quotes.

CowSwap executable quotes require their API (not on-chain eth_call).
Wire in when API access is configured; keep CoinGecko out of execution paths.
"""

from __future__ import annotations

from typing import List

from src.models import DexQuote


class CowSwapCollector:
    async def quote_sizes(self, *args, **kwargs) -> List[DexQuote]:
        return []

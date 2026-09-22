"""Curve rETH/WETH pool quote collector (get_dy)."""

from __future__ import annotations

import logging
from typing import List, Optional

from src.collectors.ethereum import EthereumClient
from src.config import Settings
from src.models import DexQuote, TradeDirection

logger = logging.getLogger(__name__)

WEI = 10**18

# Curve StableSwap (including many NG pools) uses int128 indices for get_dy
CURVE_ABI = [
    {
        "name": "get_dy",
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "j", "type": "int128"},
            {"name": "dx", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "name": "coins",
        "inputs": [{"name": "i", "type": "uint256"}],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "name": "balances",
        "inputs": [{"name": "i", "type": "uint256"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class CurveCollector:
    """Executable quotes from Curve wETH/rETH StableSwap pool."""

    def __init__(self, client: EthereumClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._pool = None
        self._reth_index: Optional[int] = None
        self._eth_index: Optional[int] = None

    def _ensure(self):
        if self._pool is None:
            self._pool = self.client.contract(self.settings.curve_reth_eth_pool, CURVE_ABI)
        return self._pool

    async def _resolve_indices(self) -> None:
        if self._reth_index is not None:
            return
        pool = self._ensure()
        reth = self.settings.reth_address.lower()
        for i in range(2):
            coin = await pool.functions.coins(i).call()
            if coin.lower() == reth:
                self._reth_index = i
            else:
                self._eth_index = i
        if self._reth_index is None or self._eth_index is None:
            self._eth_index = 0
            self._reth_index = 1
            logger.warning("Could not resolve Curve coin indices; using WETH=0, rETH=1")

    async def quote_sizes(
        self,
        trade_sizes_eur: List[float],
        eth_eur: float,
        protocol_rate: float,
    ) -> List[DexQuote]:
        await self._resolve_indices()
        pool = self._ensure()
        block = await self.client.get_block_number()
        quotes: List[DexQuote] = []
        assert self._reth_index is not None and self._eth_index is not None

        try:
            bal0 = await pool.functions.balances(0).call()
            bal1 = await pool.functions.balances(1).call()
            if bal0 == 0 or bal1 == 0:
                logger.warning("Curve pool %s has zero balances; skipping", self.settings.curve_reth_eth_pool)
                return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Curve balance check failed: %s", str(exc)[:200])

        for size_eur in trade_sizes_eur:
            eth_amount = size_eur / eth_eur
            reth_in = eth_amount / protocol_rate

            try:
                eth_out_wei = await pool.functions.get_dy(
                    self._reth_index,
                    self._eth_index,
                    int(reth_in * WEI),
                ).call()
                eth_out = eth_out_wei / WEI
                sell_price = eth_out / reth_in if reth_in > 0 else 0.0

                reth_out_wei = await pool.functions.get_dy(
                    self._eth_index,
                    self._reth_index,
                    int(eth_amount * WEI),
                ).call()
                reth_out = reth_out_wei / WEI
                buy_price = eth_amount / reth_out if reth_out > 0 else 0.0

                mid = (sell_price + buy_price) / 2 if sell_price and buy_price else sell_price

                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="curve",
                        pool=self.settings.curve_reth_eth_pool,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.SELL_RETH,
                        amount_in=reth_in,
                        amount_out=eth_out,
                        effective_price=sell_price,
                        mid_price=mid,
                        fee=0.0004,
                        price_impact=(mid - sell_price) / mid if mid else None,
                        gas_estimate=250_000,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        liquidity=None,
                    )
                )
                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="curve",
                        pool=self.settings.curve_reth_eth_pool,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.BUY_RETH,
                        amount_in=eth_amount,
                        amount_out=reth_out,
                        effective_price=buy_price,
                        mid_price=mid,
                        fee=0.0004,
                        price_impact=(buy_price - mid) / mid if mid else None,
                        gas_estimate=250_000,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        liquidity=None,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Curve quote failed for €%.0f: %s", size_eur, str(exc)[:200])

        return quotes

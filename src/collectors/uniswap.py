"""Uniswap V3 executable quote collector for rETH/WETH."""

from __future__ import annotations

import logging
import math
from typing import List, Optional

from src.collectors.ethereum import EthereumClient
from src.config import Settings
from src.models import DexQuote, TradeDirection

logger = logging.getLogger(__name__)

WEI = 10**18
Q96 = 2**96


class UniswapV3Collector:
    """Executable quotes via QuoterV2 — not mid/ticker prices."""

    def __init__(self, client: EthereumClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._quoter = None
        self._pool = None

    def _ensure(self):
        if self._quoter is None:
            self._quoter = self.client.contract(
                self.settings.uniswap_quoter_v2,
                self.settings.abis_dir / "uniswap_v3_quoter_v2.json",
            )
        if self._pool is None:
            self._pool = self.client.contract(
                self.settings.uniswap_v3_reth_weth_005,
                self.settings.abis_dir / "uniswap_v3_pool.json",
            )
        return self._quoter, self._pool

    async def mid_price(self) -> tuple[float, float]:
        """Return (mid_price ETH/rETH, liquidity)."""
        _, pool = self._ensure()
        slot0 = await self.client.call(pool.functions.slot0)
        liquidity = await self.client.call(pool.functions.liquidity)
        sqrt_price_x96 = slot0[0]
        # token0 = rETH, token1 = WETH on the 0.05% pool
        # price = (sqrtPriceX96 / 2^96)^2 = token1/token0 = WETH/rETH = ETH/rETH
        price = (sqrt_price_x96 / Q96) ** 2
        return float(price), float(liquidity)

    async def _quote_exact_in(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
        fee: int,
    ) -> Optional[tuple[int, int]]:
        quoter, _ = self._ensure()
        w3 = self.client.w3
        params = (
            w3.to_checksum_address(token_in),
            w3.to_checksum_address(token_out),
            amount_in_wei,
            fee,
            0,
        )
        try:
            # QuoterV2 uses a state-mutating call; eth_call still works
            result = await quoter.functions.quoteExactInputSingle(params).call()
            amount_out, _sqrt_after, _ticks, gas_est = result
            return int(amount_out), int(gas_est)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Quoter fee=%s failed: %s", fee, exc)
            return None

    async def best_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
    ) -> Optional[tuple[int, int, int]]:
        """Return (amount_out, gas_estimate, fee_tier) for the best fee tier."""
        best: Optional[tuple[int, int, int]] = None
        for fee in self.settings.fee_tiers():
            quoted = await self._quote_exact_in(token_in, token_out, amount_in_wei, fee)
            if quoted is None:
                continue
            amount_out, gas_est = quoted
            if best is None or amount_out > best[0]:
                best = (amount_out, gas_est, fee)
        return best

    async def quote_sizes(
        self,
        trade_sizes_eur: List[float],
        eth_eur: float,
        protocol_rate: float,
    ) -> List[DexQuote]:
        block = await self.client.get_block_number()
        mid, liquidity = await self.mid_price()
        quotes: List[DexQuote] = []

        reth = self.settings.reth_address
        weth = self.settings.weth_address

        for size_eur in trade_sizes_eur:
            eth_amount = size_eur / eth_eur
            # Sell rETH for ETH: amount_in = rETH equivalent to size_eur at protocol rate
            reth_in = eth_amount / protocol_rate
            reth_in_wei = int(reth_in * WEI)

            sell = await self.best_quote(reth, weth, reth_in_wei)
            buy = await self.best_quote(weth, reth, int(eth_amount * WEI))

            sell_price = mid
            buy_price = mid
            sell_gas = self.settings.gas_units_swap
            buy_gas = self.settings.gas_units_swap
            sell_fee = 0.0005
            buy_fee = 0.0005
            sell_out = 0.0
            buy_out = 0.0

            if sell is not None:
                amount_out, gas_est, fee = sell
                sell_out = amount_out / WEI
                sell_price = sell_out / reth_in if reth_in > 0 else mid
                sell_gas = gas_est or sell_gas
                sell_fee = fee / 1_000_000

            if buy is not None:
                amount_out, gas_est, fee = buy
                buy_out = amount_out / WEI  # rETH received
                # effective buy rate as ETH per rETH = eth_spent / reth_received
                buy_price = eth_amount / buy_out if buy_out > 0 else mid
                buy_gas = gas_est or buy_gas
                buy_fee = fee / 1_000_000

            sell_slippage = (mid - sell_price) / mid if mid else 0.0
            buy_slippage = (buy_price - mid) / mid if mid else 0.0

            if sell is not None:
                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="uniswap_v3",
                        pool=self.settings.uniswap_v3_reth_weth_005,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.SELL_RETH,
                        amount_in=reth_in,
                        amount_out=sell_out,
                        effective_price=sell_price,
                        mid_price=mid,
                        fee=sell_fee,
                        price_impact=sell_slippage,
                        gas_estimate=sell_gas,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        buy_slippage=buy_slippage,
                        sell_slippage=sell_slippage,
                        liquidity=liquidity,
                    )
                )

            if buy is not None:
                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="uniswap_v3",
                        pool=self.settings.uniswap_v3_reth_weth_005,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.BUY_RETH,
                        amount_in=eth_amount,
                        amount_out=buy_out,
                        effective_price=buy_price,
                        mid_price=mid,
                        fee=buy_fee,
                        price_impact=buy_slippage,
                        gas_estimate=buy_gas,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        buy_slippage=buy_slippage,
                        sell_slippage=sell_slippage,
                        liquidity=liquidity,
                    )
                )

            if sell is None and buy is None:
                logger.warning("No Uniswap quote for €%.0f", size_eur)

        return quotes

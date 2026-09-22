"""Balancer V2 vault queryBatchSwap for rETH/WETH."""

from __future__ import annotations

import logging
from typing import List, Optional

from src.collectors.ethereum import EthereumClient
from src.config import Settings
from src.models import DexQuote, TradeDirection

logger = logging.getLogger(__name__)

WEI = 10**18
MIN_POOL_ETH = 1.0  # skip venue if WETH balance below this

BALANCER_VAULT_ABI = [
    {
        "name": "queryBatchSwap",
        "inputs": [
            {"name": "kind", "type": "uint8"},
            {
                "name": "swaps",
                "type": "tuple[]",
                "components": [
                    {"name": "poolId", "type": "bytes32"},
                    {"name": "assetInIndex", "type": "uint256"},
                    {"name": "assetOutIndex", "type": "uint256"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "userData", "type": "bytes"},
                ],
            },
            {"name": "assets", "type": "address[]"},
            {
                "name": "funds",
                "type": "tuple",
                "components": [
                    {"name": "sender", "type": "address"},
                    {"name": "fromInternalBalance", "type": "bool"},
                    {"name": "recipient", "type": "address"},
                    {"name": "toInternalBalance", "type": "bool"},
                ],
            },
        ],
        "outputs": [{"name": "assetDeltas", "type": "int256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "name": "getPoolTokens",
        "inputs": [{"name": "poolId", "type": "bytes32"}],
        "outputs": [
            {"name": "tokens", "type": "address[]"},
            {"name": "balances", "type": "uint256[]"},
            {"name": "lastChangeBlock", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


class BalancerCollector:
    """Executable quotes via Balancer Vault queryBatchSwap."""

    def __init__(self, client: EthereumClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._vault = None
        self._liquid: Optional[bool] = None

    def _ensure(self):
        if self._vault is None:
            self._vault = self.client.contract(self.settings.balancer_vault, BALANCER_VAULT_ABI)
        return self._vault

    def _pool_id_bytes(self) -> bytes:
        return bytes.fromhex(self.settings.balancer_reth_weth_pool_id[2:])

    async def _check_liquidity(self) -> bool:
        if self._liquid is not None:
            return self._liquid
        vault = self._ensure()
        try:
            tokens, balances, _ = await vault.functions.getPoolTokens(self._pool_id_bytes()).call()
            weth = self.settings.weth_address.lower()
            weth_bal = 0.0
            for token, bal in zip(tokens, balances):
                if token.lower() == weth:
                    weth_bal = bal / WEI
            self._liquid = weth_bal >= MIN_POOL_ETH
            if not self._liquid:
                logger.warning(
                    "Balancer pool illiquid (WETH bal=%.6f); skipping venue",
                    weth_bal,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Balancer liquidity check failed: %s", str(exc)[:200])
            self._liquid = False
        return self._liquid

    async def _query_swap(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
    ) -> int | None:
        vault = self._ensure()
        w3 = self.client.w3
        assets = [
            w3.to_checksum_address(token_in),
            w3.to_checksum_address(token_out),
        ]
        swaps = [
            {
                "poolId": self._pool_id_bytes(),
                "assetInIndex": 0,
                "assetOutIndex": 1,
                "amount": amount_in_wei,
                "userData": b"",
            }
        ]
        funds = {
            "sender": "0x0000000000000000000000000000000000000000",
            "fromInternalBalance": False,
            "recipient": "0x0000000000000000000000000000000000000000",
            "toInternalBalance": False,
        }
        try:
            deltas = await vault.functions.queryBatchSwap(0, swaps, assets, funds).call()
            return abs(int(deltas[1]))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Balancer queryBatchSwap failed: %s", str(exc)[:200])
            return None

    async def quote_sizes(
        self,
        trade_sizes_eur: List[float],
        eth_eur: float,
        protocol_rate: float,
    ) -> List[DexQuote]:
        if not await self._check_liquidity():
            return []

        block = await self.client.get_block_number()
        quotes: List[DexQuote] = []
        reth = self.settings.reth_address
        weth = self.settings.weth_address

        for size_eur in trade_sizes_eur:
            eth_amount = size_eur / eth_eur
            reth_in = eth_amount / protocol_rate

            eth_out_wei = await self._query_swap(reth, weth, int(reth_in * WEI))
            reth_out_wei = await self._query_swap(weth, reth, int(eth_amount * WEI))

            if eth_out_wei is None and reth_out_wei is None:
                logger.warning("Balancer quote failed for €%.0f", size_eur)
                continue

            sell_price = (eth_out_wei / WEI) / reth_in if eth_out_wei and reth_in else 0.0
            buy_price = (
                eth_amount / (reth_out_wei / WEI) if reth_out_wei and reth_out_wei > 0 else 0.0
            )
            mid = (
                (sell_price + buy_price) / 2
                if sell_price and buy_price
                else sell_price or buy_price
            )

            if eth_out_wei is not None and sell_price > 0:
                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="balancer",
                        pool=self.settings.balancer_reth_weth_pool_id,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.SELL_RETH,
                        amount_in=reth_in,
                        amount_out=eth_out_wei / WEI,
                        effective_price=sell_price,
                        mid_price=mid,
                        fee=0.0004,
                        gas_estimate=200_000,
                        buy_price=buy_price or None,
                        sell_price=sell_price,
                    )
                )
            if reth_out_wei is not None and buy_price > 0:
                quotes.append(
                    DexQuote(
                        block_number=block,
                        venue="balancer",
                        pool=self.settings.balancer_reth_weth_pool_id,
                        trade_size_eur=size_eur,
                        direction=TradeDirection.BUY_RETH,
                        amount_in=eth_amount,
                        amount_out=reth_out_wei / WEI,
                        effective_price=buy_price,
                        mid_price=mid,
                        fee=0.0004,
                        gas_estimate=200_000,
                        buy_price=buy_price,
                        sell_price=sell_price or None,
                    )
                )

        return quotes

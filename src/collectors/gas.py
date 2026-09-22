"""Gas price collector with ETH/EUR conversion."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.collectors.ethereum import EthereumClient
from src.config import Settings
from src.models import GasPrice

logger = logging.getLogger(__name__)


class GasCollector:
    def __init__(self, client: EthereumClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._eth_eur: Optional[float] = None

    async def fetch_eth_eur(self) -> float:
        """Best-effort ETH/EUR for capital sizing. Falls back to config."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                # CoinGecko for FX only — never for rETH execution price
                r = await http.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "ethereum", "vs_currencies": "eur"},
                )
                if r.status_code == 200:
                    self._eth_eur = float(r.json()["ethereum"]["eur"])
                    return self._eth_eur
        except Exception as exc:  # noqa: BLE001
            logger.debug("ETH/EUR fetch failed: %s", exc)
        return self._eth_eur or self.settings.eth_eur_fallback

    async def fetch(self, gas_units: Optional[int] = None) -> GasPrice:
        gas_units = gas_units or self.settings.gas_units_swap
        block = await self.client.get_block("latest")
        gas_price = await self.client.get_gas_price()
        base_fee = block.get("baseFeePerGas")
        eth_eur = await self.fetch_eth_eur()
        # Pessimistic: base fee * 1.2 + 2 gwei tip when available
        if base_fee is not None:
            effective = int(base_fee * 1.2) + 2_000_000_000
            gas_price = max(gas_price, effective)
        cost_eth = (gas_price * gas_units) / 1e18
        return GasPrice(
            block_number=block["number"],
            gas_price_wei=gas_price,
            base_fee_wei=int(base_fee) if base_fee is not None else None,
            priority_fee_wei=2_000_000_000,
            eth_eur=eth_eur,
            gas_cost_eth=cost_eth,
            gas_cost_eur=cost_eth * eth_eur,
            gas_units=gas_units,
        )

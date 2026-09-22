"""Rocket Pool rETH protocol exchange-rate collector."""

from __future__ import annotations

import logging
from typing import Optional

from src.collectors.ethereum import EthereumClient
from src.config import Settings
from src.models import ProtocolRate

logger = logging.getLogger(__name__)

WEI = 10**18


class RocketPoolCollector:
    """Reads official rETH contract — no third-party rate APIs."""

    def __init__(self, client: EthereumClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._contract = None
        self._last: Optional[ProtocolRate] = None

    def _ensure_contract(self):
        if self._contract is None:
            abi_path = self.settings.abis_dir / "reth.json"
            self._contract = self.client.contract(self.settings.reth_address, abi_path)
        return self._contract

    async def fetch_rate(self) -> ProtocolRate:
        contract = self._ensure_contract()
        block = await self.client.get_block_number()

        rate_wei = await self.client.call(contract.functions.getExchangeRate)
        supply_wei = await self.client.call(contract.functions.totalSupply)

        eth_backing: Optional[float] = None
        try:
            collateral_wei = await self.client.call(contract.functions.getTotalCollateral)
            eth_backing = collateral_wei / WEI
        except Exception as exc:  # noqa: BLE001
            logger.debug("getTotalCollateral unavailable: %s", exc)

        observation = ProtocolRate(
            block_number=block,
            reth_rate=rate_wei / WEI,
            reth_supply=supply_wei / WEI,
            eth_backing=eth_backing,
            source="rocketpool_reth",
            contract_address=self.settings.reth_address,
            abi_version=self.settings.reth_abi_version,
        )
        if self._last is None or observation.reth_rate != self._last.reth_rate:
            logger.info(
                "Protocol rate update @ block %s: %.10f ETH/rETH",
                block,
                observation.reth_rate,
            )
        self._last = observation
        return observation

    @property
    def last(self) -> Optional[ProtocolRate]:
        return self._last

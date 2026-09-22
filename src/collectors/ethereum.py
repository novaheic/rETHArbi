"""Ethereum RPC client with HTTP primary and optional WebSocket fallback."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from src.config import Settings

logger = logging.getLogger(__name__)


class EthereumClient:
    """Read-only Ethereum RPC wrapper. Never holds private keys."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._http: Optional[AsyncWeb3] = None
        self._ws: Optional[AsyncWeb3] = None
        self._fail_count = 0

    async def connect(self) -> None:
        if not self.settings.eth_rpc_http and not self.settings.demo_mode:
            raise RuntimeError("ETH_RPC_HTTP is required unless DEMO_MODE=true")

        if self.settings.eth_rpc_http:
            self._http = AsyncWeb3(AsyncHTTPProvider(self.settings.eth_rpc_http))
            ok = await self._http.is_connected()
            if not ok:
                raise RuntimeError(f"Cannot connect to ETH_RPC_HTTP={self.settings.eth_rpc_http}")
            logger.info("Connected to HTTP RPC")

        if self.settings.eth_rpc_ws:
            try:
                from web3 import WebSocketProvider

                self._ws = AsyncWeb3(WebSocketProvider(self.settings.eth_rpc_ws))
                if await self._ws.is_connected():
                    logger.info("Connected to WebSocket RPC")
                else:
                    logger.warning("WebSocket RPC configured but not connected; using HTTP only")
                    self._ws = None
            except Exception as exc:  # noqa: BLE001
                logger.warning("WebSocket RPC unavailable (%s); using HTTP only", exc)
                self._ws = None

    @property
    def w3(self) -> AsyncWeb3:
        if self._http is None:
            raise RuntimeError("Ethereum client not connected")
        return self._http

    async def close(self) -> None:
        # web3 v7 AsyncHTTPProvider has no mandatory close; WS sessions do
        if self._ws is not None:
            try:
                provider = self._ws.provider
                if hasattr(provider, "disconnect"):
                    await provider.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def with_retry(self, coro_factory, retries: int = 3, delay: float = 1.0):
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                result = await coro_factory()
                self._fail_count = 0
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._fail_count += 1
                logger.warning("RPC call failed (attempt %s/%s): %s", attempt + 1, retries, exc)
                await asyncio.sleep(delay * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def get_block_number(self) -> int:
        return await self.with_retry(lambda: self.w3.eth.block_number)

    async def get_gas_price(self) -> int:
        return await self.with_retry(lambda: self.w3.eth.gas_price)

    async def get_block(self, block_identifier: str | int = "latest") -> Any:
        return await self.with_retry(lambda: self.w3.eth.get_block(block_identifier))

    def contract(self, address: str, abi: list | Path) -> Any:
        if isinstance(abi, Path):
            abi = json.loads(abi.read_text())
        checksum = self.w3.to_checksum_address(address)
        return self.w3.eth.contract(address=checksum, abi=abi)

    async def call(self, fn, *args, **kwargs):
        return await self.with_retry(lambda: fn(*args, **kwargs).call())

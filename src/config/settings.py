"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # RPC
    eth_rpc_http: str = Field(default="", alias="ETH_RPC_HTTP")
    eth_rpc_ws: str = Field(default="", alias="ETH_RPC_WS")

    # Database
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{ROOT / 'data' / 'reth_basis.db'}",
        alias="DATABASE_URL",
    )

    # Sampling
    poll_interval_seconds: float = Field(default=15.0, alias="POLL_INTERVAL_SECONDS")
    protocol_poll_every_block: bool = Field(default=True, alias="PROTOCOL_POLL_EVERY_BLOCK")

    # Capital
    capital_eur_1: float = Field(default=500.0, alias="CAPITAL_EUR_1")
    capital_eur_2: float = Field(default=1000.0, alias="CAPITAL_EUR_2")
    trade_sizes_eur: str = Field(
        default="250,500,1000,2500,5000,10000",
        alias="TRADE_SIZES_EUR",
    )

    # Costs
    max_gas_eur: float = Field(default=5.0, alias="MAX_GAS_EUR")
    mev_cost_bps: float = Field(default=2.0, alias="MEV_COST_BPS")
    eth_eur_fallback: float = Field(default=3000.0, alias="ETH_EUR_FALLBACK")

    # Strategy
    entry_thresholds_bps: str = Field(
        default="-10,-15,-20,-25,-30,-40,-50,-75,-100",
        alias="ENTRY_THRESHOLDS_BPS",
    )
    exit_thresholds_bps: str = Field(default="0,-5,-10", alias="EXIT_THRESHOLDS_BPS")
    max_holding_seconds: str = Field(
        default="3600,21600,43200,86400,259200,604800,2592000",
        alias="MAX_HOLDING_SECONDS",
    )
    min_entry_basis_bps: float = Field(default=20.0, alias="MIN_ENTRY_BASIS_BPS")

    # Runtime
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    reports_dir: Path = Field(default=ROOT / "reports", alias="REPORTS_DIR")
    dashboard_host: str = Field(default="0.0.0.0", alias="DASHBOARD_HOST")
    dashboard_port: int = Field(default=8080, alias="DASHBOARD_PORT")

    # Contracts (official Rocket Pool / Uniswap mainnet)
    reth_address: str = "0xae78736Cd615f374D3085123A210448E74Fc6393"
    reth_abi_version: str = "rocketTokenRETH-1.2"
    weth_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    uniswap_quoter_v2: str = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
    # Primary Uniswap V3 rETH/WETH 0.05% pool (token0=rETH, token1=WETH)
    uniswap_v3_reth_weth_005: str = "0xa4e0faA58465A2D369aa21B3e42d43374c6F9613"
    # Also probe 0.01% and 0.3% fee tiers via quoter
    uniswap_fee_tiers: str = "100,500,3000"

    # Curve StableSwap-NG wETH/rETH pool with liquidity (factory index i=1)
    curve_reth_eth_pool: str = "0x9EfE1A1Cbd6Ca51Ee8319AFc4573d253C3B732af"
    # Balancer rETH/WETH composable stable pool
    balancer_vault: str = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
    balancer_reth_weth_pool_id: str = (
        "0x1e19cf2d73a72ef1332c882f20534b6519be0276000200000000000000000112"
    )

    # Gas estimate defaults (swap + approval-ish overhead)
    gas_units_swap: int = 180_000
    gas_units_approval: int = 46_000

    @field_validator("demo_mode", "protocol_poll_every_block", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return v

    def trade_sizes(self) -> List[float]:
        return [float(x.strip()) for x in self.trade_sizes_eur.split(",") if x.strip()]

    def entry_thresholds(self) -> List[float]:
        return [float(x.strip()) for x in self.entry_thresholds_bps.split(",") if x.strip()]

    def exit_thresholds(self) -> List[float]:
        return [float(x.strip()) for x in self.exit_thresholds_bps.split(",") if x.strip()]

    def holding_periods(self) -> List[int]:
        return [int(x.strip()) for x in self.max_holding_seconds.split(",") if x.strip()]

    def fee_tiers(self) -> List[int]:
        return [int(x.strip()) for x in self.uniswap_fee_tiers.split(",") if x.strip()]

    @property
    def abis_dir(self) -> Path:
        return ROOT / "abis"


@lru_cache
def get_settings() -> Settings:
    return Settings()

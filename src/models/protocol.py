"""Domain models for protocol, market, and trade observations."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradeDirection(str, Enum):
    SELL_RETH = "sell_reth"  # rETH -> ETH
    BUY_RETH = "buy_reth"  # ETH -> rETH


class ProtocolRate(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    block_number: int
    reth_rate: float  # ETH per 1 rETH
    reth_supply: Optional[float] = None
    eth_backing: Optional[float] = None
    source: str = "rocketpool_reth"
    contract_address: str
    abi_version: str


class GasPrice(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    block_number: int
    gas_price_wei: int
    base_fee_wei: Optional[int] = None
    priority_fee_wei: Optional[int] = None
    eth_eur: float
    gas_cost_eth: float
    gas_cost_eur: float
    gas_units: int


class DexQuote(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    block_number: int
    venue: str
    pool: str
    trade_size_eur: float
    direction: TradeDirection
    amount_in: float
    amount_out: float
    effective_price: float  # always ETH per rETH
    mid_price: Optional[float] = None
    fee: float = 0.0  # fraction, e.g. 0.0005
    price_impact: Optional[float] = None
    gas_estimate: Optional[int] = None
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    buy_slippage: Optional[float] = None
    sell_slippage: Optional[float] = None
    liquidity: Optional[float] = None


class BasisObservation(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    block_number: int
    venue: str
    trade_size_eur: float
    protocol_rate: float
    market_rate: float  # executable ETH/rETH for the direction
    direction: TradeDirection
    basis_bps: float
    gross_premium_bps: Optional[float] = None
    gas_eur: float
    dex_fee_eur: float
    estimated_slippage_eur: float
    mev_eur: float
    net_edge_eur: float
    net_edge_bps: float
    eth_eur: float


class SimulatedTrade(BaseModel):
    strategy: str
    entry_timestamp: datetime
    exit_timestamp: Optional[datetime] = None
    entry_basis_bps: float
    exit_basis_bps: Optional[float] = None
    trade_size_eur: float
    entry_price: float
    exit_price: Optional[float] = None
    gross_pnl_eur: Optional[float] = None
    staking_carry_eur: Optional[float] = None
    trading_pnl_eur: Optional[float] = None
    gas_eur: float = 0.0
    fees_eur: float = 0.0
    slippage_eur: float = 0.0
    net_pnl_eur: Optional[float] = None
    return_pct: Optional[float] = None
    holding_seconds: Optional[int] = None
    entry_protocol_rate: float
    exit_protocol_rate: Optional[float] = None
    venue: str = "uniswap_v3"
    status: str = "open"


class PortfolioSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    strategy: str
    capital_eur: float
    eth_eur: float
    reth_eur: float
    total_eur: float
    unrealized_pnl_eur: float
    realized_pnl_eur: float
    staking_carry_eur: float
    trading_pnl_eur: float
    gas_paid_eur: float
    fees_paid_eur: float
    capital_deployed: bool

"""SQLAlchemy async database models and repository."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config import Settings
from src.models import (
    BasisObservation,
    DexQuote,
    GasPrice,
    PortfolioSnapshot,
    ProtocolRate,
    SimulatedTrade,
)

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class BlockRow(Base):
    __tablename__ = "blocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProtocolRateRow(Base):
    __tablename__ = "protocol_rates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    block_number: Mapped[int] = mapped_column(Integer, index=True)
    reth_rate: Mapped[float] = mapped_column(Float)
    reth_supply: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eth_backing: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    contract_address: Mapped[str] = mapped_column(String(42))
    abi_version: Mapped[str] = mapped_column(String(64))


class DexQuoteRow(Base):
    __tablename__ = "dex_quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    block_number: Mapped[int] = mapped_column(Integer, index=True)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    pool: Mapped[str] = mapped_column(String(128))
    trade_size_eur: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(16))
    amount_in: Mapped[float] = mapped_column(Float)
    amount_out: Mapped[float] = mapped_column(Float)
    effective_price: Mapped[float] = mapped_column(Float)
    mid_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee: Mapped[float] = mapped_column(Float)
    price_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gas_estimate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    buy_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sell_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    buy_slippage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sell_slippage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_dex_quotes_venue_size", "venue", "trade_size_eur"),)


class GasPriceRow(Base):
    __tablename__ = "gas_prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    block_number: Mapped[int] = mapped_column(Integer)
    gas_price_wei: Mapped[int] = mapped_column(Integer)
    base_fee_wei: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority_fee_wei: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eth_eur: Mapped[float] = mapped_column(Float)
    gas_cost_eth: Mapped[float] = mapped_column(Float)
    gas_cost_eur: Mapped[float] = mapped_column(Float)
    gas_units: Mapped[int] = mapped_column(Integer)


class BasisObservationRow(Base):
    __tablename__ = "basis_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    block_number: Mapped[int] = mapped_column(Integer, index=True)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    trade_size_eur: Mapped[float] = mapped_column(Float)
    protocol_rate: Mapped[float] = mapped_column(Float)
    market_rate: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(16))
    basis_bps: Mapped[float] = mapped_column(Float)
    gross_premium_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gas_eur: Mapped[float] = mapped_column(Float)
    dex_fee_eur: Mapped[float] = mapped_column(Float)
    estimated_slippage_eur: Mapped[float] = mapped_column(Float)
    mev_eur: Mapped[float] = mapped_column(Float)
    net_edge_eur: Mapped[float] = mapped_column(Float)
    net_edge_bps: Mapped[float] = mapped_column(Float)
    eth_eur: Mapped[float] = mapped_column(Float)


class SimulatedTradeRow(Base):
    __tablename__ = "simulated_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(128), index=True)
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_basis_bps: Mapped[float] = mapped_column(Float)
    exit_basis_bps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trade_size_eur: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_pnl_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    staking_carry_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trading_pnl_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gas_eur: Mapped[float] = mapped_column(Float)
    fees_eur: Mapped[float] = mapped_column(Float)
    slippage_eur: Mapped[float] = mapped_column(Float)
    net_pnl_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    holding_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entry_protocol_rate: Mapped[float] = mapped_column(Float)
    exit_protocol_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    venue: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(64))


class PortfolioSnapshotRow(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    strategy: Mapped[str] = mapped_column(String(128), index=True)
    capital_eur: Mapped[float] = mapped_column(Float)
    eth_eur: Mapped[float] = mapped_column(Float)
    reth_eur: Mapped[float] = mapped_column(Float)
    total_eur: Mapped[float] = mapped_column(Float)
    unrealized_pnl_eur: Mapped[float] = mapped_column(Float)
    realized_pnl_eur: Mapped[float] = mapped_column(Float)
    staking_carry_eur: Mapped[float] = mapped_column(Float)
    trading_pnl_eur: Mapped[float] = mapped_column(Float)
    gas_paid_eur: Mapped[float] = mapped_column(Float)
    fees_paid_eur: Mapped[float] = mapped_column(Float)
    capital_deployed: Mapped[bool] = mapped_column(Boolean)


class StrategyResultRow(Base):
    __tablename__ = "strategy_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    strategy: Mapped[str] = mapped_column(String(128), index=True)
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        url = settings.database_url
        if url.startswith("sqlite"):
            Path(url.split("///")[-1]).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database ready: %s", self.settings.database_url.split("@")[-1])

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_protocol_rate(self, obs: ProtocolRate) -> None:
        async with self.session_factory() as session:
            session.add(
                ProtocolRateRow(
                    timestamp=obs.timestamp,
                    block_number=obs.block_number,
                    reth_rate=obs.reth_rate,
                    reth_supply=obs.reth_supply,
                    eth_backing=obs.eth_backing,
                    source=obs.source,
                    contract_address=obs.contract_address,
                    abi_version=obs.abi_version,
                )
            )
            await session.commit()

    async def save_gas(self, gas: GasPrice) -> None:
        async with self.session_factory() as session:
            session.add(
                GasPriceRow(
                    timestamp=gas.timestamp,
                    block_number=gas.block_number,
                    gas_price_wei=gas.gas_price_wei,
                    base_fee_wei=gas.base_fee_wei,
                    priority_fee_wei=gas.priority_fee_wei,
                    eth_eur=gas.eth_eur,
                    gas_cost_eth=gas.gas_cost_eth,
                    gas_cost_eur=gas.gas_cost_eur,
                    gas_units=gas.gas_units,
                )
            )
            await session.commit()

    async def save_quotes(self, quotes: Sequence[DexQuote]) -> None:
        if not quotes:
            return
        async with self.session_factory() as session:
            for q in quotes:
                session.add(
                    DexQuoteRow(
                        timestamp=q.timestamp,
                        block_number=q.block_number,
                        venue=q.venue,
                        pool=q.pool,
                        trade_size_eur=q.trade_size_eur,
                        direction=q.direction.value,
                        amount_in=q.amount_in,
                        amount_out=q.amount_out,
                        effective_price=q.effective_price,
                        mid_price=q.mid_price,
                        fee=q.fee,
                        price_impact=q.price_impact,
                        gas_estimate=q.gas_estimate,
                        buy_price=q.buy_price,
                        sell_price=q.sell_price,
                        buy_slippage=q.buy_slippage,
                        sell_slippage=q.sell_slippage,
                        liquidity=q.liquidity,
                    )
                )
            await session.commit()

    async def save_basis(self, observations: Sequence[BasisObservation]) -> None:
        if not observations:
            return
        async with self.session_factory() as session:
            for o in observations:
                session.add(
                    BasisObservationRow(
                        timestamp=o.timestamp,
                        block_number=o.block_number,
                        venue=o.venue,
                        trade_size_eur=o.trade_size_eur,
                        protocol_rate=o.protocol_rate,
                        market_rate=o.market_rate,
                        direction=o.direction.value,
                        basis_bps=o.basis_bps,
                        gross_premium_bps=o.gross_premium_bps,
                        gas_eur=o.gas_eur,
                        dex_fee_eur=o.dex_fee_eur,
                        estimated_slippage_eur=o.estimated_slippage_eur,
                        mev_eur=o.mev_eur,
                        net_edge_eur=o.net_edge_eur,
                        net_edge_bps=o.net_edge_bps,
                        eth_eur=o.eth_eur,
                    )
                )
            await session.commit()

    async def save_trade(self, trade: SimulatedTrade) -> None:
        async with self.session_factory() as session:
            session.add(
                SimulatedTradeRow(
                    strategy=trade.strategy,
                    entry_timestamp=trade.entry_timestamp,
                    exit_timestamp=trade.exit_timestamp,
                    entry_basis_bps=trade.entry_basis_bps,
                    exit_basis_bps=trade.exit_basis_bps,
                    trade_size_eur=trade.trade_size_eur,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    gross_pnl_eur=trade.gross_pnl_eur,
                    staking_carry_eur=trade.staking_carry_eur,
                    trading_pnl_eur=trade.trading_pnl_eur,
                    gas_eur=trade.gas_eur,
                    fees_eur=trade.fees_eur,
                    slippage_eur=trade.slippage_eur,
                    net_pnl_eur=trade.net_pnl_eur,
                    return_pct=trade.return_pct,
                    holding_seconds=trade.holding_seconds,
                    entry_protocol_rate=trade.entry_protocol_rate,
                    exit_protocol_rate=trade.exit_protocol_rate,
                    venue=trade.venue,
                    status=trade.status,
                )
            )
            await session.commit()

    async def save_portfolio(self, snap: PortfolioSnapshot) -> None:
        async with self.session_factory() as session:
            session.add(
                PortfolioSnapshotRow(
                    timestamp=snap.timestamp,
                    strategy=snap.strategy,
                    capital_eur=snap.capital_eur,
                    eth_eur=snap.eth_eur,
                    reth_eur=snap.reth_eur,
                    total_eur=snap.total_eur,
                    unrealized_pnl_eur=snap.unrealized_pnl_eur,
                    realized_pnl_eur=snap.realized_pnl_eur,
                    staking_carry_eur=snap.staking_carry_eur,
                    trading_pnl_eur=snap.trading_pnl_eur,
                    gas_paid_eur=snap.gas_paid_eur,
                    fees_paid_eur=snap.fees_paid_eur,
                    capital_deployed=snap.capital_deployed,
                )
            )
            await session.commit()

    async def latest_basis(self, limit: int = 100) -> list[BasisObservationRow]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(BasisObservationRow).order_by(BasisObservationRow.id.desc()).limit(limit)
            )
            return list(result.scalars())

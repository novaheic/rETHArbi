"""SQLAlchemy async database models and repository."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
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

    @staticmethod
    def _window_start(window: str) -> Optional[datetime]:
        now = datetime.now(timezone.utc)
        mapping = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "all": None,
        }
        delta = mapping.get(window, timedelta(days=7))
        return None if delta is None else now - delta

    @staticmethod
    def _downsample(rows: list[Any], max_points: int = 800) -> list[Any]:
        if len(rows) <= max_points:
            return rows
        step = max(1, len(rows) // max_points)
        sampled = rows[::step]
        if rows and sampled[-1] is not rows[-1]:
            sampled.append(rows[-1])
        return sampled[:max_points]

    async def dashboard_header(self) -> dict[str, Any]:
        """Latest market snapshot + health-ish counts for the dashboard header."""
        async with self.session_factory() as session:
            obs_count = await session.scalar(select(func.count()).select_from(BasisObservationRow))
            trade_count = await session.scalar(
                select(func.count())
                .select_from(SimulatedTradeRow)
                .where(SimulatedTradeRow.status.like("closed%"))
            )
            latest_basis = await session.scalar(
                select(BasisObservationRow)
                .where(
                    BasisObservationRow.direction == "sell_reth",
                    BasisObservationRow.venue == "uniswap_v3",
                    BasisObservationRow.trade_size_eur == 1000,
                )
                .order_by(BasisObservationRow.id.desc())
                .limit(1)
            )
            if latest_basis is None:
                latest_basis = await session.scalar(
                    select(BasisObservationRow)
                    .where(BasisObservationRow.direction == "sell_reth")
                    .order_by(BasisObservationRow.id.desc())
                    .limit(1)
                )
            latest_gas = await session.scalar(
                select(GasPriceRow).order_by(GasPriceRow.id.desc()).limit(1)
            )
            latest_protocol = await session.scalar(
                select(ProtocolRateRow).order_by(ProtocolRateRow.id.desc()).limit(1)
            )
            last_write = None
            for candidate in (
                latest_basis.timestamp if latest_basis else None,
                latest_gas.timestamp if latest_gas else None,
                latest_protocol.timestamp if latest_protocol else None,
            ):
                if candidate is not None and (last_write is None or candidate > last_write):
                    last_write = candidate

            return {
                "observation_count": int(obs_count or 0),
                "closed_trade_count": int(trade_count or 0),
                "protocol_rate": latest_protocol.reth_rate if latest_protocol else None,
                "market_rate": latest_basis.market_rate if latest_basis else None,
                "basis_bps": latest_basis.basis_bps if latest_basis else None,
                "net_edge_bps": latest_basis.net_edge_bps if latest_basis else None,
                "gas_eur": latest_gas.gas_cost_eur if latest_gas else None,
                "eth_eur": latest_gas.eth_eur if latest_gas else None,
                "block_number": (
                    latest_basis.block_number
                    if latest_basis
                    else (latest_protocol.block_number if latest_protocol else None)
                ),
                "last_write": last_write.isoformat() if last_write else None,
                "venue": latest_basis.venue if latest_basis else None,
                "trade_size_eur": latest_basis.trade_size_eur if latest_basis else None,
            }

    async def basis_series(
        self,
        window: str = "7d",
        venue: str = "uniswap_v3",
        sizes: Sequence[float] = (500.0, 1000.0),
        max_points: int = 800,
    ) -> list[dict[str, Any]]:
        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = (
                select(BasisObservationRow)
                .where(
                    BasisObservationRow.direction == "sell_reth",
                    BasisObservationRow.venue == venue,
                    BasisObservationRow.trade_size_eur.in_(list(sizes)),
                )
                .order_by(BasisObservationRow.timestamp.asc())
            )
            if start is not None:
                stmt = stmt.where(BasisObservationRow.timestamp >= start)
            rows = list((await session.execute(stmt)).scalars())
            rows = self._downsample(rows, max_points=max_points)
            return [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "trade_size_eur": r.trade_size_eur,
                    "basis_bps": r.basis_bps,
                    "net_edge_bps": r.net_edge_bps,
                    "protocol_rate": r.protocol_rate,
                    "market_rate": r.market_rate,
                }
                for r in rows
            ]

    async def strategy_leaderboard(
        self,
        window: str = "7d",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = select(SimulatedTradeRow).where(SimulatedTradeRow.status.like("closed%"))
            if start is not None:
                stmt = stmt.where(SimulatedTradeRow.exit_timestamp >= start)
            rows = list((await session.execute(stmt)).scalars())

        by_strategy: dict[str, list[SimulatedTradeRow]] = {}
        for row in rows:
            by_strategy.setdefault(row.strategy, []).append(row)

        board: list[dict[str, Any]] = []
        for strategy, trades in by_strategy.items():
            pnls = [t.net_pnl_eur or 0.0 for t in trades]
            holds = [t.holding_seconds or 0 for t in trades]
            wins = sum(1 for p in pnls if p > 0)
            board.append(
                {
                    "strategy": strategy,
                    "n_trades": len(trades),
                    "total_pnl": round(sum(pnls), 4),
                    "avg_pnl": round(sum(pnls) / len(pnls), 4) if pnls else 0.0,
                    "win_rate": round(wins / len(pnls), 4) if pnls else 0.0,
                    "avg_hold_h": round((sum(holds) / len(holds)) / 3600.0, 2) if holds else 0.0,
                }
            )
        board.sort(key=lambda x: x["total_pnl"], reverse=True)
        return board[:limit]

    async def recent_trades(self, window: str = "7d", limit: int = 30) -> list[dict[str, Any]]:
        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = (
                select(SimulatedTradeRow)
                .where(SimulatedTradeRow.status.like("closed%"))
                .order_by(SimulatedTradeRow.exit_timestamp.desc())
                .limit(limit)
            )
            if start is not None:
                stmt = stmt.where(SimulatedTradeRow.exit_timestamp >= start)
            rows = list((await session.execute(stmt)).scalars())
            return [
                {
                    "strategy": r.strategy,
                    "entry_timestamp": r.entry_timestamp.isoformat() if r.entry_timestamp else None,
                    "exit_timestamp": r.exit_timestamp.isoformat() if r.exit_timestamp else None,
                    "entry_basis_bps": r.entry_basis_bps,
                    "exit_basis_bps": r.exit_basis_bps,
                    "net_pnl_eur": r.net_pnl_eur,
                    "holding_seconds": r.holding_seconds,
                    "status": r.status,
                    "trade_size_eur": r.trade_size_eur,
                }
                for r in rows
            ]

    async def venue_stats(self, window: str = "7d") -> list[dict[str, Any]]:
        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = select(BasisObservationRow).where(BasisObservationRow.direction == "sell_reth")
            if start is not None:
                stmt = stmt.where(BasisObservationRow.timestamp >= start)
            rows = list((await session.execute(stmt)).scalars())

        groups: dict[tuple[str, float], list[BasisObservationRow]] = {}
        for row in rows:
            groups.setdefault((row.venue, row.trade_size_eur), []).append(row)

        out: list[dict[str, Any]] = []
        for (venue, size), items in sorted(groups.items()):
            bases = [i.basis_bps for i in items]
            nets = [i.net_edge_bps for i in items]
            out.append(
                {
                    "venue": venue,
                    "trade_size_eur": size,
                    "n": len(items),
                    "avg_basis_bps": round(sum(bases) / len(bases), 2) if bases else 0.0,
                    "avg_net_edge_bps": round(sum(nets) / len(nets), 2) if nets else 0.0,
                    "pct_positive_net": round(
                        100.0 * sum(1 for n in nets if n > 0) / len(nets), 1
                    )
                    if nets
                    else 0.0,
                }
            )
        return out

    async def cumulative_pnl_series(
        self,
        window: str = "7d",
        top_n: int = 5,
        max_points: int = 800,
    ) -> dict[str, list[dict[str, Any]]]:
        """Cumulative net P&L over time for top strategies by total P&L in window."""
        board = await self.strategy_leaderboard(window=window, limit=top_n)
        names = [b["strategy"] for b in board]
        if not names:
            return {}

        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = (
                select(SimulatedTradeRow)
                .where(
                    SimulatedTradeRow.status.like("closed%"),
                    SimulatedTradeRow.strategy.in_(names),
                )
                .order_by(SimulatedTradeRow.exit_timestamp.asc())
            )
            if start is not None:
                stmt = stmt.where(SimulatedTradeRow.exit_timestamp >= start)
            rows = list((await session.execute(stmt)).scalars())

        series: dict[str, list[dict[str, Any]]] = {n: [] for n in names}
        cum: dict[str, float] = {n: 0.0 for n in names}
        for row in rows:
            if row.strategy not in cum:
                continue
            cum[row.strategy] += row.net_pnl_eur or 0.0
            ts = row.exit_timestamp or row.entry_timestamp
            series[row.strategy].append(
                {"timestamp": ts.isoformat() if ts else None, "cum_pnl": round(cum[row.strategy], 4)}
            )

        for name, points in list(series.items()):
            series[name] = self._downsample(points, max_points=max_points)
        return series

    async def portfolio_series(
        self,
        window: str = "7d",
        strategies: Optional[Sequence[str]] = None,
        max_points: int = 800,
    ) -> dict[str, list[dict[str, Any]]]:
        start = self._window_start(window)
        async with self.session_factory() as session:
            stmt = select(PortfolioSnapshotRow).order_by(PortfolioSnapshotRow.timestamp.asc())
            if start is not None:
                stmt = stmt.where(PortfolioSnapshotRow.timestamp >= start)
            if strategies:
                stmt = stmt.where(PortfolioSnapshotRow.strategy.in_(list(strategies)))
            rows = list((await session.execute(stmt)).scalars())

        out: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            out.setdefault(row.strategy, []).append(
                {
                    "timestamp": row.timestamp.isoformat(),
                    "total_eur": row.total_eur,
                    "realized_pnl_eur": row.realized_pnl_eur,
                }
            )
        for name, points in list(out.items()):
            out[name] = self._downsample(points, max_points=max_points)
        return out

    async def load_dashboard_payload(self, window: str = "7d") -> dict[str, Any]:
        header = await self.dashboard_header()
        series = await self.basis_series(window=window)
        board = await self.strategy_leaderboard(window=window)
        trades = await self.recent_trades(window=window)
        venues = await self.venue_stats(window=window)
        cum_pnl = await self.cumulative_pnl_series(window=window)
        portfolios = await self.portfolio_series(window=window)
        return {
            "window": window,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "header": header,
            "basis_series": series,
            "strategy_leaderboard": board,
            "recent_trades": trades,
            "venue_stats": venues,
            "cumulative_pnl": cum_pnl,
            "portfolio_series": portfolios,
            "paper_disclaimer": (
                "Paper / hypothetical only — read-only research. No private keys. No live trading."
            ),
        }

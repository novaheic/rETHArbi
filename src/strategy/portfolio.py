"""Paper portfolio ledger for hypothetical trades."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from src.models import PortfolioSnapshot, SimulatedTrade, utcnow


@dataclass
class PaperPortfolio:
    strategy: str
    capital_eur: float
    eth_eur: float = 0.0
    reth_eur: float = 0.0
    realized_pnl_eur: float = 0.0
    staking_carry_eur: float = 0.0
    trading_pnl_eur: float = 0.0
    gas_paid_eur: float = 0.0
    fees_paid_eur: float = 0.0
    slippage_paid_eur: float = 0.0
    open_trade: Optional[SimulatedTrade] = None
    closed_trades: List[SimulatedTrade] = field(default_factory=list)
    idle_seconds: float = 0.0
    deployed_seconds: float = 0.0
    _last_ts: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.eth_eur = self.capital_eur
        self.reth_eur = 0.0

    @property
    def total_eur(self) -> float:
        return self.eth_eur + self.reth_eur

    @property
    def capital_deployed(self) -> bool:
        return self.open_trade is not None

    def tick(self, ts: datetime) -> None:
        if self._last_ts is not None:
            dt = (ts - self._last_ts).total_seconds()
            if self.capital_deployed:
                self.deployed_seconds += dt
            else:
                self.idle_seconds += dt
        self._last_ts = ts

    def snapshot(self, ts: Optional[datetime] = None) -> PortfolioSnapshot:
        ts = ts or utcnow()
        return PortfolioSnapshot(
            timestamp=ts,
            strategy=self.strategy,
            capital_eur=self.capital_eur,
            eth_eur=self.eth_eur,
            reth_eur=self.reth_eur,
            total_eur=self.total_eur,
            unrealized_pnl_eur=self.total_eur - self.capital_eur - self.realized_pnl_eur,
            realized_pnl_eur=self.realized_pnl_eur,
            staking_carry_eur=self.staking_carry_eur,
            trading_pnl_eur=self.trading_pnl_eur,
            gas_paid_eur=self.gas_paid_eur,
            fees_paid_eur=self.fees_paid_eur,
            capital_deployed=self.capital_deployed,
        )

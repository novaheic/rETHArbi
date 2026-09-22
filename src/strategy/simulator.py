"""Paper-trading simulator for discount mean-reversion strategies.

No look-ahead: decisions use only the current observation.
Separates trading_pnl, staking_carry, gas, fees, slippage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import Settings
from src.models import BasisObservation, ProtocolRate, SimulatedTrade, TradeDirection
from src.strategy.portfolio import PaperPortfolio

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    name: str
    entry_bps: float  # e.g. -30
    exit_bps: float  # e.g. 0, -5, -10
    max_holding_seconds: Optional[int] = None
    fixed_time_exit: bool = False  # Strategy B
    trade_size_eur: float = 1000.0


class BasisSimulator:
    """Runs multiple Strategy A/B configs against a live observation stream."""

    def __init__(self, settings: Settings, capitals: Optional[List[float]] = None):
        self.settings = settings
        self.capitals = capitals or [settings.capital_eur_1, settings.capital_eur_2]
        self.portfolios: Dict[str, PaperPortfolio] = {}
        self.configs: List[StrategyConfig] = []
        self._build_configs()

    def _build_configs(self) -> None:
        # Strategy A: mean reversion with various entry/exit thresholds
        for capital in self.capitals:
            for entry in self.settings.entry_thresholds():
                for exit_bps in self.settings.exit_thresholds():
                    name = f"A_entry{entry:.0f}_exit{exit_bps:.0f}_€{capital:.0f}"
                    cfg = StrategyConfig(
                        name=name,
                        entry_bps=entry,
                        exit_bps=exit_bps,
                        trade_size_eur=capital,
                    )
                    self.configs.append(cfg)
                    self.portfolios[name] = PaperPortfolio(strategy=name, capital_eur=capital)

                # Strategy B: fixed-time exits
                for hold in self.settings.holding_periods():
                    name = f"B_entry{entry:.0f}_hold{hold}s_€{capital:.0f}"
                    cfg = StrategyConfig(
                        name=name,
                        entry_bps=entry,
                        exit_bps=9999,  # unused
                        max_holding_seconds=hold,
                        fixed_time_exit=True,
                        trade_size_eur=capital,
                    )
                    self.configs.append(cfg)
                    self.portfolios[name] = PaperPortfolio(strategy=name, capital_eur=capital)

        # Controls: buy-and-hold ETH / rETH at capital_eur_2
        for capital in self.capitals:
            for label in ("hold_eth", "hold_reth"):
                name = f"0_{label}_€{capital:.0f}"
                self.portfolios[name] = PaperPortfolio(strategy=name, capital_eur=capital)

    def on_observation(
        self,
        protocol: ProtocolRate,
        buy_obs: Optional[BasisObservation],
        sell_obs: Optional[BasisObservation],
        ts: Optional[datetime] = None,
        *,
        by_size: Optional[Dict[float, Tuple[BasisObservation, BasisObservation]]] = None,
    ) -> List[SimulatedTrade]:
        """Process one observation tick. Returns newly closed trades.

        Prefer ``by_size`` mapping ``trade_size_eur -> (buy_obs, sell_obs)``.
        Legacy single-size ``buy_obs``/``sell_obs`` still supported.
        """
        ts = ts or protocol.timestamp
        closed: List[SimulatedTrade] = []

        size_map: Dict[float, Tuple[BasisObservation, BasisObservation]] = {}
        if by_size:
            size_map.update(by_size)
        elif buy_obs is not None and sell_obs is not None:
            size_map[buy_obs.trade_size_eur] = (buy_obs, sell_obs)

        if not size_map:
            return closed

        # Tick all portfolios once per cycle
        for port in self.portfolios.values():
            port.tick(ts)

        for cfg in self.configs:
            pair = size_map.get(cfg.trade_size_eur)
            if pair is None:
                continue
            buy, sell = pair
            port = self.portfolios[cfg.name]

            if port.open_trade is None:
                if sell.basis_bps <= cfg.entry_bps:
                    self._enter(port, cfg, protocol, buy, sell, ts)
            else:
                should_exit, reason = self._should_exit(port, cfg, sell, ts)
                if should_exit:
                    trade = self._exit(port, cfg, protocol, sell, ts, reason)
                    if trade:
                        closed.append(trade)

        # Update hold controls using any available sell observation
        any_sell = next(iter(size_map.values()))[1]
        self._update_holds(protocol, any_sell, ts)
        return closed

    def _enter(
        self,
        port: PaperPortfolio,
        cfg: StrategyConfig,
        protocol: ProtocolRate,
        buy_obs: BasisObservation,
        sell_obs: BasisObservation,
        ts: datetime,
    ) -> None:
        size = min(cfg.trade_size_eur, port.eth_eur)
        if size <= 0:
            return

        # Costs on entry (buy rETH)
        gas = buy_obs.gas_eur
        fees = buy_obs.dex_fee_eur
        slip = buy_obs.estimated_slippage_eur
        cost = gas + fees + slip

        # Effective rETH position value after costs
        eth_spent = size
        reth_value = size - cost  # EUR value of rETH acquired (approx)
        if reth_value <= 0:
            return

        port.eth_eur -= size
        port.reth_eur += reth_value
        port.gas_paid_eur += gas
        port.fees_paid_eur += fees
        port.slippage_paid_eur += slip

        port.open_trade = SimulatedTrade(
            strategy=cfg.name,
            entry_timestamp=ts,
            entry_basis_bps=sell_obs.basis_bps,
            trade_size_eur=size,
            entry_price=buy_obs.market_rate,
            gas_eur=gas,
            fees_eur=fees,
            slippage_eur=slip,
            entry_protocol_rate=protocol.reth_rate,
            venue=buy_obs.venue,
            status="open",
        )
        logger.info(
            "ENTER %s basis=%.1fbp size=€%.0f buy_rate=%.6f",
            cfg.name,
            sell_obs.basis_bps,
            size,
            buy_obs.market_rate,
        )

    def _should_exit(
        self,
        port: PaperPortfolio,
        cfg: StrategyConfig,
        sell_obs: BasisObservation,
        ts: datetime,
    ) -> Tuple[bool, str]:
        trade = port.open_trade
        assert trade is not None
        held = (ts - trade.entry_timestamp).total_seconds()

        if cfg.fixed_time_exit and cfg.max_holding_seconds is not None:
            if held >= cfg.max_holding_seconds:
                return True, "fixed_time"

        if not cfg.fixed_time_exit:
            if sell_obs.basis_bps >= cfg.exit_bps:
                return True, "basis_recovery"
            if cfg.max_holding_seconds and held >= cfg.max_holding_seconds:
                return True, "max_hold"

        # Strategy A with max hold from settings exit-D variants could be added;
        # for combined A configs we also honor max hold if set on cfg
        return False, ""

    def _exit(
        self,
        port: PaperPortfolio,
        cfg: StrategyConfig,
        protocol: ProtocolRate,
        sell_obs: BasisObservation,
        ts: datetime,
        reason: str,
    ) -> Optional[SimulatedTrade]:
        trade = port.open_trade
        if trade is None:
            return None

        gas = sell_obs.gas_eur
        fees = sell_obs.dex_fee_eur
        slip = sell_obs.estimated_slippage_eur
        exit_costs = gas + fees + slip

        # Staking carry from protocol rate change
        rate_change = protocol.reth_rate / trade.entry_protocol_rate - 1.0
        staking_carry = trade.trade_size_eur * rate_change

        # Proceeds: sell rETH position
        reth_position = port.reth_eur
        proceeds = max(0.0, reth_position - exit_costs)

        # Mark components
        # Total PnL vs starting capital for this trade
        gross_pnl = proceeds - trade.trade_size_eur + (trade.gas_eur + trade.fees_eur + trade.slippage_eur)
        # After all round-trip costs already deducted from proceeds/entry:
        net_pnl = proceeds - trade.trade_size_eur
        trading_pnl = net_pnl - staking_carry

        port.reth_eur = 0.0
        port.eth_eur += proceeds
        port.gas_paid_eur += gas
        port.fees_paid_eur += fees
        port.slippage_paid_eur += slip
        port.staking_carry_eur += staking_carry
        port.trading_pnl_eur += trading_pnl
        port.realized_pnl_eur += net_pnl

        trade.exit_timestamp = ts
        trade.exit_basis_bps = sell_obs.basis_bps
        trade.exit_price = sell_obs.market_rate
        trade.exit_protocol_rate = protocol.reth_rate
        trade.gross_pnl_eur = gross_pnl
        trade.staking_carry_eur = staking_carry
        trade.trading_pnl_eur = trading_pnl
        trade.gas_eur += gas
        trade.fees_eur += fees
        trade.slippage_eur += slip
        trade.net_pnl_eur = net_pnl
        trade.return_pct = (net_pnl / trade.trade_size_eur) * 100 if trade.trade_size_eur else 0.0
        trade.holding_seconds = int((ts - trade.entry_timestamp).total_seconds())
        trade.status = f"closed:{reason}"

        port.closed_trades.append(trade)
        port.open_trade = None

        logger.info(
            "EXIT  %s reason=%s net=€%+.2f carry=€%+.2f trade=€%+.2f held=%ss",
            cfg.name,
            reason,
            net_pnl,
            staking_carry,
            trading_pnl,
            trade.holding_seconds,
        )
        return trade

    def _update_holds(
        self,
        protocol: ProtocolRate,
        sell_obs: BasisObservation,
        ts: datetime,
    ) -> None:
        for capital in self.capitals:
            eth_name = f"0_hold_eth_€{capital:.0f}"
            reth_name = f"0_hold_reth_€{capital:.0f}"
            eth_p = self.portfolios[eth_name]
            reth_p = self.portfolios[reth_name]
            eth_p.tick(ts)
            reth_p.tick(ts)
            # ETH hold: value constant in EUR terms only if ETH/EUR fixed;
            # track in ETH-equivalent EUR using observation eth_eur
            eth_p.eth_eur = capital  # flat EUR if we ignore ETH/EUR moves (basis-neutral control)
            # rETH hold: appreciate with protocol rate from first observation
            if not hasattr(reth_p, "_start_rate"):
                reth_p._start_rate = protocol.reth_rate  # type: ignore[attr-defined]
                reth_p._start_eth_eur = sell_obs.eth_eur  # type: ignore[attr-defined]
                reth_p.eth_eur = 0.0
                reth_p.reth_eur = capital
            start_rate = reth_p._start_rate  # type: ignore[attr-defined]
            growth = protocol.reth_rate / start_rate
            reth_p.reth_eur = capital * growth
            reth_p.staking_carry_eur = capital * (growth - 1.0)

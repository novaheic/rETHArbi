"""rETH Basis Research Daemon — main entrypoint.

Read-only. No private keys. Measure first. Trade later.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.analytics.reports import daily_text_report, write_html_dashboard
from src.collectors import (
    BalancerCollector,
    CurveCollector,
    EthereumClient,
    GasCollector,
    RocketPoolCollector,
    UniswapV3Collector,
)
from src.collectors.demo import DemoFeed
from src.config import Settings, get_settings
from src.models import TradeDirection
from src.monitoring import HealthMonitor
from src.storage import Database
from src.strategy import BasisSimulator, build_observation, format_console_report

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings)
        self.health = HealthMonitor(signal_basis_bps=-abs(settings.min_entry_basis_bps))
        self.client: EthereumClient | None = None
        self.simulator = BasisSimulator(settings)
        self._stop = asyncio.Event()
        self._basis_24h: list[float] = []
        self._signals_today = 0
        self._trades_today = 0
        self._pnl_today = 0.0
        self._pnl_cum = 0.0
        self._once = False

    def request_stop(self) -> None:
        self._stop.set()

    async def setup(self) -> None:
        await self.db.init()
        if not self.settings.demo_mode:
            self.client = EthereumClient(self.settings)
            await self.client.connect()

    async def teardown(self) -> None:
        if self.client:
            await self.client.close()
        await self.db.close()

    async def collect_once(self):
        settings = self.settings
        capitals = [settings.capital_eur_1, settings.capital_eur_2]
        # Quote a liquidity curve; always include the two capital sizes
        sizes = sorted(set(settings.trade_sizes() + capitals))

        if settings.demo_mode:
            if not hasattr(self, "_demo"):
                self._demo = DemoFeed()
            protocol, quotes, gas = self._demo.next()
        else:
            assert self.client is not None
            rocket = RocketPoolCollector(self.client, settings)
            uni = UniswapV3Collector(self.client, settings)
            curve = CurveCollector(self.client, settings)
            bal = BalancerCollector(self.client, settings)
            gas_c = GasCollector(self.client, settings)

            protocol = await rocket.fetch_rate()
            gas = await gas_c.fetch()
            quotes = []
            quotes.extend(await uni.quote_sizes(sizes, gas.eth_eur, protocol.reth_rate))
            try:
                quotes.extend(await curve.quote_sizes(sizes, gas.eth_eur, protocol.reth_rate))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Curve collector error: %s", exc)
            try:
                quotes.extend(await bal.quote_sizes(sizes, gas.eth_eur, protocol.reth_rate))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Balancer collector error: %s", exc)

        observations = [build_observation(protocol, q, gas, settings) for q in quotes]

        await self.db.save_protocol_rate(protocol)
        await self.db.save_gas(gas)
        await self.db.save_quotes(quotes)
        await self.db.save_basis(observations)

        # Paper trading for primary capital sizes on Uniswap
        by_size: dict[float, tuple] = {}
        for capital in capitals:
            buy = next(
                (
                    o
                    for o in observations
                    if o.direction == TradeDirection.BUY_RETH
                    and o.trade_size_eur == capital
                    and o.venue == "uniswap_v3"
                ),
                None,
            )
            sell = next(
                (
                    o
                    for o in observations
                    if o.direction == TradeDirection.SELL_RETH
                    and o.trade_size_eur == capital
                    and o.venue == "uniswap_v3"
                ),
                None,
            )
            if buy and sell:
                by_size[capital] = (buy, sell)
            if sell:
                self._basis_24h.append(sell.basis_bps)
                if len(self._basis_24h) > 5760:  # ~24h at 15s
                    self._basis_24h = self._basis_24h[-5760:]
            # Informational entry signal uses buy-side net edge when discount exists
            if sell and buy and sell.basis_bps <= -abs(settings.min_entry_basis_bps):
                signal_obs = buy.model_copy(update={"basis_bps": sell.basis_bps})
                alert = self.health.maybe_alert(protocol, signal_obs)
                if alert:
                    self._signals_today += 1

        closed = self.simulator.on_observation(protocol, None, None, by_size=by_size)
        for trade in closed:
            await self.db.save_trade(trade)
            self._trades_today += 1
            self._pnl_today += trade.net_pnl_eur or 0.0
            self._pnl_cum += trade.net_pnl_eur or 0.0

        # Durable equity history for check-in dashboard (small key set)
        cap2 = settings.capital_eur_2
        for key in (
            f"A_entry-30_exit0_€{cap2:.0f}",
            f"0_hold_eth_€{cap2:.0f}",
            f"0_hold_reth_€{cap2:.0f}",
        ):
            port = self.simulator.portfolios.get(key)
            if port is not None:
                await self.db.save_portfolio(port.snapshot(protocol.timestamp))

        self.health.record_success()

        print("=" * 60)
        print(format_console_report(protocol, observations, gas, capitals))
        print("=" * 60)

        # Dashboard
        reports_dir = Path(settings.reports_dir)
        primary = self.simulator.portfolios.get(
            f"A_entry-30_exit0_€{settings.capital_eur_2:.0f}"
        )
        port_val = primary.total_eur if primary else settings.capital_eur_2
        port_pnl = (primary.realized_pnl_eur if primary else 0.0) + (
            (primary.total_eur - primary.capital_eur) if primary else 0.0
        )
        write_html_dashboard(
            reports_dir / "dashboard.html",
            protocol,
            observations,
            gas.gas_cost_eur,
            port_val,
            port_pnl,
            self._signals_today,
            self._trades_today,
        )

        # Daily text report
        sell_500 = next(
            (
                o
                for o in observations
                if o.direction == TradeDirection.SELL_RETH
                and o.trade_size_eur == 500
                and o.venue == "uniswap_v3"
            ),
            None,
        )
        sell_1000 = next(
            (
                o
                for o in observations
                if o.direction == TradeDirection.SELL_RETH
                and o.trade_size_eur == 1000
                and o.venue == "uniswap_v3"
            ),
            None,
        )
        report = daily_text_report(
            protocol,
            sell_1000 or sell_500,
            self._basis_24h,
            self._signals_today,
            self._trades_today,
            self._pnl_today,
            self._pnl_cum,
            sell_500,
            sell_1000,
        )
        (reports_dir / "daily_report.txt").write_text(report)

        return protocol, observations, gas

    async def run(self, once: bool = False) -> None:
        self._once = once
        await self.setup()
        try:
            while not self._stop.is_set():
                try:
                    await self.collect_once()
                except Exception as exc:  # noqa: BLE001
                    self.health.record_failure(exc)
                    logger.exception("Observation cycle failed")
                if once:
                    break
                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=self.settings.poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            await self.teardown()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="rETH Basis Research Daemon")
    parser.add_argument("--once", action="store_true", help="Run a single observation cycle")
    parser.add_argument("--demo", action="store_true", help="Use synthetic demo feed")
    parser.add_argument("--poll", type=float, default=None, help="Override poll interval seconds")
    args = parser.parse_args(argv)

    get_settings.cache_clear()
    settings = get_settings()
    if args.demo:
        settings.demo_mode = True
    if args.poll is not None:
        settings.poll_interval_seconds = args.poll

    configure_logging(settings.log_level)
    daemon = Daemon(settings)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, daemon.request_stop)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(daemon.run(once=args.once))
    finally:
        loop.close()


if __name__ == "__main__":
    cli(sys.argv[1:])

"""Unit tests for basis math and paper simulator (no RPC required)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.analytics.statistics import basis_probabilities, trade_metrics
from src.config import Settings
from src.models import BasisObservation, DexQuote, GasPrice, ProtocolRate, TradeDirection
from src.strategy.basis import build_observation, gross_basis_bps, gross_premium_bps
from src.strategy.simulator import BasisSimulator


def test_gross_basis_example():
    # Spec example: protocol 1.1600, market 1.1565 → -30.2 bp
    bps = gross_basis_bps(1.1565, 1.1600)
    assert bps == pytest.approx(-30.1724, rel=1e-4)


def test_gross_premium_units():
    # Buy at 1.162 ETH/rETH while protocol is 1.160 → paying a premium
    # reth/eth * protocol - 1 = (1/1.162)*1.160 - 1 < 0 means you get less ETH-value? 
    # Spec: executable_buy_rate = rETH/ETH; premium = buy_rate * protocol - 1
    # If buy_price (ETH/rETH) = 1.162, reth_per_eth = 1/1.162
    # premium = (1/1.162)*1.160 - 1 ≈ -0.172% → negative = expensive buy
    bps = gross_premium_bps(1.162, 1.160)
    assert bps < 0


def test_build_observation_sell():
    settings = Settings(DEMO_MODE=True)
    protocol = ProtocolRate(
        block_number=1,
        reth_rate=1.16,
        contract_address=settings.reth_address,
        abi_version="test",
    )
    quote = DexQuote(
        block_number=1,
        venue="uniswap_v3",
        pool="x",
        trade_size_eur=500,
        direction=TradeDirection.SELL_RETH,
        amount_in=0.14,
        amount_out=0.14 * 1.1565,
        effective_price=1.1565,
        mid_price=1.158,
        fee=0.0005,
        price_impact=0.001,
        gas_estimate=180_000,
    )
    gas = GasPrice(
        block_number=1,
        gas_price_wei=30_000_000_000,
        eth_eur=3000,
        gas_cost_eth=0.0054,
        gas_cost_eur=16.2,
        gas_units=180_000,
    )
    obs = build_observation(protocol, quote, gas, settings)
    assert obs.basis_bps == pytest.approx(-30.1724, rel=1e-3)
    assert obs.gas_eur > 0
    assert obs.net_edge_bps != 0


def test_simulator_no_lookahead_entry_exit():
    settings = Settings(
        DEMO_MODE=True,
        ENTRY_THRESHOLDS_BPS="-30",
        EXIT_THRESHOLDS_BPS="0",
        MAX_HOLDING_SECONDS="86400",
        CAPITAL_EUR_1=500,
        CAPITAL_EUR_2=500,
        TRADE_SIZES_EUR="500",
    )
    sim = BasisSimulator(settings, capitals=[500])
    # Only keep Strategy A configs for this test speed
    sim.configs = [c for c in sim.configs if c.name.startswith("A_") and not c.fixed_time_exit]
    sim.portfolios = {c.name: sim.portfolios[c.name] for c in sim.configs}
    # re-add holds
    for label in ("hold_eth", "hold_reth"):
        name = f"0_{label}_€500"
        from src.strategy.portfolio import PaperPortfolio

        sim.portfolios[name] = PaperPortfolio(strategy=name, capital_eur=500)

    def make(protocol_rate, sell_rate, buy_rate, ts, basis_override=None):
        protocol = ProtocolRate(
            timestamp=ts,
            block_number=1,
            reth_rate=protocol_rate,
            contract_address=settings.reth_address,
            abi_version="test",
        )
        sell = BasisObservation(
            timestamp=ts,
            block_number=1,
            venue="uniswap_v3",
            trade_size_eur=500,
            protocol_rate=protocol_rate,
            market_rate=sell_rate,
            direction=TradeDirection.SELL_RETH,
            basis_bps=basis_override if basis_override is not None else (sell_rate / protocol_rate - 1) * 10000,
            gas_eur=1.0,
            dex_fee_eur=0.25,
            estimated_slippage_eur=0.5,
            mev_eur=0.1,
            net_edge_eur=1.0,
            net_edge_bps=20,
            eth_eur=3000,
        )
        buy = BasisObservation(
            timestamp=ts,
            block_number=1,
            venue="uniswap_v3",
            trade_size_eur=500,
            protocol_rate=protocol_rate,
            market_rate=buy_rate,
            direction=TradeDirection.BUY_RETH,
            basis_bps=(buy_rate / protocol_rate - 1) * 10000,
            gas_eur=1.0,
            dex_fee_eur=0.25,
            estimated_slippage_eur=0.5,
            mev_eur=0.1,
            net_edge_eur=1.0,
            net_edge_bps=20,
            eth_eur=3000,
        )
        return protocol, buy, sell

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # No entry yet — only -10 bp
    p, b, s = make(1.16, 1.15884, 1.159, t0, basis_override=-10)
    closed = sim.on_observation(p, b, s, t0)
    assert closed == []
    assert all(port.open_trade is None for name, port in sim.portfolios.items() if name.startswith("A_"))

    # Entry at -35 bp
    t1 = t0 + timedelta(minutes=15)
    p, b, s = make(1.16, 1.15594, 1.1565, t1, basis_override=-35)
    sim.on_observation(p, b, s, t1)
    open_ports = [port for name, port in sim.portfolios.items() if name.startswith("A_") and port.open_trade]
    assert len(open_ports) >= 1

    # Still open at -20 bp (exit only at >= 0)
    t2 = t1 + timedelta(hours=1)
    p, b, s = make(1.1601, 1.1578, 1.158, t2, basis_override=-20)
    closed = sim.on_observation(p, b, s, t2)
    assert closed == []

    # Exit at +2 bp
    t3 = t2 + timedelta(hours=1)
    p, b, s = make(1.1602, 1.1604, 1.1605, t3, basis_override=2)
    closed = sim.on_observation(p, b, s, t3)
    assert len(closed) >= 1
    trade = closed[0]
    assert trade.staking_carry_eur is not None
    assert trade.trading_pnl_eur is not None
    assert trade.net_pnl_eur is not None
    # Components recorded separately
    assert trade.status.startswith("closed")


def test_basis_probabilities():
    data = [-5, -15, -25, -40, -80, 5, 0]
    probs = basis_probabilities(data, [-10, -20, -30, -50, -100])
    assert probs["P(basis<-10bp)"] == pytest.approx(4 / 7)


def test_trade_metrics_empty():
    m = trade_metrics([], [], 1000)
    assert m["n_trades"] == 0

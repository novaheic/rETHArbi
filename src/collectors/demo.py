"""Demo/synthetic data mode for offline development and tests."""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from src.models import DexQuote, GasPrice, ProtocolRate, TradeDirection


class DemoFeed:
    """Deterministic-ish synthetic rETH market for DEMO_MODE."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.t = 0
        self.protocol_rate = 1.160432
        self.block = 20_000_000

    def next(self) -> tuple[ProtocolRate, list[DexQuote], GasPrice]:
        self.t += 1
        self.block += 1
        # Slow protocol rate drift (staking carry)
        if self.t % 100 == 0:
            self.protocol_rate *= 1.00001

        # Occasional deep discounts
        shock = 0.0
        if self.rng.random() < 0.05:
            shock = -self.rng.uniform(0.0015, 0.008)

        mid = self.protocol_rate * (1.0 + shock - 0.0005 + 0.0003 * math.sin(self.t / 10))
        eth_eur = 3000.0
        gas = GasPrice(
            block_number=self.block,
            gas_price_wei=25_000_000_000,
            base_fee_wei=20_000_000_000,
            priority_fee_wei=2_000_000_000,
            eth_eur=eth_eur,
            gas_cost_eth=0.0045,
            gas_cost_eur=0.0045 * eth_eur,
            gas_units=180_000,
        )
        protocol = ProtocolRate(
            timestamp=datetime.now(timezone.utc),
            block_number=self.block,
            reth_rate=self.protocol_rate,
            reth_supply=500_000.0,
            eth_backing=500_000.0 * self.protocol_rate,
            source="demo",
            contract_address="0xae78736Cd615f374D3085123A210448E74Fc6393",
            abi_version="demo",
        )

        quotes: list[DexQuote] = []
        for size in (250, 500, 1000, 2500, 5000, 10000):
            impact = 0.0001 * (size / 500) ** 0.8
            sell_price = mid * (1 - impact)
            buy_price = mid * (1 + impact)
            eth_amount = size / eth_eur
            reth_in = eth_amount / self.protocol_rate
            quotes.append(
                DexQuote(
                    block_number=self.block,
                    venue="uniswap_v3",
                    pool="demo",
                    trade_size_eur=float(size),
                    direction=TradeDirection.SELL_RETH,
                    amount_in=reth_in,
                    amount_out=reth_in * sell_price,
                    effective_price=sell_price,
                    mid_price=mid,
                    fee=0.0005,
                    price_impact=impact,
                    gas_estimate=180_000,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    liquidity=1e18,
                )
            )
            quotes.append(
                DexQuote(
                    block_number=self.block,
                    venue="uniswap_v3",
                    pool="demo",
                    trade_size_eur=float(size),
                    direction=TradeDirection.BUY_RETH,
                    amount_in=eth_amount,
                    amount_out=eth_amount / buy_price,
                    effective_price=buy_price,
                    mid_price=mid,
                    fee=0.0005,
                    price_impact=impact,
                    gas_estimate=180_000,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    liquidity=1e18,
                )
            )
        return protocol, quotes, gas

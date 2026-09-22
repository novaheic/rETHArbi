"""Basis and net-edge calculations.

All prices normalized to ETH per rETH before computing basis.
"""

from __future__ import annotations

from src.config import Settings
from src.models import BasisObservation, DexQuote, GasPrice, ProtocolRate, TradeDirection


def gross_basis_bps(executable_sell_rate: float, protocol_rate: float) -> float:
    """market_value / protocol_value - 1, in basis points."""
    if protocol_rate <= 0:
        raise ValueError("protocol_rate must be positive")
    return (executable_sell_rate / protocol_rate - 1.0) * 10_000


def gross_premium_bps(executable_buy_rate: float, protocol_rate: float) -> float:
    """buy_rate is ETH spent per rETH received; premium = buy_rate/protocol - 1? 

    Spec:
      executable_buy_rate = rETH received / ETH spent
      gross_premium = executable_buy_rate * protocol_rate - 1

    We store effective_price as ETH/rETH (= 1 / (rETH/ETH)), so:
      reth_per_eth = 1 / buy_price_eth_per_reth
      premium = reth_per_eth * protocol_rate - 1
             = protocol_rate / buy_price - 1
    """
    if executable_buy_rate <= 0 or protocol_rate <= 0:
        raise ValueError("rates must be positive")
    reth_per_eth = 1.0 / executable_buy_rate
    return (reth_per_eth * protocol_rate - 1.0) * 10_000


def build_observation(
    protocol: ProtocolRate,
    quote: DexQuote,
    gas: GasPrice,
    settings: Settings,
) -> BasisObservation:
    protocol_rate = protocol.reth_rate
    market_rate = quote.effective_price

    if quote.direction == TradeDirection.SELL_RETH:
        basis_bps = gross_basis_bps(market_rate, protocol_rate)
        premium_bps = None
        # Buying the discount: we buy rETH (pay premium side) then sell later.
        # For sell-side observation, gross edge if we already hold rETH and sell.
        # For entry signal we care about buy-side; still record sell basis.
        gross_edge_eur = quote.trade_size_eur * (basis_bps / 10_000)
    else:
        # BUY_RETH: how expensive is buying relative to protocol
        premium_bps = gross_premium_bps(market_rate, protocol_rate)
        # Discount mean-reversion entry uses buy: if sell basis is deep discount,
        # buy price should also be below protocol. Edge estimate:
        # protocol value of rETH received vs ETH spent
        reth_received = quote.amount_out
        protocol_eth_value = reth_received * protocol_rate
        eth_spent = quote.amount_in
        gross_edge_eur = (protocol_eth_value - eth_spent) * gas.eth_eur
        basis_bps = (market_rate / protocol_rate - 1.0) * 10_000

    gas_units = quote.gas_estimate or settings.gas_units_swap
    gas_eth = (gas.gas_price_wei * gas_units) / 1e18
    gas_eur = gas_eth * gas.eth_eur

    dex_fee_eur = quote.trade_size_eur * quote.fee
    slippage_frac = abs(quote.price_impact or 0.0)
    slippage_eur = quote.trade_size_eur * slippage_frac
    mev_eur = quote.trade_size_eur * (settings.mev_cost_bps / 10_000)

    # Round-trip cost approx for mean-reversion (entry + exit)
    round_trip_costs = 2 * (gas_eur + dex_fee_eur) + slippage_eur + mev_eur

    if quote.direction == TradeDirection.BUY_RETH:
        net_edge_eur = gross_edge_eur - round_trip_costs
    else:
        # Sell observation: net edge if selling into discount (negative = costly)
        net_edge_eur = gross_edge_eur - (gas_eur + dex_fee_eur + slippage_eur + mev_eur)

    net_edge_bps = (net_edge_eur / quote.trade_size_eur) * 10_000 if quote.trade_size_eur else 0.0

    return BasisObservation(
        block_number=quote.block_number,
        venue=quote.venue,
        trade_size_eur=quote.trade_size_eur,
        protocol_rate=protocol_rate,
        market_rate=market_rate,
        direction=quote.direction,
        basis_bps=basis_bps,
        gross_premium_bps=premium_bps,
        gas_eur=gas_eur,
        dex_fee_eur=dex_fee_eur,
        estimated_slippage_eur=slippage_eur,
        mev_eur=mev_eur,
        net_edge_eur=net_edge_eur,
        net_edge_bps=net_edge_bps,
        eth_eur=gas.eth_eur,
    )


def format_console_report(
    protocol: ProtocolRate,
    observations: list[BasisObservation],
    gas: GasPrice,
    capitals: list[float],
) -> str:
    lines = [
        protocol.timestamp.strftime("%Y-%m-%d %H:%M:%S %Z"),
        f"block:           {protocol.block_number}",
        f"rETH rate:       {protocol.reth_rate:.10f} ETH",
        f"ETH/EUR:         {gas.eth_eur:.2f}",
        f"gas:             €{gas.gas_cost_eur:.4f} ({gas.gas_units} units @ {gas.gas_price_wei / 1e9:.2f} gwei)",
    ]

    # Prefer Uniswap sell quotes for headline
    sell_obs = [o for o in observations if o.direction == TradeDirection.SELL_RETH]
    buy_obs = [o for o in observations if o.direction == TradeDirection.BUY_RETH]

    if sell_obs:
        best = max(sell_obs, key=lambda o: o.market_rate)  # best sell = highest ETH out
        # Headline: use €500 if present else first
        headline = next((o for o in sell_obs if o.trade_size_eur == 500 and o.venue == "uniswap_v3"), best)
        lines.append(f"Uniswap sell:    {headline.market_rate:.10f} ETH  ({headline.venue})")
        lines.append(f"Basis:           {headline.basis_bps:+.2f} bp")

    for capital in capitals:
        lines.append(f"€{capital:,.0f} trade:")
        buy = next(
            (o for o in buy_obs if o.trade_size_eur == capital and o.venue == "uniswap_v3"),
            next((o for o in buy_obs if o.trade_size_eur == capital), None),
        )
        sell = next(
            (o for o in sell_obs if o.trade_size_eur == capital and o.venue == "uniswap_v3"),
            next((o for o in sell_obs if o.trade_size_eur == capital), None),
        )
        obs = buy or sell
        if obs is None:
            lines.append("  (no quote)")
            continue
        # Gross edge for discount entry ≈ -basis on buy side * capital if market below protocol
        sell_basis = sell.basis_bps if sell else obs.basis_bps
        gross = capital * (-sell_basis / 10_000) if sell_basis < 0 else capital * (sell_basis / 10_000) * -1
        # Show costs from the observation
        lines.append(f"  Gross edge:      €{gross:+.4f}  (basis {sell_basis:+.2f} bp)")
        lines.append(f"  Gas (1-way):     €{obs.gas_eur:.4f}")
        lines.append(f"  Fees (1-way):    €{obs.dex_fee_eur:.4f}")
        lines.append(f"  Slippage:        €{obs.estimated_slippage_eur:.4f}")
        lines.append(f"  MEV buffer:      €{obs.mev_eur:.4f}")
        lines.append(f"  Net edge (RT):   €{obs.net_edge_eur:+.4f}  ({obs.net_edge_bps:+.2f} bp)")
        if sell:
            lines.append(f"  Sell rate:       {sell.market_rate:.10f}")
        if buy:
            lines.append(f"  Buy rate:        {buy.market_rate:.10f}")

    # Venue comparison at €1000 sell
    venue_sells = [o for o in sell_obs if o.trade_size_eur in capitals]
    if venue_sells:
        lines.append("Venue sell basis:")
        for o in sorted(venue_sells, key=lambda x: (x.trade_size_eur, x.venue)):
            lines.append(f"  {o.venue:12s} €{o.trade_size_eur:>7,.0f}  {o.basis_bps:+7.2f} bp  net {o.net_edge_bps:+7.2f} bp")

    return "\n".join(lines)

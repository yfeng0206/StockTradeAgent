"""Portfolio management test: strategies start with a RANDOM existing portfolio.

Instead of starting with $100k cash, each strategy inherits a random portfolio
of 3-7 stocks + cash totaling $100k. They must manage it -- sell what they
don't like, buy what they do -- through the full period.

The key question: which strategy best manages an inherited portfolio?
Also computes a "just hold" baseline: what if you did nothing?

Usage:
    python eval/run_portfolio_test.py                          # All 14 periods
    python eval/run_portfolio_test.py --period recession       # Single period
    python eval/run_portfolio_test.py --seed 42                # Custom seed
    python eval/run_portfolio_test.py --period bull --seed 99  # Both
"""

import argparse
import json
import os
import sys
import time
import random
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import (
    run_daily_simulation, UNIVERSE, BENCHMARKS, MACRO_ETFS,
    PERIODS, download_data,
)
from events_data import build_events_calendar

RUNS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")


def generate_random_portfolio(price_data: dict, start_date: str, seed: int,
                              initial_cash: float = 100_000,
                              min_stocks: int = 3, max_stocks: int = 7):
    """Generate a random starting portfolio from stocks with available data.

    Returns:
        dict with keys:
            positions: {ticker: {"shares": N, "entry_price": P, "entry_date": start_date}}
            cash: remaining cash after buying the random stocks
            stock_value: total value of the stock positions
            portfolio_desc: human-readable description
    """
    rng = random.Random(seed)

    # Filter UNIVERSE to only stocks that have price data on or before start_date
    available = []
    prices_on_start = {}
    for ticker in UNIVERSE:
        # Skip ETFs -- we want only individual stocks in the random portfolio
        if ticker in ("SPY", "QQQ"):
            continue
        if ticker in price_data and not price_data[ticker].empty:
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(start_date)
            if mask.any():
                price = float(df.loc[mask, "Close"].iloc[-1])
                if price > 0:
                    available.append(ticker)
                    prices_on_start[ticker] = price

    if len(available) < min_stocks:
        raise ValueError(
            f"Only {len(available)} stocks have data on {start_date}, "
            f"need at least {min_stocks}"
        )

    # Pick 3-7 random stocks
    num_stocks = rng.randint(min_stocks, min(max_stocks, len(available)))
    selected = rng.sample(available, num_stocks)

    # Target: stock value should be 70-90% of initial_cash
    target_stock_pct = rng.uniform(0.70, 0.90)
    target_stock_value = initial_cash * target_stock_pct

    # Assign random weights to each stock (Dirichlet-like: random splits)
    raw_weights = [rng.random() for _ in selected]
    total_raw = sum(raw_weights)
    weights = [w / total_raw for w in raw_weights]

    # Convert weights to share counts
    positions = {}
    actual_stock_value = 0.0
    for ticker, weight in zip(selected, weights):
        target_value = target_stock_value * weight
        price = prices_on_start[ticker]
        shares = max(1, int(target_value / price))

        # Cap: don't exceed the target too much for any single position
        cost = shares * price
        if cost > target_stock_value * 0.5:
            shares = max(1, int(target_stock_value * 0.5 / price))
            cost = shares * price

        positions[ticker] = {
            "shares": shares,
            "entry_price": price,
            "entry_date": start_date,
        }
        actual_stock_value += cost

    # If total stock value exceeds what we can afford, scale down
    if actual_stock_value > initial_cash * 0.95:
        scale = (initial_cash * 0.90) / actual_stock_value
        for ticker in positions:
            old_shares = positions[ticker]["shares"]
            new_shares = max(1, int(old_shares * scale))
            positions[ticker]["shares"] = new_shares
        # Recalculate
        actual_stock_value = sum(
            pos["shares"] * prices_on_start[t]
            for t, pos in positions.items()
        )

    remaining_cash = initial_cash - actual_stock_value

    # Build description
    desc_parts = []
    for ticker, pos in sorted(positions.items()):
        val = pos["shares"] * prices_on_start[ticker]
        desc_parts.append(f"{ticker}:{pos['shares']}sh(${val:,.0f})")
    portfolio_desc = f"[{', '.join(desc_parts)}] + ${remaining_cash:,.0f} cash"

    return {
        "positions": positions,
        "cash": remaining_cash,
        "stock_value": actual_stock_value,
        "total_value": initial_cash,
        "portfolio_desc": portfolio_desc,
        "tickers": list(positions.keys()),
        "prices": {t: prices_on_start[t] for t in positions},
    }


def compute_hold_baseline(portfolio: dict, price_data: dict, end_date: str):
    """Compute the 'just hold' baseline: what if you never traded?

    Returns final value and return % if you held the initial random portfolio
    through the entire period without any changes.
    """
    final_value = portfolio["cash"]  # cash stays the same

    for ticker, pos in portfolio["positions"].items():
        if ticker in price_data and not price_data[ticker].empty:
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(end_date)
            if mask.any():
                final_price = float(df.loc[mask, "Close"].iloc[-1])
                final_value += pos["shares"] * final_price
            else:
                # No data at end -- use entry price (conservative)
                final_value += pos["shares"] * pos["entry_price"]
        else:
            final_value += pos["shares"] * pos["entry_price"]

    return final_value


def inject_portfolio(strategy, portfolio: dict):
    """Inject a random portfolio into an already-initialized strategy.

    The strategy was initialized with $100k cash and no positions.
    We set its positions and reduce its cash to match the random portfolio.
    """
    strategy.positions = {}
    for ticker, pos in portfolio["positions"].items():
        strategy.positions[ticker] = {
            "shares": pos["shares"],
            "entry_price": pos["entry_price"],
            "entry_date": pos["entry_date"],
        }

    strategy.cash = portfolio["cash"]

    # Log the injection as a reasoning entry
    tickers_str = ", ".join(
        f"{t}({pos['shares']}sh)"
        for t, pos in portfolio["positions"].items()
    )
    strategy._log_reasoning(
        portfolio["positions"][list(portfolio["positions"].keys())[0]]["entry_date"],
        "INJECT", "", 0,
        f"Inherited portfolio: {tickers_str}. Cash: ${portfolio['cash']:,.0f}. "
        f"Stock value: ${portfolio['stock_value']:,.0f}."
    )


def run_portfolio_test_single(period_key: str, period_info: dict,
                               portfolio: dict, price_data: dict,
                               events_cal: dict, initial_cash: float,
                               max_positions: int, quiet: bool = True):
    """Run all 9 strategies on a single period with injected portfolio.

    We call run_daily_simulation and then patch each strategy's starting state.
    But run_daily_simulation creates strategies internally, so we need a
    different approach: replicate the simulation setup with injection.

    Instead, we import the internals and run the simulation loop ourselves
    with injected portfolios.
    """
    from signals import SignalEngine
    from triggers import TriggerEngine
    from sim_memory import SimulationMemory
    from risk_overlay import RiskOverlay
    from strategies import (
        ValueStrategy, MomentumStrategy, BalancedStrategy,
        DefensiveStrategy, EventDrivenStrategy, AdaptiveStrategy,
        CommodityStrategy, MixStrategy, MixLLMStrategy,
    )

    start = period_info["start"]
    end = period_info["end"]
    period_name = period_info["name"]

    # Initialize DataLoader
    LOOP_DIR = os.path.dirname(__file__)
    NEWS_DIR = os.path.join(os.path.dirname(LOOP_DIR), "data", "news")
    sys.path.insert(0, os.path.join(os.path.dirname(LOOP_DIR), "tools"))
    from data_loader import DataLoader
    data_loader = DataLoader(live_mode=False)

    # Engines — realistic mode: T-1 signals, premarket execution
    signal_engine = SignalEngine(price_data, events_cal, NEWS_DIR, data_loader=data_loader,
                                realistic=True, exec_model="premarket")
    trigger_engine = TriggerEngine(signal_engine)

    # Initialize strategies (same as daily_loop.py)
    core_strategies = [
        ValueStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        MomentumStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        BalancedStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        DefensiveStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        EventDrivenStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        AdaptiveStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        CommodityStrategy(initial_cash, events_calendar=events_cal),
    ]
    mix_strategy = MixStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions)
    mix_strategy._peer_strategies = core_strategies
    mix_llm_strategy = MixLLMStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions)
    mix_llm_strategy._peer_strategies = core_strategies
    strategies = core_strategies + [mix_strategy, mix_llm_strategy]

    # Apply realistic mode, execution model, slippage to ALL strategies
    for strat in strategies:
        strat.slippage = 0.0005
        strat._realistic = True
        strat._exec_model = "premarket"
        strat._frequency_override = "biweekly"

    # Inject the random portfolio into each strategy
    for strat in strategies:
        inject_portfolio(strat, portfolio)

    # Risk overlay
    risk_overlay = RiskOverlay()

    # Daily simulation loop — use SPY dates as ground truth (no holiday trading)
    if "SPY" in price_data and not price_data["SPY"].empty:
        spy_dates = set(price_data["SPY"].index.strftime("%Y-%m-%d"))
        trading_days = pd.date_range(start=start, end=end, freq="B")
        trading_days = trading_days[trading_days.strftime("%Y-%m-%d").isin(spy_dates)]
    else:
        trading_days = pd.date_range(start=start, end=end, freq="B")
    last_rebalance_month = None
    daily_trigger_log = []

    for i, day in enumerate(trading_days):
        date_str = day.strftime("%Y-%m-%d")
        current_month = date_str[:7]
        is_rebalance_day = (current_month != last_rebalance_month)
        if is_rebalance_day:
            last_rebalance_month = current_month

        _detect_cache = {}
        macro = signal_engine.compute_macro(date_str)
        regime = macro.get("regime", "normal")
        news = macro.get("news", {})

        if is_rebalance_day:
            risk_overlay.update_consensus(strategies, price_data, date_str)

        # Snapshot trigger state so ALL strategies see the same triggers
        _saved_trigger_regime = trigger_engine._last_regime
        _saved_trigger_news = trigger_engine._last_news_risk

        for strat in strategies:
            trigger_engine._last_regime = _saved_trigger_regime
            trigger_engine._last_news_risk = _saved_trigger_news
            trigger_engine.atr_stop_multiplier = getattr(strat, 'atr_stop_multiplier', 2.0)
            triggers = trigger_engine.scan(
                UNIVERSE, strat.positions, date_str, price_data,
                precomputed_macro=macro,
            )

            strat._last_regime = regime
            strat._last_news_summary = (
                f"geo_risk={news.get('geo_risk', 0):.2f}"
                if news.get('geo_risk', 0) > 0 else None
            )

            insight = SimulationMemory.generate_insight(
                date_str, strat.positions, strat.memory, regime, news,
            )

            if triggers:
                def _get_price(tkr):
                    return strat._get_exec_price(price_data, tkr, date_str)

                sold_today = set()

                for t in triggers:
                    if t.type == "STOP_LOSS" and t.ticker in strat.positions:
                        price = _get_price(t.ticker)
                        if price:
                            record = SimulationMemory.read_ticker_record(t.ticker, strat.memory)
                            reason = f"STOP LOSS triggered ({t.data.get('pnl_pct', '?')}% loss)"
                            if record.get("warning") == "repeated_loser":
                                reason += (
                                    f" [MEMORY: repeated loser, {record['trades']} trades "
                                    f"avg {record['avg_pnl']:+.1f}%]"
                                )
                            strat._sell(t.ticker, price, date_str, reason)
                            sold_today.add(t.ticker)

                    elif t.type == "REGIME_CHANGE":
                        new_regime = t.data.get("to", "normal")
                        old_regime = t.data.get("from", "normal")
                        entering_danger = (
                            new_regime in ("crisis", "high_volatility")
                            and old_regime not in ("crisis", "high_volatility")
                        )

                        strat._log_reasoning(
                            date_str, "REGIME", "", 0,
                            f"Regime changed: {old_regime} -> {new_regime}. {insight}",
                        )

                        if entering_danger and strat.positions:
                            pos_pnl = []
                            for tkr, pos in strat.positions.items():
                                p = _get_price(tkr)
                                if p:
                                    pnl = (p - pos["entry_price"]) / pos["entry_price"] * 100
                                    pos_pnl.append((tkr, pnl, p))
                            pos_pnl.sort(key=lambda x: x[1])

                            if strat.name == "Defensive":
                                to_sell = len(pos_pnl)
                            elif strat.name == "Momentum":
                                to_sell = max(1, len(pos_pnl) // 3)
                            elif strat.name in ("Balanced", "Adaptive", "Mix", "MixLLM"):
                                to_sell = max(1, len(pos_pnl) // 4)
                            elif strat.name == "Value":
                                to_sell = 0
                            else:
                                to_sell = max(1, len(pos_pnl) // 5)

                            for tkr, pnl, p in pos_pnl[:to_sell]:
                                strat._sell(
                                    tkr, p, date_str,
                                    f"REGIME SHIFT to {new_regime}: {strat.name} selling ({pnl:+.1f}%)",
                                )
                                sold_today.add(tkr)

                    elif t.type == "NEWS_SPIKE":
                        direction = t.data.get("direction", "")
                        themes = t.data.get("themes", [])
                        geo_risk = t.data.get("geo_risk", 0)

                        strat._log_reasoning(
                            date_str, "NEWS", "", 0,
                            f"NEWS {direction.upper()}: geo_risk "
                            f"{t.data.get('previous', 0):.2f} -> {geo_risk:.2f}. "
                            f"Themes: {', '.join(themes)}",
                        )

                        if direction == "escalation" and geo_risk > 0.6:
                            if strat.name == "Defensive":
                                if strat.positions:
                                    pos_vol = []
                                    for tkr in list(strat.positions.keys()):
                                        tech = signal_engine.compute_technical(tkr, date_str)
                                        vol = tech.get("vol_20d", 0.3)
                                        pos_vol.append((tkr, vol))
                                    pos_vol.sort(key=lambda x: -x[1])
                                    if geo_risk > 0.8:
                                        to_sell_count = len(pos_vol)
                                    else:
                                        to_sell_count = max(1, len(pos_vol) // 2)
                                    for tkr, vol in pos_vol[:to_sell_count]:
                                        p = _get_price(tkr)
                                        if p and tkr in strat.positions:
                                            strat._sell(
                                                tkr, p, date_str,
                                                f"NEWS: {strat.name} reducing exposure, "
                                                f"selling highest-vol {tkr} (vol={vol:.0%}, geo={geo_risk:.2f})",
                                            )
                                            sold_today.add(tkr)

                            elif strat.name in ("Balanced", "Adaptive"):
                                if strat.positions:
                                    pos_vol = []
                                    for tkr in list(strat.positions.keys()):
                                        tech = signal_engine.compute_technical(tkr, date_str)
                                        vol = tech.get("vol_20d", 0.3)
                                        pos_vol.append((tkr, vol))
                                    pos_vol.sort(key=lambda x: -x[1])
                                    to_sell_count = max(1, len(pos_vol) // 3)
                                    for tkr, vol in pos_vol[:to_sell_count]:
                                        p = _get_price(tkr)
                                        if p and tkr in strat.positions:
                                            strat._sell(
                                                tkr, p, date_str,
                                                f"NEWS: {strat.name} selling high-vol {tkr} "
                                                f"(vol={vol:.0%}, geo={geo_risk:.2f})",
                                            )
                                            sold_today.add(tkr)

                            elif strat.name == "EventDriven":
                                strat._log_reasoning(
                                    date_str, "NEWS", "", 0,
                                    f"NEWS: EventDriven -- geo escalation, reducing exposure",
                                )
                                worst = None
                                worst_pnl = 0
                                for tkr, pos in strat.positions.items():
                                    p = _get_price(tkr)
                                    if p:
                                        pnl = (p - pos["entry_price"]) / pos["entry_price"] * 100
                                        if worst is None or pnl < worst_pnl:
                                            worst, worst_pnl = tkr, pnl
                                if worst and worst_pnl < 0:
                                    p = _get_price(worst)
                                    if p:
                                        strat._sell(
                                            worst, p, date_str,
                                            f"NEWS: EventDriven selling worst "
                                            f"({worst} {worst_pnl:+.1f}%) on geo escalation",
                                        )
                                        sold_today.add(worst)

                    elif t.type == "EARNINGS_RELEASE" and t.severity == "HIGH":
                        ticker = t.ticker
                        signal = t.data.get("signal", "neutral")
                        surprise = t.data.get("surprise_pct", "?")
                        record = SimulationMemory.read_ticker_record(ticker, strat.memory)

                        should_buy = False
                        should_sell = False

                        if strat.name == "Momentum":
                            should_buy = signal == "strong_beat" and ticker not in strat.positions
                            should_sell = signal in ("strong_miss", "miss") and ticker in strat.positions
                        elif strat.name == "Value":
                            should_buy = False
                            should_sell = False
                        elif strat.name == "EventDriven":
                            should_buy = signal in ("strong_beat", "beat") and ticker not in strat.positions
                            should_sell = signal in ("strong_miss", "miss") and ticker in strat.positions
                        elif strat.name == "Defensive":
                            is_low_vol = False
                            tech = signal_engine.compute_technical(ticker, date_str)
                            if tech.get("vol_20d", 1) < 0.25:
                                is_low_vol = True
                            safe_regime = regime not in ("crisis", "high_volatility", "bearish")
                            should_buy = (
                                signal in ("strong_beat", "beat")
                                and is_low_vol and safe_regime
                                and ticker not in strat.positions
                            )
                            should_sell = signal in ("strong_miss",) and ticker in strat.positions
                        elif strat.name in ("Balanced", "Adaptive", "Mix", "MixLLM"):
                            safe_regime = regime not in ("crisis", "high_volatility")
                            should_buy = signal == "strong_beat" and safe_regime and ticker not in strat.positions
                            should_sell = signal == "strong_miss" and ticker in strat.positions
                        else:
                            should_buy = False
                            should_sell = signal in ("strong_miss",) and ticker in strat.positions

                        if should_buy and record.get("warning") == "repeated_loser":
                            strat._log_reasoning(
                                date_str, "SKIP", ticker, 0,
                                f"EARNINGS {signal} on {ticker} but MEMORY: repeated loser -- {strat.name} skipping",
                            )
                            should_buy = False

                        if should_buy and len(strat.positions) < strat.max_positions:
                            price = _get_price(ticker)
                            if price and strat.cash > price:
                                per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                shares = int(min(per_pos, strat.cash) / price)
                                if shares > 0 and ticker not in sold_today:
                                    reason = f"EARNINGS {signal}: surprise {surprise}% [{strat.name}]"
                                    mem_note = SimulationMemory.read_regime_wisdom(regime, strat.memory)
                                    if mem_note.get("known"):
                                        reason += f" [Regime {regime}: {mem_note['win_rate']}% win rate]"
                                    strat._buy(ticker, shares, price, date_str, reason)

                        elif should_sell and ticker in strat.positions:
                            price = _get_price(ticker)
                            if price:
                                strat._sell(
                                    ticker, price, date_str,
                                    f"EARNINGS {signal}: surprise {surprise}% [{strat.name}]",
                                )
                                sold_today.add(ticker)

                    elif t.type == "VOLUME_ANOMALY" and t.severity in ("MEDIUM", "HIGH"):
                        if strat.name in ("Value", "Balanced", "Adaptive", "Commodity"):
                            continue
                        ticker = t.ticker
                        price_move = t.data.get("price_move_pct", 0)
                        vol_ratio = t.data.get("volume_ratio", 1)

                        if strat.name in ("Defensive", "Value"):
                            if price_move < -8 and ticker in strat.positions and strat.name == "Defensive":
                                price = _get_price(ticker)
                                if price:
                                    strat._sell(
                                        ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% on {vol_ratio}x volume -- {strat.name} exiting",
                                    )
                                    sold_today.add(ticker)
                        elif strat.name in ("Momentum", "EventDriven"):
                            if (price_move > 5 and ticker not in strat.positions
                                    and len(strat.positions) < strat.max_positions):
                                record = SimulationMemory.read_ticker_record(ticker, strat.memory)
                                if not record.get("warning"):
                                    price = _get_price(ticker)
                                    if price and strat.cash > price:
                                        per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                        shares = int(min(per_pos, strat.cash * 0.5) / price)
                                        if shares > 0 and ticker not in sold_today:
                                            strat._buy(
                                                ticker, shares, price, date_str,
                                                f"VOLUME SPIKE: +{price_move:.1f}% on {vol_ratio}x vol -- {strat.name} catalyst play",
                                            )
                            elif price_move < -8 and ticker in strat.positions:
                                price = _get_price(ticker)
                                if price:
                                    strat._sell(
                                        ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% -- {strat.name} cutting loss",
                                    )
                                    sold_today.add(ticker)
                        else:
                            if (price_move > 8 and ticker not in strat.positions
                                    and len(strat.positions) < strat.max_positions):
                                record = SimulationMemory.read_ticker_record(ticker, strat.memory)
                                if not record.get("warning"):
                                    price = _get_price(ticker)
                                    if price and strat.cash > price:
                                        per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                        shares = int(min(per_pos, strat.cash * 0.3) / price)
                                        if shares > 0 and ticker not in sold_today:
                                            strat._buy(
                                                ticker, shares, price, date_str,
                                                f"VOLUME SPIKE: +{price_move:.1f}% on {vol_ratio}x vol -- {strat.name} cautious entry",
                                            )
                            elif price_move < -8 and ticker in strat.positions:
                                price = _get_price(ticker)
                                if price:
                                    strat._sell(
                                        ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% -- {strat.name} exiting",
                                    )
                                    sold_today.add(ticker)

                    elif t.type == "PROFIT_TARGET" and t.ticker in strat.positions:
                        pnl_pct = t.data.get("pnl_pct", 0)
                        ticker = t.ticker
                        pos = strat.positions[ticker]
                        last_trim_price = pos.get("_last_trim_price", 0)
                        price = _get_price(ticker)
                        trim_thresh = getattr(strat, 'trim_threshold_pct', 40.0)
                        if (price and price > last_trim_price * 1.25
                                and pnl_pct > trim_thresh and pos["shares"] > 2):
                            trim_shares = max(1, pos["shares"] // 3)
                            proceeds = trim_shares * price
                            pnl = (price - pos["entry_price"]) * trim_shares
                            strat.cash += proceeds
                            strat.positions[ticker]["shares"] -= trim_shares
                            strat.positions[ticker]["_last_trim_price"] = price
                            strat.transactions.append({
                                "date": date_str, "action": "TRIM",
                                "ticker": ticker, "shares": trim_shares,
                                "price": round(price, 2), "total": round(proceeds, 2),
                                "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                                "cash_after": round(strat.cash, 2),
                            })
                            strat._log_reasoning(
                                date_str, "TRIM", ticker, price,
                                f"PROFIT TARGET: +{pnl_pct:.0f}%, trimming 1/3 ({trim_shares} shares). "
                                f"Holding {strat.positions[ticker]['shares']}.",
                            )

            # Rebalance
            sold_today_in_rebalance = any(
                tx["date"] == date_str and tx["action"] == "SELL"
                for tx in strat.transactions
            ) if strat.transactions else False
            freq = getattr(strat, 'rebalance_frequency', 'monthly')
            if freq == "quarterly":
                is_strat_rebalance = is_rebalance_day and current_month[5:7] in ("01", "04", "07", "10")
            elif freq == "biweekly":
                day_of_month = int(date_str[8:10])
                current_half = date_str[:7] + ("A" if day_of_month <= 14 else "B")
                if not hasattr(strat, '_last_rebalance_half'):
                    strat._last_rebalance_half = None
                is_strat_rebalance = (current_half != strat._last_rebalance_half)
                if is_strat_rebalance:
                    strat._last_rebalance_half = current_half
            else:
                is_strat_rebalance = is_rebalance_day

            if is_strat_rebalance and not sold_today_in_rebalance:
                saved_regime = strat._last_regime
                scores = strat.score_stocks(UNIVERSE, price_data, date_str,
                                            signal_engine=signal_engine)
                strat._last_regime = saved_regime

                adjusted = []
                for ticker, score in scores:
                    mem_adj = strat._read_memory_for_scoring(ticker, regime)
                    adjusted.append((ticker, score + mem_adj))
                adjusted.sort(key=lambda x: x[1], reverse=True)

                size_multipliers = {}
                qualified = [(t, s) for t, s in adjusted if s >= strat.min_score_threshold]
                for ticker, score in qualified[:strat.max_positions]:
                    tech = signal_engine.compute_technical(ticker, date_str)
                    cache_key = (ticker, date_str)
                    if cache_key not in _detect_cache:
                        _detect_cache[cache_key] = risk_overlay.detect_raw(ticker, tech, macro)
                    raw_signals, raw_conflicts = _detect_cache[cache_key]
                    conv, conf = risk_overlay.judge_for_strategy(
                        ticker, raw_signals, raw_conflicts, strat,
                    )
                    size_multipliers[ticker] = risk_overlay.compute_final_size_multiplier(conv, conf)

                strat._risk_size_multipliers = size_multipliers
                consensus_active = (
                    hasattr(risk_overlay, 'consensus_signal')
                    and risk_overlay.consensus_signal
                    and risk_overlay.consensus_signal._active
                )
                floor = risk_overlay.get_cash_floor(
                    strat.get_portfolio_value(price_data, date_str),
                    regime, consensus_active,
                )
                strat._cash_floor_amount = floor["floor_amount"]

                strat.execute_rebalance(adjusted, price_data, date_str)

                if hasattr(strat, '_risk_size_multipliers'):
                    del strat._risk_size_multipliers
                if hasattr(strat, '_cash_floor_amount'):
                    del strat._cash_floor_amount

            strat.snapshot(price_data, date_str)

        # Update trigger engine to today's values (for tomorrow's change detection)
        trigger_engine._last_regime = regime
        trigger_engine._last_news_risk = news.get("geo_risk", 0)

    # Finalize
    for strat in strategies:
        strat.finalize_memory()

    # Compute benchmarks (SPY buy-and-hold)
    benchmarks = {}
    for bm in BENCHMARKS:
        if bm in price_data:
            df = price_data[bm]
            mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
            bench = df.loc[mask]
            if not bench.empty:
                entry = float(bench["Close"].iloc[0])
                shares = int(initial_cash / entry)
                cash_left = initial_cash - shares * entry
                final = float(bench["Close"].iloc[-1])
                fv = shares * final + cash_left
                benchmarks[bm] = {
                    "final_value": round(fv, 2),
                    "total_return_pct": round((fv - initial_cash) / initial_cash * 100, 2),
                }

    # Collect per-strategy results
    results = {}
    spy_ret = benchmarks.get("SPY", {}).get("total_return_pct", 0)
    for strat in strategies:
        history = strat.portfolio_history
        if not history:
            continue
        fv = history[-1]["total_value"]
        tr = (fv - initial_cash) / initial_cash * 100
        values = pd.Series([h["total_value"] for h in history])
        dr = values.pct_change().dropna()
        sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if len(dr) > 1 and dr.std() > 0 else 0
        peak = values.cummax()
        dd = (values - peak) / peak * 100
        max_dd = float(dd.min())
        sells = [t for t in strat.transactions if t["action"] == "SELL"]
        wins = sum(1 for t in sells if t.get("pnl", 0) > 0)

        results[strat.name] = {
            "final_value": round(fv, 2),
            "total_return_pct": round(tr, 2),
            "alpha_vs_spy": round(tr - spy_ret, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": len(strat.transactions),
            "win_rate_pct": round(wins / len(sells) * 100, 1) if sells else 0,
        }

    return results, benchmarks


def run_portfolio_test(period_keys: list = None, seed: int = 42,
                        initial_cash: float = 100_000, max_positions: int = 10):
    """Run the full portfolio management test across multiple periods."""
    if period_keys is None:
        period_keys = list(PERIODS.keys())

    print("=" * 90)
    print("PORTFOLIO MANAGEMENT TEST")
    print("Strategies inherit a random portfolio and must manage it.")
    print(f"Seed: {seed} | Cash: ${initial_cash:,.0f} | Max positions: {max_positions}")
    print(f"Periods: {len(period_keys)}")
    print("=" * 90)

    # Build events calendar once
    print("\nBuilding shared events calendar...")
    events_cal = build_events_calendar(UNIVERSE, cache=True)
    print(f"Calendar: {len(events_cal)} tickers")

    all_results = []
    start_time = time.time()

    for i, period_key in enumerate(period_keys):
        if period_key not in PERIODS:
            print(f"  WARNING: Unknown period '{period_key}', skipping")
            continue
        p = PERIODS[period_key]

        elapsed = time.time() - start_time
        est_remaining = (elapsed / (i + 1) * (len(period_keys) - i - 1)) if i > 0 else 0

        print(f"\n{'#' * 90}")
        print(f"# PERIOD {i + 1}/{len(period_keys)}: {p['name']} ({p['start']} to {p['end']})")
        if est_remaining > 0:
            print(f"# Estimated remaining: {est_remaining / 60:.1f} min")
        print(f"{'#' * 90}")

        # Download data once per period
        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        print(f"  Downloading data for {len(all_tickers)} tickers...")
        price_data = download_data(all_tickers, p["start"], p["end"])
        print(f"  Got data for {len(price_data)} tickers")

        # Generate random portfolio for this period (same seed per period for reproducibility)
        # Use seed + period index so each period gets a different but reproducible portfolio
        period_seed = seed + hash(period_key) % 10000
        try:
            portfolio = generate_random_portfolio(
                price_data, p["start"], period_seed, initial_cash,
            )
        except ValueError as e:
            print(f"  ERROR generating portfolio: {e}")
            continue

        print(f"  Random portfolio (seed={period_seed}): {portfolio['portfolio_desc']}")
        print(f"  Stock value: ${portfolio['stock_value']:,.0f} | "
              f"Cash: ${portfolio['cash']:,.0f} | "
              f"Stocks: {len(portfolio['positions'])}")

        # Compute hold baseline
        hold_final = compute_hold_baseline(portfolio, price_data, p["end"])
        hold_return = (hold_final - initial_cash) / initial_cash * 100
        print(f"  Hold baseline: ${hold_final:,.0f} ({hold_return:+.1f}%)")

        # Run all strategies
        print(f"  Running 9 strategies...", flush=True)
        try:
            results, benchmarks = run_portfolio_test_single(
                period_key, p, portfolio, price_data, events_cal,
                initial_cash, max_positions,
            )
        except Exception as e:
            print(f"  ERROR running simulation: {e}")
            import traceback
            traceback.print_exc()
            continue

        spy_ret = benchmarks.get("SPY", {}).get("total_return_pct", 0)

        # Print results table for this period
        print(f"\n  {'Strategy':<14} {'Final':>12} {'Return':>10} {'vs SPY':>10} "
              f"{'vs Hold':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>7}")
        print(f"  {'-' * 79}")

        for name, data in sorted(results.items(), key=lambda x: -x[1]["total_return_pct"]):
            vs_hold = data["total_return_pct"] - hold_return
            print(f"  {name:<14} ${data['final_value']:>10,.0f} {data['total_return_pct']:>9.1f}% "
                  f"{data['alpha_vs_spy']:>9.1f}% {vs_hold:>9.1f}% "
                  f"{data['sharpe_ratio']:>8.3f} {data['max_drawdown_pct']:>7.1f}% "
                  f"{data['total_trades']:>7}")

        print(f"  {'-' * 79}")
        print(f"  {'Hold (base)':<14} ${hold_final:>10,.0f} {hold_return:>9.1f}%")
        print(f"  {'SPY (B&H)':<14} ${benchmarks.get('SPY', {}).get('final_value', 0):>10,.0f} "
              f"{spy_ret:>9.1f}%")

        # Collect results for master output
        for strat_name, strat_data in results.items():
            all_results.append({
                "period": period_key,
                "period_name": p["name"],
                "start": p["start"],
                "end": p["end"],
                "seed": period_seed,
                "starting_portfolio": portfolio["portfolio_desc"],
                "starting_tickers": portfolio["tickers"],
                "starting_stock_value": round(portfolio["stock_value"], 2),
                "starting_cash": round(portfolio["cash"], 2),
                "strategy": strat_name,
                "final_value": strat_data["final_value"],
                "return_pct": strat_data["total_return_pct"],
                "alpha_vs_spy": strat_data["alpha_vs_spy"],
                "vs_hold_pct": round(strat_data["total_return_pct"] - hold_return, 2),
                "sharpe": strat_data["sharpe_ratio"],
                "max_drawdown": strat_data["max_drawdown_pct"],
                "win_rate": strat_data["win_rate_pct"],
                "trades": strat_data["total_trades"],
                "hold_baseline_value": round(hold_final, 2),
                "hold_baseline_return": round(hold_return, 2),
                "spy_return": spy_ret,
            })

    # Save all results
    os.makedirs(RUNS_DIR, exist_ok=True)
    results_path = os.path.join(RUNS_DIR, "portfolio_test_results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    # Print grand summary
    print_grand_summary(all_results)

    total_time = time.time() - start_time
    print(f"\nTotal time: {total_time / 60:.1f} minutes for {len(period_keys)} periods")


def print_grand_summary(all_results):
    """Print summary tables across all periods."""
    if not all_results:
        return

    strategies = sorted(set(r["strategy"] for r in all_results))

    # Table 1: Average performance by strategy
    print(f"\n{'=' * 100}")
    print("GRAND SUMMARY: Average Portfolio Management Performance")
    print(f"{'=' * 100}")
    print(f"{'Strategy':<14} {'Avg Return':>12} {'Avg Alpha':>12} {'Avg vs Hold':>12} "
          f"{'Avg Sharpe':>12} {'Avg MaxDD':>12} {'Beat Hold':>10}")
    print("-" * 84)

    for s in strategies:
        s_results = [r for r in all_results if r["strategy"] == s]
        if not s_results:
            continue
        avg_ret = np.mean([r["return_pct"] for r in s_results])
        avg_alpha = np.mean([r["alpha_vs_spy"] for r in s_results])
        avg_vs_hold = np.mean([r["vs_hold_pct"] for r in s_results])
        avg_sharpe = np.mean([r["sharpe"] for r in s_results])
        avg_dd = np.mean([r["max_drawdown"] for r in s_results])
        beat_hold = sum(1 for r in s_results if r["vs_hold_pct"] > 0)
        beat_pct = beat_hold / len(s_results) * 100

        print(f"{s:<14} {avg_ret:>11.1f}% {avg_alpha:>11.1f}% {avg_vs_hold:>11.1f}% "
              f"{avg_sharpe:>12.3f} {avg_dd:>11.1f}% {beat_pct:>9.0f}%")

    # Table 2: Hold baseline summary
    print(f"\n{'=' * 100}")
    print("HOLD BASELINE vs ACTIVE MANAGEMENT")
    print("(Positive 'vs Hold' means the strategy beat doing nothing)")
    print(f"{'=' * 100}")

    periods_seen = sorted(set(r["period"] for r in all_results),
                          key=lambda pk: all_results[[r["period"] for r in all_results].index(pk)]["start"]
                          if pk in [r["period"] for r in all_results] else "")

    for pk in periods_seen:
        p_results = [r for r in all_results if r["period"] == pk]
        if not p_results:
            continue
        pname = p_results[0]["period_name"]
        hold_ret = p_results[0]["hold_baseline_return"]

        best = max(p_results, key=lambda r: r["vs_hold_pct"])
        worst = min(p_results, key=lambda r: r["vs_hold_pct"])
        beat_count = sum(1 for r in p_results if r["vs_hold_pct"] > 0)

        print(f"  {pname:<30} Hold: {hold_ret:>6.1f}% | "
              f"Best: {best['strategy']:<12} ({best['vs_hold_pct']:>+6.1f}%) | "
              f"Worst: {worst['strategy']:<12} ({worst['vs_hold_pct']:>+6.1f}%) | "
              f"{beat_count}/{len(p_results)} beat hold")

    # Table 3: Which strategy most consistently beat the hold baseline?
    print(f"\n{'=' * 100}")
    print("CONSISTENCY RANKING: Who most reliably improves an inherited portfolio?")
    print(f"{'=' * 100}")

    strat_scores = []
    for s in strategies:
        s_results = [r for r in all_results if r["strategy"] == s]
        if not s_results:
            continue
        beat_hold = sum(1 for r in s_results if r["vs_hold_pct"] > 0)
        beat_rate = beat_hold / len(s_results) * 100
        avg_vs_hold = np.mean([r["vs_hold_pct"] for r in s_results])
        avg_sharpe = np.mean([r["sharpe"] for r in s_results])
        strat_scores.append((s, beat_rate, avg_vs_hold, avg_sharpe, len(s_results)))

    strat_scores.sort(key=lambda x: (-x[1], -x[2]))
    for rank, (name, beat_rate, avg_vs_hold, avg_sharpe, n) in enumerate(strat_scores, 1):
        print(f"  #{rank} {name:<14} Beat hold {beat_rate:>5.0f}% of the time | "
              f"Avg improvement: {avg_vs_hold:>+6.1f}% | Sharpe: {avg_sharpe:>.3f} | "
              f"({n} periods)")


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio management test: strategies inherit random portfolios",
    )
    parser.add_argument(
        "--period", choices=list(PERIODS.keys()),
        help="Run a single period (default: all 14)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for portfolio generation (default: 42)",
    )
    parser.add_argument(
        "--max-positions", type=int, default=10,
        help="Max positions per strategy (default: 10)",
    )
    parser.add_argument(
        "--cash", type=float, default=100_000,
        help="Initial portfolio value (default: 100000)",
    )
    args = parser.parse_args()

    period_keys = [args.period] if args.period else None
    run_portfolio_test(
        period_keys=period_keys,
        seed=args.seed,
        initial_cash=args.cash,
        max_positions=args.max_positions,
    )


if __name__ == "__main__":
    main()

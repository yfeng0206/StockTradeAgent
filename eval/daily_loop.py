"""Daily event-driven simulation engine.

Replaces the old monthly-rebalance loop with a realistic daily workflow:
- Every day: scan for triggers, only act when something happens
- Monthly: full portfolio rebalance
- Between: targeted trades on earnings, news, price alerts

Usage:
    python eval/daily_loop.py --period recession --max-positions 10
    python eval/daily_loop.py --period 2025_to_now --max-positions 10
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from signals import SignalEngine
from triggers import TriggerEngine, TriggerEvent
from sim_memory import SimulationMemory
from events_data import build_events_calendar
from risk_overlay import RiskOverlay, DEFAULT_FEATURES, DEFAULT_PARAMS
from strategies import (ValueStrategy, MomentumStrategy, BalancedStrategy,
                        DefensiveStrategy, EventDrivenStrategy, AdaptiveStrategy,
                        CommodityStrategy, MixStrategy, MixLLMStrategy)

LOOP_DIR = os.path.dirname(__file__)
RUNS_DIR = os.path.join(os.path.dirname(LOOP_DIR), "runs")
NEWS_DIR = os.path.join(os.path.dirname(LOOP_DIR), "data", "news")

PERIODS = {
    # Historical periods (2000-2018)
    "dotcom_crash":      {"start": "2000-03-01", "end": "2002-10-31", "name": "Dot-com Crash"},
    "post_dotcom":       {"start": "2003-01-02", "end": "2004-12-31", "name": "Post Dot-com Recovery"},
    "housing_bull":      {"start": "2005-01-03", "end": "2007-06-29", "name": "Housing Bull"},
    "gfc":               {"start": "2007-07-02", "end": "2009-03-31", "name": "Great Financial Crisis"},
    "post_gfc":          {"start": "2009-03-01", "end": "2011-12-30", "name": "Post GFC Recovery"},
    "qe_bull":           {"start": "2012-01-03", "end": "2015-12-31", "name": "QE Bull"},
    "pre_covid":         {"start": "2016-01-04", "end": "2018-12-31", "name": "Pre-COVID"},
    # Recent periods (2019-2026)
    "normal":            {"start": "2019-01-02", "end": "2019-12-31", "name": "2019 Steady Bull"},
    "black_swan":        {"start": "2020-01-02", "end": "2020-06-30", "name": "COVID Crash"},
    "recession":         {"start": "2022-01-03", "end": "2022-10-31", "name": "2022 Bear Market"},
    "bull":              {"start": "2023-01-02", "end": "2023-12-29", "name": "2023 AI Rally"},
    "bull_to_recession": {"start": "2021-07-01", "end": "2022-06-30", "name": "Bull to Recession"},
    "recession_to_bull": {"start": "2022-10-01", "end": "2023-06-30", "name": "Recession to Bull"},
    "2025_to_now":       {"start": "2025-01-02", "end": datetime.now().strftime("%Y-%m-%d"), "name": "2025 to Now"},
}

UNIVERSE = [
    # Tech mega-cap (12)
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "CRM", "NFLX", "AMD", "ADBE", "INTC",
    # Semiconductors (9) — was missing most of the chip sector
    "AVGO", "QCOM", "TXN", "MU", "LRCX", "AMAT", "KLAC", "MRVL", "ON",
    # Software/Cloud/Cybersecurity (5)
    "NOW", "PANW", "ZS", "CRWD", "DDOG",
    # Internet/E-commerce/Fintech (7) — high-growth names we were missing
    "SHOP", "UBER", "ABNB", "DASH", "PYPL", "COIN", "PLTR",
    # Finance (8)
    "JPM", "V", "MA", "GS", "BAC", "WFC", "MS", "AXP",
    # Healthcare/Biotech (10)
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "AMGN", "REGN", "VRTX",
    # Pharma/Med devices (3)
    "ABT", "ISRG", "MRNA",
    # Consumer staples (6)
    "PG", "KO", "PEP", "COST", "WMT", "SBUX",
    # Consumer discretionary (7)
    "HD", "MCD", "NKE", "LULU", "TGT", "ROKU", "SPOT",
    # Energy (5) — was only 2, now 5
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Industrials/Defense (8)
    "CAT", "BA", "HON", "UPS", "DE", "LMT", "RTX", "GE",
    # Telecom/Media (4)
    "DIS", "CMCSA", "TMUS", "CHTR",
    # Utilities (2)
    "NEE", "SO",
    # Real Estate (3)
    "AMT", "PLD", "D",
    # Other (4)
    "BLK", "FIS", "EMR", "MMM",
    # Index ETFs (tradeable alongside individual stocks)
    "SPY", "QQQ",
]

BENCHMARKS = ["SPY", "QQQ", "ONEQ"]  # S&P 500, NASDAQ-100, NASDAQ Composite
MACRO_ETFS = ["USO", "XLE", "GLD", "TLT", "HYG", "LQD"]  # oil, gold, bonds, credit


PRICE_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prices")


def _load_cached_price(ticker):
    """Load price data from local CSV cache. Returns (df, last_date) or (None, None)."""
    cache_path = os.path.join(PRICE_CACHE_DIR, f"{ticker}.csv")
    if not os.path.exists(cache_path):
        return None, None
    try:
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if df.empty:
            return None, None
        return df, df.index.max().strftime("%Y-%m-%d")
    except Exception:
        return None, None


def _save_cached_price(ticker, df):
    """Save price data to local CSV cache. Uses atomic write to avoid corruption."""
    os.makedirs(PRICE_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(PRICE_CACHE_DIR, f"{ticker}.csv")
    tmp_path = cache_path + ".tmp"
    try:
        df.to_csv(tmp_path)
        os.replace(tmp_path, cache_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _yf_download_batch(tickers, start, end):
    """Download from yfinance and return {ticker: DataFrame}."""
    result = {}
    try:
        raw = yf.download(tickers, start=start, end=end, progress=True, threads=True)
        if raw.empty:
            return result
        if len(tickers) == 1:
            if not raw.empty:
                result[tickers[0]] = raw
        else:
            for ticker in tickers:
                try:
                    ticker_df = pd.DataFrame({
                        "Open": raw["Open"][ticker], "High": raw["High"][ticker],
                        "Low": raw["Low"][ticker], "Close": raw["Close"][ticker],
                        "Volume": raw["Volume"][ticker],
                    }).dropna()
                    if not ticker_df.empty:
                        result[ticker] = ticker_df
                except (KeyError, TypeError):
                    continue
    except Exception:
        # Fallback: one-by-one download
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                df = t.history(start=start, end=end)
                if not df.empty:
                    result[ticker] = df
            except Exception:
                continue
    return result


def download_data(tickers, start, end, refresh=False):
    """Download OHLCV data for tickers. Cache-first, incremental updates.

    Logic (same as news — download once, never re-download):
      1. Load from local cache (data/prices/{ticker}.csv)
      2. If cache covers the date range -> done, no download
      3. If cache exists but is stale -> download ONLY the gap, merge, save
      4. If no cache at all -> full download, save
      5. Never re-downloads data that's already cached
    """
    buffer_start = (pd.Timestamp(start) - timedelta(days=400)).strftime("%Y-%m-%d")
    end_ts = pd.Timestamp(end)
    all_data = {}

    need_full_download = []  # no cache at all
    need_incremental = []    # cache exists but missing recent days

    # Phase 1: Load from cache, classify what's missing
    for ticker in tickers:
        if refresh:
            need_full_download.append(ticker)
            continue

        cached_df, cached_end = _load_cached_price(ticker)
        if cached_df is None:
            need_full_download.append(ticker)
            continue

        # Cache exists — check if it covers both start and end
        covers_start = cached_df.index.min() <= pd.Timestamp(buffer_start) + timedelta(days=5)
        covers_end = pd.Timestamp(cached_end) >= end_ts - timedelta(days=5)
        if not covers_start:
            # Cache doesn't go back far enough — need full download
            need_full_download.append(ticker)
            continue
        if covers_end:
            # Fresh enough — use as-is
            mask = cached_df.index >= pd.Timestamp(buffer_start)
            all_data[ticker] = cached_df.loc[mask] if mask.any() else cached_df
        else:
            # Stale — need incremental update (download only the gap)
            all_data[ticker] = cached_df  # use what we have for now
            need_incremental.append((ticker, cached_end))

    # Phase 2: Incremental updates (download only missing days, merge with cache)
    if need_incremental:
        # Start download from 3 days before the oldest gap (overlap handles weekends)
        gap_dates = [d for _, d in need_incremental]
        gap_start = (pd.Timestamp(min(gap_dates)) - timedelta(days=3)).strftime("%Y-%m-%d")
        gap_tickers = [t for t, _ in need_incremental]

        new_data = _yf_download_batch(gap_tickers, gap_start, end)
        for ticker in gap_tickers:
            if ticker in new_data and not new_data[ticker].empty:
                # Merge with existing cache
                existing = all_data[ticker]
                merged = pd.concat([existing, new_data[ticker]])
                merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                _save_cached_price(ticker, merged)
                mask = merged.index >= pd.Timestamp(buffer_start)
                all_data[ticker] = merged.loc[mask] if mask.any() else merged

    # Phase 3: Full download for tickers with no cache
    if need_full_download:
        new_data = _yf_download_batch(need_full_download, buffer_start, end)
        for ticker, df in new_data.items():
            all_data[ticker] = df
            _save_cached_price(ticker, df)

    return all_data


def save_strategies_state(strategies, last_date: str) -> dict:
    """Serialize all strategy states for live trading persistence."""
    state = {"last_date": last_date, "saved_at": datetime.now().isoformat(), "strategies": {}}
    for s in strategies:
        ss = {
            "class": type(s).__name__,
            "cash": s.cash,
            "positions": s.positions,
            "transactions": s.transactions,
            "portfolio_history": s.portfolio_history,
            "memory": s.memory,
            "reasoning_log": s.reasoning_log[-100:],
            "watchnotes": s.watchnotes,
            "pending_checks": s.pending_checks,
            "_last_regime": s._last_regime,
            "_last_news_summary": s._last_news_summary,
            "_sold_cooldown": getattr(s, "_sold_cooldown", {}),
        }
        # Mix/MixLLM regime state
        if hasattr(s, "detected_regime"):
            ss["detected_regime"] = s.detected_regime
            ss["regime_history"] = s.regime_history
            ss["_sensor_readings"] = s._sensor_readings
            ss["_pending_regime"] = s._pending_regime
            ss["_pending_count"] = s._pending_count
        # MixLLM LLM call state
        if hasattr(s, "_llm_log"):
            ss["_llm_log"] = getattr(s, "_llm_log", [])
            ss["_llm_call_count"] = getattr(s, "_llm_call_count", 0)
            ss["_llm_fallback_count"] = getattr(s, "_llm_fallback_count", 0)
        state["strategies"][s.name] = ss
    return state


def _restore_strategies(strategies, state: dict):
    """Restore strategy states from a saved checkpoint."""
    saved = state.get("strategies", {})
    for s in strategies:
        if s.name not in saved:
            continue
        ss = saved[s.name]
        s.cash = ss["cash"]
        s.positions = ss["positions"]
        s.transactions = ss.get("transactions", [])
        s.portfolio_history = ss.get("portfolio_history", [])
        s.memory = ss.get("memory", s.memory)
        s.reasoning_log = ss.get("reasoning_log", [])
        s.watchnotes = ss.get("watchnotes", {})
        s.pending_checks = ss.get("pending_checks", [])
        s._last_regime = ss.get("_last_regime")
        s._last_news_summary = ss.get("_last_news_summary")
        s._sold_cooldown = ss.get("_sold_cooldown", {})
        if hasattr(s, "detected_regime"):
            s.detected_regime = ss.get("detected_regime", "UNCERTAIN")
            s.regime_history = ss.get("regime_history", [])
            s._sensor_readings = ss.get("_sensor_readings", {})
            s._pending_regime = ss.get("_pending_regime")
            s._pending_count = ss.get("_pending_count", 0)
        if hasattr(s, "_llm_log"):
            s._llm_log = ss.get("_llm_log", [])
            s._llm_call_count = ss.get("_llm_call_count", 0)
            s._llm_fallback_count = ss.get("_llm_fallback_count", 0)


def run_daily_simulation(start: str, end: str, initial_cash: float = 100_000,
                         max_positions: int = 10, period_name: str = "custom",
                         shared_price_data: dict = None, shared_events_cal: dict = None,
                         quiet: bool = False,
                         risk_features: dict = None, risk_params: dict = None,
                         regime_stickiness: int = 1,
                         realistic: bool = True, slippage: float = 0.0005,
                         exec_model: str = "open", frequency: str = None,
                         chandelier: bool = False, cooldown: bool = False,
                         breadth: bool = False, mixllm_class=None,
                         resume_state: dict = None, live_mode: bool = False):
    if not quiet:
        print("=" * 80)
        print(f"DAILY EVENT-DRIVEN SIMULATION")
        print(f"Period: {period_name} ({start} to {end})")
        print(f"Cash: ${initial_cash:,.0f} | Max positions: {max_positions}")
        print("=" * 80)

    # Use shared data if provided (sweep mode), otherwise download
    if shared_price_data is not None:
        price_data = shared_price_data
    else:
        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        if not quiet:
            print(f"\nDownloading data for {len(all_tickers)} tickers...")
        price_data = download_data(all_tickers, start, end)
        if not quiet:
            print(f"Got data for {len(price_data)} tickers")

    if shared_events_cal is not None:  # explicit None check — {} is a valid empty calendar
        events_cal = shared_events_cal
    else:
        if not quiet:
            print("Building events calendar...")
        events_cal = build_events_calendar(UNIVERSE, cache=True)

    # Initialize DataLoader (unified data access for both sim and real-time)
    sys.path.insert(0, os.path.join(os.path.dirname(LOOP_DIR), "tools"))
    from data_loader import DataLoader
    data_loader = DataLoader(live_mode=False)  # simulation = read-only from cached files

    # Initialize engines with DataLoader
    signal_engine = SignalEngine(price_data, events_cal, NEWS_DIR, data_loader=data_loader,
                                realistic=realistic, exec_model=exec_model)
    trigger_engine = TriggerEngine(signal_engine)

    # Initialize strategies (7 core + Mix)
    # Mix runs AFTER the other 7 — it reads their live state as sensors
    core_strategies = [
        ValueStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        MomentumStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        BalancedStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        DefensiveStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        EventDrivenStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        AdaptiveStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions),
        CommodityStrategy(initial_cash, events_calendar=events_cal),
    ]
    mix_strategy = MixStrategy(initial_cash, events_calendar=events_cal, max_positions=max_positions,
                               regime_stickiness=regime_stickiness)
    mix_strategy._peer_strategies = core_strategies  # wire up peer references
    # Use custom MixLLM class if provided (for ablation testing V1/V2/V3)
    llm_cls = mixllm_class or MixLLMStrategy
    mix_llm_strategy = llm_cls(initial_cash, events_calendar=events_cal, max_positions=max_positions,
                               regime_stickiness=regime_stickiness)
    mix_llm_strategy._peer_strategies = core_strategies  # same peer references
    strategies = core_strategies + [mix_strategy, mix_llm_strategy]

    # Apply realistic mode, execution model, and slippage to ALL strategies
    for strat in strategies:
        strat.slippage = slippage
        strat._realistic = realistic
        strat._exec_model = exec_model
        strat.use_cooldown = cooldown

    # Apply improvement flags
    trigger_engine.use_chandelier_stop = chandelier
    mix_strategy.use_breadth_signal = breadth
    mix_llm_strategy.use_breadth_signal = breadth

    # Override rebalance frequency if specified
    if frequency:
        for strat in strategies:
            strat._frequency_override = frequency

    # Restore strategy state from checkpoint (live trading mode)
    if resume_state:
        _restore_strategies(strategies, resume_state)
        if not quiet:
            print(f"  Restored state from {resume_state.get('last_date', '?')}")

    # Initialize risk overlay
    risk_overlay = RiskOverlay(features=risk_features, params=risk_params)

    # Daily stats tracking
    daily_trigger_log = []
    regime_log = []  # shared market-level log
    # Use CustomBusinessDay with NYSE holidays to avoid trading on closed days
    _nyse_holidays = [
        # Fixed holidays (approximate — covers the major ones)
        "2000-01-17", "2001-01-15", "2002-01-21", "2003-01-20", "2004-01-19",
        "2005-01-17", "2006-01-16", "2007-01-15", "2008-01-21", "2009-01-19",
        "2010-01-18", "2011-01-17", "2012-01-16", "2013-01-21", "2014-01-20",
        "2015-01-19", "2016-01-18", "2017-01-16", "2018-01-15", "2019-01-21",
        "2020-01-20", "2021-01-18", "2022-01-17", "2023-01-16", "2024-01-15",
        "2025-01-20", "2026-01-19",  # MLK Day
    ]
    # Use price data as ground truth: only trade on days we have price data
    # This naturally excludes holidays (yfinance has no data for closed days)
    if "SPY" in price_data and not price_data["SPY"].empty:
        spy_dates = set(price_data["SPY"].index.strftime("%Y-%m-%d"))
        trading_days = pd.date_range(start=start, end=end, freq="B")
        trading_days = trading_days[trading_days.strftime("%Y-%m-%d").isin(spy_dates)]
    else:
        trading_days = pd.date_range(start=start, end=end, freq="B")
    total_trigger_days = 0
    last_rebalance_month = None

    if not quiet:
        print(f"\nSimulating {len(trading_days)} trading days with event-driven triggers...")
    milestone = max(1, len(trading_days) // 10)

    for i, day in enumerate(trading_days):
        date_str = day.strftime("%Y-%m-%d")
        current_month = date_str[:7]
        is_rebalance_day = (current_month != last_rebalance_month)
        if is_rebalance_day:
            last_rebalance_month = current_month

        # === PHASE 1: MORNING ANALYSIS ===
        _detect_cache = {}  # Reset per-day cache for shared signal detection
        macro = signal_engine.compute_macro(date_str)
        regime = macro.get("regime", "normal")
        news = macro.get("news", {})
        day_had_triggers = False

        # Log regime for shared output
        regime_log.append({
            "date": date_str, "regime": regime,
            "geo_risk": news.get("geo_risk", 0),
            "vol_20d": (macro.get("volatility") or {}).get("vol_20d"),
        })

        # Cross-strategy consensus: compute once per rebalance day, before any strategy acts
        if is_rebalance_day:
            risk_overlay.update_consensus(strategies, price_data, date_str)

        # Snapshot trigger engine state so ALL strategies see the same triggers
        # Bug fix: without this, only the first strategy sees REGIME_CHANGE/NEWS_SPIKE
        # because the engine updates _last_regime/_last_news_risk after scanning.
        _saved_trigger_regime = trigger_engine._last_regime
        _saved_trigger_news = trigger_engine._last_news_risk

        for strat in strategies:
            # Restore state so each strategy sees the same day's triggers
            trigger_engine._last_regime = _saved_trigger_regime
            trigger_engine._last_news_risk = _saved_trigger_news
            # Use strategy-specific ATR multiplier for stops
            trigger_engine.atr_stop_multiplier = getattr(strat, 'atr_stop_multiplier', 2.0)
            triggers = trigger_engine.scan(UNIVERSE, strat.positions, date_str, price_data,
                                           precomputed_macro=macro)

            # Watchnotes are checked inside execute_rebalance() only
            # Bug fix: was calling _check_watchnotes twice (here AND in execute_rebalance),
            # first call consumed fired notes so second call saw stale data

            strat._last_regime = regime
            strat._last_news_summary = f"geo_risk={news.get('geo_risk', 0):.2f}" if news.get('geo_risk', 0) > 0 else None

            insight = SimulationMemory.generate_insight(
                date_str, strat.positions, strat.memory, regime, news
            )

            if triggers:
                day_had_triggers = True

                # Log triggers
                for t in triggers:
                    daily_trigger_log.append({
                        "date": date_str, "strategy": strat.name,
                        "trigger": t.type, "ticker": t.ticker,
                        "severity": t.severity, "action": t.suggested_action,
                    })

                # === PHASE 2: REACT TO ALL TRIGGERS ===
                def _get_price(tkr):
                    """Get execution price using the strategy's configured model."""
                    return strat._get_exec_price(price_data, tkr, date_str)

                # Track what was sold today — never buy back same day
                sold_today = set()

                for t in triggers:
                    # --- STOP LOSS (CRITICAL) → Force sell ---
                    if t.type == "STOP_LOSS" and t.ticker in strat.positions:
                        price = _get_price(t.ticker)
                        if price:
                            record = SimulationMemory.read_ticker_record(t.ticker, strat.memory)
                            reason = f"STOP LOSS triggered ({t.data.get('pnl_pct', '?')}% loss)"
                            if record.get("warning") == "repeated_loser":
                                reason += f" [MEMORY: repeated loser, {record['trades']} trades avg {record['avg_pnl']:+.1f}%]"
                            strat._sell(t.ticker, price, date_str, reason)
                            sold_today.add(t.ticker)

                    # --- REGIME CHANGE → Strategy-specific reaction ---
                    elif t.type == "REGIME_CHANGE":
                        new_regime = t.data.get("to", "normal")
                        old_regime = t.data.get("from", "normal")
                        entering_danger = new_regime in ("crisis", "high_volatility") and old_regime not in ("crisis", "high_volatility")
                        leaving_danger = old_regime in ("crisis", "high_volatility") and new_regime not in ("crisis", "high_volatility")

                        strat._log_reasoning(date_str, "REGIME", "", 0,
                            f"Regime changed: {old_regime} -> {new_regime}. {insight}")

                        # ENTERING DANGER → sell based on strategy personality
                        if entering_danger and strat.positions:
                            pos_pnl = []
                            for tkr, pos in strat.positions.items():
                                p = _get_price(tkr)
                                if p:
                                    pnl = (p - pos["entry_price"]) / pos["entry_price"] * 100
                                    pos_pnl.append((tkr, pnl, p))
                            pos_pnl.sort(key=lambda x: x[1])

                            if strat.name == "Defensive":
                                to_sell = len(pos_pnl)  # sell ALL
                            elif strat.name == "Momentum":
                                to_sell = max(1, len(pos_pnl) // 3)
                            elif strat.name in ("Balanced", "Adaptive", "Mix") or strat.name.startswith("MixLLM"):
                                to_sell = max(1, len(pos_pnl) // 4)
                            elif strat.name == "Value":
                                to_sell = 0  # hold through volatility
                            else:
                                to_sell = max(1, len(pos_pnl) // 5)

                            for tkr, pnl, p in pos_pnl[:to_sell]:
                                strat._sell(tkr, p, date_str,
                                    f"REGIME SHIFT to {new_regime}: {strat.name} selling ({pnl:+.1f}%)")
                                sold_today.add(tkr)

                        # LEAVING DANGER → let monthly rebalance handle re-entry via scoring
                        elif leaving_danger and len(strat.positions) < strat.max_positions // 2:
                            strat._log_reasoning(date_str, "REGIME", "", 0,
                                f"REGIME RECOVERY: {old_regime} -> {new_regime}. Will re-enter via next rebalance scoring.")

                    # --- NEWS SPIKE → Strategy-specific reaction ---
                    elif t.type == "NEWS_SPIKE":
                        direction = t.data.get("direction", "")
                        themes = t.data.get("themes", [])
                        geo_risk = t.data.get("geo_risk", 0)

                        strat._log_reasoning(date_str, "NEWS", "", 0,
                            f"NEWS {direction.upper()}: geo_risk {t.data.get('previous',0):.2f} -> {geo_risk:.2f}. "
                            f"Themes: {', '.join(themes)}")

                        if direction == "escalation" and geo_risk > 0.6:
                            # STRATEGY-SPECIFIC news reactions — NO hardcoded stock names
                            if strat.name == "Defensive":
                                # Defensive: reduce exposure proportional to geo_risk (3-state)
                                # geo_risk 0.6-0.8: sell 50% of positions (highest vol first)
                                # geo_risk >0.8: sell all
                                if strat.positions:
                                    pos_vol = []
                                    for tkr in list(strat.positions.keys()):
                                        tech = signal_engine.compute_technical(tkr, date_str)
                                        vol = tech.get("vol_20d", 0.3)
                                        pos_vol.append((tkr, vol))
                                    pos_vol.sort(key=lambda x: -x[1])  # highest vol first

                                    if geo_risk > 0.8:
                                        to_sell = len(pos_vol)  # sell all
                                    else:
                                        to_sell = max(1, len(pos_vol) // 2)  # sell half

                                    for tkr, vol in pos_vol[:to_sell]:
                                        p = _get_price(tkr)
                                        if p and tkr in strat.positions:
                                            strat._sell(tkr, p, date_str,
                                                f"NEWS: {strat.name} reducing exposure, selling highest-vol {tkr} (vol={vol:.0%}, geo={geo_risk:.2f})")
                                            sold_today.add(tkr)

                            elif strat.name in ("Balanced", "Adaptive"):
                                # Sell highest-volatility positions (data-driven, not hardcoded names)
                                if strat.positions:
                                    pos_vol = []
                                    for tkr in list(strat.positions.keys()):
                                        tech = signal_engine.compute_technical(tkr, date_str)
                                        vol = tech.get("vol_20d", 0.3)
                                        pos_vol.append((tkr, vol))
                                    pos_vol.sort(key=lambda x: -x[1])
                                    # Sell top 1/3 by volatility
                                    to_sell = max(1, len(pos_vol) // 3)
                                    for tkr, vol in pos_vol[:to_sell]:
                                        p = _get_price(tkr)
                                        if p and tkr in strat.positions:
                                            strat._sell(tkr, p, date_str,
                                                f"NEWS: {strat.name} selling high-vol {tkr} (vol={vol:.0%}, geo={geo_risk:.2f})")
                                            sold_today.add(tkr)

                            elif strat.name == "Commodity":
                                if "war/conflict" in themes or "oil/energy" in themes:
                                    strat._log_reasoning(date_str, "NEWS", "", 0,
                                        f"NEWS: Commodity — war/oil bullish signal, holding")

                            elif strat.name == "EventDriven":
                                # EventDriven: sell most exposed, log for tracking
                                strat._log_reasoning(date_str, "NEWS", "", 0,
                                    f"NEWS: EventDriven — geo escalation, reducing exposure")
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
                                        strat._sell(worst, p, date_str,
                                            f"NEWS: EventDriven selling worst ({worst} {worst_pnl:+.1f}%) on geo escalation")
                                        sold_today.add(worst)

                            elif strat.name == "Momentum":
                                pass  # follows price only

                            elif strat.name == "Value":
                                strat._log_reasoning(date_str, "NEWS", "", 0,
                                    f"NEWS: Value — holding through volatility, watching for bargains")

                        elif direction == "de-escalation":
                            # De-escalation: let monthly rebalance handle re-entry via scoring
                            strat._log_reasoning(date_str, "NEWS", "", 0,
                                f"NEWS DE-ESCALATION: geo_risk {geo_risk:.2f}. Will re-enter via next rebalance scoring.")

                    # --- EARNINGS RELEASE → Strategy-specific reaction ---
                    elif t.type == "EARNINGS_RELEASE" and t.severity == "HIGH":
                        ticker = t.ticker
                        signal = t.data.get("signal", "neutral")
                        surprise = t.data.get("surprise_pct", "?")
                        record = SimulationMemory.read_ticker_record(ticker, strat.memory)

                        # Strategy decides: should I act on this earnings?
                        should_buy = False
                        should_sell = False

                        if strat.name == "Momentum":
                            # Only buy strong beats (ride the drift), sell any miss
                            should_buy = signal == "strong_beat" and ticker not in strat.positions
                            should_sell = signal in ("strong_miss", "miss") and ticker in strat.positions

                        elif strat.name == "Value":
                            # Value does NOT trade on earnings triggers at all.
                            # Monthly scoring already handles misses (-1.5 penalty).
                            # No contradiction: misses are penalized, not chased.
                            should_buy = False
                            should_sell = False

                        elif strat.name == "EventDriven":
                            # Core signal: trade any strong earnings event
                            should_buy = signal in ("strong_beat", "beat") and ticker not in strat.positions
                            should_sell = signal in ("strong_miss", "miss") and ticker in strat.positions

                        elif strat.name == "Defensive":
                            # Only buy beats on low-vol stocks in non-danger regimes
                            # BUG FIX: Defensive was buying NFLX earnings beat during bearish
                            # regime and losing 21.8%. Now requires non-danger regime too.
                            is_low_vol = False
                            tech = signal_engine.compute_technical(ticker, date_str)
                            if tech.get("vol_20d", 1) < 0.25:
                                is_low_vol = True
                            safe_regime = regime not in ("crisis", "high_volatility", "bearish")
                            should_buy = signal in ("strong_beat", "beat") and is_low_vol and safe_regime and ticker not in strat.positions
                            should_sell = signal in ("strong_miss",) and ticker in strat.positions

                        elif strat.name in ("Balanced", "Adaptive", "Mix", "MixLLM"):
                            # Moderate: only strong beats, and skip during danger regimes
                            safe_regime = regime not in ("crisis", "high_volatility")
                            should_buy = signal == "strong_beat" and safe_regime and ticker not in strat.positions
                            should_sell = signal == "strong_miss" and ticker in strat.positions

                        else:  # Commodity, default — don't react to individual stock earnings
                            should_buy = False
                            should_sell = signal in ("strong_miss",) and ticker in strat.positions

                        # Memory override: skip repeated losers
                        if should_buy and record.get("warning") == "repeated_loser":
                            strat._log_reasoning(date_str, "SKIP", ticker, 0,
                                f"EARNINGS {signal} on {ticker} but MEMORY: repeated loser — {strat.name} skipping")
                            should_buy = False

                        # Execute buy
                        if should_buy and len(strat.positions) < strat.max_positions:
                            price = _get_price(ticker)
                            if price and strat.cash > price:
                                per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                shares = int(min(per_pos, strat.cash) / price)
                                if shares > 0:
                                    reason = f"EARNINGS {signal}: surprise {surprise}% [{strat.name}]"
                                    mem_note = SimulationMemory.read_regime_wisdom(regime, strat.memory)
                                    if mem_note.get("known"):
                                        reason += f" [Regime {regime}: {mem_note['win_rate']}% win rate]"
                                    if ticker not in sold_today:
                                        strat._buy(ticker, shares, price, date_str, reason,
                                                   price_data=price_data)

                        # Execute sell
                        elif should_sell and ticker in strat.positions:
                            price = _get_price(ticker)
                            if price:
                                pnl = (price - strat.positions[ticker]["entry_price"]) / strat.positions[ticker]["entry_price"] * 100
                                strat._sell(ticker, price, date_str,
                                    f"EARNINGS {signal}: surprise {surprise}% [{strat.name}]")
                                sold_today.add(ticker)

                        # Regular miss (not strong) on held position → watchnote
                        elif signal == "miss" and ticker in strat.positions and strat.name != "Value":
                            strat._log_reasoning(date_str, "WATCH", ticker, 0,
                                f"EARNINGS miss (not strong) on {ticker}: monitoring. Next earnings could confirm weakness.")

                    # --- VOLUME ANOMALY → Only event/momentum strategies react ---
                    elif t.type == "VOLUME_ANOMALY" and t.severity in ("MEDIUM", "HIGH"):
                        # Value, Balanced, Adaptive, Commodity: skip volume triggers
                        # Their alpha comes from scoring, not chasing intraday moves
                        if strat.name in ("Value", "Balanced", "Adaptive", "Commodity"):
                            continue
                        ticker = t.ticker
                        price_move = t.data.get("price_move_pct", 0)
                        vol_ratio = t.data.get("volume_ratio", 1)

                        # Defensive + Value: NEVER chase volume spikes for buys
                        # They only sell on volume crashes for held positions
                        if strat.name in ("Defensive", "Value"):
                            if price_move < -8 and ticker in strat.positions and strat.name == "Defensive":
                                price = _get_price(ticker)
                                if price:
                                    pnl = (price - strat.positions[ticker]["entry_price"]) / strat.positions[ticker]["entry_price"] * 100
                                    strat._sell(ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% on {vol_ratio}x volume — {strat.name} exiting")
                                    sold_today.add(ticker)
                            # Value watches crashes as potential buy later
                            elif price_move < -10 and strat.name == "Value":
                                strat._log_reasoning(date_str, "WATCH", ticker, 0,
                                    f"VOLUME CRASH {price_move:.1f}%: Value watching {ticker} for potential bargain entry")

                        # Momentum + EventDriven: chase positive spikes aggressively
                        elif strat.name in ("Momentum", "EventDriven"):
                            if price_move > 5 and ticker not in strat.positions and len(strat.positions) < strat.max_positions:
                                record = SimulationMemory.read_ticker_record(ticker, strat.memory)
                                if not record.get("warning"):
                                    price = _get_price(ticker)
                                    if price and strat.cash > price:
                                        per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                        shares = int(min(per_pos, strat.cash * 0.5) / price)
                                        if shares > 0:
                                            if ticker not in sold_today:
                                                strat._buy(ticker, shares, price, date_str,
                                                f"VOLUME SPIKE: +{price_move:.1f}% on {vol_ratio}x vol — {strat.name} catalyst play",
                                                price_data=price_data)
                            elif price_move < -8 and ticker in strat.positions:
                                price = _get_price(ticker)
                                if price:
                                    pnl = (price - strat.positions[ticker]["entry_price"]) / strat.positions[ticker]["entry_price"] * 100
                                    strat._sell(ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% — {strat.name} cutting loss")
                                    sold_today.add(ticker)

                        # Balanced + Adaptive: moderate — buy only very large spikes, sell crashes
                        else:
                            if price_move > 8 and ticker not in strat.positions and len(strat.positions) < strat.max_positions:
                                record = SimulationMemory.read_ticker_record(ticker, strat.memory)
                                if not record.get("warning"):
                                    price = _get_price(ticker)
                                    if price and strat.cash > price:
                                        per_pos = strat.cash / max(1, strat.max_positions - len(strat.positions))
                                        shares = int(min(per_pos, strat.cash * 0.3) / price)  # small position
                                        if shares > 0:
                                            if ticker not in sold_today:
                                                strat._buy(ticker, shares, price, date_str,
                                                f"VOLUME SPIKE: +{price_move:.1f}% on {vol_ratio}x vol — {strat.name} cautious entry",
                                                price_data=price_data)
                            elif price_move < -8 and ticker in strat.positions:
                                price = _get_price(ticker)
                                if price:
                                    pnl = (price - strat.positions[ticker]["entry_price"]) / strat.positions[ticker]["entry_price"] * 100
                                    strat._sell(ticker, price, date_str,
                                        f"VOLUME CRASH: {price_move:.1f}% — {strat.name} exiting")
                                    sold_today.add(ticker)

                    # --- PROFIT TARGET → Take partial profits on big winners ---
                    elif t.type == "PROFIT_TARGET" and t.ticker in strat.positions:
                        pnl_pct = t.data.get("pnl_pct", 0)
                        ticker = t.ticker
                        pos = strat.positions[ticker]

                        # Only trim once per threshold: check if already trimmed at this level
                        last_trim_price = pos.get("_last_trim_price", 0)
                        price = _get_price(ticker)
                        trim_thresh = getattr(strat, 'trim_threshold_pct', 40.0)
                        if price and price > last_trim_price * 1.25 and pnl_pct > trim_thresh and pos["shares"] > 2:
                            # Sell 1/3 of position (not half — less aggressive)
                            trim_shares = max(1, pos["shares"] // 3)
                            # Apply slippage: in reality you receive slightly less
                            sell_price = price * (1 - strat.slippage) if strat.slippage > 0 else price
                            proceeds = trim_shares * sell_price
                            pnl = (sell_price - pos["entry_price"]) * trim_shares
                            strat.cash += proceeds
                            strat.positions[ticker]["shares"] -= trim_shares
                            # Mark trim price so we don't re-trim until another +25% from here
                            strat.positions[ticker]["_last_trim_price"] = price
                            strat.transactions.append({
                                "date": date_str, "action": "TRIM",
                                "ticker": ticker, "shares": trim_shares,
                                "price": round(sell_price, 2), "total": round(proceeds, 2),
                                "pnl": round(pnl, 2),
                                "pnl_pct": round(pnl_pct, 2),
                                "cash_after": round(strat.cash, 2),
                            })
                            strat._log_reasoning(date_str, "TRIM", ticker, price,
                                f"PROFIT TARGET: +{pnl_pct:.0f}%, trimming 1/3 ({trim_shares} shares). "
                                f"Holding {strat.positions[ticker]['shares']}. Next trim at +25% from ${price:.0f}.")

            # === REBALANCE (respects per-strategy frequency) ===
            # Bug fix: rebalance_frequency was defined but never used
            # Bug fix: only block rebalance if a SELL happened today (stop-loss, regime sell)
            # Trims and logs should NOT block the monthly rebalance
            sold_today_in_rebalance = any(
                tx["date"] == date_str and tx["action"] == "SELL"
                for tx in strat.transactions
            ) if strat.transactions else False
            freq = getattr(strat, 'rebalance_frequency', 'monthly')
            if freq == "quarterly":
                # Quarterly: only rebalance in Jan, Apr, Jul, Oct
                is_strat_rebalance = is_rebalance_day and current_month[5:7] in ("01", "04", "07", "10")
            elif freq == "biweekly":
                # Biweekly: first trading day of each half-month (1st-14th and 15th-end)
                day_of_month = int(date_str[8:10])
                current_half = date_str[:7] + ("A" if day_of_month <= 14 else "B")
                if not hasattr(strat, '_last_rebalance_half'):
                    strat._last_rebalance_half = None
                is_strat_rebalance = (current_half != strat._last_rebalance_half)
                if is_strat_rebalance:
                    strat._last_rebalance_half = current_half
            elif freq == "weekly":
                # Weekly: rebalance every Monday (or first trading day of week)
                is_strat_rebalance = day.weekday() == 0  # Monday
            else:
                is_strat_rebalance = is_rebalance_day
            # Force rebalance on first day if strategy has no positions (live trading start)
            if not is_strat_rebalance and len(strat.positions) == 0 and i == 0 and live_mode:
                is_strat_rebalance = True
            if is_strat_rebalance and not sold_today_in_rebalance:
                # Full rebalance using strategy's scoring + memory adjustments
                pre_rebal_count = len(strat.transactions)
                # Bug fix: save macro regime before score_stocks (strategies overwrite _last_regime
                # with internal labels like "defensive:NORMAL" which corrupts memory writes)
                saved_regime = strat._last_regime
                scores = strat.score_stocks(UNIVERSE, price_data, date_str,
                                            signal_engine=signal_engine)
                strat._last_regime = saved_regime  # restore macro regime for memory

                # Adjust scores based on memory
                adjusted = []
                for ticker, score in scores:
                    mem_adj = strat._read_memory_for_scoring(ticker, regime)
                    adjusted.append((ticker, score + mem_adj))
                adjusted.sort(key=lambda x: x[1], reverse=True)

                # === RISK OVERLAY: shared detect → per-strategy judge ===
                # Bug fix: cache detect_raw per-ticker per-day (was calling 7x per stock)
                size_multipliers = {}
                qualified = [(t, s) for t, s in adjusted if s >= strat.min_score_threshold]
                for ticker, score in qualified[:strat.max_positions]:
                    tech = signal_engine.compute_technical(ticker, date_str)

                    # SHARED: detect raw signals + conflicts ONCE per ticker per day
                    cache_key = (ticker, date_str)
                    if cache_key not in _detect_cache:
                        _detect_cache[cache_key] = risk_overlay.detect_raw(ticker, tech, macro)
                    raw_signals, raw_conflicts = _detect_cache[cache_key]

                    # PER-STRATEGY: this judge interprets through its own lens
                    conv, conf = risk_overlay.judge_for_strategy(
                        ticker, raw_signals, raw_conflicts, strat)

                    # Combined size multiplier
                    size_multipliers[ticker] = risk_overlay.compute_final_size_multiplier(conv, conf)

                # Attach size multipliers and cash floor to strategy for execute_rebalance
                strat._risk_size_multipliers = size_multipliers

                # Cash floor: dynamic minimum cash reserve
                consensus_active = hasattr(risk_overlay, 'consensus_signal') and \
                    risk_overlay.consensus_signal and risk_overlay.consensus_signal._active
                floor = risk_overlay.get_cash_floor(
                    strat.get_portfolio_value(price_data, date_str),
                    regime, consensus_active)
                strat._cash_floor_amount = floor["floor_amount"]

                strat.execute_rebalance(adjusted, price_data, date_str)
                # Memory writes happen inside _sell() automatically

                # Clean up temporary attributes
                if hasattr(strat, '_risk_size_multipliers'):
                    del strat._risk_size_multipliers
                if hasattr(strat, '_cash_floor_amount'):
                    del strat._cash_floor_amount

            # === CLOSE: Record snapshot ===
            strat.snapshot(price_data, date_str)

        # Update trigger engine to today's actual values (for tomorrow's change detection)
        trigger_engine._last_regime = regime
        trigger_engine._last_news_risk = news.get("geo_risk", 0)

        if day_had_triggers:
            total_trigger_days += 1

        # Progress
        if not quiet and (i + 1) % milestone == 0:
            pct = int((i + 1) / len(trading_days) * 100)
            print(f"  [{pct:>3}%] {date_str}", end="")
            trig_today = sum(1 for t in daily_trigger_log if t["date"] == date_str)
            print(f" | triggers: {trig_today}", end="")
            for s in strategies[:4]:
                val = s.portfolio_history[-1]["total_value"] if s.portfolio_history else initial_cash
                ret = (val - initial_cash) / initial_cash * 100
                print(f" | {s.name[:3]}: {ret:+.1f}%", end="")
            print()

    # Finalize
    for strat in strategies:
        strat.finalize_memory()

    # Compute benchmarks
    benchmarks = {}
    for bm in BENCHMARKS:
        if bm in price_data:
            df = price_data[bm]
            mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
            bench = df.loc[mask]
            if not bench.empty:
                # Use Open for entry to match strategy execution (strategies buy at Open)
                entry = float(bench["Open"].iloc[0]) if "Open" in bench.columns else float(bench["Close"].iloc[0])
                shares = int(initial_cash / entry)
                cash_left = initial_cash - shares * entry
                final = float(bench["Close"].iloc[-1])
                fv = shares * final + cash_left
                values = (bench["Close"] * shares + cash_left).values
                peak = np.maximum.accumulate(values)
                dd = (values - peak) / peak * 100
                daily_ret = pd.Series(values).pct_change().dropna()
                sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
                benchmarks[bm] = {
                    "final_value": round(fv, 2),
                    "total_return_pct": round((fv - initial_cash) / initial_cash * 100, 2),
                    "sharpe_ratio": round(sharpe, 3),
                    "max_drawdown_pct": round(float(np.min(dd)), 2),
                }

    # === SAVE RESULTS ===
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    period_slug = period_name.lower().replace(" ", "_")[:20]
    run_name = f"{timestamp}_{period_slug}_mp{max_positions}_daily"
    run_dir = os.path.join(RUNS_DIR, run_name)
    os.makedirs(run_dir, exist_ok=True)

    # Config (with feature flags for reproducibility)
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({
            "run_name": run_name, "engine": "daily_event_driven",
            "engine_version": "2.0",
            "period": period_name, "start": start, "end": end,
            "initial_cash": initial_cash, "max_positions": max_positions,
            "regime_stickiness": regime_stickiness,
            "realistic": realistic, "slippage": slippage, "exec_model": exec_model,
            "universe_size": len(UNIVERSE), "trading_days": len(trading_days),
            "total_triggers": len(daily_trigger_log),
            "trigger_days": total_trigger_days,
            "features": risk_overlay.features,
            "params": risk_overlay.params,
        }, f, indent=2)

    # Trigger log
    with open(os.path.join(run_dir, "trigger_log.json"), "w") as f:
        json.dump(daily_trigger_log, f, indent=2, default=str)

    # === SHARED DATA (computed once, read by all strategies) ===
    shared_dir = os.path.join(run_dir, "shared")
    os.makedirs(shared_dir, exist_ok=True)

    with open(os.path.join(shared_dir, "regime_log.json"), "w") as f:
        json.dump(regime_log, f, indent=2)

    if risk_overlay.consensus_logs:
        with open(os.path.join(shared_dir, "consensus_log.json"), "w") as f:
            json.dump(risk_overlay.consensus_logs, f, indent=2, default=str)

    # Raw signals + conflicts (shared detection — same facts for all strategies)
    if risk_overlay.raw_signals_log:
        with open(os.path.join(shared_dir, "signals_raw.json"), "w") as f:
            json.dump(risk_overlay.raw_signals_log, f, indent=2, default=str)

    if risk_overlay.raw_conflicts_log:
        with open(os.path.join(shared_dir, "conflicts_raw.json"), "w") as f:
            json.dump(risk_overlay.raw_conflicts_log, f, indent=2, default=str)

    # Per-strategy results
    results = {"strategies": {}, "benchmarks": benchmarks}
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
        spy_ret = benchmarks.get("SPY", {}).get("total_return_pct", 0)

        results["strategies"][strat.name] = {
            "final_value": round(fv, 2), "total_return_pct": round(tr, 2),
            "alpha_vs_spy": round(tr - spy_ret, 2), "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": len(strat.transactions),
            "win_rate_pct": round(wins / len(sells) * 100, 1) if sells else 0,
        }

        # Save per-strategy files
        sdir = os.path.join(run_dir, "portfolios", strat.name)
        os.makedirs(sdir, exist_ok=True)

        with open(os.path.join(sdir, "state.json"), "w") as f:
            json.dump({"final_value": round(fv, 2), "cash": round(strat.cash, 2),
                       "positions": strat.positions, "return_pct": round(tr, 2)}, f, indent=2, default=str)

        if strat.transactions:
            all_keys = set()
            for t in strat.transactions:
                all_keys.update(t.keys())
            fieldnames = ["date", "action", "ticker", "shares", "price", "total", "pnl", "pnl_pct", "cash_after"]
            fieldnames = [k for k in fieldnames if k in all_keys]
            fieldnames.extend(k for k in sorted(all_keys) if k not in fieldnames)
            with open(os.path.join(sdir, "transactions.csv"), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                w.writerows(strat.transactions)

        if strat.reasoning_log:
            with open(os.path.join(sdir, "reasoning.json"), "w") as f:
                json.dump(strat.reasoning_log, f, indent=2, default=str)

        with open(os.path.join(sdir, "memory.json"), "w") as f:
            json.dump(strat.memory, f, indent=2, default=str)

        with open(os.path.join(sdir, "history.json"), "w") as f:
            json.dump(history, f, indent=2)

        if strat.watchnotes:
            with open(os.path.join(sdir, "watchnotes.json"), "w") as f:
                json.dump(strat.watchnotes, f, indent=2, default=str)

        # Save conviction logs (per-strategy, from risk overlay)
        # Per-strategy risk overlay logs (how THIS judge interpreted shared signals)
        conv_logs = risk_overlay.conviction_logs.get(strat.name, [])
        if conv_logs:
            with open(os.path.join(sdir, "conviction_log.json"), "w") as f:
                json.dump(conv_logs, f, indent=2, default=str)

        # Save LLM call log (MixLLM strategy only)
        if hasattr(strat, '_llm_log') and strat._llm_log:
            with open(os.path.join(sdir, "llm_calls.json"), "w") as f:
                json.dump(strat._llm_log, f, indent=2, default=str)
            if not quiet:
                print(f"  {strat.name}: {getattr(strat, '_llm_call_count', 0)} LLM calls, "
                      f"{getattr(strat, '_llm_fallback_count', 0)} fallbacks")

        # Save regime history (Mix/MixLLM)
        if hasattr(strat, 'regime_history') and strat.regime_history:
            with open(os.path.join(sdir, "regime_history.json"), "w") as f:
                json.dump(strat.regime_history, f, indent=2, default=str)

        conf_logs = risk_overlay.conflict_logs.get(strat.name, [])
        if conf_logs:
            with open(os.path.join(sdir, "conflicts.json"), "w") as f:
                json.dump(conf_logs, f, indent=2, default=str)

    # Summary
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print results
    if not quiet:
        print(f"\n{'=' * 80}")
        print(f"RESULTS: {period_name} (Daily Event-Driven Engine)")
        print(f"{'=' * 80}")
        print(f"Trading days: {len(trading_days)} | Total triggers: {len(daily_trigger_log)} | Trigger days: {total_trigger_days}")
        print()
        print(f"{'Strategy':<14} {'Return':>10} {'Alpha':>10} {'Sharpe':>10} {'MaxDD':>10} {'WinRate':>10} {'Trades':>8}")
        print("-" * 72)
        for name, data in results["strategies"].items():
            print(f"{name:<14} {data['total_return_pct']:>9.1f}% {data['alpha_vs_spy']:>9.1f}% "
                  f"{data['sharpe_ratio']:>10.3f} {data['max_drawdown_pct']:>9.1f}% "
                  f"{data['win_rate_pct']:>9.1f}% {data['total_trades']:>8}")
        print("-" * 72)
        for name, data in benchmarks.items():
            print(f"{name + ' (B&H)':<14} {data['total_return_pct']:>9.1f}% {'--':>10} "
                  f"{data['sharpe_ratio']:>10.3f} {data['max_drawdown_pct']:>9.1f}% {'--':>10} {'--':>8}")
        print(f"\nRun saved to: {run_dir}")
    if live_mode:
        return results, strategies
    return results


def main():
    parser = argparse.ArgumentParser(description="Daily event-driven simulation")
    parser.add_argument("--period", choices=list(PERIODS.keys()), help="Named period")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=100_000)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--regime-stickiness", type=int, default=1,
                        help="Days of consecutive regime signal before switching (1=instant, 3 or 5=sticky)")
    parser.add_argument("--realistic", action="store_true", default=True,
                        help="Use T-1 data for signals, T for execution (default: True)")
    parser.add_argument("--no-realistic", dest="realistic", action="store_false",
                        help="Use T data for both signals and execution (legacy mode)")
    parser.add_argument("--slippage", type=float, default=0.0005,
                        help="Execution slippage (0.0005 = 5bps, Zipline default)")
    parser.add_argument("--exec-model", choices=["open", "premarket", "open30", "vwap"], default="premarket",
                        help="Execution price model: open=T open, premarket=T open with gap filter, open30/vwap=benchmarks")
    parser.add_argument("--frequency", choices=["weekly", "biweekly", "monthly", "quarterly"],
                        default="biweekly", help="Rebalance frequency (default: biweekly, best overall)")
    parser.add_argument("--chandelier", action="store_true", default=False,
                        help="Enable Chandelier Exit trailing stop (default: off)")
    parser.add_argument("--cooldown", action="store_true", default=False,
                        help="Enable cooldown timer + min holding period (default: off)")
    parser.add_argument("--breadth", action="store_true", default=False,
                        help="Enable breadth + HYG recovery signal (default: off)")
    args = parser.parse_args()

    if args.period:
        p = PERIODS[args.period]
        run_daily_simulation(p["start"], p["end"], args.cash, args.max_positions, p["name"],
                             regime_stickiness=args.regime_stickiness,
                             realistic=args.realistic, slippage=args.slippage,
                             exec_model=args.exec_model, frequency=args.frequency,
                             chandelier=args.chandelier, cooldown=args.cooldown,
                             breadth=args.breadth)
    elif args.start and args.end:
        run_daily_simulation(args.start, args.end, args.cash, args.max_positions, "Custom",
                             regime_stickiness=args.regime_stickiness,
                             realistic=args.realistic, slippage=args.slippage,
                             exec_model=args.exec_model, frequency=args.frequency,
                             chandelier=args.chandelier, cooldown=args.cooldown,
                             breadth=args.breadth)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

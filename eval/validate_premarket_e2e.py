"""End-to-end validation: proxy premarket vs real premarket prices.

For the last 60 days (where yfinance has 5m data with prepost=True):
1. Fetch REAL pre-market prices (last bar before 9:30 AM) for all universe stocks
2. Run simulation with REAL pre-market prices injected
3. Run simulation with PROXY pre-market prices (0.2*T-1 Close + 0.8*T Open)
4. Compare strategy returns — if similar, proxy is validated for all historical periods.

Usage:
    python eval/validate_premarket_e2e.py
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import UNIVERSE, run_daily_simulation


def fetch_real_premarket_prices(tickers, batch_size=10):
    """Fetch last pre-market price (before 9:30 AM) for all tickers, last 60 days.

    Returns: {ticker: {date_str: premarket_price}}
    """
    premarket_data = {}
    total = len(tickers)

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        print(f"  Fetching pre-market data: batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} "
              f"({', '.join(batch[:3])}...)")

        for ticker in batch:
            try:
                tk = yf.Ticker(ticker)
                df = tk.history(period="60d", interval="5m", prepost=True)
                if df.empty:
                    continue

                # Group by date, find last pre-market bar (before 9:30 AM)
                ticker_pm = {}
                for date, group in df.groupby(df.index.date):
                    # Pre-market: hour < 9, or hour == 9 and minute < 30
                    pm_bars = group[(group.index.hour < 9) |
                                   ((group.index.hour == 9) & (group.index.minute < 30))]
                    if not pm_bars.empty:
                        ticker_pm[str(date)] = float(pm_bars["Close"].iloc[-1])

                if ticker_pm:
                    premarket_data[ticker] = ticker_pm

            except Exception as e:
                print(f"    {ticker}: error - {e}")
                continue

        # Small delay between batches to avoid rate limiting
        if i + batch_size < total:
            time.sleep(1)

    print(f"  Got pre-market data for {len(premarket_data)} tickers")
    return premarket_data


def patch_premarket_prices(premarket_data):
    """Monkey-patch BaseStrategy._get_premarket_price to use real data when available."""
    from strategies.base_strategy import BaseStrategy

    # Save original method
    original_method = BaseStrategy._get_premarket_price

    def _get_real_premarket_price(self, price_data, ticker, date):
        """Use real pre-market price if available, otherwise fall back to proxy."""
        # Check if we have real data for this ticker+date
        if ticker in premarket_data:
            if date in premarket_data[ticker]:
                real_price = premarket_data[ticker][date]

                # Still need gap_pct for the gap filter
                if ticker in price_data and not price_data[ticker].empty:
                    df = price_data[ticker]
                    mask_t = df.index <= pd.Timestamp(date)
                    mask_t1 = df.index < pd.Timestamp(date)
                    if mask_t.any() and mask_t1.any() and "Open" in df.columns:
                        t_open = float(df.loc[mask_t].iloc[-1]["Open"])
                        t1_close = float(df.loc[mask_t1, "Close"].iloc[-1])
                        gap_pct = (t_open - t1_close) / t1_close * 100 if t1_close > 0 else 0
                        return real_price, gap_pct

                return real_price, 0.0

        # Fallback to proxy
        return original_method(self, price_data, ticker, date)

    BaseStrategy._get_premarket_price = _get_real_premarket_price
    return original_method


def unpatch_premarket_prices(original_method):
    """Restore original proxy method."""
    from strategies.base_strategy import BaseStrategy
    BaseStrategy._get_premarket_price = original_method


def extract_results(results):
    """Extract strategy returns from simulation results."""
    summary = {}
    # Results format: {"strategies": {name: {total_return_pct, ...}}, "benchmarks": {...}}
    strats = results.get("strategies", {})
    for name, data in strats.items():
        if isinstance(data, dict) and "total_return_pct" in data:
            summary[name] = {
                "return": data["total_return_pct"],
                "sharpe": data.get("sharpe_ratio", 0),
                "max_dd": data.get("max_drawdown_pct", 0),
                "trades": data.get("total_trades", 0),
            }
    benchmarks = results.get("benchmarks", {})
    for name, data in benchmarks.items():
        bname = f"{name}_BH"
        if isinstance(data, dict) and "total_return_pct" in data:
            summary[bname] = {"return": data["total_return_pct"]}
    return summary


def main():
    print("=" * 70)
    print("END-TO-END PREMARKET VALIDATION")
    print("Real pre-market prices vs 0.2/0.8 proxy — last 60 trading days")
    print("=" * 70)

    # Determine date range: last ~60 trading days ≈ last 85 calendar days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=85)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"\nPeriod: {start_str} to {end_str}")
    print(f"Universe: {len(UNIVERSE)} stocks")

    # Step 1: Fetch real pre-market data
    print("\n--- Step 1: Fetching real pre-market prices (5m bars, prepost=True) ---")
    premarket_data = fetch_real_premarket_prices(UNIVERSE)

    # Count coverage
    all_dates = set()
    for ticker_dates in premarket_data.values():
        all_dates.update(ticker_dates.keys())
    print(f"  Coverage: {len(all_dates)} unique dates, "
          f"avg {np.mean([len(v) for v in premarket_data.values()]):.0f} dates per ticker")

    # Step 2: Run with PROXY premarket
    print("\n--- Step 2: Running simulation with PROXY premarket ---")
    proxy_results = run_daily_simulation(
        start_str, end_str, 100_000, 10, "ProxyPremarket",
        realistic=True, slippage=0.0005, exec_model="premarket", quiet=True)

    # Step 3: Run with REAL premarket (monkey-patched)
    print("\n--- Step 3: Running simulation with REAL premarket prices ---")
    original_method = patch_premarket_prices(premarket_data)
    try:
        real_results = run_daily_simulation(
            start_str, end_str, 100_000, 10, "RealPremarket",
            realistic=True, slippage=0.0005, exec_model="premarket", quiet=True)
    finally:
        unpatch_premarket_prices(original_method)

    # Step 4: Compare
    print("\n" + "=" * 70)
    print("COMPARISON: Proxy vs Real Pre-market Prices")
    print("=" * 70)

    proxy_summary = extract_results(proxy_results)
    real_summary = extract_results(real_results)

    print(f"\n{'Strategy':<14} {'Proxy':>8} {'Real':>8} {'Delta':>8} {'Match?':>8}")
    print("-" * 50)

    deltas = []
    for strat in ["Value", "Momentum", "Balanced", "Defensive", "EventDriven",
                   "Adaptive", "Commodity", "Mix", "MixLLM"]:
        p = proxy_summary.get(strat, {}).get("return", 0)
        r = real_summary.get(strat, {}).get("return", 0)
        d = p - r
        deltas.append(abs(d))
        match = "YES" if abs(d) < 2.0 else "CLOSE" if abs(d) < 5.0 else "NO"
        print(f"{strat:<14} {p:>7.1f}% {r:>7.1f}% {d:>+7.1f}% {match:>8}")

    # Also show benchmarks
    for bench in ["SPY_BH", "QQQ_BH"]:
        p = proxy_summary.get(bench, {}).get("return", 0)
        r = real_summary.get(bench, {}).get("return", 0)
        print(f"{bench:<14} {p:>7.1f}% {r:>7.1f}% {p - r:>+7.1f}%")

    print("-" * 50)
    mean_delta = np.mean(deltas)
    max_delta = np.max(deltas)
    print(f"\nMean |delta|: {mean_delta:.2f}%")
    print(f"Max |delta|:  {max_delta:.2f}%")

    if mean_delta < 1.0:
        print("\nVERDICT: EXCELLENT — proxy and real premarket produce nearly identical results.")
        print("Safe to use proxy for all historical backtests.")
    elif mean_delta < 3.0:
        print("\nVERDICT: GOOD — proxy is close enough for historical backtests.")
        print("Small differences from pre-market liquidity/timing won't change conclusions.")
    else:
        print("\nVERDICT: SIGNIFICANT DIVERGENCE — proxy may not be accurate enough.")
        print("Consider adjusting the 0.2/0.8 blend or using a different approach.")


if __name__ == "__main__":
    main()

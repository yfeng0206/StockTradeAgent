"""Pre-fetch and cache price data for all periods and tickers.

Downloads OHLCV data from yfinance and saves to data/prices/ as parquet files.
Subsequent simulation runs will read from cache instead of re-downloading.

Usage:
    python eval/prefetch_prices.py              # All 14 periods
    python eval/prefetch_prices.py --refresh    # Force re-download
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import PERIODS, UNIVERSE, BENCHMARKS, MACRO_ETFS, download_data, PRICE_CACHE_DIR


def main():
    parser = argparse.ArgumentParser(description="Pre-fetch and cache all price data")
    parser.add_argument("--refresh", action="store_true", help="Force re-download, ignoring cache")
    args = parser.parse_args()

    all_tickers = sorted(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
    print(f"Tickers: {len(all_tickers)}")
    print(f"Periods: {len(PERIODS)}")
    print(f"Cache dir: {PRICE_CACHE_DIR}")
    print()

    # Find the widest date range needed (earliest start - 400d buffer to latest end)
    starts = [p["start"] for p in PERIODS.values()]
    ends = [p["end"] for p in PERIODS.values()]
    earliest = min(starts)
    latest = max(ends)
    print(f"Date range: {earliest} to {latest} (+ 400-day buffer)")
    print()

    # Single bulk download covering all periods
    print(f"Downloading {len(all_tickers)} tickers...")
    start_time = time.time()
    data = download_data(all_tickers, earliest, latest, refresh=args.refresh)
    elapsed = time.time() - start_time

    # Report
    cached_files = [f for f in os.listdir(PRICE_CACHE_DIR) if f.endswith(".csv")]
    print(f"\nDone in {elapsed:.0f}s")
    print(f"Downloaded: {len(data)} tickers")
    print(f"Cached files: {len(cached_files)} in {PRICE_CACHE_DIR}")

    # Verify coverage for each period
    print(f"\nPeriod coverage check:")
    for key, p in PERIODS.items():
        covered = 0
        for ticker in UNIVERSE:
            if ticker in data and not data[ticker].empty:
                covered += 1
        print(f"  {p['name']:<30} {covered}/{len(UNIVERSE)} tickers")


if __name__ == "__main__":
    main()

"""Backfill GDELT geopolitical events for all missing weekend dates.

Our news collector previously skipped weekends. This fills the gap
with GDELT data (free, no API key, works for any historical date).

Usage:
    python tools/backfill_weekends.py              # Backfill all missing weekends
    python tools/backfill_weekends.py --dry-run    # Count missing without fetching
    python tools/backfill_weekends.py --year 2025  # Backfill specific year only
"""

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from news_collector import collect_geopolitical, collect_macro

NEWS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "news")


def find_missing_weekends(start_year=2019, end_date=None):
    """Find all weekend dates missing geopolitical data."""
    if end_date is None:
        end_date = date.today()
    else:
        end_date = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date

    start = date(start_year, 1, 1)
    existing = set(os.listdir(NEWS_DIR)) if os.path.exists(NEWS_DIR) else set()

    missing = []
    d = start
    while d <= end_date:
        if d.weekday() >= 5:  # Saturday or Sunday
            ds = d.isoformat()
            geo_path = os.path.join(NEWS_DIR, ds, "geopolitical")
            has_geo = os.path.exists(geo_path) and os.listdir(geo_path)
            if not has_geo:
                missing.append(ds)
        d += timedelta(days=1)

    return missing


def backfill_date(date_str):
    """Backfill geopolitical + macro news for a single date."""
    try:
        # GDELT geopolitical events (works for any historical date)
        collect_geopolitical(date_str, force=False)

        # Macro news via Google RSS (only works for recent dates, but try anyway)
        collect_macro(date_str, force=False)

        return True
    except Exception as e:
        print(f"  Error on {date_str}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Backfill weekend GDELT data")
    parser.add_argument("--dry-run", action="store_true", help="Count missing without fetching")
    parser.add_argument("--year", type=int, help="Backfill specific year only")
    parser.add_argument("--limit", type=int, default=0, help="Max dates to process (0=all)")
    args = parser.parse_args()

    start_year = args.year or 2019
    end_year = args.year or 2026

    print("=" * 60)
    print("WEEKEND NEWS BACKFILL")
    print(f"Source: GDELT API (free, no key)")
    print(f"Range: {start_year} to {end_year}")
    print("=" * 60)

    missing = find_missing_weekends(start_year)
    if args.year:
        missing = [d for d in missing if d.startswith(str(args.year))]

    print(f"Missing weekend dates: {len(missing)}")

    if args.dry_run:
        # Show by year
        from collections import Counter
        by_year = Counter(d[:4] for d in missing)
        for y in sorted(by_year):
            print(f"  {y}: {by_year[y]} weekends missing")
        return

    if args.limit:
        missing = missing[:args.limit]
        print(f"Processing first {args.limit} dates")

    success = 0
    failed = 0
    t0 = time.time()

    for i, date_str in enumerate(missing):
        if i % 50 == 0 and i > 0:
            elapsed = time.time() - t0
            rate = i / elapsed * 60
            remaining = (len(missing) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(missing)}] {date_str} | {rate:.0f}/min | ~{remaining:.0f} min left")

        ok = backfill_date(date_str)
        if ok:
            success += 1
        else:
            failed += 1

        # Rate limit: ~2 requests per date, keep under GDELT limits
        time.sleep(0.5)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Success: {success} | Failed: {failed} | Total: {len(missing)}")


if __name__ == "__main__":
    main()

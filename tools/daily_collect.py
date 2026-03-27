"""Daily auto-collector — runs all news collection and fills any gaps.

Run this once a day. It will:
1. Check for any missing days since last collection
2. Backfill missing days (company news won't be available, but GDELT and macro will be)
3. Collect all categories for today
4. Show a status summary

Usage:
    python tools/daily_collect.py           # Collect today + fill gaps
    python tools/daily_collect.py --check   # Just show what's missing
    python tools/daily_collect.py --days 30 # Check/fill last 30 days of gaps
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

# Add tools dir to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from news_collector import (
    collect_all, category_exists, ALL_CATEGORIES,
    collect_geopolitical, collect_macro, collect_commodities,
    collect_currencies, collect_sectors, collect_sentiment,
    generate_briefing, show_status, BASE_DIR
)

# Categories that can be backfilled for past dates
# (company news from yfinance only gives current headlines, can't backfill)
BACKFILLABLE = ["geopolitical", "macro", "commodities", "currencies", "sectors", "sentiment"]


def find_gaps(days: int = 14) -> list:
    """Find dates with missing news data."""
    today = date.today()
    gaps = []

    for i in range(1, days + 1):
        d = (today - timedelta(days=i)).isoformat()
        # Skip weekends
        dt = date.fromisoformat(d)
        if dt.weekday() >= 5:
            continue

        missing = []
        for cat in BACKFILLABLE:
            if not category_exists(d, cat):
                missing.append(cat)

        if missing:
            gaps.append({"date": d, "missing": missing})

    return gaps


def fill_gaps(gaps: list):
    """Fill missing categories for gap dates."""
    if not gaps:
        print("No gaps to fill!")
        return

    print(f"\nFilling {len(gaps)} gap days...")
    for gap in gaps:
        d = gap["date"]
        missing = gap["missing"]
        print(f"\n  {d}: filling {', '.join(missing)}")

        for cat in missing:
            print(f"    {cat}...", end=" ", flush=True)
            try:
                if cat == "geopolitical":
                    count = collect_geopolitical(d, force=True)
                elif cat == "macro":
                    count = collect_macro(d, force=True)
                elif cat == "commodities":
                    count = collect_commodities(d, force=True)
                elif cat == "currencies":
                    count = collect_currencies(d, force=True)
                elif cat == "sectors":
                    count = collect_sectors(d, force=True)
                elif cat == "sentiment":
                    count = collect_sentiment(d, force=True)
                else:
                    count = 0
                print(f"{count} items")
            except Exception as e:
                print(f"error: {e}")


def daily_run(check_days: int = 14):
    """Full daily collection routine."""
    today = date.today().isoformat()

    print("=" * 60)
    print(f"DAILY NEWS COLLECTION — {today}")
    print("=" * 60)

    # Step 1: Check for gaps
    print(f"\n1. Checking for gaps (last {check_days} business days)...")
    gaps = find_gaps(check_days)
    if gaps:
        print(f"   Found {len(gaps)} days with missing data:")
        for g in gaps[:5]:
            print(f"     {g['date']}: missing {', '.join(g['missing'])}")
        if len(gaps) > 5:
            print(f"     ... and {len(gaps) - 5} more")
    else:
        print("   No gaps found!")

    # Step 2: Fill gaps
    if gaps:
        print(f"\n2. Filling gaps...")
        fill_gaps(gaps)
    else:
        print(f"\n2. No gaps to fill.")

    # Step 3: Collect today
    print(f"\n3. Collecting all categories for today ({today})...")
    results = collect_all(today)

    # Step 4: Show status
    print(f"\n4. Collection status:")
    show_status(min(check_days, 7))

    # Step 5: Generate briefing
    print(f"\n5. Today's briefing preview:")
    briefing = generate_briefing(today)
    # Only show first 20 lines
    lines = briefing.split("\n")
    for line in lines[:20]:
        try:
            print(f"   {line}")
        except UnicodeEncodeError:
            print(f"   {line.encode('ascii', errors='replace').decode('ascii')}")
    if len(lines) > 20:
        print(f"   ... ({len(lines) - 20} more lines, run --briefing for full)")

    print(f"\n{'=' * 60}")
    print("Done! Run 'python tools/news_collector.py --briefing' for full briefing.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Daily news auto-collector with gap filling")
    parser.add_argument("--check", action="store_true", help="Just show gaps, don't fill")
    parser.add_argument("--days", type=int, default=14, help="How many days back to check for gaps")
    args = parser.parse_args()

    if args.check:
        gaps = find_gaps(args.days)
        if gaps:
            print(f"Found {len(gaps)} days with missing data:")
            for g in gaps:
                print(f"  {g['date']}: missing {', '.join(g['missing'])}")
        else:
            print("No gaps! All data collected.")
        show_status(min(args.days, 14))
    else:
        daily_run(args.days)


if __name__ == "__main__":
    main()

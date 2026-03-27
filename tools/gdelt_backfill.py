"""GDELT historical news backfiller.

Fetches geopolitical/macro news from GDELT for historical date ranges.
Respects rate limits (1 request per 5 seconds). Stores in data/news/{date}/geopolitical/.

Usage:
    python tools/gdelt_backfill.py --start 2022-01-03 --end 2022-10-31
    python tools/gdelt_backfill.py --period recession
    python tools/gdelt_backfill.py --period all
    python tools/gdelt_backfill.py --check   # Show what's already backfilled
"""

import argparse
import json
import os
import time
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus

import requests

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news")

PERIODS = {
    "recession":        ("2022-01-03", "2022-10-31"),
    "normal":           ("2019-01-02", "2019-12-31"),
    "black_swan":       ("2020-01-02", "2020-06-30"),
    "bull":             ("2023-01-02", "2023-12-29"),
    "bull_to_recession":("2021-07-01", "2022-06-30"),
}

# Queries covering key market-moving global events
GDELT_QUERIES = [
    "(war OR conflict OR military OR airstrike OR invasion)",
    "(sanctions OR embargo OR trade war OR tariffs)",
    "(OPEC OR oil crisis OR energy crisis OR oil production)",
    "(pandemic OR covid OR lockdown OR outbreak)",
    "(federal reserve OR interest rate OR inflation OR recession)",
    "(Iran OR Ukraine OR Russia OR China Taiwan OR North Korea)",
]

RATE_LIMIT_SECONDS = 6  # GDELT free tier needs spacing


def fetch_gdelt_day(target_date: str, max_per_query: int = 15) -> list:
    """Fetch GDELT articles for a single day across all queries."""
    dt = target_date.replace("-", "")
    start_dt = f"{dt}000000"
    end_dt = f"{dt}235959"
    all_articles = []

    for query in GDELT_QUERIES:
        try:
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc?"
                f"query={quote_plus(query)}&mode=artlist&maxrecords={max_per_query}"
                f"&format=json&startdatetime={start_dt}&enddatetime={end_dt}"
            )
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    articles = data.get("articles", [])
                    for a in articles:
                        all_articles.append({
                            "title": a.get("title", ""),
                            "source": a.get("domain", ""),
                            "url": a.get("url", ""),
                            "published": a.get("seendate", ""),
                            "language": a.get("language", "English"),
                            "source_country": a.get("sourcecountry", ""),
                            "query_category": query[:40],
                        })
                except Exception:
                    pass  # Non-JSON response (error message)
            elif resp.status_code == 429:
                print(f"    Rate limited, waiting 10s...")
                time.sleep(10)
            time.sleep(RATE_LIMIT_SECONDS)
        except Exception as e:
            print(f"    Error for query '{query[:30]}': {e}")
            time.sleep(RATE_LIMIT_SECONDS)

    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        title = a.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(a)

    return unique


def save_day(target_date: str, articles: list):
    """Save articles to data/news/{date}/geopolitical/events.json"""
    cat_dir = os.path.join(BASE_DIR, target_date, "geopolitical")
    os.makedirs(cat_dir, exist_ok=True)
    filepath = os.path.join(cat_dir, "events.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "collected": datetime.now().isoformat(),
            "date": target_date,
            "source": "GDELT_historical",
            "article_count": len(articles),
            "articles": articles,
        }, f, indent=2, ensure_ascii=False, default=str)
    return filepath


def day_exists(target_date: str) -> bool:
    """Check if geopolitical news already collected for this date."""
    filepath = os.path.join(BASE_DIR, target_date, "geopolitical", "events.json")
    return os.path.exists(filepath)


def get_sample_dates(start: str, end: str, interval_days: int = 7) -> list:
    """Get sample dates from a range at regular intervals.

    We don't need EVERY day — geopolitical news changes weekly, not daily.
    Sampling every 7 days gives good coverage without hitting rate limits.
    """
    dates = []
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while current <= end_dt:
        # Skip weekends
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=interval_days)
    return dates


def backfill_period(start: str, end: str, interval_days: int = 7):
    """Backfill GDELT news for a date range."""
    sample_dates = get_sample_dates(start, end, interval_days)
    already = sum(1 for d in sample_dates if day_exists(d))
    needed = [d for d in sample_dates if not day_exists(d)]

    print(f"  Period: {start} to {end}")
    print(f"  Sample dates: {len(sample_dates)} (every {interval_days} days)")
    print(f"  Already have: {already}")
    print(f"  Need to fetch: {len(needed)}")

    if not needed:
        print("  All dates already backfilled!")
        return

    est_time = len(needed) * len(GDELT_QUERIES) * RATE_LIMIT_SECONDS
    print(f"  Estimated time: ~{est_time // 60} minutes")

    for i, d in enumerate(needed):
        print(f"  [{i+1}/{len(needed)}] {d}...", end=" ", flush=True)
        articles = fetch_gdelt_day(d)
        save_day(d, articles)
        print(f"{len(articles)} articles")

    print(f"  Done! Backfilled {len(needed)} days.")


def check_status():
    """Show backfill status for all periods."""
    print("\nGDELT Backfill Status:")
    print(f"{'Period':<22} {'Dates':<12} {'Have':<8} {'Missing':<8} {'Coverage':<10}")
    print("-" * 60)

    for name, (start, end) in PERIODS.items():
        sample = get_sample_dates(start, end, 7)
        have = sum(1 for d in sample if day_exists(d))
        total = len(sample)
        coverage = f"{have/total*100:.0f}%" if total > 0 else "0%"
        print(f"{name:<22} {total:<12} {have:<8} {total-have:<8} {coverage:<10}")


def load_gdelt_for_sim(target_date: str, lookback_days: int = 7) -> list:
    """Load geopolitical news for simulation use.

    Checks both GDELT (events.json) and Wikipedia (wiki_events.json).
    Looks back up to N days for nearest data.
    TEMPORAL GATING: Only returns events from dates <= target_date.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    for i in range(lookback_days + 1):
        check_date = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        geo_dir = os.path.join(BASE_DIR, check_date, "geopolitical")

        # Check GDELT first
        gdelt_path = os.path.join(geo_dir, "events.json")
        if os.path.exists(gdelt_path):
            with open(gdelt_path, encoding="utf-8") as f:
                data = json.load(f)
            articles = data.get("articles", [])
            if articles:
                return articles

        # Fall back to Wikipedia events
        wiki_path = os.path.join(geo_dir, "wiki_events.json")
        if os.path.exists(wiki_path):
            with open(wiki_path, encoding="utf-8") as f:
                data = json.load(f)
            # Convert wiki events to article-like format for compatibility
            events = data.get("events", [])
            return [{"title": e.get("text", ""), "source": "wikipedia",
                      "query": e.get("category", "")} for e in events]

    return []


def summarize_gdelt(articles: list) -> dict:
    """Create a compact summary of GDELT articles for the agent."""
    if not articles:
        return {"has_news": False}

    # Count by category
    categories = {}
    for a in articles:
        cat = a.get("query_category", "other")[:20]
        categories[cat] = categories.get(cat, 0) + 1

    # Top headlines (English only, deduplicated)
    headlines = []
    seen = set()
    for a in articles:
        title = a.get("title", "")
        lang = a.get("language", "")
        if title and title not in seen and ("english" in lang.lower() or not lang):
            seen.add(title)
            headlines.append(title)
        if len(headlines) >= 10:
            break

    # Detect key themes
    all_text = " ".join(a.get("title", "").lower() for a in articles)
    themes = []
    theme_keywords = {
        "war/conflict": ["war", "military", "airstrike", "invasion", "troops"],
        "sanctions/trade": ["sanctions", "tariff", "embargo", "trade war"],
        "oil/energy": ["oil", "opec", "energy", "crude", "pipeline"],
        "pandemic": ["covid", "pandemic", "lockdown", "outbreak", "vaccine"],
        "rates/inflation": ["federal reserve", "interest rate", "inflation", "recession", "fed"],
        "geopolitical_tension": ["iran", "ukraine", "russia", "china", "taiwan", "north korea"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in all_text for kw in keywords):
            themes.append(theme)

    return {
        "has_news": True,
        "article_count": len(articles),
        "active_themes": themes,
        "category_counts": categories,
        "top_headlines": headlines,
    }


def main():
    parser = argparse.ArgumentParser(description="GDELT historical news backfiller")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--period", choices=list(PERIODS.keys()) + ["all"], help="Named period to backfill")
    parser.add_argument("--interval", type=int, default=7, help="Days between samples (default 7)")
    parser.add_argument("--check", action="store_true", help="Show backfill status")
    args = parser.parse_args()

    if args.check:
        check_status()
        return

    if args.period:
        if args.period == "all":
            for name, (start, end) in PERIODS.items():
                print(f"\n{'=' * 50}")
                print(f"Backfilling: {name}")
                print(f"{'=' * 50}")
                backfill_period(start, end, args.interval)
        else:
            start, end = PERIODS[args.period]
            backfill_period(start, end, args.interval)
    elif args.start and args.end:
        backfill_period(args.start, args.end, args.interval)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python tools/gdelt_backfill.py --period recession")
        print("  python tools/gdelt_backfill.py --period all")
        print("  python tools/gdelt_backfill.py --check")


if __name__ == "__main__":
    main()

"""Wikipedia Current Events backfiller — free historical news with no rate limits.

Fetches daily world events from Wikipedia's Current Events portal.
Events are already human-curated and categorized (Armed conflicts, Business,
Health, Politics, etc.) — perfect for stock research context.

One request per day, no API key, no rate limits for reasonable use.

Usage:
    python tools/wiki_news_backfill.py --period all          # All 5 test periods
    python tools/wiki_news_backfill.py --period black_swan   # Just COVID period
    python tools/wiki_news_backfill.py --start 2022-01-03 --end 2022-10-31
    python tools/wiki_news_backfill.py --check               # Show status
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, date, timedelta

import requests

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news")
HEADERS = {"User-Agent": "ConsensusAITrader/1.0 (educational stock research project)"}

PERIODS = {
    "recession":         ("2022-01-03", "2022-10-31"),
    "normal":            ("2019-01-02", "2019-12-31"),
    "black_swan":        ("2020-01-02", "2020-06-30"),
    "bull":              ("2023-01-02", "2023-12-29"),
    "bull_to_recession": ("2021-07-01", "2022-06-30"),
}

# Market-relevant categories to extract
MARKET_CATEGORIES = {
    "Armed conflicts and attacks": "geopolitical",
    "Business and economy": "business",
    "Disasters and accidents": "disaster",
    "Health and environment": "health",
    "International relations": "geopolitical",
    "Law and crime": "legal",
    "Politics and elections": "politics",
    "Science and technology": "tech",
    "Sports": "sports",
}


def fetch_wiki_day(year: int, month: int, day: int) -> dict:
    """Fetch a single day's events from Wikipedia Current Events portal."""
    month_name = datetime(year, month, 1).strftime("%B")
    page = f"Portal:Current_events/{year}_{month_name}_{day}"
    url = f"https://en.wikipedia.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json"

    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}"}

    data = resp.json()
    if "error" in data:
        return {"error": data["error"].get("info", "Page not found")}

    wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    if not wikitext:
        return {"error": "Empty page"}

    return parse_wiki_events(wikitext, f"{year}-{month:02d}-{day:02d}")


def parse_wiki_events(wikitext: str, date_str: str) -> dict:
    """Parse Wikipedia Current Events wikitext into structured events."""
    events = []
    current_category = "uncategorized"

    # Clean up wikitext
    lines = wikitext.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect category headers (;Armed conflicts and attacks)
        if line.startswith(";"):
            cat_name = line.lstrip(";").strip()
            # Remove wiki links from category name
            cat_name = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", cat_name)
            current_category = cat_name
            continue

        # Detect event lines (start with * or **)
        if line.startswith("*"):
            # Clean wiki markup
            event_text = line.lstrip("*").strip()
            # Remove wiki links but keep display text
            event_text = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", event_text)
            # Remove references [https://... (Source)]
            sources = re.findall(r"\[https?://\S+\s+\(([^)]+)\)\]", event_text)
            event_text = re.sub(r"\[https?://\S+\s+\([^)]+\)\]", "", event_text)
            # Remove remaining markup
            event_text = re.sub(r"'''?", "", event_text)  # bold/italic
            event_text = re.sub(r"\{\{[^}]+\}\}", "", event_text)  # templates
            event_text = event_text.strip()

            if len(event_text) > 10:  # Skip very short fragments
                market_relevance = MARKET_CATEGORIES.get(current_category, "other")
                events.append({
                    "text": event_text,
                    "category": current_category,
                    "market_category": market_relevance,
                    "sources": sources[:3],
                    "is_subevent": line.startswith("**"),
                })

    # Summarize by market relevance
    summary = {}
    for cat in set(e["market_category"] for e in events):
        cat_events = [e for e in events if e["market_category"] == cat]
        # Get top-level events only for summary (not sub-events)
        top_events = [e for e in cat_events if not e["is_subevent"]]
        summary[cat] = {
            "count": len(cat_events),
            "headlines": [e["text"][:200] for e in top_events[:5]],
        }

    return {
        "date": date_str,
        "source": "Wikipedia_Current_Events",
        "total_events": len(events),
        "categories": summary,
        "events": events,
    }


def save_wiki_day(date_str: str, data: dict):
    """Save to data/news/{date}/geopolitical/wiki_events.json"""
    cat_dir = os.path.join(BASE_DIR, date_str, "geopolitical")
    os.makedirs(cat_dir, exist_ok=True)
    filepath = os.path.join(cat_dir, "wiki_events.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def day_has_wiki(date_str: str) -> bool:
    return os.path.exists(os.path.join(BASE_DIR, date_str, "geopolitical", "wiki_events.json"))


def backfill_range(start: str, end: str, interval: int = 3):
    """Backfill Wikipedia events for a date range.

    interval=3 means every 3 days (good balance of coverage vs speed).
    interval=1 for full daily coverage.
    """
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    dates = []
    while current <= end_dt:
        if current.weekday() < 5:  # Skip weekends
            dates.append(current)
        current += timedelta(days=interval)

    already = sum(1 for d in dates if day_has_wiki(d.strftime("%Y-%m-%d")))
    needed = [d for d in dates if not day_has_wiki(d.strftime("%Y-%m-%d"))]

    print(f"  Range: {start} to {end} (every {interval} days)")
    print(f"  Total sample dates: {len(dates)}, already have: {already}, need: {len(needed)}")

    if not needed:
        print("  All done!")
        return 0

    fetched = 0
    for i, d in enumerate(needed):
        date_str = d.strftime("%Y-%m-%d")
        print(f"  [{i+1}/{len(needed)}] {date_str}...", end=" ", flush=True)
        try:
            data = fetch_wiki_day(d.year, d.month, d.day)
            if "error" not in data:
                save_wiki_day(date_str, data)
                print(f"{data['total_events']} events")
                fetched += 1
            else:
                print(f"skip ({data['error'][:40]})")
            time.sleep(0.5)  # Be polite, but Wikipedia is generous
        except Exception as e:
            print(f"error: {e}")

    return fetched


def load_wiki_for_sim(target_date: str, lookback_days: int = 7) -> dict:
    """Load Wikipedia events for simulation. Looks back up to N days for nearest data.

    TEMPORAL GATING: Only returns events from dates <= target_date.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    for i in range(lookback_days + 1):
        check_date = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = os.path.join(BASE_DIR, check_date, "geopolitical", "wiki_events.json")
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            return data
    return {}


def summarize_for_agent(data: dict) -> str:
    """Create a compact summary string for the agent to read."""
    if not data or "categories" not in data:
        return "No geopolitical news available for this date."

    lines = [f"World Events ({data.get('date', '?')}):"]
    priority_order = ["geopolitical", "business", "health", "disaster", "politics", "tech"]

    for cat in priority_order:
        if cat in data["categories"]:
            info = data["categories"][cat]
            if info["headlines"]:
                lines.append(f"  [{cat.upper()}]")
                for h in info["headlines"][:3]:
                    lines.append(f"    - {h}")

    return "\n".join(lines)


def check_status():
    """Show backfill status for all periods."""
    print("\nWikipedia News Backfill Status:")
    print(f"{'Period':<22} {'Need':>6} {'Have':>6} {'Coverage':>10}")
    print("-" * 48)
    for name, (start, end) in PERIODS.items():
        current = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        total = 0
        have = 0
        while current <= end_dt:
            if current.weekday() < 5:
                total += 1
                if day_has_wiki(current.strftime("%Y-%m-%d")):
                    have += 1
            current += timedelta(days=3)
        pct = f"{have/total*100:.0f}%" if total > 0 else "0%"
        print(f"  {name:<20} {total:>6} {have:>6} {pct:>10}")


def main():
    parser = argparse.ArgumentParser(description="Wikipedia Current Events backfiller")
    parser.add_argument("--period", choices=list(PERIODS.keys()) + ["all"])
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--interval", type=int, default=3, help="Days between samples (default 3)")
    parser.add_argument("--check", action="store_true", help="Show status")
    args = parser.parse_args()

    if args.check:
        check_status()
        return

    if args.period == "all":
        for name, (start, end) in PERIODS.items():
            print(f"\n{'='*50}")
            print(f"Backfilling: {name}")
            backfill_range(start, end, args.interval)
        check_status()
    elif args.period:
        start, end = PERIODS[args.period]
        backfill_range(start, end, args.interval)
    elif args.start and args.end:
        backfill_range(args.start, args.end, args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

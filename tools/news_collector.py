"""Category-aware daily news collector.

Collects news across 7 categories, organized by date. Only fetches what's missing.
All sources are free — no API keys required.

Categories:
  company      — Per-ticker corporate news (yfinance)
  geopolitical — Wars, sanctions, diplomacy, global events (GDELT)
  macro        — Fed policy, economic data, central banks (RSS feeds)
  commodities  — Oil, gold, copper, natural gas prices & news (yfinance)
  currencies   — USD index, EUR/USD, yields, forex moves (yfinance)
  sectors      — Sector ETF performance & rotation (yfinance)
  sentiment    — VIX, market breadth, fear/greed signals (yfinance)

Usage:
    python tools/news_collector.py                  # Collect ALL missing categories for today
    python tools/news_collector.py --category company --tickers AAPL NVDA
    python tools/news_collector.py --category geopolitical
    python tools/news_collector.py --force           # Re-fetch even if already collected
    python tools/news_collector.py --date 2026-03-23 # Collect for a specific date
    python tools/news_collector.py --status          # Show what's collected vs missing
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus

import yfinance as yf
import requests

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news")
WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio", "watchlist.json")

ALL_CATEGORIES = ["company", "geopolitical", "macro", "commodities", "currencies", "sectors", "sentiment"]

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "CRM", "NFLX", "AMD",
    "JPM", "V", "MA", "GS", "BRK-B",
    "UNH", "JNJ", "LLY", "ABBV", "MRK",
    "PG", "KO", "PEP", "COST", "WMT", "HD",
    "XOM", "CVX", "CAT", "BA",
]

COMMODITY_TICKERS = {
    "CL=F": "crude_oil",
    "GC=F": "gold",
    "SI=F": "silver",
    "HG=F": "copper",
    "NG=F": "natural_gas",
}

CURRENCY_TICKERS = {
    "DX-Y.NYB": "us_dollar_index",
    "EURUSD=X": "eur_usd",
    "USDJPY=X": "usd_jpy",
    "GBPUSD=X": "gbp_usd",
    "USDCNY=X": "usd_cny",
    "^TNX": "treasury_10y",
    "^TYX": "treasury_30y",
    "^FVX": "treasury_5y",
}

SECTOR_ETFS = {
    "XLK": "technology", "XLF": "financials", "XLV": "healthcare",
    "XLE": "energy", "XLI": "industrials", "XLP": "consumer_staples",
    "XLY": "consumer_discretionary", "XLU": "utilities", "XLRE": "real_estate",
    "XLB": "materials", "XLC": "communication_services",
}

# RSS feeds for macro/economic news (free, no auth)
MACRO_RSS_FEEDS = {
    "reuters_markets": "https://news.google.com/rss/search?q=federal+reserve+OR+inflation+OR+interest+rates+OR+GDP+OR+economic+data&hl=en-US&gl=US&ceid=US:en",
    "reuters_world": "https://news.google.com/rss/search?q=trade+war+OR+tariffs+OR+sanctions+OR+central+bank&hl=en-US&gl=US&ceid=US:en",
}

# GDELT search terms for geopolitical events (parens required for OR)
GDELT_QUERIES = [
    "(war OR conflict OR military OR sanctions)",
    "(trade war OR tariffs OR embargo)",
    "(OPEC OR oil production OR energy crisis)",
    "(Iran OR Ukraine OR Russia OR China Taiwan)",
]


def get_date_dir(target_date: str) -> str:
    """Get the directory for a specific date's news."""
    return os.path.join(BASE_DIR, target_date)


def category_exists(target_date: str, category: str) -> bool:
    """Check if a category has already been collected for this date."""
    cat_dir = os.path.join(get_date_dir(target_date), category)
    if not os.path.exists(cat_dir):
        return False
    # Check if any json files exist in the category
    return any(f.endswith(".json") for f in os.listdir(cat_dir))


def save_category_data(target_date: str, category: str, filename: str, data: dict):
    """Save data to the correct date/category path."""
    cat_dir = os.path.join(get_date_dir(target_date), category)
    os.makedirs(cat_dir, exist_ok=True)
    filepath = os.path.join(cat_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return filepath


# ─── CATEGORY: COMPANY NEWS ─────────────────────────────────────────

def collect_company_news(target_date: str, tickers: list, force: bool = False):
    """Collect per-ticker corporate news from yfinance."""
    cat_dir = os.path.join(get_date_dir(target_date), "company")
    collected = 0

    for ticker in tickers:
        ticker_file = os.path.join(cat_dir, f"{ticker}.json")
        if not force and os.path.exists(ticker_file):
            continue  # Already have this ticker

        try:
            stock = yf.Ticker(ticker)
            news = stock.news or []
            articles = []
            for item in news[:10]:
                content = item.get("content", {})
                articles.append({
                    "title": content.get("title", item.get("title", "")),
                    "publisher": content.get("provider", {}).get("displayName", ""),
                    "published": content.get("pubDate", ""),
                    "link": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
                    "type": item.get("type", ""),
                })

            # Enrich top articles with summaries
            try:
                from article_summarizer import enrich_articles
                enrich_articles(articles, max_to_enrich=3)
            except Exception:
                pass

            save_category_data(target_date, "company", f"{ticker}.json", {
                "ticker": ticker,
                "collected": datetime.now().isoformat(),
                "article_count": len(articles),
                "articles": articles,
            })
            collected += 1
        except Exception as e:
            save_category_data(target_date, "company", f"{ticker}.json", {
                "ticker": ticker, "error": str(e), "articles": [],
            })

    return collected


# ─── CATEGORY: GEOPOLITICAL (GDELT) ─────────────────────────────────

def collect_geopolitical(target_date: str, force: bool = False):
    """Collect global geopolitical events from GDELT API."""
    if not force and category_exists(target_date, "geopolitical"):
        return 0

    all_articles = []
    for query in GDELT_QUERIES:
        try:
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc?"
                f"query={quote_plus(query)}&mode=artlist&maxrecords=20"
                f"&format=json&timespan=1d&sourcelang=english"
            )
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                for a in articles:
                    all_articles.append({
                        "title": a.get("title", ""),
                        "source": a.get("domain", ""),
                        "url": a.get("url", ""),
                        "published": a.get("seendate", ""),
                        "language": a.get("language", ""),
                        "source_country": a.get("sourcecountry", ""),
                        "query": query,
                    })
        except Exception:
            continue

    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        title = a.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(a)

    # Enrich top English articles with summaries (3-4 sentences)
    try:
        from article_summarizer import enrich_articles
        enrich_articles(unique, max_to_enrich=6)
    except Exception:
        pass  # Summarization is best-effort, don't fail collection

    save_category_data(target_date, "geopolitical", "events.json", {
        "collected": datetime.now().isoformat(),
        "source": "GDELT",
        "queries": GDELT_QUERIES,
        "article_count": len(unique),
        "articles": unique,
    })
    return len(unique)


# ─── CATEGORY: MACRO (RSS FEEDS) ────────────────────────────────────

def parse_rss(url: str, max_items: int = 15) -> list:
    """Parse an RSS feed and return articles."""
    articles = []
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "ConsensusAITrader/1.0"})
        root = ET.fromstring(resp.content)

        # Handle both RSS 2.0 and Atom formats
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item")  # RSS 2.0
        if not items:
            items = root.findall(".//atom:entry", ns)  # Atom

        for item in items[:max_items]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", item.findtext("published", ""))
            description = item.findtext("description", "")
            source = item.findtext("source", "")

            articles.append({
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "published": pub_date.strip() if pub_date else "",
                "source": source.strip() if source else "",
                "summary": description[:300] if description else "",
            })
    except Exception:
        pass
    return articles


def collect_macro(target_date: str, force: bool = False):
    """Collect macro/economic news from RSS feeds."""
    if not force and category_exists(target_date, "macro"):
        return 0

    all_articles = []
    for feed_name, url in MACRO_RSS_FEEDS.items():
        articles = parse_rss(url)
        for a in articles:
            a["feed"] = feed_name
        all_articles.extend(articles)

    # Deduplicate
    seen = set()
    unique = []
    for a in all_articles:
        title = a.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(a)

    save_category_data(target_date, "macro", "headlines.json", {
        "collected": datetime.now().isoformat(),
        "sources": list(MACRO_RSS_FEEDS.keys()),
        "article_count": len(unique),
        "articles": unique,
    })
    return len(unique)


# ─── CATEGORY: COMMODITIES ──────────────────────────────────────────

def collect_commodities(target_date: str, force: bool = False):
    """Collect commodity prices and news."""
    if not force and category_exists(target_date, "commodities"):
        return 0

    commodities = {}
    for symbol, name in COMMODITY_TICKERS.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
                change_pct = round((current - prev) / prev * 100, 2) if prev != 0 else 0

                # Get news for this commodity
                news = t.news or []
                articles = []
                for item in news[:5]:
                    content = item.get("content", {})
                    articles.append({
                        "title": content.get("title", item.get("title", "")),
                        "publisher": content.get("provider", {}).get("displayName", ""),
                        "published": content.get("pubDate", ""),
                    })

                commodities[name] = {
                    "symbol": symbol,
                    "price": round(current, 2),
                    "change_pct": change_pct,
                    "articles": articles,
                }
        except Exception:
            continue

    save_category_data(target_date, "commodities", "prices_and_news.json", {
        "collected": datetime.now().isoformat(),
        "commodities": commodities,
    })
    return len(commodities)


# ─── CATEGORY: CURRENCIES ───────────────────────────────────────────

def collect_currencies(target_date: str, force: bool = False):
    """Collect currency and yield data."""
    if not force and category_exists(target_date, "currencies"):
        return 0

    currencies = {}
    for symbol, name in CURRENCY_TICKERS.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
                change_pct = round((current - prev) / prev * 100, 2) if prev != 0 else 0

                currencies[name] = {
                    "symbol": symbol,
                    "value": round(current, 4),
                    "change_pct": change_pct,
                }
        except Exception:
            continue

    # Get forex news
    fx_articles = []
    try:
        t = yf.Ticker("DX-Y.NYB")
        news = t.news or []
        for item in news[:5]:
            content = item.get("content", {})
            fx_articles.append({
                "title": content.get("title", item.get("title", "")),
                "published": content.get("pubDate", ""),
            })
    except Exception:
        pass

    save_category_data(target_date, "currencies", "fx.json", {
        "collected": datetime.now().isoformat(),
        "currencies": currencies,
        "fx_news": fx_articles,
    })
    return len(currencies)


# ─── CATEGORY: SECTORS ──────────────────────────────────────────────

def collect_sectors(target_date: str, force: bool = False):
    """Collect sector ETF performance and rotation signals."""
    if not force and category_exists(target_date, "sectors"):
        return 0

    sectors = {}
    for symbol, name in SECTOR_ETFS.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1mo")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev_day = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
                month_ago = float(hist["Close"].iloc[0])

                sectors[name] = {
                    "symbol": symbol,
                    "price": round(current, 2),
                    "daily_change_pct": round((current - prev_day) / prev_day * 100, 2),
                    "monthly_change_pct": round((current - month_ago) / month_ago * 100, 2),
                }
        except Exception:
            continue

    # Determine rotation: which sectors are leading/lagging
    if sectors:
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("monthly_change_pct", 0), reverse=True)
        leaders = [s[0] for s in sorted_sectors[:3]]
        laggards = [s[0] for s in sorted_sectors[-3:]]
    else:
        leaders, laggards = [], []

    save_category_data(target_date, "sectors", "sectors.json", {
        "collected": datetime.now().isoformat(),
        "sectors": sectors,
        "rotation": {"leaders_1mo": leaders, "laggards_1mo": laggards},
    })
    return len(sectors)


# ─── CATEGORY: SENTIMENT ────────────────────────────────────────────

def collect_sentiment(target_date: str, force: bool = False):
    """Collect market-level sentiment indicators."""
    if not force and category_exists(target_date, "sentiment"):
        return 0

    sentiment = {}

    # VIX
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if not hist.empty:
            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
            if current < 15:
                mood = "Complacent / Low fear"
            elif current < 20:
                mood = "Normal"
            elif current < 30:
                mood = "Elevated fear"
            else:
                mood = "High fear / Panic"
            sentiment["vix"] = {"value": round(current, 2), "change": round(current - prev, 2), "mood": mood}
    except Exception:
        pass

    # Market breadth: SPY vs equal-weight RSP
    try:
        spy = yf.Ticker("SPY")
        rsp = yf.Ticker("RSP")
        spy_hist = spy.history(period="1mo")
        rsp_hist = rsp.history(period="1mo")
        if not spy_hist.empty and not rsp_hist.empty:
            spy_ret = (float(spy_hist["Close"].iloc[-1]) / float(spy_hist["Close"].iloc[0]) - 1) * 100
            rsp_ret = (float(rsp_hist["Close"].iloc[-1]) / float(rsp_hist["Close"].iloc[0]) - 1) * 100
            breadth_gap = round(rsp_ret - spy_ret, 2)
            sentiment["breadth"] = {
                "spy_1mo_pct": round(spy_ret, 2),
                "rsp_equal_weight_1mo_pct": round(rsp_ret, 2),
                "breadth_gap": breadth_gap,
                "signal": "Broad rally" if breadth_gap > 1 else "Narrow / top-heavy" if breadth_gap < -2 else "Normal",
            }
    except Exception:
        pass

    # Put/Call and market news
    market_articles = []
    try:
        spy_t = yf.Ticker("SPY")
        news = spy_t.news or []
        for item in news[:8]:
            content = item.get("content", {})
            market_articles.append({
                "title": content.get("title", item.get("title", "")),
                "published": content.get("pubDate", ""),
            })
    except Exception:
        pass

    save_category_data(target_date, "sentiment", "market_mood.json", {
        "collected": datetime.now().isoformat(),
        "indicators": sentiment,
        "market_headlines": market_articles,
    })
    return len(sentiment)


# ─── MAIN COLLECTOR ─────────────────────────────────────────────────

CATEGORY_COLLECTORS = {
    "company": collect_company_news,
    "geopolitical": collect_geopolitical,
    "macro": collect_macro,
    "commodities": collect_commodities,
    "currencies": collect_currencies,
    "sectors": collect_sectors,
    "sentiment": collect_sentiment,
}


def collect_all(target_date: str, tickers: list = None, categories: list = None,
                force: bool = False) -> dict:
    """Collect all missing categories for a date."""
    if tickers is None:
        tickers = DEFAULT_TICKERS
    if categories is None:
        categories = ALL_CATEGORIES

    results = {}
    for cat in categories:
        if cat not in CATEGORY_COLLECTORS:
            print(f"  Unknown category: {cat}")
            continue

        already = category_exists(target_date, cat)
        if already and not force:
            print(f"  {cat:15s} — already collected, skipping")
            results[cat] = "skipped"
            continue

        print(f"  {cat:15s} — collecting...", end=" ")
        if cat == "company":
            count = collect_company_news(target_date, tickers, force)
        else:
            count = CATEGORY_COLLECTORS[cat](target_date, force)
        print(f"{count} items")
        results[cat] = count

    return results


def show_status(days: int = 7):
    """Show collection status for recent days."""
    today = date.today()
    print(f"\n{'Date':<14}", end="")
    for cat in ALL_CATEGORIES:
        print(f"{cat[:8]:>10}", end="")
    print()
    print("-" * (14 + 10 * len(ALL_CATEGORIES)))

    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        print(f"{d:<14}", end="")
        for cat in ALL_CATEGORIES:
            if category_exists(d, cat):
                # Count files/items
                cat_dir = os.path.join(get_date_dir(d), cat)
                files = [f for f in os.listdir(cat_dir) if f.endswith(".json")]
                print(f"{'yes(' + str(len(files)) + ')':>10}", end="")
            else:
                print(f"{'MISSING':>10}", end="")
        print()


def load_category(target_date: str, category: str) -> dict:
    """Load all data for a category on a given date. Used by the agent."""
    cat_dir = os.path.join(get_date_dir(target_date), category)
    if not os.path.exists(cat_dir):
        return {"status": "not_collected"}

    data = {}
    for f in os.listdir(cat_dir):
        if f.endswith(".json"):
            with open(os.path.join(cat_dir, f), encoding="utf-8") as fh:
                data[f.replace(".json", "")] = json.load(fh)
    return data


def generate_briefing(target_date: str, ticker: str = None) -> str:
    """Generate a compact daily news briefing for the agent.

    Returns a summary string — headlines only, key numbers highlighted,
    grouped by category. This is what Claude reads, not the raw JSON.

    Args:
        target_date: date string
        ticker: if provided, includes company-specific news for this ticker
    """
    lines = [f"=== DAILY BRIEFING: {target_date} ===\n"]

    # SENTIMENT — market mood first
    sent = load_category(target_date, "sentiment")
    if "market_mood" in sent:
        mood = sent["market_mood"]
        indicators = mood.get("indicators", {})
        vix = indicators.get("vix", {})
        breadth = indicators.get("breadth", {})
        lines.append("## MARKET MOOD")
        if vix:
            lines.append(f"  VIX: {vix.get('value', '?')} ({vix.get('mood', '')})")
        if breadth:
            lines.append(f"  SPY 1mo: {breadth.get('spy_1mo_pct', '?')}% | Breadth: {breadth.get('signal', '')}")
        headlines = mood.get("market_headlines", [])
        for h in headlines[:3]:
            lines.append(f"  - {h.get('title', '')}")
        lines.append("")

    # COMMODITIES — key prices
    comm = load_category(target_date, "commodities")
    if "prices_and_news" in comm:
        commodities = comm["prices_and_news"].get("commodities", {})
        lines.append("## COMMODITIES")
        for name, data in commodities.items():
            arrow = "+" if data.get("change_pct", 0) >= 0 else ""
            lines.append(f"  {name}: ${data.get('price', '?')} ({arrow}{data.get('change_pct', '?')}%)")
            for a in data.get("articles", [])[:1]:
                lines.append(f"    > {a.get('title', '')}")
        lines.append("")

    # CURRENCIES — key FX
    curr = load_category(target_date, "currencies")
    if "fx" in curr:
        currencies = curr["fx"].get("currencies", {})
        lines.append("## CURRENCIES & YIELDS")
        for name, data in currencies.items():
            arrow = "+" if data.get("change_pct", 0) >= 0 else ""
            lines.append(f"  {name}: {data.get('value', '?')} ({arrow}{data.get('change_pct', '?')}%)")
        lines.append("")

    # SECTORS — rotation
    sec = load_category(target_date, "sectors")
    if "sectors" in sec:
        rotation = sec["sectors"].get("rotation", {})
        lines.append("## SECTOR ROTATION (1 month)")
        leaders = rotation.get("leaders_1mo", [])
        laggards = rotation.get("laggards_1mo", [])
        if leaders:
            lines.append(f"  Leading: {', '.join(leaders)}")
        if laggards:
            lines.append(f"  Lagging: {', '.join(laggards)}")
        lines.append("")

    # GEOPOLITICAL — global events (with summaries if available)
    geo = load_category(target_date, "geopolitical")
    if "events" in geo:
        articles = geo["events"].get("articles", [])
        if articles:
            lines.append("## GEOPOLITICAL")
            for a in articles[:8]:
                source = a.get("source", "")
                lines.append(f"  - {a.get('title', '')} [{source}]")
                if a.get("summary"):
                    # Show first 200 chars of summary, indented
                    lines.append(f"    >> {a['summary'][:200]}")
            lines.append("")

    # MACRO — economic/policy news
    mac = load_category(target_date, "macro")
    if "headlines" in mac:
        articles = mac["headlines"].get("articles", [])
        if articles:
            lines.append("## MACRO / POLICY")
            for a in articles[:8]:
                lines.append(f"  - {a.get('title', '')}")
                if a.get("summary"):
                    lines.append(f"    >> {a['summary'][:200]}")
            lines.append("")

    # COMPANY-SPECIFIC — only if ticker requested (with summaries)
    if ticker:
        comp = load_category(target_date, "company")
        ticker_key = ticker.upper()
        if ticker_key in comp:
            articles = comp[ticker_key].get("articles", [])
            if articles:
                lines.append(f"## {ticker_key} NEWS")
                for a in articles[:6]:
                    pub = a.get("publisher", "")
                    lines.append(f"  - {a.get('title', '')} [{pub}]")
                    if a.get("summary"):
                        lines.append(f"    >> {a['summary'][:200]}")
                lines.append("")

    if len(lines) <= 2:
        lines.append("No news data collected for this date. Run: python tools/news_collector.py")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Category-aware news collector")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date to collect for (YYYY-MM-DD)")
    parser.add_argument("--category", nargs="+", help="Specific categories to collect")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers for company news")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already collected")
    parser.add_argument("--status", action="store_true", help="Show collection status")
    parser.add_argument("--briefing", action="store_true", help="Generate compact briefing for agent")
    parser.add_argument("--ticker", help="Ticker to include in briefing")
    parser.add_argument("--days", type=int, default=7, help="Days to show in status")
    args = parser.parse_args()

    if args.status:
        show_status(args.days)
        return

    if args.briefing:
        briefing = generate_briefing(args.date, args.ticker)
        print(briefing.encode("ascii", errors="replace").decode("ascii"))
        return

    target_date = args.date
    tickers = [t.upper() for t in args.tickers] if args.tickers else None
    categories = args.category if args.category else None

    print(f"News Collection for {target_date}")
    print("=" * 50)
    results = collect_all(target_date, tickers, categories, args.force)
    print("=" * 50)

    collected = sum(1 for v in results.values() if v != "skipped")
    skipped = sum(1 for v in results.values() if v == "skipped")
    print(f"Done: {collected} collected, {skipped} already had data")


if __name__ == "__main__":
    main()

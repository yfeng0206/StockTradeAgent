"""Unified data loader — checks local cache first, pulls live if missing.

Works the same for historical simulation and real-time:
  1. Check data/news/{date}/{category}/ → if exists, use it
  2. If missing → call the appropriate tool to fetch it
  3. Save to folder so next time it's cached

This way historical runs use pre-downloaded data, and real-time runs
auto-fetch what's needed. Same code path, same interface.

Usage:
    from data_loader import DataLoader
    loader = DataLoader()

    # This works for BOTH historical and real-time:
    news = loader.get_news("2026-03-25", ticker="AAPL")
    earnings = loader.get_earnings("AAPL", "2026-03-25")
    macro = loader.get_macro("2026-03-25")
    geo = loader.get_geopolitical("2026-03-25")
"""

import json
import os
import sys
import subprocess
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
NEWS_DIR = os.path.join(BASE_DIR, "data", "news")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
CACHE_DIR = os.path.join(BASE_DIR, "eval", "cache")


class DataLoader:
    """Check folder first → use cached. Missing → pull live. Same interface."""

    def __init__(self, live_mode: bool = False):
        """
        live_mode=False: only read from existing files, never fetch (safe for backtests)
        live_mode=True: fetch missing data by calling tools (for real-time use)
        """
        self.live_mode = live_mode
        self._earnings_cache = {}  # {ticker: data from yfinance}

    # ─── HELPERS ────────────────────────────────────────────────────

    def _read_json(self, filepath: str) -> dict:
        """Read a JSON file if it exists."""
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_json(self, filepath: str, data: dict):
        """Save JSON, creating directories as needed."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _run_tool(self, script: str, args: list = None) -> dict:
        """Run a Python tool and return parsed JSON output."""
        cmd = [sys.executable, os.path.join(TOOLS_DIR, script)]
        if args:
            cmd.extend(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=TOOLS_DIR)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception:
            pass
        return None

    # ─── COMPANY NEWS ───────────────────────────────────────────────

    def get_company_news(self, ticker: str, target_date: str) -> dict:
        """Get company news for a ticker on a date."""
        filepath = os.path.join(NEWS_DIR, target_date, "company", f"{ticker}.json")
        data = self._read_json(filepath)
        if data:
            return data

        # Not cached → fetch live if allowed
        if self.live_mode:
            data = self._run_tool("fetch_news.py", [ticker])
            if data:
                self._save_json(filepath, data)
                return data

        return {"articles": [], "status": "not_available"}

    # ─── GEOPOLITICAL NEWS ──────────────────────────────────────────

    def get_geopolitical(self, target_date: str) -> dict:
        """Get geopolitical events for a date. Checks GDELT + Wikipedia."""
        geo_dir = os.path.join(NEWS_DIR, target_date, "geopolitical")

        # Check GDELT
        gdelt_path = os.path.join(geo_dir, "events.json")
        gdelt_data = self._read_json(gdelt_path)

        # Check Wikipedia
        wiki_path = os.path.join(geo_dir, "wiki_events.json")
        wiki_data = self._read_json(wiki_path)

        if gdelt_data or wiki_data:
            return {
                "gdelt": gdelt_data,
                "wikipedia": wiki_data,
                "has_data": True,
            }

        # Not cached → fetch live if allowed
        if self.live_mode:
            # Try GDELT for today's news
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_geopolitical
                collect_geopolitical(target_date, force=True)
                gdelt_data = self._read_json(gdelt_path)
                if gdelt_data:
                    return {"gdelt": gdelt_data, "wikipedia": None, "has_data": True}
            except Exception:
                pass

        # Try lookback — find nearest available date
        from datetime import timedelta
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        for i in range(1, 15):
            check = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
            check_dir = os.path.join(NEWS_DIR, check, "geopolitical")
            for fname in ["events.json", "wiki_events.json"]:
                fpath = os.path.join(check_dir, fname)
                cached = self._read_json(fpath)
                if cached:
                    return {"data": cached, "has_data": True, "source_date": check}

        return {"has_data": False}

    # ─── MACRO / ECONOMIC ───────────────────────────────────────────

    def get_macro(self, target_date: str) -> dict:
        """Get macro/economic headlines for a date."""
        filepath = os.path.join(NEWS_DIR, target_date, "macro", "headlines.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_macro
                collect_macro(target_date, force=True)
                return self._read_json(filepath) or {"articles": [], "status": "fetch_failed"}
            except Exception:
                pass

        return {"articles": [], "status": "not_available"}

    # ─── COMMODITIES ────────────────────────────────────────────────

    def get_commodities(self, target_date: str) -> dict:
        """Get commodity prices and news."""
        filepath = os.path.join(NEWS_DIR, target_date, "commodities", "prices_and_news.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_commodities
                collect_commodities(target_date, force=True)
                return self._read_json(filepath) or {"commodities": {}, "status": "fetch_failed"}
            except Exception:
                pass

        return {"commodities": {}, "status": "not_available"}

    # ─── CURRENCIES ─────────────────────────────────────────────────

    def get_currencies(self, target_date: str) -> dict:
        """Get currency/yield data."""
        filepath = os.path.join(NEWS_DIR, target_date, "currencies", "fx.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_currencies
                collect_currencies(target_date, force=True)
                return self._read_json(filepath) or {"currencies": {}, "status": "fetch_failed"}
            except Exception:
                pass

        return {"currencies": {}, "status": "not_available"}

    # ─── SECTORS ────────────────────────────────────────────────────

    def get_sectors(self, target_date: str) -> dict:
        """Get sector performance and rotation."""
        filepath = os.path.join(NEWS_DIR, target_date, "sectors", "sectors.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_sectors
                collect_sectors(target_date, force=True)
                return self._read_json(filepath) or {"sectors": {}, "status": "fetch_failed"}
            except Exception:
                pass

        return {"sectors": {}, "status": "not_available"}

    # ─── SENTIMENT ──────────────────────────────────────────────────

    def get_sentiment(self, target_date: str) -> dict:
        """Get market sentiment (VIX, breadth)."""
        filepath = os.path.join(NEWS_DIR, target_date, "sentiment", "market_mood.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            sys.path.insert(0, TOOLS_DIR)
            try:
                from news_collector import collect_sentiment
                collect_sentiment(target_date, force=True)
                return self._read_json(filepath) or {"indicators": {}, "status": "fetch_failed"}
            except Exception:
                pass

        return {"indicators": {}, "status": "not_available"}

    # ─── EARNINGS ───────────────────────────────────────────────────

    def get_earnings(self, ticker: str, target_date: str) -> dict:
        """Get earnings data for a ticker. Checks events calendar first, then live.

        Returns: {has_earnings, date, surprise_pct, signal, eps_actual, eps_estimate}
        """
        # Check events calendar cache
        cal_path = os.path.join(CACHE_DIR, "events_calendar.json")
        if os.path.exists(cal_path):
            if not hasattr(self, '_events_cal'):
                self._events_cal = self._read_json(cal_path) or {}
            if ticker in self._events_cal:
                from datetime import timedelta
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                for event in self._events_cal[ticker]:
                    if event.get("type") != "earnings":
                        continue
                    event_date = event.get("date", "")
                    if not event_date:
                        continue
                    try:
                        event_dt = datetime.strptime(event_date, "%Y-%m-%d")
                        days_diff = (target_dt - event_dt).days
                        if 0 <= days_diff <= 3:  # Earnings happened 0-3 days ago
                            return {
                                "has_earnings": True,
                                "date": event_date,
                                "days_since": days_diff,
                                "surprise_pct": event.get("surprisePercent"),
                                "signal": event.get("signal", "neutral"),
                                "eps_actual": event.get("epsActual"),
                                "eps_estimate": event.get("epsEstimate"),
                                "source": "events_calendar",
                            }
                    except Exception:
                        continue

        # Not in calendar → try live fetch
        if self.live_mode:
            data = self._run_tool("earnings.py", [ticker])
            if data:
                # Check if earnings just happened (within 3 days)
                next_date = data.get("next_earnings_date")
                eps_trailing = data.get("eps_trailing")
                # Save for future reference
                earnings_dir = os.path.join(NEWS_DIR, target_date, "earnings")
                self._save_json(os.path.join(earnings_dir, f"{ticker}.json"), data)
                return {
                    "has_earnings": False,  # Can't confirm past earnings from this
                    "next_earnings": next_date,
                    "eps_trailing": eps_trailing,
                    "analyst_targets": data.get("analyst_price_target"),
                    "source": "live_fetch",
                }

        return {"has_earnings": False, "source": "not_available"}

    # ─── FUNDAMENTALS ───────────────────────────────────────────────

    def get_fundamentals(self, ticker: str, target_date: str) -> dict:
        """Get fundamental data. Only available live (can't get historical)."""
        filepath = os.path.join(NEWS_DIR, target_date, "fundamentals", f"{ticker}.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            data = self._run_tool("fetch_fundamentals.py", [ticker])
            if data:
                self._save_json(filepath, data)
                return data

        return {"status": "not_available"}

    # ─── INSIDER ACTIVITY ───────────────────────────────────────────

    def get_insider(self, ticker: str, target_date: str) -> dict:
        """Get insider trading data. Only available live."""
        filepath = os.path.join(NEWS_DIR, target_date, "insider", f"{ticker}.json")
        data = self._read_json(filepath)
        if data:
            return data

        if self.live_mode:
            data = self._run_tool("insider_activity.py", [ticker])
            if data:
                self._save_json(filepath, data)
                return data

        return {"status": "not_available"}

    # ─── ALL DATA FOR A DATE ────────────────────────────────────────

    def get_daily_briefing(self, target_date: str, ticker: str = None) -> dict:
        """Get everything available for a date. One call, checks all sources."""
        briefing = {
            "date": target_date,
            "geopolitical": self.get_geopolitical(target_date),
            "macro": self.get_macro(target_date),
            "commodities": self.get_commodities(target_date),
            "currencies": self.get_currencies(target_date),
            "sectors": self.get_sectors(target_date),
            "sentiment": self.get_sentiment(target_date),
        }
        if ticker:
            briefing["company_news"] = self.get_company_news(ticker, target_date)
            briefing["earnings"] = self.get_earnings(ticker, target_date)
        return briefing

    def check_availability(self, target_date: str) -> dict:
        """Check what data is available vs missing for a date."""
        categories = ["company", "geopolitical", "macro", "commodities",
                       "currencies", "sectors", "sentiment"]
        status = {}
        for cat in categories:
            cat_dir = os.path.join(NEWS_DIR, target_date, cat)
            if os.path.exists(cat_dir) and any(f.endswith(".json") for f in os.listdir(cat_dir)):
                files = [f for f in os.listdir(cat_dir) if f.endswith(".json")]
                status[cat] = {"available": True, "files": len(files)}
            else:
                status[cat] = {"available": False}
        return status


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified data loader")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--live", action="store_true", help="Enable live fetching for missing data")
    parser.add_argument("--check", action="store_true", help="Check data availability")
    args = parser.parse_args()

    loader = DataLoader(live_mode=args.live)

    if args.check:
        status = loader.check_availability(args.date)
        print(f"Data availability for {args.date}:")
        for cat, info in status.items():
            icon = "YES" if info["available"] else "NO "
            print(f"  [{icon}] {cat}")
    else:
        briefing = loader.get_daily_briefing(args.date, args.ticker)
        for key, val in briefing.items():
            if isinstance(val, dict):
                has = val.get("has_data", val.get("has_earnings", bool(val.get("articles"))))
                print(f"  {key}: {'HAS DATA' if has else 'no data'}")
            else:
                print(f"  {key}: {type(val)}")

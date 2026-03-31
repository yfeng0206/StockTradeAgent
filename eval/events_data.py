"""Fetch historical earnings events and SEC filing dates for backtest use.

Provides event signals that strategies can use as "news proxies" in historical simulations.
"""

import json
import os
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SEC_HEADERS = {
    "User-Agent": "ConsensusAITrader/1.0 (garyfeng@example.com)",
    "Accept-Encoding": "gzip, deflate",
}


def fetch_earnings_events(ticker: str) -> list:
    """Fetch historical earnings dates and surprises from yfinance.

    Uses earnings_dates which gives EXACT dates + surprise data
    going back ~25 quarters (~6 years).
    """
    stock = yf.Ticker(ticker)
    events = []

    # Primary source: earnings_dates (has exact dates + surprise %)
    try:
        ed = stock.earnings_dates
        if ed is not None and not ed.empty:
            for idx, row in ed.iterrows():
                # idx is the earnings date (Timestamp with timezone)
                earnings_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]

                # Skip future earnings with no reported data
                reported_eps = row.get("Reported EPS")
                if pd.isna(reported_eps):
                    continue

                surprise_pct = row.get("Surprise(%)")
                eps_estimate = row.get("EPS Estimate")

                # Determine signal strength
                signal = "neutral"
                if pd.notna(surprise_pct):
                    if surprise_pct > 5:
                        signal = "strong_beat"
                    elif surprise_pct > 0:
                        signal = "beat"
                    elif surprise_pct > -5:
                        signal = "miss"
                    else:
                        signal = "strong_miss"

                events.append({
                    "ticker": ticker,
                    "type": "earnings",
                    "date": earnings_date,
                    "date_source": "yfinance_earnings_dates",
                    "epsActual": round(float(reported_eps), 4) if pd.notna(reported_eps) else None,
                    "epsEstimate": round(float(eps_estimate), 4) if pd.notna(eps_estimate) else None,
                    "surprisePercent": round(float(surprise_pct) / 100, 4) if pd.notna(surprise_pct) else None,
                    "signal": signal,
                })
    except Exception:
        pass

    # Fallback: earnings_history (has surprise but no dates — old method)
    if not events:
        try:
            eh = stock.earnings_history
            if eh is not None and not eh.empty:
                for _, row in eh.iterrows():
                    event = {"ticker": ticker, "type": "earnings"}
                    for col in eh.columns:
                        val = row[col]
                        if pd.notna(val):
                            if isinstance(val, (pd.Timestamp, datetime)):
                                event[str(col)] = val.strftime("%Y-%m-%d")
                            elif isinstance(val, (int, float)):
                                event[str(col)] = round(float(val), 4)
                            else:
                                event[str(col)] = str(val)
                    events.append(event)
        except Exception:
            pass

    return events


def fetch_sec_filing_dates(ticker: str) -> list:
    """Fetch SEC filing dates (10-K, 10-Q, 8-K) from EDGAR."""
    events = []
    try:
        # Resolve CIK
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        cik = ""
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                cik = str(entry["cik_str"]).zfill(10)
                break
        if not cik:
            return events

        # Fetch submissions
        sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(sub_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        sub_data = resp.json()

        recent = sub_data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])

        for i in range(len(forms)):
            if forms[i] in ["10-K", "10-Q", "8-K"]:
                events.append({
                    "ticker": ticker,
                    "type": "sec_filing",
                    "form": forms[i],
                    "date": dates[i],
                })
    except Exception:
        pass

    return events


def build_events_calendar(tickers: list, cache: bool = True) -> dict:
    """Build a complete events calendar for all tickers.

    Returns: {ticker: [events sorted by date]}
    """
    cache_path = os.path.join(CACHE_DIR, "events_calendar.json")
    os.makedirs(CACHE_DIR, exist_ok=True)

    if cache and os.path.exists(cache_path):
        # Use cache if less than 24 hours old
        mtime = os.path.getmtime(cache_path)
        if (datetime.now().timestamp() - mtime) < 86400:
            with open(cache_path) as f:
                return json.load(f)

    print("Building events calendar...")
    calendar = {}
    for ticker in tickers:
        events = []

        # Earnings events
        earnings = fetch_earnings_events(ticker)
        events.extend(earnings)

        # SEC filings
        filings = fetch_sec_filing_dates(ticker)
        events.extend(filings)

        # Infer earnings dates from 10-Q filing dates
        # Logic: 10-Q is filed ~30-45 days after quarter end. Earnings are reported
        # ~1-2 weeks before the 10-Q filing. So earnings_date ≈ 10-Q_date - 14 days.
        tenq_dates = sorted([e["date"] for e in filings if e.get("form") == "10-Q"])
        dateless_earnings = [e for e in earnings if not e.get("date") and not e.get("Earnings Date")]

        if tenq_dates and dateless_earnings:
            # Match earnings to 10-Q filings (most recent 10-Qs match most recent earnings)
            # Reverse both to match newest first
            tenq_reversed = list(reversed(tenq_dates))
            for i, earn in enumerate(dateless_earnings):
                if i < len(tenq_reversed):
                    tenq_date = tenq_reversed[i]
                    # Earnings ~14 days before 10-Q filing
                    try:
                        _td = timedelta
                        inferred = (datetime.strptime(tenq_date, "%Y-%m-%d") - _td(days=14)).strftime("%Y-%m-%d")
                        earn["date"] = inferred
                        earn["date_source"] = "inferred_from_10Q"
                    except Exception:
                        pass

        # Sort by date
        events.sort(key=lambda x: x.get("date", x.get("Earnings Date", "9999")))
        calendar[ticker] = events

        dated_earnings = sum(1 for e in earnings if e.get("date"))
        print(f"  {ticker}: {len(earnings)} earnings ({dated_earnings} dated) + {len(filings)} filings")

    if cache:
        with open(cache_path, "w") as f:
            json.dump(calendar, f, indent=2, default=str)

    return calendar


def get_events_near_date(calendar: dict, ticker: str, target_date: str,
                         window_days: int = 14, past_only: bool = False) -> list:
    """Get events near a target date for a ticker.

    TEMPORAL GATING: When past_only=True, only returns events that occurred
    ON or BEFORE target_date. This prevents look-ahead bias in simulation.
    The agent on date T should not know about events on T+1.
    """
    if ticker not in calendar:
        return []

    target = pd.Timestamp(target_date)
    nearby = []

    for event in calendar[ticker]:
        event_date_str = event.get("date", event.get("Earnings Date", ""))
        if not event_date_str:
            continue
        try:
            event_date = pd.Timestamp(event_date_str)
            days_diff = int((event_date - target).days)

            if past_only:
                # STRICT: only events on or before target date, within window
                if days_diff > 0:
                    continue  # future event — agent can't see this
                if abs(days_diff) > window_days:
                    continue
            else:
                if abs(days_diff) > window_days:
                    continue

            event_copy = dict(event)
            event_copy["days_from_target"] = days_diff
            nearby.append(event_copy)
        except Exception:
            continue

    return nearby


def compute_earnings_surprise_signal(calendar: dict, ticker: str, date: str) -> dict:
    """Compute an earnings-based event signal for a given date.

    Returns signal info if there was a recent earnings event, otherwise None.
    """
    # STRICT TEMPORAL GATING: only see past events for surprise data
    # For "upcoming" check, we allow a small forward window (public calendar dates)
    past_events = get_events_near_date(calendar, ticker, date, window_days=45, past_only=True)
    future_events = get_events_near_date(calendar, ticker, date, window_days=14, past_only=False)
    past_earnings = [e for e in past_events if e.get("type") == "earnings"]
    future_earnings = [e for e in future_events if e.get("type") == "earnings" and e.get("days_from_target", 0) > 0]
    earnings = past_earnings  # surprise data only from past

    if not earnings and not future_earnings:
        return {"has_recent_earnings": False}

    if not earnings:
        # No past earnings, but maybe upcoming (publicly known calendar dates)
        if future_earnings:
            days_until = future_earnings[0]["days_from_target"]
            return {
                "has_recent_earnings": False,
                "upcoming_earnings": True,
                "days_until_earnings": days_until,
                "signal": "pre_earnings_caution" if days_until <= 7 else "normal",
            }
        return {"has_recent_earnings": False}

    latest = earnings[-1]  # most recent past earnings
    surprise_pct = latest.get("surprisePercent", latest.get("Surprise(%)", None))

    # Use pre-computed signal if available (from earnings_dates source)
    signal = latest.get("signal", "neutral")
    if signal == "neutral" and surprise_pct is not None:
        # surprisePercent is stored as decimal (0.05 = 5%), so thresholds are decimal
        if surprise_pct > 0.05:
            signal = "strong_beat"
        elif surprise_pct > 0:
            signal = "beat"
        elif surprise_pct > -0.05:
            signal = "miss"
        else:
            signal = "strong_miss"

    return {
        "has_recent_earnings": True,
        "days_since_earnings": abs(latest.get("days_from_target", 0)),
        "surprise_pct": surprise_pct,
        "signal": signal,
    }


if __name__ == "__main__":
    # Quick test
    tickers = ["AAPL", "NVDA", "TSLA"]
    cal = build_events_calendar(tickers, cache=False)
    for t in tickers:
        print(f"\n{t}: {len(cal.get(t, []))} events")
        signal = compute_earnings_surprise_signal(cal, t, "2025-11-01")
        print(f"  Signal near 2025-11-01: {signal}")

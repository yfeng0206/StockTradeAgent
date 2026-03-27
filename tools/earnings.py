"""Fetch earnings data: history, surprises, and upcoming dates."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd


def fetch_earnings(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    # Earnings history with surprises
    earnings_history = []
    try:
        eh = stock.earnings_history
        if eh is not None and not eh.empty:
            for _, row in eh.iterrows():
                entry = {}
                for col in eh.columns:
                    val = row[col]
                    if pd.notna(val):
                        if isinstance(val, (pd.Timestamp, datetime)):
                            entry[str(col)] = val.strftime("%Y-%m-%d")
                        elif isinstance(val, (int, float)):
                            entry[str(col)] = round(float(val), 4)
                        else:
                            entry[str(col)] = str(val)
                earnings_history.append(entry)
    except Exception:
        pass

    # Quarterly earnings
    quarterly_earnings = []
    try:
        qe = stock.quarterly_earnings
        if qe is not None and not qe.empty:
            for idx, row in qe.iterrows():
                entry = {"quarter": str(idx)}
                if pd.notna(row.get("Revenue")):
                    entry["revenue"] = float(row["Revenue"])
                if pd.notna(row.get("Earnings")):
                    entry["earnings"] = float(row["Earnings"])
                quarterly_earnings.append(entry)
    except Exception:
        pass

    # Upcoming earnings date
    next_earnings = None
    try:
        cal = stock.calendar
        if cal is not None:
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed:
                    if isinstance(ed, list) and len(ed) > 0:
                        next_earnings = str(ed[0])
                    else:
                        next_earnings = str(ed)
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                if "Earnings Date" in cal.index:
                    val = cal.loc["Earnings Date"].iloc[0]
                    next_earnings = str(val)
    except Exception:
        pass

    # EPS data
    eps_trailing = info.get("trailingEps")
    eps_forward = info.get("forwardEps")

    # Analyst estimates
    analyst_target = info.get("targetMeanPrice")
    analyst_low = info.get("targetLowPrice")
    analyst_high = info.get("targetHighPrice")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    num_analysts = info.get("numberOfAnalystOpinions")

    upside_pct = None
    if analyst_target and current_price and current_price > 0:
        upside_pct = round((analyst_target - current_price) / current_price * 100, 2)

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "next_earnings_date": next_earnings,
        "eps_trailing": round(eps_trailing, 2) if eps_trailing else None,
        "eps_forward": round(eps_forward, 2) if eps_forward else None,
        "analyst_price_target": {
            "mean": analyst_target,
            "low": analyst_low,
            "high": analyst_high,
            "upside_pct": upside_pct,
            "num_analysts": num_analysts,
        },
        "earnings_history": earnings_history[:8],
        "quarterly_earnings": quarterly_earnings[:8],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch earnings data")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()

    result = fetch_earnings(args.ticker.upper())
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

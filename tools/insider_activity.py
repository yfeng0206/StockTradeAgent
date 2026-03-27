"""Fetch insider trading activity from SEC EDGAR Form 4 filings and yfinance."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd
import requests

from config import SEC_USER_AGENT

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def fetch_insider_yfinance(ticker: str) -> list:
    """Get insider transactions from yfinance."""
    stock = yf.Ticker(ticker)
    transactions = []

    try:
        insiders = stock.insider_transactions
        if insiders is not None and not insiders.empty:
            for _, row in insiders.head(20).iterrows():
                tx = {
                    "insider": str(row.get("Insider", "")),
                    "relation": str(row.get("Position", row.get("Relation", ""))),
                    "transaction": str(row.get("Transaction", row.get("Text", ""))),
                    "date": str(row.get("Start Date", row.get("Date", ""))),
                    "shares": int(row["Shares"]) if pd.notna(row.get("Shares")) else None,
                    "value": float(row["Value"]) if pd.notna(row.get("Value")) else None,
                }
                transactions.append(tx)
    except Exception:
        pass

    return transactions


def fetch_insider_holdings(ticker: str) -> list:
    """Get major holders info from yfinance."""
    stock = yf.Ticker(ticker)
    holders = []

    try:
        major = stock.major_holders
        if major is not None and not major.empty:
            for _, row in major.iterrows():
                holders.append({
                    "metric": str(row.iloc[1]) if len(row) > 1 else "",
                    "value": str(row.iloc[0]) if len(row) > 0 else "",
                })
    except Exception:
        pass

    try:
        inst = stock.institutional_holders
        if inst is not None and not inst.empty:
            top_inst = []
            for _, row in inst.head(10).iterrows():
                top_inst.append({
                    "holder": str(row.get("Holder", "")),
                    "shares": int(row["Shares"]) if pd.notna(row.get("Shares")) else None,
                    "date_reported": str(row.get("Date Reported", "")),
                    "pct_out": float(row["% Out"]) if pd.notna(row.get("% Out")) else None,
                })
            return holders, top_inst
    except Exception:
        pass

    return holders, []


def fetch_insider_activity(ticker: str) -> dict:
    transactions = fetch_insider_yfinance(ticker)
    holders, institutional = fetch_insider_holdings(ticker)

    # Summarize buy/sell activity
    buys = sum(1 for t in transactions if "buy" in t.get("transaction", "").lower() or "purchase" in t.get("transaction", "").lower())
    sells = sum(1 for t in transactions if "sale" in t.get("transaction", "").lower() or "sell" in t.get("transaction", "").lower())

    if buys > sells * 2:
        insider_signal = "Strong insider buying — Bullish signal"
    elif buys > sells:
        insider_signal = "Net insider buying — Mildly bullish"
    elif sells > buys * 2:
        insider_signal = "Heavy insider selling — Bearish signal (but could be routine)"
    elif sells > buys:
        insider_signal = "Net insider selling — Monitor closely"
    else:
        insider_signal = "Mixed/neutral insider activity"

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "insider_signal": insider_signal,
        "recent_buys": buys,
        "recent_sells": sells,
        "transactions": transactions[:15],
        "major_holders": holders,
        "top_institutional_holders": institutional,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch insider activity")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()

    result = fetch_insider_activity(args.ticker.upper())
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

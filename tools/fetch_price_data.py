"""Fetch price data (OHLCV) for a stock ticker via yfinance."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd


def fetch_price_data(ticker: str, period: str = "1y", interval: str = "1d") -> dict:
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period, interval=interval)

    if hist.empty:
        return {"error": f"No price data found for {ticker}", "ticker": ticker}

    info = stock.info or {}
    current = hist.iloc[-1]
    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current["Close"]

    # 52-week high/low from the data we have
    high_52w = float(hist["High"].max())
    low_52w = float(hist["Low"].min())

    # Daily returns for basic stats
    returns = hist["Close"].pct_change().dropna()

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current_price": round(float(current["Close"]), 2),
        "previous_close": round(float(prev_close), 2),
        "daily_change_pct": round(((current["Close"] - prev_close) / prev_close) * 100, 2),
        "open": round(float(current["Open"]), 2),
        "high": round(float(current["High"]), 2),
        "low": round(float(current["Low"]), 2),
        "volume": int(current["Volume"]),
        "avg_volume_30d": int(hist["Volume"].tail(30).mean()) if len(hist) >= 30 else int(hist["Volume"].mean()),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "pct_from_52w_high": round(((current["Close"] - high_52w) / high_52w) * 100, 2),
        "pct_from_52w_low": round(((current["Close"] - low_52w) / low_52w) * 100, 2),
        "market_cap": info.get("marketCap"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange", ""),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "volatility_30d": round(float(returns.tail(30).std() * (252 ** 0.5) * 100), 2) if len(returns) >= 30 else None,
        "recent_prices": [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
            for idx, row in hist.tail(10).iterrows()
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch stock price data")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--period", default="1y", help="Data period (1d,5d,1mo,3mo,6mo,1y,2y,5y,max)")
    parser.add_argument("--interval", default="1d", help="Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo)")
    args = parser.parse_args()

    result = fetch_price_data(args.ticker.upper(), args.period, args.interval)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

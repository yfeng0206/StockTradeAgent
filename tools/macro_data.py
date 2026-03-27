"""Fetch macro economic data. Uses yfinance market proxies (no API key needed).
Optionally uses FRED API if FRED_API_KEY is set for richer data."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd

from config import FRED_API_KEY


def fetch_macro_yfinance() -> dict:
    """Fetch macro indicators via yfinance market tickers."""
    tickers = {
        "^GSPC": "sp500",
        "^DJI": "dow_jones",
        "^IXIC": "nasdaq",
        "^RUT": "russell_2000",
        "^VIX": "vix",
        "^TNX": "treasury_10y_yield",
        "^TYX": "treasury_30y_yield",
        "^FVX": "treasury_5y_yield",
        "^IRX": "treasury_3m_yield",
        "GC=F": "gold",
        "CL=F": "crude_oil",
        "DX-Y.NYB": "us_dollar_index",
    }

    # Sector ETFs
    sector_tickers = {
        "XLK": "technology",
        "XLF": "financials",
        "XLV": "healthcare",
        "XLE": "energy",
        "XLI": "industrials",
        "XLP": "consumer_staples",
        "XLY": "consumer_discretionary",
        "XLU": "utilities",
        "XLRE": "real_estate",
        "XLB": "materials",
        "XLC": "communication_services",
    }

    market = {}
    for symbol, name in tickers.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
                change_pct = round((current - prev) / prev * 100, 2) if prev != 0 else 0
                market[name] = {
                    "value": round(current, 2),
                    "change_pct": change_pct,
                }
        except Exception:
            continue

    sectors = {}
    all_sector_symbols = list(sector_tickers.keys())
    try:
        data = yf.download(all_sector_symbols, period="1mo", progress=False, threads=True)
        if not data.empty:
            closes = data["Close"] if "Close" in data.columns.get_level_values(0) else data
            for symbol, name in sector_tickers.items():
                if symbol in closes.columns:
                    series = closes[symbol].dropna()
                    if len(series) >= 2:
                        current = float(series.iloc[-1])
                        month_ago = float(series.iloc[0])
                        sectors[name] = {
                            "current": round(current, 2),
                            "month_change_pct": round((current - month_ago) / month_ago * 100, 2),
                        }
    except Exception:
        pass

    return {"market_indicators": market, "sector_performance_1mo": sectors}


def fetch_macro_fred() -> dict:
    """Fetch macro data from FRED (requires API key)."""
    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)

        series_map = {
            "DGS10": "treasury_10y",
            "DGS2": "treasury_2y",
            "T10Y2Y": "yield_curve_10y_2y",
            "FEDFUNDS": "fed_funds_rate",
            "CPIAUCSL": "cpi",
            "UNRATE": "unemployment_rate",
            "GDP": "gdp",
            "UMCSENT": "consumer_sentiment",
            "VIXCLS": "vix",
        }

        fred_data = {}
        for series_id, name in series_map.items():
            try:
                s = fred.get_series(series_id, observation_start="2024-01-01")
                if s is not None and not s.empty:
                    latest = s.dropna().iloc[-1]
                    fred_data[name] = {
                        "value": round(float(latest), 2),
                        "date": s.dropna().index[-1].strftime("%Y-%m-%d"),
                    }
            except Exception:
                continue

        return {"fred_indicators": fred_data}
    except ImportError:
        return {"fred_indicators": {"note": "fredapi not installed"}}
    except Exception as e:
        return {"fred_indicators": {"error": str(e)}}


def fetch_macro() -> dict:
    result = {
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Always get yfinance data (no key needed)
    yf_data = fetch_macro_yfinance()
    result.update(yf_data)

    # Add FRED data if key available
    if FRED_API_KEY:
        fred_data = fetch_macro_fred()
        result.update(fred_data)

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch macro economic data")
    args = parser.parse_args()

    result = fetch_macro()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

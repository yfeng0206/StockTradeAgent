"""Fetch sentiment data: analyst recommendations and available sentiment signals."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd


def fetch_analyst_recommendations(ticker: str) -> dict:
    """Get analyst recommendations from yfinance."""
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    # Current recommendation
    rec = info.get("recommendationKey", "")
    rec_mean = info.get("recommendationMean")  # 1=Strong Buy, 5=Sell
    num_analysts = info.get("numberOfAnalystOpinions")

    # Recommendation history
    rec_history = []
    try:
        recs = stock.recommendations
        if recs is not None and not recs.empty:
            recent = recs.tail(10)
            for idx, row in recent.iterrows():
                entry = {"date": str(idx) if not isinstance(idx, int) else ""}
                for col in recent.columns:
                    val = row[col]
                    if pd.notna(val):
                        entry[str(col)] = int(val) if isinstance(val, (int, float)) else str(val)
                rec_history.append(entry)
    except Exception:
        pass

    # Upgrades/downgrades
    upgrades = []
    try:
        ug = stock.upgrades_downgrades
        if ug is not None and not ug.empty:
            recent_ug = ug.tail(10)
            for idx, row in recent_ug.iterrows():
                entry = {
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                }
                for col in recent_ug.columns:
                    val = row[col]
                    if pd.notna(val):
                        entry[str(col)] = str(val)
                upgrades.append(entry)
    except Exception:
        pass

    return {
        "recommendation": rec,
        "recommendation_mean": rec_mean,
        "num_analysts": num_analysts,
        "recommendation_history": rec_history,
        "recent_upgrades_downgrades": upgrades,
    }


def compute_price_sentiment(ticker: str) -> dict:
    """Derive sentiment signals from price action and options."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")

    if hist.empty:
        return {}

    close = hist["Close"]
    volume = hist["Volume"]

    # Price momentum sentiment
    returns_1w = float((close.iloc[-1] / close.iloc[-5] - 1) * 100) if len(close) >= 5 else None
    returns_1m = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
    returns_3m = float((close.iloc[-1] / close.iloc[0] - 1) * 100)

    # Volume trend
    vol_recent = float(volume.tail(5).mean())
    vol_avg = float(volume.mean())
    vol_trend = "Increasing" if vol_recent > vol_avg * 1.2 else \
                "Decreasing" if vol_recent < vol_avg * 0.8 else "Stable"

    # Simple price action sentiment
    if returns_1w and returns_1w > 5:
        short_term = "Very bullish momentum"
    elif returns_1w and returns_1w > 2:
        short_term = "Bullish momentum"
    elif returns_1w and returns_1w < -5:
        short_term = "Very bearish momentum"
    elif returns_1w and returns_1w < -2:
        short_term = "Bearish momentum"
    else:
        short_term = "Neutral/sideways"

    # Options sentiment (put/call from info)
    info = stock.info or {}

    return {
        "returns_1w_pct": round(returns_1w, 2) if returns_1w else None,
        "returns_1m_pct": round(returns_1m, 2) if returns_1m else None,
        "returns_3m_pct": round(returns_3m, 2),
        "volume_trend": vol_trend,
        "short_term_sentiment": short_term,
        "short_interest": info.get("shortRatio"),
        "short_pct_float": info.get("shortPercentOfFloat"),
    }


def fetch_sentiment(ticker: str) -> dict:
    analyst = fetch_analyst_recommendations(ticker)
    price_sentiment = compute_price_sentiment(ticker)

    # Overall sentiment summary
    signals = []
    if analyst.get("recommendation_mean"):
        mean = analyst["recommendation_mean"]
        if mean <= 2.0:
            signals.append("Analysts: Strong Buy")
        elif mean <= 2.5:
            signals.append("Analysts: Buy")
        elif mean <= 3.5:
            signals.append("Analysts: Hold")
        else:
            signals.append("Analysts: Sell")

    if price_sentiment.get("short_term_sentiment"):
        signals.append(f"Price action: {price_sentiment['short_term_sentiment']}")

    short_pct = price_sentiment.get("short_pct_float")
    if short_pct:
        if short_pct > 0.10:
            signals.append(f"High short interest ({round(short_pct*100, 1)}%) — potential squeeze or bear thesis")
        elif short_pct > 0.05:
            signals.append(f"Moderate short interest ({round(short_pct*100, 1)}%)")

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sentiment_signals": signals,
        "analyst_data": analyst,
        "price_sentiment": price_sentiment,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch sentiment data")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()

    result = fetch_sentiment(args.ticker.upper())
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

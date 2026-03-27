"""Fetch recent news for a stock ticker via yfinance."""

import argparse
import json
from datetime import datetime

import yfinance as yf


def fetch_news(ticker: str, limit: int = 15) -> dict:
    stock = yf.Ticker(ticker)
    news = stock.news or []

    articles = []
    for item in news[:limit]:
        content = item.get("content", {})
        article = {
            "title": content.get("title", item.get("title", "")),
            "publisher": content.get("provider", {}).get("displayName", ""),
            "link": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
            "published": content.get("pubDate", ""),
            "type": item.get("type", ""),
        }
        # Extract thumbnail if available
        thumbnail = content.get("thumbnail")
        if thumbnail and isinstance(thumbnail, dict):
            resolutions = thumbnail.get("resolutions", [])
            if resolutions:
                article["thumbnail"] = resolutions[0].get("url", "")

        articles.append(article)

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "article_count": len(articles),
        "articles": articles,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch stock news")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--limit", type=int, default=15, help="Max articles to return")
    args = parser.parse_args()

    result = fetch_news(args.ticker.upper(), args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

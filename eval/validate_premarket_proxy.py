"""Validate the 80% pre-market proxy against actual pre-market prices.

yfinance provides ~60 days of intraday data with prepost=True.
We fetch 5-minute bars at 9:00-9:25 AM (pre-market) and compare
the last pre-market price against our proxy:

    proxy = 0.2 * T-1_Close + 0.8 * T_Open

This tells us how close our proxy is to real pre-market prices.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Sample of stocks across sectors (not full universe — API rate limits)
SAMPLE_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",   # mega-cap tech
    "JPM", "GS",                                   # financials
    "JNJ", "UNH",                                  # healthcare
    "XOM", "CVX",                                   # energy
    "SPY", "QQQ",                                   # ETFs
]


def fetch_premarket_prices(ticker, days=60):
    """Fetch 5-min bars with pre/post market for last N days.

    Returns DataFrame with columns: date, premarket_price, open, prev_close, proxy
    """
    end = datetime.now()
    start = end - timedelta(days=days)

    # 5m interval, extended hours — use period="60d" (yfinance requires this for 5m)
    tk = yf.Ticker(ticker)
    try:
        df = tk.history(period="60d", interval="5m", prepost=True)
    except Exception as e:
        print(f"  {ticker}: error fetching intraday: {e}")
        return None

    if df.empty:
        print(f"  {ticker}: no intraday data")
        return None

    # Also get daily bars for Open/Close reference
    daily = tk.history(period="90d", interval="1d")
    if daily.empty:
        return None

    results = []
    for date in daily.index:
        date_str = date.strftime("%Y-%m-%d")

        # Get T's Open from daily
        t_open = float(daily.loc[date, "Open"])

        # Get T-1 Close (previous trading day)
        prev_days = daily.index[daily.index < date]
        if len(prev_days) == 0:
            continue
        t1_close = float(daily.loc[prev_days[-1], "Close"])

        # Get pre-market price: last 5m bar before 9:30 AM ET
        day_bars = df[df.index.date == date.date()]
        if day_bars.empty:
            continue

        # Pre-market bars are before 9:30 AM
        premarket_bars = day_bars[day_bars.index.hour < 9]
        # Also include 9:00-9:25 bars
        early_bars = day_bars[(day_bars.index.hour == 9) & (day_bars.index.minute < 30)]
        pm_bars = pd.concat([premarket_bars, early_bars])

        if pm_bars.empty:
            # No pre-market data for this day
            continue

        # Use the last pre-market Close (closest to 9:30)
        actual_premarket = float(pm_bars["Close"].iloc[-1])

        # Our proxy
        proxy = 0.2 * t1_close + 0.8 * t_open

        # Gap
        gap_pct = (t_open - t1_close) / t1_close * 100

        results.append({
            "date": date_str,
            "prev_close": round(t1_close, 2),
            "actual_premarket": round(actual_premarket, 2),
            "proxy": round(proxy, 2),
            "t_open": round(t_open, 2),
            "gap_pct": round(gap_pct, 2),
            "proxy_error_pct": round((proxy - actual_premarket) / actual_premarket * 100, 3),
        })

    return pd.DataFrame(results) if results else None


def main():
    print("=" * 70)
    print("PRE-MARKET PROXY VALIDATION")
    print("Proxy: 0.2 × T-1 Close + 0.8 × T Open")
    print("vs actual last pre-market price (9:00-9:25 AM)")
    print("=" * 70)

    all_errors = []
    per_ticker = {}

    for ticker in SAMPLE_TICKERS:
        print(f"\nFetching {ticker}...")
        df = fetch_premarket_prices(ticker)
        if df is None or df.empty:
            continue

        errors = df["proxy_error_pct"].values
        all_errors.extend(errors)
        per_ticker[ticker] = {
            "days": len(df),
            "mean_error": round(np.mean(np.abs(errors)), 3),
            "median_error": round(np.median(np.abs(errors)), 3),
            "max_error": round(np.max(np.abs(errors)), 3),
            "p95_error": round(np.percentile(np.abs(errors), 95), 3),
        }
        print(f"  {ticker}: {len(df)} days, mean |error| = {per_ticker[ticker]['mean_error']:.3f}%, "
              f"max = {per_ticker[ticker]['max_error']:.3f}%")

    if not all_errors:
        print("\nNo data collected. yfinance may not have pre-market data available.")
        return

    all_errors = np.array(all_errors)
    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print(f"Total days×tickers: {len(all_errors)}")
    print(f"Mean |error|:   {np.mean(np.abs(all_errors)):.3f}%")
    print(f"Median |error|: {np.median(np.abs(all_errors)):.3f}%")
    print(f"P95 |error|:    {np.percentile(np.abs(all_errors), 95):.3f}%")
    print(f"Max |error|:    {np.max(np.abs(all_errors)):.3f}%")
    print(f"Std of error:   {np.std(all_errors):.3f}%")
    print()

    # Interpretation
    mean_err = np.mean(np.abs(all_errors))
    if mean_err < 0.5:
        print("VERDICT: Proxy is excellent (<0.5% mean error). Safe for all historical backtests.")
    elif mean_err < 1.0:
        print("VERDICT: Proxy is good (<1% mean error). Acceptable for historical backtests.")
    elif mean_err < 2.0:
        print("VERDICT: Proxy is fair (1-2% mean error). Use with caution on volatile stocks.")
    else:
        print("VERDICT: Proxy is poor (>2% mean error). Consider adjusting the 0.2/0.8 blend.")

    print("\nPer-ticker breakdown:")
    print(f"{'Ticker':<8} {'Days':>5} {'Mean':>8} {'Median':>8} {'P95':>8} {'Max':>8}")
    for ticker, stats in sorted(per_ticker.items()):
        print(f"{ticker:<8} {stats['days']:>5} {stats['mean_error']:>7.3f}% "
              f"{stats['median_error']:>7.3f}% {stats['p95_error']:>7.3f}% {stats['max_error']:>7.3f}%")


if __name__ == "__main__":
    main()

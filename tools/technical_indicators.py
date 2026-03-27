"""Compute technical indicators for a stock ticker."""

import argparse
import json
import sys
from datetime import datetime

import yfinance as yf
import pandas as pd
import ta


def compute_indicators(ticker: str, period: str = "1y") -> dict:
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)

    if hist.empty:
        return {"error": f"No data found for {ticker}", "ticker": ticker}

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    current_price = float(close.iloc[-1])

    # --- Moving Averages ---
    sma_10 = float(close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else None
    sma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    sma_100 = float(close.rolling(100).mean().iloc[-1]) if len(close) >= 100 else None
    sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    ema_12 = float(close.ewm(span=12).mean().iloc[-1])
    ema_26 = float(close.ewm(span=26).mean().iloc[-1])

    # Trend determination
    trend_signals = []
    if sma_50 and sma_200:
        if sma_50 > sma_200:
            trend_signals.append("Golden Cross (50 > 200 SMA) — Bullish")
        else:
            trend_signals.append("Death Cross (50 < 200 SMA) — Bearish")
    if sma_20:
        if current_price > sma_20:
            trend_signals.append("Price above 20 SMA — Short-term bullish")
        else:
            trend_signals.append("Price below 20 SMA — Short-term bearish")

    # --- RSI ---
    rsi_indicator = ta.momentum.RSIIndicator(close, window=14)
    rsi = float(rsi_indicator.rsi().iloc[-1])
    rsi_signal = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"

    # --- MACD ---
    macd_indicator = ta.trend.MACD(close)
    macd_line = float(macd_indicator.macd().iloc[-1])
    macd_signal_line = float(macd_indicator.macd_signal().iloc[-1])
    macd_histogram = float(macd_indicator.macd_diff().iloc[-1])
    macd_signal = "Bullish" if macd_line > macd_signal_line else "Bearish"

    # --- Bollinger Bands ---
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_upper = float(bb.bollinger_hband().iloc[-1])
    bb_middle = float(bb.bollinger_mavg().iloc[-1])
    bb_lower = float(bb.bollinger_lband().iloc[-1])
    bb_width = round((bb_upper - bb_lower) / bb_middle * 100, 2)
    bb_signal = "Near upper band — potential resistance" if current_price > bb_upper * 0.98 else \
                "Near lower band — potential support" if current_price < bb_lower * 1.02 else "Within bands"

    # --- Stochastic Oscillator ---
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    stoch_k = float(stoch.stoch().iloc[-1])
    stoch_d = float(stoch.stoch_signal().iloc[-1])

    # --- ADX (Trend Strength) ---
    adx_indicator = ta.trend.ADXIndicator(high, low, close)
    adx = float(adx_indicator.adx().iloc[-1])
    adx_signal = "Strong trend" if adx > 25 else "Weak/no trend"

    # --- Volume Analysis ---
    obv = ta.volume.OnBalanceVolumeIndicator(close, volume)
    obv_current = float(obv.on_balance_volume().iloc[-1])
    avg_vol_20 = float(volume.tail(20).mean())
    vol_ratio = round(float(volume.iloc[-1]) / avg_vol_20, 2) if avg_vol_20 > 0 else None
    vol_signal = "High volume" if vol_ratio and vol_ratio > 1.5 else \
                 "Low volume" if vol_ratio and vol_ratio < 0.5 else "Normal volume"

    # --- ATR (Volatility) ---
    atr_indicator = ta.volatility.AverageTrueRange(high, low, close)
    atr = float(atr_indicator.average_true_range().iloc[-1])
    atr_pct = round(atr / current_price * 100, 2)

    # --- Support / Resistance (simple pivot-based) ---
    recent = hist.tail(20)
    pivot = (float(recent["High"].max()) + float(recent["Low"].min()) + current_price) / 3
    support_1 = round(2 * pivot - float(recent["High"].max()), 2)
    resistance_1 = round(2 * pivot - float(recent["Low"].min()), 2)

    # --- Overall Technical Summary ---
    bullish_count = 0
    bearish_count = 0
    if rsi < 30: bullish_count += 1
    elif rsi > 70: bearish_count += 1
    if macd_line > macd_signal_line: bullish_count += 1
    else: bearish_count += 1
    if sma_50 and sma_200 and sma_50 > sma_200: bullish_count += 1
    elif sma_50 and sma_200: bearish_count += 1
    if current_price > (sma_50 or 0): bullish_count += 1
    else: bearish_count += 1
    if adx > 25 and macd_line > macd_signal_line: bullish_count += 1
    elif adx > 25: bearish_count += 1

    total = bullish_count + bearish_count
    tech_score = round(bullish_count / total * 10, 1) if total > 0 else 5.0

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current_price": round(current_price, 2),
        "technical_score": tech_score,
        "technical_bias": "Bullish" if tech_score > 6 else "Bearish" if tech_score < 4 else "Neutral",
        "moving_averages": {
            "sma_10": round(sma_10, 2) if sma_10 else None,
            "sma_20": round(sma_20, 2) if sma_20 else None,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_100": round(sma_100, 2) if sma_100 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "ema_12": round(ema_12, 2),
            "ema_26": round(ema_26, 2),
            "trend_signals": trend_signals,
        },
        "momentum": {
            "rsi_14": round(rsi, 2),
            "rsi_signal": rsi_signal,
            "stochastic_k": round(stoch_k, 2),
            "stochastic_d": round(stoch_d, 2),
        },
        "macd": {
            "macd_line": round(macd_line, 4),
            "signal_line": round(macd_signal_line, 4),
            "histogram": round(macd_histogram, 4),
            "signal": macd_signal,
        },
        "bollinger_bands": {
            "upper": round(bb_upper, 2),
            "middle": round(bb_middle, 2),
            "lower": round(bb_lower, 2),
            "width_pct": bb_width,
            "signal": bb_signal,
        },
        "trend": {
            "adx": round(adx, 2),
            "adx_signal": adx_signal,
        },
        "volume": {
            "current_volume": int(volume.iloc[-1]),
            "avg_volume_20d": int(avg_vol_20),
            "volume_ratio": vol_ratio,
            "volume_signal": vol_signal,
        },
        "volatility": {
            "atr_14": round(atr, 2),
            "atr_pct": atr_pct,
        },
        "support_resistance": {
            "pivot": round(pivot, 2),
            "support_1": support_1,
            "resistance_1": resistance_1,
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Compute technical indicators")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--period", default="1y", help="Data period (1y, 2y, etc.)")
    args = parser.parse_args()

    result = compute_indicators(args.ticker.upper(), args.period)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

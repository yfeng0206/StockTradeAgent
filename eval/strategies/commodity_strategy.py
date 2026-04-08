"""Commodity Strategy — Tracks oil (and other commodities later).

Instead of trading stocks, this strategy trades commodity ETFs/proxies:
  - USO (United States Oil Fund) for crude oil exposure
  - Falls back to XLE (Energy Select Sector) if USO data unavailable

Uses oil price momentum, geopolitical risk from news (wars = oil spikes),
and mean-reversion when oil gets overextended.

This serves as a benchmark: "what if you just tracked oil instead of stocks?"

Rebalances monthly. Single position (oil), can go to cash if bearish.
"""

import os
import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


# Oil proxy tickers in priority order
OIL_PROXIES = ["USO", "XLE", "XOM"]


class CommodityStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 1):
        super().__init__("Commodity", initial_cash, max_positions=1)  # always 1 for commodity
        self.min_score_threshold = 4.0
        self.atr_stop_multiplier = 2.5
        self.trim_threshold_pct = 50.0
        self.events_calendar = events_calendar or {}
        self._invested = False

    @property
    def rebalance_frequency(self) -> str:
        if hasattr(self, '_frequency_override') and self._frequency_override:
            return self._frequency_override
        return "monthly"

    def _get_oil_signal(self, price_data: dict, date: str) -> dict:
        """Analyze oil/energy trend using available proxy data."""
        for proxy in OIL_PROXIES:
            if proxy in price_data and not price_data[proxy].empty:
                df = price_data[proxy]
                mask = self._signal_mask(df, date)
                if not mask.any() or mask.sum() < 30:
                    continue

                close = df.loc[mask, "Close"].tail(252)
                current = float(close.iloc[-1])
                returns = close.pct_change().dropna()

                # Trend
                sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
                sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current
                above_50 = current > sma_50
                above_200 = current > sma_200

                # Momentum
                ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
                ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0

                # Volatility
                vol = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0.3

                # RSI
                delta = close.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if not rs.empty and pd.notna((100 - (100 / (1 + rs))).iloc[-1]) else 50

                return {
                    "proxy": proxy,
                    "price": current,
                    "above_50ma": above_50,
                    "above_200ma": above_200,
                    "ret_1m": ret_1m,
                    "ret_3m": ret_3m,
                    "vol": vol,
                    "rsi": rsi,
                }

        return None

    def _get_geo_oil_signal(self, date: str) -> float:
        """REMOVED — ablation proved news hurts Commodity (-6.5%).
        Oil trend is now purely price-driven (MAs, RSI, momentum)."""
        return 0.0

    def score_stocks(self, universe: list, price_data: dict, date: str, **kwargs) -> list:
        """Score oil proxies — returns at most 1 ticker to buy."""
        oil = self._get_oil_signal(price_data, date)
        if not oil:
            self._last_regime = "no_data"
            return []

        geo_boost = self._get_geo_oil_signal(date)

        # Scoring: should we be in oil or in cash?
        trend_score = 0
        if oil["above_50ma"]: trend_score += 3
        if oil["above_200ma"]: trend_score += 2
        if oil["ret_1m"] > 0: trend_score += 2
        if oil["ret_3m"] > 0: trend_score += 1

        # RSI filter: don't buy extremely overbought
        if oil["rsi"] > 75:
            trend_score -= 2
        elif oil["rsi"] < 30:
            trend_score += 2  # Oversold bounce opportunity

        # Geo boost: wars/sanctions are bullish for oil
        trend_score += geo_boost * 3

        # Decision threshold: buy if score > 4, sell/cash if < 3
        proxy = oil["proxy"]

        self._last_scores[proxy] = {
            "composite": round(trend_score, 2),
            "mode": "OIL",
            "above_50ma": oil["above_50ma"],
            "above_200ma": oil["above_200ma"],
            "ret_1m": round(oil["ret_1m"], 1),
            "ret_3m": round(oil["ret_3m"], 1),
            "rsi": round(oil["rsi"], 1),
            "geo_boost": round(geo_boost, 2),
        }

        self._last_regime = f"oil:{'bullish' if trend_score > 4 else 'bearish' if trend_score < 3 else 'neutral'}"
        # Note: _last_news_summary is set by daily_loop from SignalEngine — don't overwrite it
        # here with a different format (geo_oil=), as downstream strategies (Mix) and base class
        # (snapshot, reasoning log, watchnotes) expect the canonical geo_risk= format.

        if trend_score > 4:
            return [(proxy, trend_score)]
        else:
            return []  # Go to cash

    def execute_rebalance(self, scores, price_data, date):
        """Capped rebalance: max 50% in commodity, rest stays cash as buffer."""
        if not scores:
            # Sell everything — go to cash
            for ticker in list(self.positions.keys()):
                price = self._get_exec_price(price_data, ticker, date)
                if price:
                    self._sell(ticker, price, date, "Oil signal bearish/neutral, going to cash")
        else:
            ticker, score = scores[0]
            if ticker not in self.positions:
                # First sell any existing different position
                for old in list(self.positions.keys()):
                    if old != ticker:
                        price = self._get_exec_price(price_data, old, date)
                        if price:
                            self._sell(old, price, date, f"Switching oil proxy to {ticker}")

                # Buy new
                price = self._get_exec_price(price_data, ticker, date)
                if price and price > 0 and self.cash > price:
                            # Cap at 50% of total portfolio value (not all-in)
                            max_allocation = self.initial_cash * 0.5
                            allocatable = min(self.cash, max_allocation)
                            shares = int(allocatable / price)
                            score_data = self._last_scores.get(ticker, {})
                            self._buy(ticker, shares, price, date,
                                     f"Oil bullish signal (score={score:.1f})", score_data,
                                     price_data=price_data)

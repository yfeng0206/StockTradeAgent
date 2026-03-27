"""Adaptive Strategy — Switches between modes based on detected conditions.

The "smart agent" approach: reads the market regime, news themes, and trend data,
then picks the best strategy mode for current conditions.

Modes:
  MOMENTUM — when market is bullish and trending up
  DEFENSIVE — when danger signals fire (high vol, downtrend, geopolitical risk)
  VALUE — when market is range-bound/sideways, look for beaten-down quality
  RECOVERY — when coming out of a crash (high vol but trend turning up)

Switches mode at each rebalance. Cannot predict the future —
only uses data available up to the current date.

Rebalances monthly. Holds up to 5 positions.
"""

import os
import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class AdaptiveStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("Adaptive", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 4.0
        self.atr_stop_multiplier = 2.0
        self.trim_threshold_pct = 40.0
        self.events_calendar = events_calendar or {}
        self.current_mode = "MOMENTUM"  # start optimistic
        self.mode_history = []  # track mode switches

    @property
    def rebalance_frequency(self) -> str:
        return "monthly"

    def _detect_mode(self, price_data: dict, date: str) -> str:
        """Detect which mode to use based on available data.

        ONLY uses data up to `date` — no look-ahead.
        """
        if "SPY" not in price_data or price_data["SPY"].empty:
            return "MOMENTUM"

        df = price_data["SPY"]
        mask = df.index <= pd.Timestamp(date)
        if not mask.any() or mask.sum() < 50:
            return "MOMENTUM"

        hist = df.loc[mask].tail(252)
        close = hist["Close"]
        returns = close.pct_change().dropna()
        current = float(close.iloc[-1])

        # Key market signals
        vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0.15
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
        sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current
        ret_1m = float((current / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0
        ret_3m = float((current / close.iloc[-63] - 1) * 100) if len(close) >= 63 else 0

        # Peak and drawdown
        peak_60d = float(close.tail(60).max())
        drawdown = (current - peak_60d) / peak_60d * 100

        # Geopolitical risk (from _last_news_summary, set by daily loop)
        geo_risk = 0.0
        try:
            ns = str(self._last_news_summary or "")
            if "geo_risk=" in ns:
                geo_risk = float(ns.split("geo_risk=")[1][:4])
        except (ValueError, IndexError):
            pass

        # Decision tree — simple and interpretable
        danger = (vol_20d > 0.28 and current < sma_50 * 0.97) or \
                 (drawdown < -12) or \
                 (geo_risk > 0.5 and vol_20d > 0.22)

        recovering = vol_20d > 0.22 and ret_1m > 3 and current > sma_50 * 0.98

        bullish = current > sma_50 and current > sma_200 and ret_3m > 0 and vol_20d < 0.25

        sideways = abs(ret_3m) < 5 and vol_20d < 0.20

        if danger:
            return "DEFENSIVE"
        elif recovering:
            return "RECOVERY"
        elif bullish:
            return "MOMENTUM"
        elif sideways:
            return "VALUE"
        else:
            return "MOMENTUM"  # default to momentum

    def score_stocks(self, universe: list, price_data: dict, date: str) -> list:
        # Detect mode
        new_mode = self._detect_mode(price_data, date)
        if new_mode != self.current_mode:
            self.mode_history.append({"date": date, "from": self.current_mode, "to": new_mode})
        self.current_mode = new_mode
        self._last_regime = f"adaptive:{new_mode}"

        # Delegate to the appropriate scoring logic
        if self.current_mode == "DEFENSIVE":
            return self._score_defensive(universe, price_data, date)
        elif self.current_mode == "VALUE":
            return self._score_value(universe, price_data, date)
        elif self.current_mode == "RECOVERY":
            return self._score_recovery(universe, price_data, date)
        else:  # MOMENTUM
            return self._score_momentum(universe, price_data, date)

    def _score_momentum(self, universe, price_data, date):
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            current = float(close.iloc[-1])

            ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0
            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
            above_ma = current > sma_50

            ema_12 = float(close.ewm(span=12).mean().iloc[-1])
            ema_26 = float(close.ewm(span=26).mean().iloc[-1])
            macd_bull = ema_12 > ema_26

            mom = min(10, max(0, 5 + ret_3m / 4))
            trend = 7 if above_ma else 3
            macd = 7 if macd_bull else 3

            composite = mom * 0.45 + trend * 0.30 + macd * 0.25
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "mode": "MOMENTUM",
                "momentum": round(mom, 2), "trend": round(trend, 2), "macd": round(macd, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_defensive(self, universe, price_data, date):
        """In defensive mode, go mostly to cash. Only hold lowest-vol stocks."""
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            returns = close.pct_change().dropna()

            vol = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else 0.5
            if vol == 0: continue
            vol_score = max(0, 10 - vol * 25)

            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
            current = float(close.iloc[-1])
            trend = 7 if current > sma_200 else 2

            composite = vol_score * 0.50 + trend * 0.50
            # Only keep stocks scoring very high — otherwise go to cash
            if composite < 5:
                continue
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "mode": "DEFENSIVE",
                "low_vol": round(vol_score, 2), "trend": round(trend, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        # In defensive mode, only hold 2-3 positions max
        # In defensive mode, hold fewer positions (half of max)
        return scores[:max(2, self.max_positions // 2)]

    def _score_value(self, universe, price_data, date):
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            returns = close.pct_change().dropna()
            current = float(close.iloc[-1])

            vol = float(returns.tail(90).std() * np.sqrt(252)) if len(returns) >= 90 else 0.3
            vol_score = max(0, 10 - vol * 20)

            high = float(close.max())
            dist = (high - current) / high * 100
            value = min(10, max(0, dist * 0.4)) if dist > 5 else dist * 0.2

            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if not rs.empty else 50
            rsi_score = max(0, (60 - rsi) / 6)

            composite = vol_score * 0.35 + value * 0.35 + rsi_score * 0.30
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "mode": "VALUE",
                "low_vol": round(vol_score, 2), "value_dist": round(value, 2), "rsi": round(rsi_score, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_recovery(self, universe, price_data, date):
        """Recovery mode — buy quality stocks bouncing off lows."""
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            current = float(close.iloc[-1])

            # Bounce strength: how much has it recovered from recent low?
            low_60d = float(close.tail(60).min())
            bounce = (current - low_60d) / low_60d * 100 if low_60d > 0 else 0
            bounce_score = min(10, max(0, bounce / 3))

            # Still below high = upside room
            high_252d = float(close.max())
            upside = (high_252d - current) / current * 100
            upside_score = min(10, max(0, upside / 5))

            # Momentum turning positive
            ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            mom_score = min(10, max(0, 5 + ret_1m / 2))

            composite = bounce_score * 0.35 + upside_score * 0.30 + mom_score * 0.35
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "mode": "RECOVERY",
                "bounce": round(bounce_score, 2), "upside": round(upside_score, 2),
                "momentum": round(mom_score, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

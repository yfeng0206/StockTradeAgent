"""Momentum Strategy — Buy stocks with the strongest recent price trends.

Uses:
- 3-month price return (cross-sectional momentum)
- Price above 50-day moving average (trend confirmation)
- MACD positive (momentum confirmation)
- Volume trend (increasing volume = conviction)

Rebalances monthly. Holds 5 positions.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("Momentum", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 5.0
        self.atr_stop_multiplier = 2.5
        self.trim_threshold_pct = 50.0
        self.events_calendar = events_calendar or {}

    @property
    def rebalance_frequency(self) -> str:
        if hasattr(self, '_frequency_override') and self._frequency_override:
            return self._frequency_override
        return "monthly"

    def score_stocks(self, universe: list, price_data: dict, date: str, **kwargs) -> list:
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            hist = df.loc[mask].tail(252)
            close = hist["Close"]
            volume = hist["Volume"]

            # 1. 12-minus-1 month momentum (academic standard)
            # Use 12-month return but exclude the most recent month
            # This avoids short-term reversal contamination
            current = float(close.iloc[-1])
            if len(close) >= 252:
                # Price 12 months ago vs price 1 month ago (skip last 21 days)
                price_12m_ago = float(close.iloc[-252])
                price_1m_ago = float(close.iloc[-21])
                ret_12m1 = (price_1m_ago / price_12m_ago - 1) * 100
            elif len(close) >= 126:
                # Fallback: 6-month excluding last month
                ret_12m1 = (float(close.iloc[-21]) / float(close.iloc[-126]) - 1) * 100
            elif len(close) >= 63:
                # Fallback: 3-month
                ret_12m1 = (float(close.iloc[-21]) / float(close.iloc[-63]) - 1) * 100
            else:
                continue
            # Normalize: 30% return -> 10, 0% -> 5, -30% -> 0
            mom_score = min(10, max(0, 5 + ret_12m1 / 6))

            # 2. Trend: price vs 200-day MA (long-term trend confirmation)
            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
            # Score: above both MAs = strong, above 200 only = moderate, below both = weak
            trend_score = 5
            if sma_200 and current > sma_200:
                trend_score += 2  # long-term uptrend
            if sma_50 and current > sma_50:
                trend_score += 2  # short-term uptrend
            if sma_50 and sma_200 and sma_50 > sma_200:
                trend_score += 1  # golden cross
            trend_score = min(10, max(0, trend_score))

            # 3. MACD signal
            ema_12 = close.ewm(span=12).mean()
            ema_26 = close.ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            macd_val = float(macd.iloc[-1])
            signal_val = float(signal.iloc[-1])
            # MACD above signal = bullish
            macd_score = 7 if macd_val > signal_val else 3
            # Bonus if MACD just crossed above
            if len(macd) >= 2:
                prev_diff = float(macd.iloc[-2]) - float(signal.iloc[-2])
                curr_diff = macd_val - signal_val
                if prev_diff < 0 and curr_diff > 0:
                    macd_score = 9  # Fresh bullish cross

            # 4. Volume trend (increasing = conviction)
            if len(volume) >= 20:
                vol_recent = float(volume.tail(10).mean())
                vol_avg = float(volume.tail(50).mean()) if len(volume) >= 50 else float(volume.mean())
                vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1
                vol_score = min(10, max(0, vol_ratio * 5))
            else:
                vol_score = 5

            # 5. RSI filter: skip overbought (>75) — momentum exhaustion risk
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if not rs.empty else 50
            if rsi > 78:
                # Penalize overbought
                mom_score *= 0.6

            # 6. Earnings event signal (post-earnings drift = momentum catalyst)
            event_boost = 0
            if self.events_calendar and ticker in self.events_calendar:
                from events_data import compute_earnings_surprise_signal
                earnings_signal = compute_earnings_surprise_signal(self.events_calendar, ticker, date)
                if earnings_signal.get("has_recent_earnings"):
                    days_since = earnings_signal.get("days_since_earnings", 99)
                    signal = earnings_signal.get("signal", "neutral")
                    if days_since <= 20:  # Post-earnings drift window
                        if signal == "strong_beat":
                            event_boost = 1.5  # Ride the drift
                        elif signal == "beat":
                            event_boost = 0.8
                        elif signal == "miss":
                            event_boost = -1.0  # Avoid falling knives
                        elif signal == "strong_miss":
                            event_boost = -2.0
                elif earnings_signal.get("upcoming_earnings") and earnings_signal.get("days_until_earnings", 99) <= 3:
                    event_boost = -0.5  # Reduce exposure right before earnings

            # Composite: heavily weight momentum and trend, plus event boost
            composite = mom_score * 0.40 + trend_score * 0.25 + macd_score * 0.20 + vol_score * 0.15 + event_boost
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "momentum": round(mom_score, 2),
                "trend": round(trend_score, 2), "macd": round(macd_score, 2),
                "volume": round(vol_score, 2), "event_boost": round(event_boost, 2),
            }
            scores.append((ticker, round(composite, 3)))

        self._last_regime = "momentum_screen"
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

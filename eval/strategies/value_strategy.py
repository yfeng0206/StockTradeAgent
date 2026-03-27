"""Value Strategy — Buy low-volatility, high-yield, beaten-down quality stocks.

Approximates fundamental value using price-derived signals since we can't
get historical fundamentals from yfinance. Uses:
- Low 90-day volatility (stability = quality proxy)
- Distance from 52-week high (beaten down = potentially undervalued)
- Dividend yield where available
- Low beta / defensive characteristics

Rebalances quarterly. Holds 5 positions.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class ValueStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("Value", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 3.5
        self.atr_stop_multiplier = 3.0
        self.trim_threshold_pct = 30.0
        self.events_calendar = events_calendar or {}

    @property
    def rebalance_frequency(self) -> str:
        return "quarterly"

    def score_stocks(self, universe: list, price_data: dict, date: str) -> list:
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 60:
                continue
            hist = df.loc[mask].tail(252)  # up to 1 year
            close = hist["Close"]

            # 1. Low volatility score (lower vol = higher score)
            returns = close.pct_change().dropna()
            vol_90d = float(returns.tail(90).std() * np.sqrt(252)) if len(returns) >= 90 else None
            if vol_90d is None or vol_90d == 0:
                continue
            vol_score = max(0, 10 - vol_90d * 20)  # ~25% vol -> score 5, ~10% vol -> score 8

            # 2. Distance from 52-week high (more beaten down = higher value score)
            high_52w = float(close.max())
            current = float(close.iloc[-1])
            pct_from_high = (high_52w - current) / high_52w * 100
            # 20% off high -> good value score, 0% -> low value score
            value_score = min(10, pct_from_high * 0.4) if pct_from_high > 5 else pct_from_high * 0.2

            # 3. Mean reversion potential (RSI-based, prefer lower RSI)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else 50
            # RSI < 40 -> higher score, RSI > 60 -> lower
            rsi_score = max(0, (60 - current_rsi) / 6)

            # 4. Price stability (low drawdown = quality)
            rolling_max = close.rolling(90).max()
            drawdown = (close - rolling_max) / rolling_max
            max_dd = float(drawdown.min()) if not drawdown.empty else -0.5
            stability_score = max(0, 10 + max_dd * 20)  # -25% dd -> 5, -10% dd -> 8

            # 5. Earnings event signal (value investor cares about earnings quality)
            event_adj = 0
            if self.events_calendar and ticker in self.events_calendar:
                from events_data import compute_earnings_surprise_signal
                earnings_signal = compute_earnings_surprise_signal(self.events_calendar, ticker, date)
                if earnings_signal.get("has_recent_earnings"):
                    signal = earnings_signal.get("signal", "neutral")
                    days_since = earnings_signal.get("days_since_earnings", 99)
                    if days_since <= 45:  # Value investors react slower
                        if signal == "strong_miss":
                            # Beaten down + strong miss = value trap, avoid
                            event_adj = -1.5
                        elif signal == "miss":
                            event_adj = -0.5
                        elif signal == "strong_beat":
                            # Beaten down + strong beat = potential turnaround
                            event_adj = 1.5
                        elif signal == "beat":
                            event_adj = 0.5

            # Composite: emphasize stability and value
            composite = vol_score * 0.30 + value_score * 0.30 + rsi_score * 0.20 + stability_score * 0.20 + event_adj
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "volatility": round(vol_score, 2),
                "value_dist": round(value_score, 2), "rsi": round(rsi_score, 2),
                "stability": round(stability_score, 2), "event_adj": round(event_adj, 2),
            }
            scores.append((ticker, round(composite, 3)))

        self._last_regime = "value_screen"
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

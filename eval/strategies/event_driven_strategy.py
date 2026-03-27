"""Event-Driven Strategy — Reacts specifically to earnings surprises and volatility events.

Core logic:
- After a strong earnings beat: buy and ride the post-earnings drift (hold ~20 days)
- After a strong earnings miss: avoid / sell
- After a volatility spike on high volume: check if mean-reversion trade exists
- More active than other strategies — trades around events, not on a fixed calendar

Rebalances monthly baseline, but also checks weekly for event triggers.
Holds up to 5 positions.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class EventDrivenStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("EventDriven", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 3.0
        self.atr_stop_multiplier = 2.0
        self.trim_threshold_pct = 35.0
        self.events_calendar = events_calendar or {}

    @property
    def rebalance_frequency(self) -> str:
        return "monthly"  # baseline, but we also check weekly

    def score_stocks(self, universe: list, price_data: dict, date: str) -> list:
        scores = []
        for ticker in universe:
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 30:
                continue
            hist = df.loc[mask].tail(252)
            close = hist["Close"]
            volume = hist["Volume"]
            current = float(close.iloc[-1])

            # === HARD EVENT ELIGIBILITY GATE ===
            # Only score stocks with a real event. No event = skip entirely.
            # This prevents the sleeve from drifting into generic stocks.
            has_event = False
            event_score = 0

            if self.events_calendar and ticker in self.events_calendar:
                from events_data import compute_earnings_surprise_signal, get_events_near_date
                sig = compute_earnings_surprise_signal(self.events_calendar, ticker, date)

                if sig.get("has_recent_earnings") and sig.get("days_since_earnings", 99) <= 45:
                    has_event = True
                    days_since = sig.get("days_since_earnings", 99)
                    signal = sig.get("signal", "neutral")

                    if days_since <= 25:
                        if signal == "strong_beat": event_score = 9
                        elif signal == "beat": event_score = 7.5
                        elif signal == "miss": event_score = 2
                        elif signal == "strong_miss": event_score = 0.5
                    elif days_since <= 45:
                        if signal in ("strong_beat", "beat"): event_score = 6.5
                        elif signal in ("miss", "strong_miss"): event_score = 3.5

                elif sig.get("upcoming_earnings") and sig.get("days_until_earnings", 99) <= 3:
                    has_event = True
                    event_score = 4

                # 8-K filings (material events) — past only
                recent_filings = get_events_near_date(
                    self.events_calendar, ticker, date, window_days=5, past_only=True
                )
                recent_8k = [e for e in recent_filings if e.get("form") == "8-K"]
                if recent_8k and len(close) >= 5:
                    has_event = True  # 8-K counts as an event
                    ret_5d = (current / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
                    if ret_5d > 3:
                        event_score = min(10, event_score + 1.5)
                    elif ret_5d < -3:
                        event_score = max(0, event_score - 1.5)

            # GATE: Skip stock entirely if no event
            if not has_event:
                continue

            # === VOLUME SPIKE (confirmation for event stocks only) ===
            vol_score = 5
            if len(volume) >= 20:
                avg_vol = float(volume.tail(20).mean())
                current_vol = float(volume.iloc[-1])
                vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

                if vol_ratio > 2.0:
                    # Major volume spike — something happened
                    ret_1d = (current / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
                    if ret_1d > 2:
                        vol_score = 8  # Positive catalyst on volume
                    elif ret_1d < -2:
                        vol_score = 2  # Negative catalyst on volume

            # === MOMENTUM CONFIRMATION ===
            if len(close) >= 20:
                sma_20 = float(close.rolling(20).mean().iloc[-1])
                above_trend = current > sma_20
                mom_score = 7 if above_trend else 3
            else:
                mom_score = 5

            # === COMPOSITE: event-heavy weighting ===
            composite = event_score * 0.55 + vol_score * 0.25 + mom_score * 0.20
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "event": round(event_score, 2),
                "vol_spike": round(vol_score, 2), "momentum": round(mom_score, 2),
            }
            scores.append((ticker, round(composite, 3)))

        self._last_regime = "event_driven"
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

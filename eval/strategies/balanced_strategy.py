"""Balanced Strategy — Combines value, momentum, quality, AND event signals.

This is the "full agent" approach that blends multiple signal families,
mirroring what the Claude research skill does qualitatively.

Uses:
- Value signals (distance from high, low volatility)
- Momentum signals (3m return, trend, MACD)
- Quality signals (stability, consistent returns, low drawdown)
- Event signals (earnings surprises, SEC filings, upcoming catalysts)
- Context-adaptive weighting (in high-vol regimes, shift to quality)

Rebalances monthly. Holds 5 positions.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class BalancedStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("Balanced", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 4.5
        self.atr_stop_multiplier = 2.0
        self.trim_threshold_pct = 40.0
        self.events_calendar = events_calendar or {}

    @property
    def rebalance_frequency(self) -> str:
        if hasattr(self, '_frequency_override') and self._frequency_override:
            return self._frequency_override
        return "monthly"

    def _get_market_regime(self, spy_data: pd.DataFrame, date: str) -> str:
        """Detect market regime from SPY data."""
        mask = self._signal_mask(spy_data, date)
        if not mask.any() or mask.sum() < 60:
            return "normal"
        close = spy_data.loc[mask, "Close"].tail(60)
        returns = close.pct_change().dropna()
        vol = float(returns.std() * np.sqrt(252))
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else float(close.mean())
        current = float(close.iloc[-1])

        if vol > 0.25:
            return "high_volatility"
        elif current < sma_50 * 0.95:
            return "bearish"
        elif current > sma_50 * 1.05:
            return "bullish"
        return "normal"

    def _get_geopolitical_risk(self, date: str) -> float:
        """Read geo_risk from _last_news_summary (set by daily loop from SignalEngine).
        Single source of truth — same value triggers and strategies both see."""
        try:
            ns = str(self._last_news_summary or "")
            if "geo_risk=" in ns:
                return float(ns.split("geo_risk=")[1][:4])
        except (ValueError, IndexError):
            pass
        return 0.0

    def score_stocks(self, universe: list, price_data: dict, date: str, **kwargs) -> list:
        # Detect market regime for adaptive weighting
        regime = "normal"
        if "SPY" in price_data:
            regime = self._get_market_regime(price_data["SPY"], date)

        # Check geopolitical risk from GDELT news
        geo_risk = self._get_geopolitical_risk(date)

        # Adaptive weights based on regime AND news
        if regime == "high_volatility" or geo_risk > 0.6:
            w_value, w_momentum, w_quality = 0.40, 0.10, 0.50
        elif regime == "bearish" or geo_risk > 0.4:
            w_value, w_momentum, w_quality = 0.45, 0.15, 0.40
        elif regime == "bullish" and geo_risk < 0.2:
            w_value, w_momentum, w_quality = 0.20, 0.45, 0.35
        else:
            w_value, w_momentum, w_quality = 0.30, 0.35, 0.35

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
            current = float(close.iloc[-1])

            # === VALUE SIGNALS ===
            # Distance from 52w high
            high_52w = float(close.max())
            pct_from_high = (high_52w - current) / high_52w * 100
            value_dist = min(10, max(0, pct_from_high * 0.4)) if pct_from_high > 5 else max(0, pct_from_high * 0.2)

            # Low volatility
            returns = close.pct_change().dropna()
            vol_90d = float(returns.tail(90).std() * np.sqrt(252)) if len(returns) >= 90 else 0.3
            value_vol = max(0, 10 - vol_90d * 20)

            value_score = value_dist * 0.5 + value_vol * 0.5

            # === MOMENTUM SIGNALS ===
            # 3-month return
            if len(close) >= 63:
                ret_3m = (current / float(close.iloc[-63]) - 1) * 100
            elif len(close) >= 21:
                ret_3m = (current / float(close.iloc[-21]) - 1) * 100
            else:
                ret_3m = 0
            mom_ret = min(10, max(0, 5 + ret_3m / 4))

            # Trend
            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
            pct_above = (current - sma_50) / sma_50 * 100 if sma_50 > 0 else 0
            mom_trend = min(10, max(0, 5 + pct_above / 2))

            # MACD
            ema_12 = float(close.ewm(span=12).mean().iloc[-1])
            ema_26 = float(close.ewm(span=26).mean().iloc[-1])
            macd_bullish = 7 if ema_12 > ema_26 else 3

            momentum_score = mom_ret * 0.45 + mom_trend * 0.30 + macd_bullish * 0.25

            # === STABILITY SIGNALS (not "quality" — this measures price stability) ===
            # Return consistency (Sharpe-like)
            if len(returns) >= 60:
                mean_ret = float(returns.tail(60).mean())
                std_ret = float(returns.tail(60).std())
                sharpe_proxy = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
                stability_sharpe = min(10, max(0, sharpe_proxy * 3 + 5))
            else:
                stability_sharpe = 5

            # Max drawdown
            rolling_max = close.rolling(90, min_periods=1).max()
            drawdown = (close - rolling_max) / rolling_max
            max_dd = float(drawdown.min()) if not drawdown.empty else -0.3
            stability_dd = max(0, 10 + max_dd * 20)

            # Volume stability
            if len(volume) >= 20:
                vol_cv = float(volume.tail(20).std() / volume.tail(20).mean()) if float(volume.tail(20).mean()) > 0 else 1
                stability_vol = max(0, 10 - vol_cv * 5)
            else:
                stability_vol = 5

            stability_score = stability_sharpe * 0.40 + stability_dd * 0.35 + stability_vol * 0.25

            # === EVENT SIGNALS ===
            event_adjustment = 0
            if self.events_calendar and ticker in self.events_calendar:
                from events_data import compute_earnings_surprise_signal, get_events_near_date
                earnings_signal = compute_earnings_surprise_signal(self.events_calendar, ticker, date)

                if earnings_signal.get("has_recent_earnings"):
                    days_since = earnings_signal.get("days_since_earnings", 99)
                    surprise = earnings_signal.get("surprise_pct")
                    signal = earnings_signal.get("signal", "neutral")

                    # Post-earnings drift: recent beat = bullish boost, recent miss = penalty
                    if days_since <= 30:  # Within drift window
                        if signal == "strong_beat":
                            event_adjustment = 2.0
                        elif signal == "beat":
                            event_adjustment = 1.0
                        elif signal == "miss":
                            event_adjustment = -1.0
                        elif signal == "strong_miss":
                            event_adjustment = -2.0

                elif earnings_signal.get("upcoming_earnings"):
                    days_until = earnings_signal.get("days_until_earnings", 99)
                    if days_until <= 5:
                        # Right before earnings — increase uncertainty, slight penalty
                        event_adjustment = -0.5

                # SEC filing events (8-K = material event) — PAST ONLY, no look-ahead
                nearby_events = get_events_near_date(self.events_calendar, ticker, date, window_days=7, past_only=True)
                recent_8k = [e for e in nearby_events if e.get("form") == "8-K"]
                if recent_8k:
                    # Recent 8-K + positive momentum = bullish; 8-K + negative momentum = bearish
                    if ret_3m > 0:
                        event_adjustment += 0.5
                    else:
                        event_adjustment -= 0.5

            # === COMPOSITE (value + momentum + stability) ===
            composite = (value_score * w_value +
                        momentum_score * w_momentum +
                        stability_score * w_quality +
                        event_adjustment)
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "value": round(value_score, 2),
                "momentum": round(momentum_score, 2), "stability": round(stability_score, 2),
                "event_adj": round(event_adjustment, 2),
                "weights": f"v={w_value} m={w_momentum} s={w_quality}",
            }
            scores.append((ticker, round(composite, 3)))

        self._last_regime = regime
        # Note: _last_news_summary is set by daily_loop from SignalEngine — don't overwrite it
        # here, as downstream strategies (Mix) and base class (snapshot, reasoning log) rely
        # on the canonical value.
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

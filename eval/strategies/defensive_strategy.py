"""Defensive / Minimum Volatility Strategy — 3-state exposure scaling.

3 states instead of binary on/off:
  NORMAL:  100% invested in lowest-vol stocks (0-1 danger signals)
  REDUCED:  50% invested, sell highest-vol positions (2 danger signals)
  DEFENSE:  20% invested, hold only safest names (3-4 danger signals)

Gradual scaling prevents whipsaw from flipping 100%↔0%.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


class DefensiveStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None, max_positions: int = 5):
        super().__init__("Defensive", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 4.0
        self.atr_stop_multiplier = 1.5
        self.trim_threshold_pct = 35.0
        self.events_calendar = events_calendar or {}
        self._defense_state = "NORMAL"  # NORMAL, REDUCED, DEFENSE

    @property
    def rebalance_frequency(self) -> str:
        return "monthly"

    def _count_danger_signals(self, price_data: dict, date: str) -> int:
        """Count how many danger signals are active (0-4)."""
        if "SPY" not in price_data or price_data["SPY"].empty:
            return 0

        df = price_data["SPY"]
        mask = self._signal_mask(df, date)
        if not mask.any() or mask.sum() < 50:
            return 0
        hist = df.loc[mask].tail(252)
        close = hist["Close"]
        returns = close.pct_change().dropna()

        count = 0

        # Signal 1: High volatility
        vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0.15
        if vol_20d > 0.28:
            count += 1

        # Signal 2: Below trend
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else float(close.mean())
        current = float(close.iloc[-1])
        if current < sma_50 * 0.97:
            count += 1

        # Signal 3: Deep drawdown
        peak_60d = float(close.tail(60).max())
        drawdown = (current - peak_60d) / peak_60d * 100
        if drawdown < -10:
            count += 1

        # Signal 4: REMOVED — ablation proved news hurts Defensive (-3.4%)
        # Defensive now uses only price-based signals (vol, trend, drawdown)

        return count

    def score_stocks(self, universe: list, price_data: dict, date: str) -> list:
        danger = self._count_danger_signals(price_data, date)

        # 3-state transition
        if danger >= 3:
            self._defense_state = "DEFENSE"
        elif danger >= 2:
            self._defense_state = "REDUCED"
        else:
            self._defense_state = "NORMAL"

        self._last_regime = f"defensive:{self._defense_state}(signals={danger})"

        # How many positions to hold based on state
        if self._defense_state == "DEFENSE":
            effective_max = max(1, self.max_positions // 5)  # ~20% invested
        elif self._defense_state == "REDUCED":
            effective_max = max(2, self.max_positions // 2)  # ~50% invested
        else:
            effective_max = self.max_positions  # 100% invested

        # Score stocks by lowest volatility + trend
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
            returns = close.pct_change().dropna()

            vol = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else 0.5
            if vol == 0:
                continue
            vol_score = max(0, 10 - vol * 20)

            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
            current = float(close.iloc[-1])
            trend_score = 7 if current > sma_200 else 3

            rolling_max = close.rolling(90, min_periods=1).max()
            dd = (close - rolling_max) / rolling_max
            max_dd = float(dd.min()) if not dd.empty else -0.3
            dd_score = max(0, 10 + max_dd * 20)

            event_adj = 0
            if self.events_calendar and ticker in self.events_calendar:
                from events_data import compute_earnings_surprise_signal
                sig = compute_earnings_surprise_signal(self.events_calendar, ticker, date)
                if sig.get("signal") == "strong_miss":
                    event_adj = -3
                elif sig.get("signal") == "strong_beat":
                    event_adj = 1

            composite = vol_score * 0.40 + trend_score * 0.30 + dd_score * 0.30 + event_adj
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "low_vol": round(vol_score, 2),
                "trend": round(trend_score, 2), "drawdown": round(dd_score, 2),
                "event_adj": round(event_adj, 2), "state": self._defense_state,
            }
            scores.append((ticker, round(composite, 3)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:effective_max]  # limit by defense state

    def execute_rebalance(self, scores, price_data, date):
        """Override: in DEFENSE state, also sell positions beyond effective_max."""
        if self._defense_state in ("DEFENSE", "REDUCED"):
            if self._defense_state == "DEFENSE":
                effective_max = max(1, self.max_positions // 5)
            else:
                effective_max = max(2, self.max_positions // 2)

            # If holding more than effective_max, sell excess (highest vol first)
            if len(self.positions) > effective_max:
                pos_vol = []
                for tkr, pos in self.positions.items():
                    if tkr in price_data and not price_data[tkr].empty:
                        df = price_data[tkr]
                        # Signal mask for vol computation (T-1 data)
                        mask = self._signal_mask(df, date)
                        if mask.any():
                            returns = df.loc[mask, "Close"].tail(60).pct_change().dropna()
                            vol = float(returns.std() * (252**0.5)) if len(returns) > 10 else 0.3
                            # Execution price (T Open via exec_model)
                            price = self._get_exec_price(price_data, tkr, date)
                            if price:
                                pos_vol.append((tkr, vol, price))
                pos_vol.sort(key=lambda x: -x[1])  # highest vol first
                to_sell = len(self.positions) - effective_max
                for tkr, vol, price in pos_vol[:to_sell]:
                    if tkr in self.positions:
                        self._sell(tkr, price, date,
                            f"DEFENSIVE {self._defense_state}: reducing to {effective_max} positions, selling {tkr} (vol={vol:.0%})")

        super().execute_rebalance(scores, price_data, date)

"""Trigger detection system — scans for events that require action.

Instead of "is it rebalance day?", asks "did anything happen?"
Most days: nothing triggers, no trades. Event day: triggers fire, targeted action.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class TriggerEvent:
    type: str          # EARNINGS_RELEASE, STOP_LOSS, PROFIT_TARGET, NEWS_SPIKE, REGIME_CHANGE, VOLUME_ANOMALY, WATCHNOTE_FIRED, MONTHLY_REBALANCE
    ticker: Optional[str]  # None for market-level triggers
    date: str
    severity: str      # LOW, MEDIUM, HIGH, CRITICAL
    data: dict         # signal data that caused the trigger
    suggested_action: str  # BUY, SELL, TRIM, REVIEW, FULL_REBALANCE, HOLD


class TriggerEngine:
    """Scans for events that require portfolio action."""

    def __init__(self, signal_engine, atr_stop_multiplier: float = 2.0, profit_target_pct: float = 25):
        self.signals = signal_engine
        self.atr_stop_multiplier = atr_stop_multiplier  # stop = entry - N * ATR
        self.profit_target_pct = profit_target_pct
        self._last_regime = None
        self._last_news_risk = 0

    def scan(self, universe: list, positions: dict, date: str, price_data: dict,
             precomputed_macro: dict = None) -> list:
        """Scan all trigger types. Returns list of TriggerEvents sorted by severity.

        Pass precomputed_macro to avoid recomputing signals 3x per day.
        Monthly rebalance is handled by the daily loop, NOT here.
        """
        triggers = []

        # Cache macro to avoid recomputing
        self._cached_macro = precomputed_macro

        # 1. Price alerts on held positions
        triggers.extend(self._check_price_alerts(positions, date, price_data))

        # 2. Earnings events (only check stocks near known earnings dates)
        triggers.extend(self._check_earnings(universe, date))

        # 3. Regime change
        triggers.extend(self._check_regime(date))

        # 4. News spike
        triggers.extend(self._check_news(date))

        # 5. Volume anomalies (only check held + top volume stocks, not all 50)
        triggers.extend(self._check_volume(universe, date, positions))

        # Sort: CRITICAL > HIGH > MEDIUM > LOW
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        triggers.sort(key=lambda t: severity_order.get(t.severity, 9))

        return triggers


    def _check_price_alerts(self, positions: dict, date: str, price_data: dict) -> list:
        """Check ATR-based stop-loss and profit targets on held positions.

        Stop = entry_price - (multiplier * ATR_20)
        TSLA (high vol, ATR ~3.4%) → stop ~7% below entry
        PG (low vol, ATR ~2.1%) → stop ~4% below entry
        Each stock gets a stop calibrated to its own volatility.
        """
        triggers = []
        for ticker, pos in positions.items():
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = df.index <= pd.Timestamp(date)
            if not mask.any() or mask.sum() < 20:
                continue

            hist = df.loc[mask].tail(30)
            current = float(hist["Close"].iloc[-1])
            entry = pos["entry_price"]
            pnl_pct = (current - entry) / entry * 100

            # Compute ATR-based stop level
            try:
                import numpy as np
                tr = np.maximum(
                    hist["High"].values - hist["Low"].values,
                    np.maximum(
                        np.abs(hist["High"].values - np.roll(hist["Close"].values, 1)),
                        np.abs(hist["Low"].values - np.roll(hist["Close"].values, 1))
                    )
                )
                atr_20 = float(np.nanmean(tr[-20:]))
                stop_level = entry - (self.atr_stop_multiplier * atr_20)
                stop_pct = (stop_level - entry) / entry * 100
            except Exception:
                atr_20 = entry * 0.02  # fallback: 2% of price
                stop_level = entry * 0.88  # fallback: 12%
                stop_pct = -12.0

            if current <= stop_level:
                triggers.append(TriggerEvent(
                    type="STOP_LOSS", ticker=ticker, date=date,
                    severity="CRITICAL",
                    data={"entry": entry, "current": round(current, 2), "pnl_pct": round(pnl_pct, 2),
                          "atr": round(atr_20, 2), "stop_level": round(stop_level, 2),
                          "stop_pct": round(stop_pct, 1)},
                    suggested_action="SELL",
                ))
            elif pnl_pct >= self.profit_target_pct:
                triggers.append(TriggerEvent(
                    type="PROFIT_TARGET", ticker=ticker, date=date,
                    severity="LOW",
                    data={"entry": entry, "current": round(current, 2), "pnl_pct": round(pnl_pct, 2)},
                    suggested_action="REVIEW",
                ))

            # Gap detection (>5% overnight move)
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                gap_pct = (current - prev_close) / prev_close * 100
                if abs(gap_pct) > 5:
                    triggers.append(TriggerEvent(
                        type="PRICE_ALERT", ticker=ticker, date=date,
                        severity="HIGH" if abs(gap_pct) > 8 else "MEDIUM",
                        data={"gap_pct": round(gap_pct, 2), "current": round(current, 2)},
                        suggested_action="REVIEW",
                    ))

        return triggers

    def _check_earnings(self, universe: list, date: str) -> list:
        """Check if any stock had an earnings event in the last 1-2 days."""
        triggers = []
        for ticker in universe:
            earnings = self.signals.compute_earnings(ticker, date)
            if earnings.get("has_recent_earnings"):
                days_since = earnings.get("days_since_earnings", 99)
                signal = earnings.get("signal", "neutral")
                if days_since <= 3:  # Very recent — act on it
                    severity = "HIGH" if signal in ("strong_beat", "strong_miss") else "MEDIUM"
                    action = "BUY" if signal in ("strong_beat", "beat") else "SELL" if signal in ("strong_miss", "miss") else "REVIEW"
                    triggers.append(TriggerEvent(
                        type="EARNINGS_RELEASE", ticker=ticker, date=date,
                        severity=severity,
                        data={"signal": signal, "surprise_pct": earnings.get("surprise_pct"),
                              "days_since": days_since},
                        suggested_action=action,
                    ))
        return triggers

    def _check_regime(self, date: str) -> list:
        """Detect market regime changes. Uses cached macro from scan()."""
        macro = self._cached_macro or self.signals.compute_macro(date)
        current_regime = macro.get("regime", "normal")

        triggers = []
        if self._last_regime and current_regime != self._last_regime:
            severity = "HIGH"
            if current_regime in ("crisis", "high_volatility") or self._last_regime in ("crisis",):
                severity = "CRITICAL"

            triggers.append(TriggerEvent(
                type="REGIME_CHANGE", ticker=None, date=date,
                severity=severity,
                data={"from": self._last_regime, "to": current_regime, "macro": macro},
                suggested_action="REVIEW",
            ))

        self._last_regime = current_regime
        return triggers

    def _check_news(self, date: str) -> list:
        """Detect significant news changes. Uses cached macro from scan()."""
        macro = self._cached_macro or self.signals.compute_macro(date)
        news = macro.get("news", {})
        geo_risk = news.get("geo_risk", 0)

        triggers = []
        risk_delta = abs(geo_risk - self._last_news_risk)

        if risk_delta > 0.3:
            direction = "escalation" if geo_risk > self._last_news_risk else "de-escalation"
            triggers.append(TriggerEvent(
                type="NEWS_SPIKE", ticker=None, date=date,
                severity="HIGH" if risk_delta > 0.5 else "MEDIUM",
                data={"geo_risk": geo_risk, "previous": self._last_news_risk,
                      "delta": round(risk_delta, 2), "direction": direction,
                      "themes": news.get("themes", [])},
                suggested_action="REVIEW",
            ))

        self._last_news_risk = geo_risk
        return triggers

    def _check_volume(self, universe: list, date: str, positions: dict = None) -> list:
        """Detect volume anomalies. Checks held positions + scans universe for big movers."""
        triggers = []
        # Always check held positions
        check_tickers = set(positions.keys()) if positions else set()
        # Also check the full universe but only keep truly large spikes
        for ticker in universe:
            vol_sig = self.signals.compute_volume_signals(ticker, date)
            if not vol_sig.get("spike_with_move"):
                continue
            price_move = vol_sig.get("price_move_on_volume", 0)
            vol_ratio = vol_sig.get("ratio_vs_avg", 1)

            # For held positions: any spike matters
            # For universe: only very large spikes (>2.5x volume AND >5% move)
            if ticker in check_tickers or (vol_ratio > 2.5 and abs(price_move) > 5):
                triggers.append(TriggerEvent(
                    type="VOLUME_ANOMALY", ticker=ticker, date=date,
                    severity="HIGH" if abs(price_move) > 8 else "MEDIUM",
                    data={"volume_ratio": round(vol_ratio, 1),
                          "price_move_pct": round(price_move, 1)},
                    suggested_action="BUY" if price_move > 5 else "SELL" if price_move < -5 else "REVIEW",
                ))
        return triggers

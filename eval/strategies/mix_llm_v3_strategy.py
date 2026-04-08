"""Mix LLM V3 Strategy — Bidirectional LLM, event-triggered only.

Key differences from MixLLM (v2):
- LLM is NOT called on every rebalance — only on trigger events:
  1. Regime CHANGED from last detection (e.g., AGGRESSIVE -> CAUTIOUS)
  2. Portfolio drawdown > 10% from peak
  3. Market breadth divergence (if breadth data available)
- BIDIRECTIONAL: LLM can move regime in EITHER direction (more aggressive OR more defensive)
  — no escalate-only constraint
- Same extended market sensing, same SDK/CLI infrastructure, same formatting
- Falls back to coded rules if no trigger fires (saves cost — most rebalances use coded rules)
"""

import json
import os
import numpy as np
import pandas as pd
from .mix_strategy import MixStrategy, REGIME_ALLOCATIONS, OIL_PROXIES

# Try Anthropic SDK first (no browser tabs), fallback to CLI
_USE_SDK = False
_anthropic_client = None
try:
    import anthropic
    # SDK needs API key — check env or Claude CLI config
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
        _USE_SDK = True
except ImportError:
    pass

if not _USE_SDK:
    import subprocess
    CLAUDE_CMD = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
    if not os.path.exists(CLAUDE_CMD):
        CLAUDE_CMD = "claude"  # fallback to PATH

# Macro ETFs available in simulation price_data
SAFE_HAVEN_TICKERS = {
    "GLD": "Gold",
    "TLT": "Long-Term Treasuries (20y+)",
}
RISK_TICKERS = {
    "HYG": "High Yield Bonds (junk)",
    "LQD": "Investment Grade Bonds",
}
ENERGY_TICKERS = {
    "USO": "Oil (USO ETF)",
    "XLE": "Energy Sector ETF",
}
# Sector proxies (same as signals.py uses)
SECTOR_PROXIES = {
    "energy": ["XOM", "CVX", "COP"],
    "tech": ["AAPL", "MSFT", "NVDA", "GOOGL"],
    "finance": ["JPM", "GS", "V", "BAC"],
    "healthcare": ["UNH", "JNJ", "LLY"],
    "consumer_staples": ["PG", "KO", "WMT"],
    "consumer_disc": ["HD", "MCD", "NKE"],
    "industrial": ["CAT", "BA", "HON", "DE"],
}

# Expert knowledge prompt — LLM is the BIDIRECTIONAL TIE-BREAKER at critical moments
EXPERT_KNOWLEDGE = """You are called ONLY at critical moments — regime transitions or significant drawdowns. Your judgment on direction (more aggressive or more defensive) will be followed. Be thoughtful — you're the tie-breaker, not the default.

A coded decision tree has classified the current regime. You are being called because something CHANGED — either the coded regime just shifted, the portfolio hit a significant drawdown, or market breadth is diverging from price action.

YOUR ROLE: Decide what the regime SHOULD be. You can move it in EITHER direction:
- More aggressive (if the coded rules are too scared)
- More defensive (if the coded rules are too optimistic)
- Confirm the coded regime (if it's right)

## WHEN TO CONFIRM (default — unless you have strong evidence):
- If the coded regime change looks justified by the data → CONFIRM.
- If the drawdown triggered this call but the market is broadly healthy → CONFIRM the coded regime.
- Mixed signals with no clear direction → CONFIRM. Don't add noise.

## WHEN TO OVERRIDE MORE AGGRESSIVE:
- Coded rules shifted to CAUTIOUS/DEFENSIVE but the selloff looks like a buying opportunity
- A sharp drawdown triggered this call, but breadth is healthy, credit is fine, and the dip is technical
- Multiple strategies still making money despite the scare — false alarm signals
- Recovery is underway but coded rules haven't caught up yet (lagging indicators)

## WHEN TO OVERRIDE MORE DEFENSIVE:
- Coded rules stayed AGGRESSIVE but safe havens are surging and credit is deteriorating
- Oil is outperforming SPY by >15% over 3 months — commodity shock the rules haven't caught
- Energy is the ONLY positive sector AND geo_risk is elevated
- Multiple strategies heavy in cash — peer consensus says de-risk
- Classic flight-to-safety pattern: Gold up, Treasuries up, HYG down

## KEY LESSON FROM BACKTESTING:
- In 2025 bull market, the coded rules stayed AGGRESSIVE and earned +24.4%.
  An overly worried LLM would have cost 15%+ in missed gains.
- In Q1 2026 Hormuz crisis, DEFENSIVE would have captured the +28% oil trade.
  The coded rules missed the transition.
- Your value is catching the inflection points — both bullish and bearish.
- You are called rarely (only at trigger events), so each call matters.

## Regime allocations:
- AGGRESSIVE: 90% stocks, 0% commodity, 10% cash
- CAUTIOUS: 50% stocks, 20% commodity, 30% cash
- DEFENSIVE: 20% stocks, 30% commodity, 50% cash
- RECOVERY: 80% stocks, 0% commodity, 20% cash
- UNCERTAIN: 70% stocks, 0% commodity, 30% cash

## Output format:
Respond with ONLY a JSON object:
{"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", "action": "CONFIRM|OVERRIDE", "confidence": 0.0-1.0, "reasoning": "1-2 sentences. What signal justifies your call?"}"""


class MixLLMV3Strategy(MixStrategy):
    """Mix strategy with bidirectional, event-triggered LLM regime detection (v3)."""

    def __init__(self, initial_cash=100_000, events_calendar=None, max_positions=10,
                 regime_stickiness=1):
        super().__init__(initial_cash, events_calendar, max_positions,
                         regime_stickiness=regime_stickiness)
        self.name = "MixLLM_V3"
        self._llm_call_count = 0
        self._llm_fallback_count = 0
        self._llm_log = []  # log every LLM call for debugging

        # V3-specific: trigger tracking
        self._last_regime_for_trigger = None  # last coded regime (to detect changes)
        self._peak_value = 0.0               # peak portfolio value (for drawdown calc)

    # ================================================================
    # TRIGGER DETECTION — should we call the LLM?
    # ================================================================
    def _is_trigger_event(self, coded_regime, price_data, date, breadth=None):
        """Check if this rebalance warrants an LLM call.

        Returns (is_trigger: bool, reasons: list[str]).
        Only calls LLM when something meaningful changed.
        """
        reasons = []

        # 1. Regime changed from last detection
        if self._last_regime_for_trigger is not None and coded_regime != self._last_regime_for_trigger:
            reasons.append(
                f"Regime changed: {self._last_regime_for_trigger} -> {coded_regime}"
            )

        # 2. Portfolio drawdown > 10% from peak
        if self.portfolio_history:
            current_value = self.portfolio_history[-1].get("total_value", 0)
            if current_value > self._peak_value:
                self._peak_value = current_value
            if self._peak_value > 0:
                drawdown_pct = (current_value - self._peak_value) / self._peak_value * 100
                if drawdown_pct < -10:
                    reasons.append(
                        f"Portfolio drawdown {drawdown_pct:.1f}% from peak "
                        f"(peak=${self._peak_value:,.0f}, current=${current_value:,.0f})"
                    )

        # 3. Market breadth divergence (if breadth data available)
        if breadth:
            pct_above_200 = breadth.get("pct_above_200ma", 50)
            pct_above_50 = breadth.get("pct_above_50ma", 50)
            # SPY going up but breadth is narrow — divergence
            market = self._sensor_readings.get("market", {})
            spy_ret_1m = market.get("spy_ret_1m", 0)
            if pct_above_50 < 40 and spy_ret_1m > 3:
                reasons.append(
                    f"Breadth divergence: SPY +{spy_ret_1m:.1f}% but only "
                    f"{pct_above_50:.0f}% above 50MA, {pct_above_200:.0f}% above 200MA"
                )
            # SPY falling but breadth recovering
            if breadth.get("breadth_recovering") and spy_ret_1m < -3:
                reasons.append(
                    f"Breadth recovering while SPY is down {spy_ret_1m:.1f}%"
                )

        return len(reasons) > 0, reasons

    # ================================================================
    # REGIME DETECTION — coded first, LLM only on trigger events
    # ================================================================
    # Defensive ordering: higher = more defensive
    _DEFENSE_LEVEL = {
        "AGGRESSIVE": 0, "RECOVERY": 1, "UNCERTAIN": 2, "CAUTIOUS": 3, "DEFENSIVE": 4,
    }

    def _detect_regime(self, price_data, date, breadth: dict = None):
        """Override: coded rules FIRST, then LLM ONLY on trigger events.

        Unlike MixLLM v2 which calls LLM every rebalance:
        - Most rebalances: just use coded regime (no LLM call, saves cost)
        - Trigger events: call LLM with full context, accept bidirectional override
        """
        # Step 1: Get the coded regime from parent class (this also sets sensors)
        coded_regime = super()._detect_regime(price_data, date, breadth=breadth)
        peers = self._sensor_readings.get("peers", {})
        market = self._sensor_readings.get("market", {})

        # Step 2: Update peak value tracking
        if self.portfolio_history:
            current_value = self.portfolio_history[-1].get("total_value", 0)
            if current_value > self._peak_value:
                self._peak_value = current_value

        # Step 3: Check if this is a trigger event
        is_trigger, trigger_reasons = self._is_trigger_event(
            coded_regime, price_data, date, breadth=breadth
        )

        # Always update the last regime for next trigger check
        self._last_regime_for_trigger = coded_regime

        # Step 4: If NOT a trigger event, return coded regime (no LLM call)
        if not is_trigger:
            self._llm_log.append({
                "date": date, "source": "coded_only", "regime": coded_regime,
                "reason": "No trigger event — using coded regime",
            })
            return coded_regime

        # Step 5: IS a trigger event — compute extended data and call LLM
        extended = self._sense_market_extended(price_data, date)

        sensor_summary = self._format_sensors_for_llm_v3(
            peers, market, extended, date,
            coded_regime=coded_regime, trigger_reasons=trigger_reasons,
        )

        llm_regime = self._call_llm(sensor_summary, date, trigger_reasons)

        # Step 6: BIDIRECTIONAL — accept LLM's regime in either direction
        valid_regimes = set(REGIME_ALLOCATIONS.keys())
        if llm_regime not in valid_regimes:
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "fallback", "regime": coded_regime,
                "reason": "LLM returned invalid regime, using coded rules",
                "trigger_reasons": trigger_reasons,
            })
            return coded_regime

        coded_level = self._DEFENSE_LEVEL.get(coded_regime, 2)
        llm_level = self._DEFENSE_LEVEL.get(llm_regime, 2)

        if llm_regime == coded_regime:
            self._llm_log[-1]["action"] = "CONFIRM"
            return coded_regime
        elif llm_level > coded_level:
            # LLM says go MORE defensive
            self._llm_log[-1]["action"] = "OVERRIDE_DEFENSIVE"
            self._llm_log[-1]["note"] = (
                f"LLM overrode {coded_regime} -> {llm_regime} (more defensive)"
            )
            return llm_regime
        else:
            # LLM says go MORE aggressive — ACCEPTED in V3 (bidirectional)
            self._llm_log[-1]["action"] = "OVERRIDE_AGGRESSIVE"
            self._llm_log[-1]["note"] = (
                f"LLM overrode {coded_regime} -> {llm_regime} (more aggressive)"
            )
            return llm_regime

    # ================================================================
    # EXTENDED MARKET SENSING — sectors, safe havens, bonds, oil detail
    # ================================================================
    def _sense_market_extended(self, price_data, date):
        """Compute rich market context beyond basic SPY/oil signals."""
        result = {
            "sectors": {},
            "safe_havens": {},
            "risk_appetite": {},
            "energy_detail": {},
            "vol_trend": "unknown",
            "breadth": 0,  # how many sectors are positive
        }

        ts = pd.Timestamp(date)

        # --- Sector rotation (1m and 3m returns) ---
        for sector_name, tickers in SECTOR_PROXIES.items():
            rets_1m = []
            rets_3m = []
            for ticker in tickers:
                r1m, r3m = self._get_returns(price_data, ticker, date)
                if r1m is not None:
                    rets_1m.append(r1m)
                if r3m is not None:
                    rets_3m.append(r3m)
            if rets_1m:
                result["sectors"][sector_name] = {
                    "ret_1m": round(np.mean(rets_1m), 1),
                    "ret_3m": round(np.mean(rets_3m), 1) if rets_3m else 0,
                }

        # Count positive sectors (breadth)
        result["breadth"] = sum(
            1 for s in result["sectors"].values()
            if s.get("ret_3m", 0) > 0
        )

        # --- Safe havens ---
        for ticker, name in SAFE_HAVEN_TICKERS.items():
            r1m, r3m = self._get_returns(price_data, ticker, date)
            if r1m is not None:
                result["safe_havens"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Risk appetite (credit spreads proxy) ---
        for ticker, name in RISK_TICKERS.items():
            r1m, r3m = self._get_returns(price_data, ticker, date)
            if r1m is not None:
                result["risk_appetite"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Energy/oil detail ---
        for ticker, name in ENERGY_TICKERS.items():
            r1m, r3m = self._get_returns(price_data, ticker, date)
            if r1m is not None:
                result["energy_detail"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Volatility trend ---
        if "SPY" in price_data and not price_data["SPY"].empty:
            df = price_data["SPY"]
            mask = self._signal_mask(df, date)
            if mask.any() and mask.sum() >= 60:
                close = df.loc[mask, "Close"].tail(252)
                returns = close.pct_change().dropna()
                if len(returns) >= 60:
                    vol_20d = float(returns.tail(20).std() * np.sqrt(252))
                    vol_60d = float(returns.tail(60).std() * np.sqrt(252))
                    if vol_20d > vol_60d * 1.2:
                        result["vol_trend"] = "RISING (20d vol > 60d avg by 20%+)"
                    elif vol_20d < vol_60d * 0.8:
                        result["vol_trend"] = "FALLING (20d vol < 60d avg by 20%+)"
                    else:
                        result["vol_trend"] = "STABLE"

        return result

    def _get_returns(self, price_data, ticker, date):
        """Get 1-month and 3-month returns for a ticker. Respects T-1 gating."""
        if ticker not in price_data or price_data[ticker].empty:
            return None, None
        df = price_data[ticker]
        mask = self._signal_mask(df, date)
        if not mask.any() or mask.sum() < 22:
            return None, None
        close = df.loc[mask, "Close"].tail(252)
        current = float(close.iloc[-1])
        r1m = (current / float(close.iloc[-22]) - 1) * 100 if len(close) >= 22 else None
        r3m = (current / float(close.iloc[-66]) - 1) * 100 if len(close) >= 66 else None
        return r1m, r3m

    # ================================================================
    # FORMAT — rich context for the LLM (V3: includes trigger reasons)
    # ================================================================
    def _format_sensors_for_llm_v3(self, peers, market, extended, date,
                                    coded_regime=None, trigger_reasons=None):
        """Format comprehensive market data for the LLM — V3 includes trigger context."""
        lines = [f"Date: {date}", ""]

        # === 0. WHY YOU WERE CALLED (trigger reasons) ===
        lines.append("=== WHY YOU WERE CALLED ===")
        if trigger_reasons:
            for reason in trigger_reasons:
                lines.append(f"  TRIGGER: {reason}")
        else:
            lines.append("  (No specific trigger — routine check)")
        lines.append("")

        # === 1. Coded regime baseline ===
        if coded_regime:
            lines.append(f"=== CODED REGIME CLASSIFICATION: {coded_regime} ===")
            lines.append(f"The rule-based decision tree classified this as {coded_regime}.")
            lines.append("Your job: CONFIRM this or OVERRIDE it (in either direction) with evidence.")
            lines.append("")

        # === 2. Portfolio drawdown context ===
        if self.portfolio_history:
            current_value = self.portfolio_history[-1].get("total_value", 0)
            if self._peak_value > 0:
                dd_pct = (current_value - self._peak_value) / self._peak_value * 100
                lines.append(f"=== PORTFOLIO STATUS ===")
                lines.append(f"  Peak value: ${self._peak_value:,.0f}")
                lines.append(f"  Current value: ${current_value:,.0f}")
                lines.append(f"  Drawdown from peak: {dd_pct:.1f}%")
                lines.append("")

        # === 3. Peer strategy signals ===
        lines.append("=== STRATEGY SIGNALS (7 live trading strategies) ===")
        for name, ret in peers.get("strategy_returns", {}).items():
            lines.append(f"  {name}: return={ret:+.1f}%")
        lines.append(f"  Average return across all strategies: {peers.get('avg_return', 0):+.1f}%")
        lines.append(f"  Defensive strategy state: {peers.get('defensive_state', '?')}")
        lines.append(f"  Adaptive strategy mode: {peers.get('adaptive_mode', '?')}")
        lines.append(f"  Commodity strategy: {'INVESTED in oil' if peers.get('commodity_invested') else 'IN CASH'} (return: {peers.get('commodity_return', 0):+.1f}%)")
        lines.append(f"  Strategies heavy in cash (>50% cash): {peers.get('cash_heavy_count', 0)} of 7")
        lines.append("")

        # === 4. SPY / market data ===
        lines.append("=== SPY / BROAD MARKET ===")
        lines.append(f"  SPY above 50-day MA: {market.get('spy_above_50ma', '?')}")
        lines.append(f"  SPY above 200-day MA: {market.get('spy_above_200ma', '?')}")
        lines.append(f"  SPY 20-day annualized volatility: {market.get('spy_vol_20d', 0):.1%}")
        lines.append(f"  SPY 1-month return: {market.get('spy_ret_1m', 0):+.1f}%")
        lines.append(f"  SPY 3-month return: {market.get('spy_ret_3m', 0):+.1f}%")
        lines.append(f"  SPY drawdown from 60-day peak: {market.get('spy_drawdown', 0):.1f}%")
        lines.append(f"  Volatility trend: {extended.get('vol_trend', '?')}")
        lines.append("")

        # === 5. Sector rotation ===
        lines.append("=== SECTOR ROTATION (1-month / 3-month returns) ===")
        sectors = extended.get("sectors", {})
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("ret_3m", 0), reverse=True)
        for sector_name, data in sorted_sectors:
            lines.append(f"  {sector_name}: 1m={data.get('ret_1m', 0):+.1f}%, 3m={data.get('ret_3m', 0):+.1f}%")
        breadth = extended.get("breadth", 0)
        total_sectors = len(sectors)
        lines.append(f"  Market breadth: {breadth}/{total_sectors} sectors positive (3m)")
        lines.append("")

        # === 6. Safe havens ===
        lines.append("=== SAFE HAVEN SIGNALS ===")
        for name, data in extended.get("safe_havens", {}).items():
            lines.append(f"  {name}: 1m={data.get('ret_1m', 0):+.1f}%, 3m={data.get('ret_3m', 0):+.1f}%")
        for name, data in extended.get("risk_appetite", {}).items():
            lines.append(f"  {name}: 1m={data.get('ret_1m', 0):+.1f}%, 3m={data.get('ret_3m', 0):+.1f}%")
        # Interpret
        gld = extended.get("safe_havens", {}).get("Gold", {})
        tlt = extended.get("safe_havens", {}).get("Long-Term Treasuries (20y+)", {})
        hyg = extended.get("risk_appetite", {}).get("High Yield Bonds (junk)", {})
        if gld.get("ret_1m", 0) > 3 and tlt.get("ret_1m", 0) > 1:
            lines.append("  SIGNAL: Gold and Treasuries both up = flight to safety (RISK-OFF)")
        elif gld.get("ret_1m", 0) < -2 and tlt.get("ret_1m", 0) < -1:
            lines.append("  SIGNAL: Gold and Treasuries both down = risk appetite (RISK-ON)")
        elif gld.get("ret_1m", 0) > 3 and tlt.get("ret_1m", 0) < -1:
            lines.append("  SIGNAL: Gold up but Treasuries down = inflation fear")
        if hyg.get("ret_1m", 0) < -3:
            lines.append("  SIGNAL: High yield bonds falling = credit stress / risk-off")
        lines.append("")

        # === 7. Energy / Oil detail ===
        lines.append("=== ENERGY / OIL DETAIL ===")
        lines.append(f"  Oil signal from market sensor: {'BULLISH' if market.get('oil_bullish') else 'BEARISH'}")
        for name, data in extended.get("energy_detail", {}).items():
            lines.append(f"  {name}: 1m={data.get('ret_1m', 0):+.1f}%, 3m={data.get('ret_3m', 0):+.1f}%")
        # Oil vs SPY divergence
        uso = extended.get("energy_detail", {}).get("Oil (USO ETF)", {})
        spy_3m = market.get("spy_ret_3m", 0)
        oil_3m = uso.get("ret_3m", 0)
        if oil_3m - spy_3m > 15:
            lines.append(f"  ALERT: Oil outperforming SPY by {oil_3m - spy_3m:.0f}% over 3 months (STRONG commodity signal)")
        elif oil_3m - spy_3m > 5:
            lines.append(f"  WARNING: Oil outperforming SPY by {oil_3m - spy_3m:.0f}% (commodity dominance building)")
        lines.append("")

        # === 8. News / Geopolitical context ===
        lines.append("=== NEWS / GEOPOLITICAL CONTEXT ===")
        news_summary = getattr(self, '_last_news_summary', None)
        if news_summary:
            lines.append(f"  {news_summary}")
        else:
            lines.append("  No significant geopolitical news detected")
        signal_regime = getattr(self, '_last_regime', None)
        if signal_regime and not signal_regime.startswith("mix:"):
            lines.append(f"  Signal engine macro regime: {signal_regime}")
        lines.append("")

        # === 9. Your regime history (last 5 classifications) ===
        lines.append("=== YOUR REGIME HISTORY (recent classifications) ===")
        if self.regime_history:
            recent = self.regime_history[-5:]
            for entry in recent:
                lines.append(f"  {entry['date']}: {entry.get('from', '?')} -> {entry.get('to', '?')}")
            lines.append(f"  Current regime: {self.detected_regime}")
            if len(self.regime_history) > 0:
                last_change = self.regime_history[-1].get("date", "?")
                lines.append(f"  Last regime change: {last_change}")
        else:
            lines.append(f"  No prior classifications yet (first rebalance)")
            lines.append(f"  Starting regime: {self.detected_regime}")
        lines.append("")

        # === 10. Key pattern alerts ===
        lines.append("=== KEY PATTERN ALERTS ===")
        alerts = []

        # Commodity dominance
        comm_ret = peers.get("commodity_return", 0)
        avg_ret = peers.get("avg_return", 0)
        if comm_ret > avg_ret + 10:
            alerts.append(f"STRONG: Commodity outperforming average by {comm_ret - avg_ret:.0f}% (late-cycle/crisis)")
        elif comm_ret > avg_ret + 5:
            alerts.append(f"WARNING: Commodity outperforming average by {comm_ret - avg_ret:.0f}% (late-cycle signal)")

        # Both momentum and value negative
        mom_ret = peers.get("momentum_return", 0)
        val_ret = peers.get("value_return", 0)
        if mom_ret < -3 and val_ret < -3:
            alerts.append(f"DANGER: Both Momentum ({mom_ret:+.1f}%) and Value ({val_ret:+.1f}%) significantly negative")
        elif mom_ret < 0 and val_ret < 0:
            alerts.append(f"WARNING: Both Momentum ({mom_ret:+.1f}%) and Value ({val_ret:+.1f}%) negative")

        # Defensive + Adaptive confirmation
        if peers.get("defensive_state") == "DEFENSE" and peers.get("adaptive_mode") == "DEFENSIVE":
            alerts.append("CONFIRMED BEAR: Both Defensive (DEFENSE) and Adaptive (DEFENSIVE) in crisis mode")
        elif peers.get("defensive_state") == "DEFENSE":
            alerts.append("ALERT: Defensive strategy in DEFENSE mode (multiple danger signals)")

        # Cash heavy
        cash_heavy = peers.get("cash_heavy_count", 0)
        if cash_heavy >= 4:
            alerts.append(f"ALERT: {cash_heavy} of 7 strategies are heavy cash — strong consensus to de-risk")
        elif cash_heavy >= 3:
            alerts.append(f"WARNING: {cash_heavy} of 7 strategies going to cash")

        # Narrow breadth
        if breadth <= 2 and total_sectors >= 5:
            alerts.append(f"NARROW MARKET: Only {breadth}/{total_sectors} sectors positive — concentrated/fragile")
        elif breadth >= 5:
            alerts.append(f"BROAD MARKET: {breadth}/{total_sectors} sectors positive — healthy participation")

        # Energy-only market
        energy_data = sectors.get("energy", {})
        if energy_data.get("ret_3m", 0) > 10:
            non_energy_positive = sum(1 for s, d in sectors.items() if s != "energy" and d.get("ret_3m", 0) > 0)
            if non_energy_positive <= 1:
                alerts.append("ENERGY-ONLY MARKET: Energy is the only winning sector — classic late-cycle/crisis")

        if not alerts:
            alerts.append("No major pattern alerts detected")

        for alert in alerts:
            lines.append(f"  {alert}")

        return "\n".join(lines)

    # ================================================================
    # LLM CALL — same SDK/CLI infrastructure as v2
    # ================================================================
    # Model selection — set via env var MIXLLM_MODEL (default: opus)
    LLM_MODEL = os.environ.get("MIXLLM_MODEL", "opus")

    # Map short names to SDK model IDs
    _MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001",
    }

    def _call_llm(self, sensor_data, date, trigger_reasons=None):
        """Call Claude for regime classification — only at trigger events.

        Uses Anthropic SDK if ANTHROPIC_API_KEY is set (no browser tabs).
        Falls back to Claude CLI subprocess otherwise.
        """
        trigger_context = ""
        if trigger_reasons:
            trigger_context = (
                "You were called because:\n" +
                "\n".join(f"- {r}" for r in trigger_reasons) +
                "\n\n"
            )

        user_prompt = (
            f"{trigger_context}"
            f"Review the coded regime classification below and decide: CONFIRM or OVERRIDE.\n"
            f"You may override in EITHER direction — more aggressive or more defensive.\n\n"
            f"{sensor_data}\n\n"
            "Look at the extended data (sectors, safe havens, oil detail, news, regime history, "
            "portfolio drawdown) for signals the coded rules missed or misinterpreted.\n\n"
            'Reply with ONLY a JSON object: {"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", '
            '"action": "CONFIRM|OVERRIDE", "confidence": 0.0-1.0, '
            '"reasoning": "1-2 sentences. What signal justifies your call?"}'
        )

        try:
            if _USE_SDK:
                response = self._call_sdk(user_prompt)
            else:
                response = self._call_cli(user_prompt)

            self._llm_call_count += 1
            regime, confidence, reasoning = self._parse_llm_response(response)

            self._llm_log.append({
                "date": date, "source": "llm", "regime": regime,
                "confidence": confidence, "reasoning": reasoning,
                "trigger_reasons": trigger_reasons or [],
                "raw_response": response[:500],
            })
            return regime

        except Exception as e:
            error_str = str(e).lower()
            if "auth" in error_str or "key" in error_str or "rate" in error_str or "billing" in error_str:
                print(f"  WARNING: LLM API error ({type(e).__name__}): {str(e).encode('ascii', 'replace').decode()}")
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "error", "regime": None,
                "reason": str(e)[:200],
                "trigger_reasons": trigger_reasons or [],
            })
            return None

    def _call_sdk(self, user_prompt):
        """Call via Anthropic Python SDK — no browser tabs, no subprocess."""
        model_id = self._MODEL_MAP.get(self.LLM_MODEL, self.LLM_MODEL)
        message = _anthropic_client.messages.create(
            model=model_id,
            max_tokens=512,
            system=EXPERT_KNOWLEDGE,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text.strip()

    def _call_cli(self, user_prompt):
        """Call via Claude CLI subprocess — fallback if no API key."""
        import tempfile
        result = subprocess.run(
            [CLAUDE_CMD, "-p", "-",
             "--model", self.LLM_MODEL,
             "--system-prompt", EXPERT_KNOWLEDGE,
             "--output-format", "text"],
            input=user_prompt,
            capture_output=True, text=True, timeout=90,
            cwd=tempfile.gettempdir(),
        )
        return result.stdout.strip()

    def _parse_llm_response(self, response):
        """Parse the LLM response to extract regime classification."""
        regime = None
        confidence = 0.5
        reasoning = ""

        # Look for JSON block
        try:
            if "{" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                data = json.loads(json_str)
                regime = data.get("regime", "").upper()
                confidence = data.get("confidence", 0.5)
                reasoning = data.get("reasoning", "")
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: look for regime keyword in response
        if not regime:
            response_upper = response.upper()
            for r in ["DEFENSIVE", "AGGRESSIVE", "RECOVERY", "CAUTIOUS", "UNCERTAIN"]:
                if r in response_upper:
                    regime = r
                    break

        return regime, confidence, reasoning

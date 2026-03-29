"""Mix LLM Strategy v2 — Enhanced regime detection with rich market context.

Major upgrade from v1:
- Sends sector rotation, safe havens, bonds, oil detail, news, regime history
- Uses Sonnet instead of Haiku for better reasoning
- Gives LLM the same quality of data a human analyst would use
- Falls back to coded rules if LLM call fails

Only calls LLM on rebalance days (~10-15 calls per period, not every day).
"""

import json
import subprocess
import os
import numpy as np
import pandas as pd
from .mix_strategy import MixStrategy, REGIME_ALLOCATIONS, OIL_PROXIES

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

# Expert knowledge prompt — LLM acts as RISK MONITOR (defensive escalation only)
EXPERT_KNOWLEDGE = """You are a RISK MONITOR for a multi-strategy trading system.

A coded decision tree has classified the current regime (usually AGGRESSIVE).
The coded rules work well — they correctly stay AGGRESSIVE in bull markets and the
momentum stock picker naturally finds sector winners (including energy in oil rallies).

YOUR ROLE: Decide if the coded regime should be ESCALATED to a more defensive posture.
The system will IGNORE any attempt to make the regime LESS defensive.
You can only move the needle toward: CAUTIOUS → DEFENSIVE (not the other way).

## WHEN TO CONFIRM (most of the time — 80%+):
- If SPY is above both MAs and vol is low → CONFIRM. Gold rising alone is not enough to override.
- If the coded rules say AGGRESSIVE and the stock market is broadly healthy → CONFIRM.
- Mixed signals with no clear crisis → CONFIRM. Don't second-guess without crisis-level evidence.
- Rising geo_risk alone is NOT enough. It needs to be paired with market damage (SPY below MAs, sectors collapsing).
- The momentum stock picker handles sector rotation automatically — it finds energy winners in energy-led markets.

## WHEN TO ESCALATE TO CAUTIOUS (rare — genuine transition):
- SPY dropped below 50ma AND oil is outperforming SPY by >15% over 3 months
- Gold up >15% (3m) AND safe havens rising AND breadth narrowing below 3 sectors
- Coded says AGGRESSIVE but the market is clearly turning — not just a dip, but a structural shift
- This is a WARNING call, not a panic call

## WHEN TO ESCALATE TO DEFENSIVE (very rare — genuine crisis):
- Oil surging >30% in 3 months AND SPY below BOTH MAs (commodity shock / supply disruption)
- Gold surging AND treasuries surging AND HYG falling (classic flight to safety)
- Energy is the ONLY positive sector AND geo_risk > 0.5 AND SPY in drawdown > -5%
- Multiple strategies heavy in cash (4+) AND Defensive in DEFENSE mode
- This is a CRISIS call — Q1 2026 Hormuz, COVID crash, 2022 bear territory
- DEFENSIVE allocates 30% commodity, 50% cash — this captures oil spikes

## KEY LESSON FROM BACKTESTING:
- In 2025, the coded rules stayed AGGRESSIVE and earned +24.4%. An LLM that constantly worried
  about gold, geo_risk, and healthcare weakness would have earned only +7.3%.
- In Q1 2026, DEFENSIVE would have captured the +28% oil trade, but the coded rules missed it.
- The LLM's value is ONLY in catching genuine crises — NOT in being perpetually worried.
- If you escalate when you shouldn't, you cost the portfolio 15%+ in missed bull market gains.
- If you fail to escalate during a real crisis, you cost the portfolio 20%+ in losses.
- The cost of false alarms is HIGHER than the cost of late detection. Be conservative with overrides.

## Regime allocations:
- AGGRESSIVE: 90% stocks, 0% commodity, 10% cash
- CAUTIOUS: 50% stocks, 20% commodity, 30% cash
- DEFENSIVE: 20% stocks, 30% commodity, 50% cash
- RECOVERY: 80% stocks, 0% commodity, 20% cash
- UNCERTAIN: 70% stocks, 0% commodity, 30% cash

## Output format:
Respond with ONLY a JSON object:
{"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", "action": "CONFIRM|ESCALATE", "confidence": 0.0-1.0, "reasoning": "1-2 sentences. If ESCALATE, what crisis signal did the coded rules miss?"}"""


class MixLLMStrategy(MixStrategy):
    """Mix strategy with enhanced LLM-powered regime detection (v2)."""

    def __init__(self, initial_cash=100_000, events_calendar=None, max_positions=10):
        super().__init__(initial_cash, events_calendar, max_positions)
        self.name = "MixLLM"
        self._llm_call_count = 0
        self._llm_fallback_count = 0
        self._llm_log = []  # log every LLM call for debugging

    # Defensive ordering: higher = more defensive
    _DEFENSE_LEVEL = {
        "AGGRESSIVE": 0, "RECOVERY": 1, "UNCERTAIN": 2, "CAUTIOUS": 3, "DEFENSIVE": 4,
    }

    def _detect_regime(self, price_data, date):
        """Override: coded rules FIRST, then LLM can only ESCALATE defensiveness.

        The coded rules work well 80%+ of the time and bias AGGRESSIVE (correct).
        The LLM's value is catching genuine crises the rules miss.
        LLM can make the regime MORE defensive, but CANNOT reduce defensiveness.
        """
        # Step 1: Get the coded regime from parent class (this also sets sensors)
        coded_regime = super()._detect_regime(price_data, date)
        peers = self._sensor_readings.get("peers", {})
        market = self._sensor_readings.get("market", {})

        # Step 2: Compute extended market data (sectors, safe havens, bonds, oil)
        extended = self._sense_market_extended(price_data, date)

        # Step 3: Build rich data payload including the coded regime
        sensor_summary = self._format_sensors_for_llm_v2(
            peers, market, extended, date, coded_regime=coded_regime)

        # Step 4: Ask LLM to confirm or override
        llm_regime = self._call_llm(sensor_summary, date)

        # Step 5: Apply directional filter — LLM can only escalate defensiveness
        valid_regimes = set(REGIME_ALLOCATIONS.keys())
        if llm_regime not in valid_regimes:
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "fallback", "regime": coded_regime,
                "reason": "LLM returned invalid regime, using coded rules",
            })
            return coded_regime

        coded_level = self._DEFENSE_LEVEL.get(coded_regime, 2)
        llm_level = self._DEFENSE_LEVEL.get(llm_regime, 2)

        if llm_level > coded_level:
            # LLM is escalating defensiveness — accept (this is the value-add)
            self._llm_log[-1]["action"] = "ESCALATE"
            self._llm_log[-1]["note"] = f"Overrode {coded_regime} -> {llm_regime} (more defensive)"
            return llm_regime
        else:
            # LLM is confirming or trying to go LESS defensive — use coded
            self._llm_log[-1]["action"] = "CONFIRM" if llm_regime == coded_regime else "REJECTED"
            if llm_regime != coded_regime:
                self._llm_log[-1]["note"] = (
                    f"LLM wanted {llm_regime} but coded={coded_regime} is more defensive, keeping coded")
            return coded_regime

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
                r1m, r3m = self._get_returns(price_data, ticker, ts)
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
            r1m, r3m = self._get_returns(price_data, ticker, ts)
            if r1m is not None:
                result["safe_havens"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Risk appetite (credit spreads proxy) ---
        for ticker, name in RISK_TICKERS.items():
            r1m, r3m = self._get_returns(price_data, ticker, ts)
            if r1m is not None:
                result["risk_appetite"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Energy/oil detail ---
        for ticker, name in ENERGY_TICKERS.items():
            r1m, r3m = self._get_returns(price_data, ticker, ts)
            if r1m is not None:
                result["energy_detail"][name] = {
                    "ticker": ticker, "ret_1m": round(r1m, 1),
                    "ret_3m": round(r3m, 1) if r3m else 0,
                }

        # --- Volatility trend ---
        if "SPY" in price_data and not price_data["SPY"].empty:
            df = price_data["SPY"]
            mask = df.index <= ts
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

    def _get_returns(self, price_data, ticker, ts):
        """Get 1-month and 3-month returns for a ticker."""
        if ticker not in price_data or price_data[ticker].empty:
            return None, None
        df = price_data[ticker]
        mask = df.index <= ts
        if not mask.any() or mask.sum() < 22:
            return None, None
        close = df.loc[mask, "Close"].tail(252)
        current = float(close.iloc[-1])
        r1m = (current / float(close.iloc[-22]) - 1) * 100 if len(close) >= 22 else None
        r3m = (current / float(close.iloc[-66]) - 1) * 100 if len(close) >= 66 else None
        return r1m, r3m

    # ================================================================
    # FORMAT — rich context for the LLM
    # ================================================================
    def _format_sensors_for_llm_v2(self, peers, market, extended, date, coded_regime=None):
        """Format comprehensive market data for the LLM — same quality as human analysis."""
        lines = [f"Date: {date}", ""]

        # === 0. Coded regime baseline ===
        if coded_regime:
            lines.append(f"=== CODED REGIME CLASSIFICATION: {coded_regime} ===")
            lines.append(f"The rule-based decision tree classified this as {coded_regime}.")
            lines.append("Your job: CONFIRM this or OVERRIDE with strong evidence from the data below.")
            lines.append("")

        # === 1. Peer strategy signals ===
        lines.append("=== STRATEGY SIGNALS (7 live trading strategies) ===")
        for name, ret in peers.get("strategy_returns", {}).items():
            lines.append(f"  {name}: return={ret:+.1f}%")
        lines.append(f"  Average return across all strategies: {peers.get('avg_return', 0):+.1f}%")
        lines.append(f"  Defensive strategy state: {peers.get('defensive_state', '?')}")
        lines.append(f"  Adaptive strategy mode: {peers.get('adaptive_mode', '?')}")
        lines.append(f"  Commodity strategy: {'INVESTED in oil' if peers.get('commodity_invested') else 'IN CASH'} (return: {peers.get('commodity_return', 0):+.1f}%)")
        lines.append(f"  Strategies heavy in cash (>50% cash): {peers.get('cash_heavy_count', 0)} of 7")
        lines.append("")

        # === 2. SPY / market data ===
        lines.append("=== SPY / BROAD MARKET ===")
        lines.append(f"  SPY above 50-day MA: {market.get('spy_above_50ma', '?')}")
        lines.append(f"  SPY above 200-day MA: {market.get('spy_above_200ma', '?')}")
        lines.append(f"  SPY 20-day annualized volatility: {market.get('spy_vol_20d', 0):.1%}")
        lines.append(f"  SPY 1-month return: {market.get('spy_ret_1m', 0):+.1f}%")
        lines.append(f"  SPY 3-month return: {market.get('spy_ret_3m', 0):+.1f}%")
        lines.append(f"  SPY drawdown from 60-day peak: {market.get('spy_drawdown', 0):.1f}%")
        lines.append(f"  Volatility trend: {extended.get('vol_trend', '?')}")
        lines.append("")

        # === 3. Sector rotation ===
        lines.append("=== SECTOR ROTATION (1-month / 3-month returns) ===")
        sectors = extended.get("sectors", {})
        # Sort by 3m return to show leaders/laggers clearly
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("ret_3m", 0), reverse=True)
        for sector_name, data in sorted_sectors:
            lines.append(f"  {sector_name}: 1m={data.get('ret_1m', 0):+.1f}%, 3m={data.get('ret_3m', 0):+.1f}%")
        breadth = extended.get("breadth", 0)
        total_sectors = len(sectors)
        lines.append(f"  Market breadth: {breadth}/{total_sectors} sectors positive (3m)")
        lines.append("")

        # === 4. Safe havens ===
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

        # === 5. Energy / Oil detail ===
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

        # === 6. News / Geopolitical context ===
        lines.append("=== NEWS / GEOPOLITICAL CONTEXT ===")
        news_summary = getattr(self, '_last_news_summary', None)
        if news_summary:
            lines.append(f"  {news_summary}")
        else:
            lines.append("  No significant geopolitical news detected")
        # Also check signal engine regime if available
        signal_regime = getattr(self, '_last_regime', None)
        if signal_regime and not signal_regime.startswith("mix:"):
            lines.append(f"  Signal engine macro regime: {signal_regime}")
        lines.append("")

        # === 7. Your regime history (last 5 classifications) ===
        lines.append("=== YOUR REGIME HISTORY (recent classifications) ===")
        if self.regime_history:
            recent = self.regime_history[-5:]
            for entry in recent:
                lines.append(f"  {entry['date']}: {entry.get('from', '?')} -> {entry.get('to', '?')}")
            lines.append(f"  Current regime: {self.detected_regime}")
            # How long in current regime
            if len(self.regime_history) > 0:
                last_change = self.regime_history[-1].get("date", "?")
                lines.append(f"  Last regime change: {last_change}")
        else:
            lines.append(f"  No prior classifications yet (first rebalance)")
            lines.append(f"  Starting regime: {self.detected_regime}")
        lines.append("")

        # === 8. Key pattern alerts ===
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

    def _call_llm(self, sensor_data, date):
        """Call Claude CLI (Sonnet) for regime classification.

        Uses Sonnet for better reasoning on complex multi-signal analysis.
        Pipes prompt via stdin to avoid Windows arg length limits.
        Runs from temp dir to avoid Claude Code picking up codebase context.
        """
        user_prompt = (
            f"Review the coded regime classification below and CONFIRM or OVERRIDE it.\n\n"
            f"{sensor_data}\n\n"
            "Look at the extended data (sectors, safe havens, oil detail, news, regime history) "
            "for signals the coded rules CANNOT see. If no strong override signal exists, CONFIRM.\n\n"
            'Reply with ONLY a JSON object: {"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", '
            '"action": "CONFIRM|OVERRIDE", "confidence": 0.0-1.0, '
            '"reasoning": "1-2 sentences. If OVERRIDE, what did the coded rules miss?"}'
        )

        try:
            import tempfile
            result = subprocess.run(
                [CLAUDE_CMD, "-p", "-",
                 "--model", "sonnet",
                 "--system-prompt", EXPERT_KNOWLEDGE,
                 "--output-format", "text"],
                input=user_prompt,
                capture_output=True, text=True, timeout=90,
                cwd=tempfile.gettempdir(),
            )

            self._llm_call_count += 1
            response = result.stdout.strip()

            # Parse JSON from response
            regime, confidence, reasoning = self._parse_llm_response(response)

            self._llm_log.append({
                "date": date, "source": "llm", "regime": regime,
                "confidence": confidence, "reasoning": reasoning,
                "raw_response": response[:500],
            })

            return regime

        except subprocess.TimeoutExpired:
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "timeout", "regime": None,
                "reason": "LLM call timed out after 90s",
            })
            return None  # will trigger fallback

        except Exception as e:
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "error", "regime": None,
                "reason": str(e)[:200],
            })
            return None

    def _parse_llm_response(self, response):
        """Parse the LLM response to extract regime classification."""
        regime = None
        confidence = 0.5
        reasoning = ""
        action = "CONFIRM"

        # Look for JSON block
        try:
            if "{" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                data = json.loads(json_str)
                regime = data.get("regime", "").upper()
                confidence = data.get("confidence", 0.5)
                reasoning = data.get("reasoning", "")
                action = data.get("action", "CONFIRM").upper()
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

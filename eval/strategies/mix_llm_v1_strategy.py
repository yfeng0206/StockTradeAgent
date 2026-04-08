"""Mix LLM V1 Strategy — Recovery-detecting variant of MixLLM.

Opposite constraint from MixLLM (v2):
- MixLLM v2: LLM can only ESCALATE defensiveness (coded rules handle aggression)
- MixLLM V1: LLM can only REDUCE defensiveness (coded rules handle defense)

The coded decision tree is already good at detecting danger and going defensive.
Where it struggles is knowing when the danger has PASSED and it's safe to go back
to aggressive. This variant lets the LLM confirm recovery signals — it can only
make the regime LESS defensive, never more.

Same infrastructure: Anthropic SDK or CLI fallback, extended sensing, rich context.
Only calls LLM on rebalance days (~10-15 calls per period, not every day).
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

# Expert knowledge prompt — LLM acts as RECOVERY DETECTOR (can only reduce defensiveness)
EXPERT_KNOWLEDGE_V1 = """You are a RECOVERY DETECTOR for a multi-strategy trading system.

A coded decision tree has classified the current regime. The coded rules are EXCELLENT at
detecting danger — they catch crashes, commodity shocks, and bear markets reliably.
Where they FAIL is recognizing when the danger has PASSED. They stay defensive too long,
missing 10-20% of recovery gains because they wait for lagging indicators to confirm safety.

YOUR ROLE: Decide if the coded regime should be DE-ESCALATED to a less defensive posture.
The system will IGNORE any attempt to make the regime MORE defensive.
You can only move the needle toward: RECOVERY -> AGGRESSIVE (not toward DEFENSIVE).

## WHEN TO CONFIRM (most of the time — 70%+):
- If the coded rules say AGGRESSIVE and the market IS healthy -> CONFIRM. Don't interfere.
- If the coded rules say DEFENSIVE and there IS genuine danger -> CONFIRM. The rules are right.
- If the danger signals are still active (SPY below MAs, VIX elevated, credit stress) -> CONFIRM.
- Mixed signals with no clear recovery evidence -> CONFIRM. Don't force optimism.

## WHEN TO DE-ESCALATE TO RECOVERY (the key value-add — 20%):
- Coded says DEFENSIVE but SPY has reclaimed 50-day MA and breadth is improving (3+ sectors positive)
- Coded says CAUTIOUS but the crisis catalyst has faded (oil settling, VIX declining, credit stable)
- Safe havens (gold, treasuries) are FALLING while risk assets (HYG) are rising -> risk-on transition
- Multiple strategies turning profitable again after a drawdown (momentum picking up new leaders)
- The coded rules are still anchored on a danger signal that is 2-4 weeks stale

## WHEN TO DE-ESCALATE TO AGGRESSIVE (rare — clear all-clear):
- Coded says CAUTIOUS/DEFENSIVE but SPY is above BOTH MAs, vol is falling, breadth is 5+ sectors
- The crisis that triggered defensiveness is definitively over (not just pausing)
- Risk appetite indicators all healthy: HYG rising, gold flat/falling, VIX < 20 equivalent
- This should be rare — RECOVERY is usually the right intermediate step

## WHEN NOT TO DE-ESCALATE (critical — avoid these traps):
- Bear market rallies: sharp bounces within a downtrend. Check if SPY is still below 200-day MA.
- Dead cat bounces: brief recoveries before another leg down. Look for breadth confirmation.
- Coded says DEFENSIVE and oil is still surging / geopolitical crisis is still active -> DON'T override.
- If only 1-2 sectors are recovering but the rest are flat/down -> not enough breadth.

## KEY LESSON FROM BACKTESTING:
- The coded rules correctly go DEFENSIVE during genuine crises (COVID, 2022 bear, Q1 2026 Hormuz).
- But they take 4-8 weeks too long to come back to AGGRESSIVE after the danger passes.
- In recovery phases, being 4 weeks early to AGGRESSIVE beats being 4 weeks late by 8-15%.
- The cost of a false recovery call (going aggressive during a bear rally) is ~5% drawdown.
- The cost of staying defensive too long after a real recovery starts is ~10-15% in missed gains.
- Your job is to catch the REAL recoveries early, not to call every bounce a recovery.

## Regime allocations:
- AGGRESSIVE: 90% stocks, 0% commodity, 10% cash
- CAUTIOUS: 50% stocks, 20% commodity, 30% cash
- DEFENSIVE: 20% stocks, 30% commodity, 50% cash
- RECOVERY: 80% stocks, 0% commodity, 20% cash
- UNCERTAIN: 70% stocks, 0% commodity, 30% cash

## Output format:
Respond with ONLY a JSON object:
{"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", "action": "CONFIRM|DE-ESCALATE", "confidence": 0.0-1.0, "reasoning": "1-2 sentences. If DE-ESCALATE, what recovery signal did the coded rules miss?"}"""


class MixLLMV1Strategy(MixStrategy):
    """Mix strategy with LLM-powered recovery detection (V1 — LLM reduces defensiveness only)."""

    def __init__(self, initial_cash=100_000, events_calendar=None, max_positions=10,
                 regime_stickiness=1):
        super().__init__(initial_cash, events_calendar, max_positions,
                         regime_stickiness=regime_stickiness)
        self.name = "MixLLM_V1"
        self._llm_call_count = 0
        self._llm_fallback_count = 0
        self._llm_log = []  # log every LLM call for debugging

    # Defensive ordering: higher = more defensive
    _DEFENSE_LEVEL = {
        "AGGRESSIVE": 0, "RECOVERY": 1, "UNCERTAIN": 2, "CAUTIOUS": 3, "DEFENSIVE": 4,
    }

    def _detect_regime(self, price_data, date, breadth: dict = None):
        """Override: coded rules FIRST, then LLM can only REDUCE defensiveness.

        The coded rules work well at detecting danger and going defensive.
        The LLM's value is catching when recovery is real and the coded rules
        are being too cautious. LLM can make the regime LESS defensive,
        but CANNOT increase defensiveness.
        """
        # Step 1: Get the coded regime from parent class (this also sets sensors)
        coded_regime = super()._detect_regime(price_data, date, breadth=breadth)
        peers = self._sensor_readings.get("peers", {})
        market = self._sensor_readings.get("market", {})

        # Step 2: Compute extended market data (sectors, safe havens, bonds, oil)
        extended = self._sense_market_extended(price_data, date)

        # Step 3: Build rich data payload including the coded regime
        sensor_summary = self._format_sensors_for_llm_v1(
            peers, market, extended, date, coded_regime=coded_regime)

        # Step 4: Ask LLM to confirm or de-escalate
        llm_regime = self._call_llm(sensor_summary, date)

        # Step 5: Apply directional filter — LLM can only REDUCE defensiveness
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

        if llm_level < coded_level:
            # LLM is reducing defensiveness — accept (this is the value-add)
            self._llm_log[-1]["action"] = "DE-ESCALATE"
            self._llm_log[-1]["note"] = f"Overrode {coded_regime} -> {llm_regime} (less defensive)"
            return llm_regime
        else:
            # LLM is confirming or trying to go MORE defensive — use coded
            self._llm_log[-1]["action"] = "CONFIRM" if llm_regime == coded_regime else "REJECTED"
            if llm_regime != coded_regime:
                self._llm_log[-1]["note"] = (
                    f"LLM wanted {llm_regime} but coded={coded_regime} is less defensive, keeping coded")
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
    # FORMAT — rich context for the LLM (recovery-focused framing)
    # ================================================================
    def _format_sensors_for_llm_v1(self, peers, market, extended, date, coded_regime=None):
        """Format comprehensive market data for the LLM — recovery detection framing."""
        lines = [f"Date: {date}", ""]

        # === 0. Coded regime baseline ===
        if coded_regime:
            lines.append(f"=== CODED REGIME CLASSIFICATION: {coded_regime} ===")
            lines.append(f"The rule-based decision tree classified this as {coded_regime}.")
            lines.append("Your job: CONFIRM this or DE-ESCALATE if recovery evidence shows the coded rules are too cautious.")
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
        if hyg.get("ret_1m", 0) > 2:
            lines.append("  SIGNAL: High yield bonds rising = improving risk appetite (RISK-ON)")
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

        # === 8. Key pattern alerts (recovery-focused) ===
        lines.append("=== KEY PATTERN ALERTS (RECOVERY FOCUS) ===")
        alerts = []

        # Recovery signals — these are what the LLM should look for
        spy_above_50 = market.get("spy_above_50ma", False)
        spy_above_200 = market.get("spy_above_200ma", False)
        vol_trend = extended.get("vol_trend", "unknown")

        if spy_above_50 and spy_above_200 and breadth >= 4:
            alerts.append(f"RECOVERY SIGNAL: SPY above both MAs AND {breadth}/{total_sectors} sectors positive — broad health")
        elif spy_above_50 and breadth >= 3:
            alerts.append(f"IMPROVING: SPY reclaimed 50-day MA AND {breadth}/{total_sectors} sectors positive")

        if "FALLING" in vol_trend:
            alerts.append("RECOVERY SIGNAL: Volatility declining — fear subsiding")

        # Risk-on rotation: safe havens falling, risk assets rising
        gld_falling = gld.get("ret_1m", 0) < -1
        hyg_rising = hyg.get("ret_1m", 0) > 1
        if gld_falling and hyg_rising:
            alerts.append("RISK-ON ROTATION: Gold falling + HYG rising = money moving back to risk assets")

        # Strategy recovery
        avg_ret = peers.get("avg_return", 0)
        if avg_ret > 0 and peers.get("cash_heavy_count", 0) <= 2:
            alerts.append(f"STRATEGY RECOVERY: Average return positive ({avg_ret:+.1f}%) and most strategies deployed")

        # Danger signals still active — warn against premature de-escalation
        if not spy_above_50 and not spy_above_200:
            alerts.append("CAUTION: SPY still below BOTH MAs — trend damage not repaired")
        elif not spy_above_200:
            alerts.append("CAUTION: SPY still below 200-day MA — long-term trend still broken")

        comm_ret = peers.get("commodity_return", 0)
        if comm_ret > avg_ret + 10:
            alerts.append(f"CAUTION: Commodity still outperforming average by {comm_ret - avg_ret:.0f}% (crisis may be active)")

        cash_heavy = peers.get("cash_heavy_count", 0)
        if cash_heavy >= 4:
            alerts.append(f"CAUTION: {cash_heavy} of 7 strategies still heavy cash — broad consensus to stay defensive")

        if peers.get("defensive_state") == "DEFENSE" and peers.get("adaptive_mode") == "DEFENSIVE":
            alerts.append("CAUTION: Both Defensive and Adaptive still in crisis mode — wait for them to relax")

        if breadth <= 2 and total_sectors >= 5:
            alerts.append(f"CAUTION: Only {breadth}/{total_sectors} sectors positive — recovery not broad enough")

        if not alerts:
            alerts.append("No major pattern alerts detected")

        for alert in alerts:
            lines.append(f"  {alert}")

        return "\n".join(lines)

    # Model selection — set via env var MIXLLM_MODEL (default: opus)
    LLM_MODEL = os.environ.get("MIXLLM_MODEL", "opus")

    # Map short names to SDK model IDs
    _MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001",
    }

    def _call_llm(self, sensor_data, date):
        """Call Claude for regime classification.

        Uses Anthropic SDK if ANTHROPIC_API_KEY is set (no browser tabs).
        Falls back to Claude CLI subprocess otherwise.
        """
        user_prompt = (
            f"Review the coded regime classification below and CONFIRM or DE-ESCALATE it.\n\n"
            f"{sensor_data}\n\n"
            "Look at the extended data (sectors, safe havens, oil detail, news, regime history) "
            "for recovery signals the coded rules CANNOT see. If no clear recovery evidence exists, CONFIRM.\n\n"
            'Reply with ONLY a JSON object: {"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", '
            '"action": "CONFIRM|DE-ESCALATE", "confidence": 0.0-1.0, '
            '"reasoning": "1-2 sentences. If DE-ESCALATE, what recovery signal did the coded rules miss?"}'
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
            })
            return None

    def _call_sdk(self, user_prompt):
        """Call via Anthropic Python SDK — no browser tabs, no subprocess."""
        model_id = self._MODEL_MAP.get(self.LLM_MODEL, self.LLM_MODEL)
        message = _anthropic_client.messages.create(
            model=model_id,
            max_tokens=512,
            system=EXPERT_KNOWLEDGE_V1,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text.strip()

    def _call_cli(self, user_prompt):
        """Call via Claude CLI subprocess — fallback if no API key."""
        import tempfile
        result = subprocess.run(
            [CLAUDE_CMD, "-p", "-",
             "--model", self.LLM_MODEL,
             "--system-prompt", EXPERT_KNOWLEDGE_V1,
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

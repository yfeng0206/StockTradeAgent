"""Mix LLM Strategy — Same as Mix but uses Claude for regime detection.

Instead of coded decision tree rules, this variant sends the sensor data
to Claude (via CLI) and asks it to classify the regime. Claude gets
expert knowledge about what each regime looks like, based on our backtesting.

Uses claude CLI (-p flag) for non-interactive calls. Defaults to haiku for speed.
Falls back to coded rules if LLM call fails.

Only calls LLM on rebalance days (~10-15 calls per period, not every day).
"""

import json
import subprocess
import os
from .mix_strategy import MixStrategy, REGIME_ALLOCATIONS, OIL_PROXIES

CLAUDE_CMD = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
if not os.path.exists(CLAUDE_CMD):
    CLAUDE_CMD = "claude"  # fallback to PATH

# Expert knowledge prompt — what we learned from backtesting 7 periods
EXPERT_KNOWLEDGE = """You are a market regime classifier for a multi-strategy trading system.
You have expert knowledge from backtesting 7 market periods (2019-2026).

Your job: given sensor readings from 7 live trading strategies + market data,
classify the current regime as one of: AGGRESSIVE, CAUTIOUS, DEFENSIVE, RECOVERY, UNCERTAIN.

## What each regime means (from backtesting):

### AGGRESSIVE (bull market)
- SPY above both 50ma and 200ma, low volatility (<22%)
- Momentum strategy making money, Adaptive in MOMENTUM mode
- Defensive strategy in NORMAL state, few strategies heavy in cash
- Historical: 2019 bull (+30% SPY), 2023 AI rally (+27% SPY)
- Best strategies in bull: Momentum, Value, EventDriven, Adaptive
- Action: 90% stocks (momentum picks), 0% commodity, 10% cash

### CAUTIOUS (late-cycle / transition)
- Commodity outperforming other strategies significantly
- SPY trend weakening (below 50ma but maybe above 200ma)
- Defensive in REDUCED state, some strategies going to cash
- Oil is bullish while stocks are flat/down
- Historical: Late 2021 before 2022 bear, parts of 2025
- Action: 50% stocks (low-vol), 20% commodity, 30% cash

### DEFENSIVE (bear market / crisis)
- Defensive strategy in DEFENSE mode, multiple danger signals
- Adaptive in DEFENSIVE mode, high volatility (>25%)
- Many strategies (4+) holding >50% cash
- SPY in drawdown, below both MAs
- Historical: 2022 bear (-17.6% SPY), COVID crash
- Action: 20% stocks (ultra-safe), 30% commodity, 50% cash

### RECOVERY (coming out of downturn)
- Adaptive in RECOVERY mode
- Market was recently in drawdown but bouncing (1m return > 2%)
- Momentum turning positive, value stocks bouncing off lows
- Historical: Oct 2022-Jun 2023 recovery (+20.9% SPY)
- Action: 80% stocks (bounce plays), 0% commodity, 20% cash

### UNCERTAIN (mixed signals)
- No clear regime — signals are contradictory
- SPY above 200ma but other signals mixed
- Default to moderate exposure
- Action: 70% stocks (balanced), 0% commodity, 30% cash

## Important patterns from backtesting:
- Commodity dominance (oil outperforming stocks by >10%) = late-cycle warning
- Value and Balanced underwater while SPY is positive = narrow/concentrated market
- When Defensive goes DEFENSE + Adaptive goes DEFENSIVE = confirmed bear (strong signal)
- Bear rally traps: in a bear market, SPY can briefly bounce above 50ma — don't flip to AGGRESSIVE on one signal
- Markets trend up more often than down — default to AGGRESSIVE when unsure and SPY > 200ma
- Speed matters: be FAST to go aggressive when bull signals appear, but SLOW to exit defensive (require confirmation)

## Output format:
Respond with ONLY a JSON object, nothing else:
{"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", "confidence": 0.0-1.0, "reasoning": "one sentence"}"""


class MixLLMStrategy(MixStrategy):
    """Mix strategy with LLM-powered regime detection."""

    def __init__(self, initial_cash=100_000, events_calendar=None, max_positions=10):
        super().__init__(initial_cash, events_calendar, max_positions)
        self.name = "MixLLM"
        self._llm_call_count = 0
        self._llm_fallback_count = 0
        self._llm_log = []  # log every LLM call for debugging

    def _detect_regime(self, price_data, date):
        """Override: use Claude LLM for regime classification."""
        # Still compute sensors (needed for allocation + logging)
        peers = self._sense_peers(price_data, date)
        market = self._sense_market(price_data, date)
        self._sensor_readings = {"peers": peers, "market": market}

        # Build the data payload for the LLM
        sensor_summary = self._format_sensors_for_llm(peers, market, date)

        # Call LLM
        regime = self._call_llm(sensor_summary, date)

        # Validate
        valid_regimes = set(REGIME_ALLOCATIONS.keys())
        if regime not in valid_regimes:
            # Fallback to coded rules
            self._llm_fallback_count += 1
            regime = super()._detect_regime(price_data, date)
            self._llm_log.append({
                "date": date, "source": "fallback", "regime": regime,
                "reason": f"LLM returned invalid regime, falling back to coded rules",
            })

        return regime

    def _format_sensors_for_llm(self, peers, market, date):
        """Format sensor data into a readable string for the LLM."""
        lines = [f"Date: {date}"]
        lines.append("")

        # Peer strategy data
        lines.append("=== STRATEGY SIGNALS (from 7 live strategies) ===")
        for name, ret in peers.get("strategy_returns", {}).items():
            lines.append(f"  {name}: return={ret:+.1f}%")
        lines.append(f"  Average return: {peers.get('avg_return', 0):+.1f}%")
        lines.append(f"  Defensive state: {peers.get('defensive_state', '?')}")
        lines.append(f"  Adaptive mode: {peers.get('adaptive_mode', '?')}")
        lines.append(f"  Commodity strategy: {'INVESTED in oil' if peers.get('commodity_invested') else 'IN CASH'}")
        lines.append(f"  Commodity return: {peers.get('commodity_return', 0):+.1f}%")
        lines.append(f"  Strategies heavy in cash (>50%): {peers.get('cash_heavy_count', 0)} of 7")
        lines.append("")

        # Market data
        lines.append("=== MARKET DATA (SPY + Oil) ===")
        lines.append(f"  SPY above 50ma: {market.get('spy_above_50ma', '?')}")
        lines.append(f"  SPY above 200ma: {market.get('spy_above_200ma', '?')}")
        lines.append(f"  SPY 20d volatility: {market.get('spy_vol_20d', 0):.1%}")
        lines.append(f"  SPY 1-month return: {market.get('spy_ret_1m', 0):+.1f}%")
        lines.append(f"  SPY 3-month return: {market.get('spy_ret_3m', 0):+.1f}%")
        lines.append(f"  SPY drawdown from 60d peak: {market.get('spy_drawdown', 0):.1f}%")
        lines.append(f"  Oil signal bullish: {market.get('oil_bullish', '?')}")
        lines.append("")

        # Key derived signals
        lines.append("=== KEY PATTERNS ===")
        comm_ret = peers.get("commodity_return", 0)
        avg_ret = peers.get("avg_return", 0)
        if comm_ret > avg_ret + 5:
            lines.append(f"  WARNING: Commodity outperforming average by {comm_ret - avg_ret:.1f}% (late-cycle signal)")
        mom_ret = peers.get("momentum_return", 0)
        val_ret = peers.get("value_return", 0)
        if mom_ret < 0 and val_ret < 0:
            lines.append(f"  WARNING: Both Momentum ({mom_ret:+.1f}%) and Value ({val_ret:+.1f}%) negative")
        if peers.get("defensive_state") == "DEFENSE":
            lines.append(f"  ALERT: Defensive strategy in DEFENSE mode (multiple danger signals)")
        if peers.get("cash_heavy_count", 0) >= 3:
            lines.append(f"  ALERT: {peers['cash_heavy_count']} strategies are heavy cash (>50%)")

        return "\n".join(lines)

    def _call_llm(self, sensor_data, date):
        """Call Claude CLI for regime classification.

        Pipes prompt via stdin to avoid Windows arg length limits.
        Runs from temp dir to avoid Claude Code picking up codebase context.
        Uses --system-prompt for expert knowledge.
        """
        user_prompt = (
            f"Current sensor readings:\n\n{sensor_data}\n\n"
            "Classify the current market regime. "
            'Reply with ONLY a JSON object: {"regime": "AGGRESSIVE|CAUTIOUS|DEFENSIVE|RECOVERY|UNCERTAIN", "confidence": 0.0-1.0, "reasoning": "one sentence"}'
        )

        try:
            import tempfile
            result = subprocess.run(
                [CLAUDE_CMD, "-p", "-",
                 "--model", "haiku",
                 "--system-prompt", EXPERT_KNOWLEDGE,
                 "--output-format", "text"],
                input=user_prompt,
                capture_output=True, text=True, timeout=45,
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
                "reason": "LLM call timed out after 30s",
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
        # Try to find JSON in the response
        regime = None
        confidence = 0.5
        reasoning = ""

        # Look for JSON block
        try:
            # Try direct JSON parse
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

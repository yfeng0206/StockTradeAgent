"""Mix LLM V2 Strategy — LLM as NEWS INTERPRETER, not regime adjuster.

Key difference from MixLLM v1:
- v1: LLM overrides the regime classifier (coded regime -> LLM can escalate)
- v2: LLM interprets news to adjust STOCK SCORES (coded regime stays untouched)

The LLM reads today's news, macro context, and sector data, then returns
structured sentiment adjustments that boost/penalize tickers by sector.
This is a pure information layer — the LLM is NOT making trading decisions,
just providing sentiment context that the scoring system can use.

Only calls LLM on rebalance days. Caches response per day. Falls back to
unchanged scores if LLM fails.

Uses same SDK/CLI infrastructure as MixLLM v1.
"""

import json
import os
import glob
import numpy as np
import pandas as pd
from .mix_strategy import MixStrategy, REGIME_ALLOCATIONS, OIL_PROXIES

# Try Anthropic SDK first (no browser tabs), fallback to CLI
_USE_SDK = False
_anthropic_client = None
try:
    import anthropic
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

# Ticker -> sector mapping (comprehensive, matches risk_overlay.py + signals.py)
TICKER_SECTOR_MAP = {
    "XOM": "energy", "CVX": "energy", "COP": "energy",
    "JPM": "finance", "GS": "finance", "V": "finance", "MA": "finance",
    "BAC": "finance", "WFC": "finance", "MS": "finance", "BLK": "finance",
    "UNH": "healthcare", "JNJ": "healthcare", "LLY": "healthcare",
    "ABBV": "healthcare", "MRK": "healthcare", "PFE": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare",
    "AAPL": "tech", "MSFT": "tech", "NVDA": "tech", "GOOGL": "tech",
    "AMZN": "tech", "META": "tech", "TSLA": "tech", "CRM": "tech",
    "NFLX": "tech", "AMD": "tech", "ADBE": "tech", "INTC": "tech",
    "PG": "consumer", "KO": "consumer", "PEP": "consumer",
    "COST": "consumer", "WMT": "consumer", "HD": "consumer",
    "MCD": "consumer", "NKE": "consumer",
    "CAT": "industrial", "BA": "industrial", "HON": "industrial",
    "UPS": "industrial", "DE": "industrial", "LMT": "industrial",
    "DIS": "comm", "CMCSA": "comm", "T": "comm", "VZ": "comm",
    "NEE": "utilities", "SO": "utilities",
}

# News data directory
NEWS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        "data", "news")

NEWS_ANALYST_PROMPT = """You are a market news analyst for a quantitative trading system.

Your job: read today's news, geopolitical events, and market context, then provide
SENTIMENT ADJUSTMENTS that the scoring system will apply to stock scores.

You are NOT making trading decisions. You are providing information — like a research
analyst writing a morning note. The portfolio manager (the coded scoring system) will
decide what to do with your input.

## What you provide:

1. **risk_adjustment** (-0.5 to +0.5): Overall market sentiment shift.
   - Positive = news is broadly bullish (trade deals, peace, strong data)
   - Negative = news is broadly bearish (escalation, crisis, weak data)
   - Zero = neutral or mixed signals
   - Keep this small. +/-0.1 to 0.2 is a normal adjustment. +/-0.5 is extreme.

2. **sector_boosts** (dict of sector -> adjustment, -2.0 to +2.0):
   - Sectors: tech, finance, healthcare, energy, consumer, industrial, comm, utilities
   - Positive = news is bullish for this sector (e.g., "tech" +1.0 if AI breakthroughs)
   - Negative = news is bearish (e.g., "energy" -1.0 if oil price collapse)
   - Only include sectors with CLEAR news-driven sentiment. Omit neutral sectors.
   - These adjustments are added directly to stock composite scores (which range 0-10).

3. **reasoning** (1-2 sentences): What drove your assessment.

## Guidelines:
- Be conservative. Most days, news is noise. Return small or zero adjustments.
- Only provide large sector boosts (+/-1.5 or more) for major, unambiguous events.
- Geopolitical escalation -> energy boost, broad market penalty.
- Trade war news -> industrial/tech penalty, sometimes consumer penalty.
- Fed/rate news -> finance boost/penalty, tech inverse sensitivity.
- Pandemic/health crisis -> healthcare boost, consumer/industrial penalty.
- If news is sparse or ambiguous, return all zeros. That's a valid answer.

## Output format:
Respond with ONLY a JSON object:
{"risk_adjustment": 0.0, "sector_boosts": {"tech": 0.5, "energy": -0.3}, "reasoning": "..."}"""


class MixLLMV2Strategy(MixStrategy):
    """Mix strategy with LLM-powered news interpretation for score adjustment.

    Uses the SAME coded regime detection as MixStrategy (no override).
    The LLM only adjusts stock scores based on news sentiment.
    """

    def __init__(self, initial_cash=100_000, events_calendar=None, max_positions=10,
                 regime_stickiness=1):
        super().__init__(initial_cash, events_calendar, max_positions,
                         regime_stickiness=regime_stickiness)
        self.name = "MixLLM_V2"
        self._llm_call_count = 0
        self._llm_fallback_count = 0
        self._llm_log = []  # log every LLM call for debugging
        self._llm_day_cache = {}  # {date_str: llm_response_dict} — one call per day

    # Model selection — set via env var MIXLLM_V2_MODEL (default: opus)
    LLM_MODEL = os.environ.get("MIXLLM_V2_MODEL",
                               os.environ.get("MIXLLM_MODEL", "opus"))

    # Map short names to SDK model IDs
    _MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001",
    }

    # ================================================================
    # SCORE_STOCKS — override to add LLM news interpretation
    # ================================================================
    def score_stocks(self, universe: list, price_data: dict, date: str,
                     signal_engine=None) -> list:
        """Score stocks using coded regime + LLM news sentiment adjustment.

        1. Call parent score_stocks (coded regime detection + stock scoring)
        2. On rebalance days, call LLM once with news context
        3. Apply sentiment adjustments to scores
        """
        # Step 1: Get coded scores from parent (regime detection happens here)
        coded_scores = super().score_stocks(universe, price_data, date,
                                            signal_engine=signal_engine)

        # Step 2: Only call LLM on rebalance days (monthly)
        # Note: score_stocks is only called on rebalance days by daily_loop,
        # so no need for internal rebalance check. The day cache prevents duplicate calls.

        # Step 3: Get LLM news interpretation (cached per day)
        llm_adjustments = self._get_news_adjustments(price_data, date, signal_engine)
        if llm_adjustments is None:
            return coded_scores

        # Step 4: Apply adjustments to scores
        adjusted_scores = self._apply_adjustments(coded_scores, llm_adjustments, date)
        return adjusted_scores

    # ================================================================
    # REBALANCE CHECK
    # ================================================================
    def _is_rebalance_day(self, date: str) -> bool:
        """Check if this is a rebalance day (monthly).

        Uses the same logic the base class uses: first trading day of the month
        or if enough days have passed since last rebalance.
        """
        # If we have portfolio history, check if this is month boundary
        if self.portfolio_history:
            last_date = self.portfolio_history[-1].get("date", "")
            if last_date:
                last_month = last_date[:7]  # YYYY-MM
                this_month = date[:7]
                if this_month != last_month:
                    return True
                return False
        # First day — always rebalance
        return True

    # ================================================================
    # NEWS CONTEXT BUILDER
    # ================================================================
    def _build_news_context(self, price_data: dict, date: str,
                            signal_engine=None) -> str:
        """Build a news + market context string for the LLM.

        Combines:
        - Geopolitical news from _last_news_summary / signal engine
        - Headlines from data/news/{date}/ files
        - Sector rotation data from market sensing
        - Current regime for context
        """
        lines = [f"Date: {date}", f"Current regime: {self.detected_regime}", ""]

        # === 1. Geopolitical risk from signal engine ===
        lines.append("=== GEOPOLITICAL / NEWS CONTEXT ===")
        news_summary = getattr(self, '_last_news_summary', None)
        if news_summary:
            lines.append(f"  Signal engine: {news_summary}")

        # Try to get richer news from signal engine's compute_news
        if signal_engine is not None and hasattr(signal_engine, 'compute_news'):
            try:
                raw_news = signal_engine.compute_news(date)
                if raw_news.get("has_news"):
                    geo_risk = raw_news.get("geo_risk", 0)
                    themes = raw_news.get("themes", [])
                    headlines = raw_news.get("headlines", [])
                    lines.append(f"  Geo risk score: {geo_risk:.2f}")
                    if themes:
                        lines.append(f"  Active themes: {', '.join(themes)}")
                    if headlines:
                        lines.append("  Top headlines:")
                        for h in headlines[:5]:
                            lines.append(f"    - {h}")
            except Exception:
                pass

        # === 2. News files from data/news/{date}/ ===
        news_from_files = self._load_news_files(date)
        if news_from_files:
            lines.append("")
            lines.append("=== NEWS FROM FILES ===")
            lines.extend(news_from_files)

        # === 3. Sector rotation (quick summary) ===
        lines.append("")
        lines.append("=== SECTOR PERFORMANCE (context for your adjustments) ===")
        if signal_engine is not None and hasattr(signal_engine, 'compute_macro'):
            try:
                macro = signal_engine.compute_macro(date)
                sector_rot = macro.get("sector_rotation", {})
                if sector_rot:
                    sorted_sectors = sorted(sector_rot.items(),
                                            key=lambda x: x[1], reverse=True)
                    for sector, ret in sorted_sectors:
                        lines.append(f"  {sector}: {ret:+.1f}% (1m)")
            except Exception:
                lines.append("  (sector data unavailable)")
        else:
            lines.append("  (no signal engine available)")

        # === 4. SPY context ===
        lines.append("")
        lines.append("=== BROAD MARKET ===")
        market = self._sensor_readings.get("market", {})
        if market:
            lines.append(f"  SPY above 50-day MA: {market.get('spy_above_50ma', '?')}")
            lines.append(f"  SPY above 200-day MA: {market.get('spy_above_200ma', '?')}")
            lines.append(f"  SPY 1-month return: {market.get('spy_ret_1m', 0):+.1f}%")
            lines.append(f"  SPY drawdown from 60-day peak: {market.get('spy_drawdown', 0):.1f}%")

        return "\n".join(lines)

    def _load_news_files(self, date: str) -> list:
        """Load news headlines from data/news/{date}/ directory.

        Reads geopolitical, macro, commodities, sectors, sentiment files
        and extracts key headlines for the LLM.
        """
        lines = []
        date_dir = os.path.join(NEWS_DIR, date)
        if not os.path.isdir(date_dir):
            return lines

        # Look for geopolitical news
        geo_dir = os.path.join(date_dir, "geopolitical")
        if os.path.isdir(geo_dir):
            for fpath in glob.glob(os.path.join(geo_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Handle wiki_events.json format
                    if "categories" in data:
                        for cat, cat_data in data["categories"].items():
                            headlines = cat_data.get("headlines", [])
                            if headlines:
                                lines.append(f"  Geopolitical ({cat}): {'; '.join(headlines[:3])}")
                    # Handle GDELT format
                    elif "articles" in data:
                        for article in data["articles"][:5]:
                            title = article.get("title", "")
                            if title:
                                lines.append(f"  GDELT: {title}")
                except (json.JSONDecodeError, IOError):
                    pass

        # Look for macro news
        macro_dir = os.path.join(date_dir, "macro")
        if os.path.isdir(macro_dir):
            for fpath in glob.glob(os.path.join(macro_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    headlines = data.get("headlines", [])
                    if headlines:
                        lines.append(f"  Macro: {'; '.join(headlines[:3])}")
                except (json.JSONDecodeError, IOError):
                    pass

        # Look for commodity news
        comm_dir = os.path.join(date_dir, "commodities")
        if os.path.isdir(comm_dir):
            for fpath in glob.glob(os.path.join(comm_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    headlines = data.get("headlines", [])
                    if headlines:
                        lines.append(f"  Commodities: {'; '.join(headlines[:3])}")
                except (json.JSONDecodeError, IOError):
                    pass

        # Look for sector news
        sector_dir = os.path.join(date_dir, "sectors")
        if os.path.isdir(sector_dir):
            for fpath in glob.glob(os.path.join(sector_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    headlines = data.get("headlines", [])
                    if headlines:
                        lines.append(f"  Sectors: {'; '.join(headlines[:3])}")
                except (json.JSONDecodeError, IOError):
                    pass

        # Look for sentiment data
        sent_dir = os.path.join(date_dir, "sentiment")
        if os.path.isdir(sent_dir):
            for fpath in glob.glob(os.path.join(sent_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "vix" in data:
                        lines.append(f"  VIX: {data['vix']}")
                    headlines = data.get("headlines", [])
                    if headlines:
                        lines.append(f"  Sentiment: {'; '.join(headlines[:2])}")
                except (json.JSONDecodeError, IOError):
                    pass

        return lines

    # ================================================================
    # LLM CALL — get news adjustments
    # ================================================================
    def _get_news_adjustments(self, price_data: dict, date: str,
                              signal_engine=None) -> dict | None:
        """Get LLM news interpretation. Cached per day.

        Returns dict with:
            risk_adjustment: float (-0.5 to +0.5)
            sector_boosts: dict {sector: float}
            reasoning: str
        Or None if LLM fails.
        """
        # Check day cache — don't call LLM twice on the same day
        if date in self._llm_day_cache:
            return self._llm_day_cache[date]

        # Build context
        context = self._build_news_context(price_data, date, signal_engine)

        # Call LLM
        result = self._call_llm(context, date)

        # Cache result (even None, to prevent retries on same day)
        self._llm_day_cache[date] = result
        return result

    def _call_llm(self, context: str, date: str) -> dict | None:
        """Call Claude for news interpretation.

        Uses Anthropic SDK if ANTHROPIC_API_KEY is set.
        Falls back to Claude CLI subprocess otherwise.
        """
        user_prompt = (
            f"Analyze today's news and market context, then provide sentiment adjustments.\n\n"
            f"{context}\n\n"
            "Based on the news above, provide your sentiment adjustments.\n"
            "If news is sparse or neutral, return zeros — that is a valid and common response.\n\n"
            'Reply with ONLY a JSON object: '
            '{"risk_adjustment": 0.0, "sector_boosts": {"sector": 0.0}, "reasoning": "..."}'
        )

        try:
            if _USE_SDK:
                response = self._call_sdk(user_prompt)
            else:
                response = self._call_cli(user_prompt)

            self._llm_call_count += 1
            result = self._parse_llm_response(response)

            self._llm_log.append({
                "date": date, "source": "llm",
                "risk_adjustment": result.get("risk_adjustment", 0),
                "sector_boosts": result.get("sector_boosts", {}),
                "reasoning": result.get("reasoning", ""),
                "raw_response": response[:500],
            })
            return result

        except Exception as e:
            error_str = str(e).lower()
            if "auth" in error_str or "key" in error_str or "rate" in error_str or "billing" in error_str:
                print(f"  WARNING: LLM API error ({type(e).__name__}): {str(e).encode('ascii', 'replace').decode()}")
            self._llm_fallback_count += 1
            self._llm_log.append({
                "date": date, "source": "error",
                "reason": str(e)[:200],
            })
            return None

    def _call_sdk(self, user_prompt: str) -> str:
        """Call via Anthropic Python SDK."""
        model_id = self._MODEL_MAP.get(self.LLM_MODEL, self.LLM_MODEL)
        message = _anthropic_client.messages.create(
            model=model_id,
            max_tokens=512,
            system=NEWS_ANALYST_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text.strip()

    def _call_cli(self, user_prompt: str) -> str:
        """Call via Claude CLI subprocess — fallback if no API key."""
        import tempfile
        result = subprocess.run(
            [CLAUDE_CMD, "-p", "-",
             "--model", self.LLM_MODEL,
             "--system-prompt", NEWS_ANALYST_PROMPT,
             "--output-format", "text"],
            input=user_prompt,
            capture_output=True, text=True, timeout=90,
            cwd=tempfile.gettempdir(),
        )
        return result.stdout.strip()

    def _parse_llm_response(self, response: str) -> dict:
        """Parse LLM response into structured adjustments.

        Returns dict with risk_adjustment, sector_boosts, reasoning.
        Clamps values to valid ranges.
        """
        result = {
            "risk_adjustment": 0.0,
            "sector_boosts": {},
            "reasoning": "",
        }

        try:
            if "{" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                data = json.loads(json_str)

                # risk_adjustment: clamp to [-0.5, +0.5]
                ra = float(data.get("risk_adjustment", 0))
                result["risk_adjustment"] = max(-0.5, min(0.5, ra))

                # sector_boosts: clamp each to [-2.0, +2.0]
                boosts = data.get("sector_boosts", {})
                if isinstance(boosts, dict):
                    valid_sectors = {"tech", "finance", "healthcare", "energy",
                                     "consumer", "industrial", "comm", "utilities"}
                    for sector, val in boosts.items():
                        sector_lower = sector.lower()
                        if sector_lower in valid_sectors:
                            result["sector_boosts"][sector_lower] = max(-2.0, min(2.0, float(val)))

                result["reasoning"] = str(data.get("reasoning", ""))[:500]

        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        return result

    # ================================================================
    # APPLY ADJUSTMENTS — modify scores based on LLM sentiment
    # ================================================================
    def _apply_adjustments(self, coded_scores: list, adjustments: dict,
                           date: str) -> list:
        """Apply LLM sentiment adjustments to coded stock scores.

        - risk_adjustment shifts ALL scores (positive = more bullish)
        - sector_boosts shift scores for tickers in specific sectors
        - Scores are clamped to [0, 10] after adjustment
        """
        risk_adj = adjustments.get("risk_adjustment", 0)
        sector_boosts = adjustments.get("sector_boosts", {})

        if risk_adj == 0 and not sector_boosts:
            return coded_scores

        adjusted = []
        for ticker, score in coded_scores:
            new_score = score + risk_adj

            # Apply sector boost if ticker has a known sector
            sector = TICKER_SECTOR_MAP.get(ticker)
            if sector and sector in sector_boosts:
                new_score += sector_boosts[sector]

            # Clamp to valid range
            new_score = max(0.0, min(10.0, new_score))

            # Update _last_scores with adjustment info
            if ticker in self._last_scores:
                self._last_scores[ticker]["llm_risk_adj"] = round(risk_adj, 3)
                if sector and sector in sector_boosts:
                    self._last_scores[ticker]["llm_sector_boost"] = round(
                        sector_boosts[sector], 3)
                self._last_scores[ticker]["llm_adjusted"] = round(new_score, 3)

            adjusted.append((ticker, round(new_score, 3)))

        # Re-sort by adjusted score
        adjusted.sort(key=lambda x: x[1], reverse=True)

        # Log the adjustment
        self._log_reasoning(date, "LLM_NEWS", "", 0,
            f"MixLLM_V2 news adjustment: risk={risk_adj:+.2f}, "
            f"sectors={sector_boosts}, "
            f"reason: {adjustments.get('reasoning', 'n/a')[:200]}")

        return adjusted

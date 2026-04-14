"""Risk overlay layer — sits BETWEEN scoring and execution.

Architecture (mirrors TradingAgents paper):
  SHARED DETECTION → PER-STRATEGY INTERPRETATION → EXECUTION

1. Raw signals (bull/bear) are DETECTED once (shared — same market for all)
2. Raw conflicts are DETECTED once (shared — same contradictions exist for all)
3. Each STRATEGY JUDGE interprets them through its own lens (per-strategy)
   - Value judge ignores RSI overbought, cares about valuation divergence
   - Momentum judge ignores valuation, cares about trend breakdown
   - Defensive judge cares most about volatility and drawdown risk
4. ConsensusSignal is computed across all strategies (shared)
5. CashFloor is computed per-strategy using shared + per-strategy inputs

All produce structured logs:
  - shared/signals_raw.json — raw bull/bear signals + conflicts (same for all)
  - portfolios/{Strategy}/conviction_log.json — how this judge weighed them
  - portfolios/{Strategy}/conflicts.json — which conflicts this judge flagged
"""

import numpy as np


# ---------------------------------------------------------------------------
# Feature flags and params
# ---------------------------------------------------------------------------
DEFAULT_FEATURES = {
    "conviction_gate": False,           # OFF: costs 14% in bull to save 5% in bear
    "contradiction_detection": True,    # ON but logging only (no size changes)
    "cross_strategy_consensus": False,  # OFF: strategies should be independent
    "dynamic_cash_floor": True,         # ON: small 2% base cash reserve
    "partial_fill": True,               # ON: always (bug fix, no cost)
}

DEFAULT_PARAMS = {
    # Conviction gate (disabled by default, params kept for manual testing)
    "conviction_full_threshold": 0.3,
    "conviction_half_threshold": 0.1,

    # Conflict detection — logging only, no size changes
    "conflict_reduce_pct": 0.0,         # 0 = log conflicts but don't reduce size
    "conflict_skip_threshold": 999.0,   # never skip (effectively disabled for sizing)

    # Consensus (disabled by default)
    "consensus_bearish_threshold": 0.7,
    "consensus_persistence_required": 1,
    "consensus_exposure_cap": 0.60,

    # Cash floor — reduced to 2% base (was 5%)
    "cash_floor_base_pct": 0.02,        # minimal drag
    "cash_floor_danger_add_pct": 0.08,  # 10% total during danger (was 20%)
    "cash_floor_consensus_add_pct": 0.0, # consensus is off
    "cash_floor_max_pct": 0.15,         # cap at 15% (was 40%)
}


# ---------------------------------------------------------------------------
# Strategy-specific interpretation weights
# Same signals detected, but each judge cares about different ones.
# Relevance 0.0 = ignore this conflict, 1.0 = this is critical
# ---------------------------------------------------------------------------
STRATEGY_CONFLICT_RELEVANCE = {
    "Value": {
        "stock_rising_in_crisis": 0.2,             # Value holds through storms
        "stock_falling_in_bull_market": 0.9,        # Possible value trap
        "stock_outpacing_sector": 0.3,              # Doesn't worry Value
        "stock_lagging_sector": 0.7,                # Might be for a reason
        "uptrend_with_extreme_vol": 0.5,            # Moderate concern
        "overbought_but_all_signals_bullish": 0.1,  # Value ignores RSI
        "oversold_in_downtrend": 0.8,               # Catching a knife?
    },
    "Momentum": {
        "stock_rising_in_crisis": 0.1,              # Momentum follows price, period
        "stock_falling_in_bull_market": 0.9,         # Trend breakdown — bad
        "stock_outpacing_sector": 0.2,               # Relative strength = good
        "stock_lagging_sector": 0.8,                 # Losing momentum — bad
        "uptrend_with_extreme_vol": 0.6,             # Unstable trend
        "overbought_but_all_signals_bullish": 0.7,   # Momentum watches RSI
        "oversold_in_downtrend": 0.3,                # Momentum avoids falling knives
    },
    "Defensive": {
        "stock_rising_in_crisis": 0.8,              # Defensive hates crisis exposure
        "stock_falling_in_bull_market": 0.5,         # Moderate concern
        "stock_outpacing_sector": 0.4,
        "stock_lagging_sector": 0.6,
        "uptrend_with_extreme_vol": 0.9,             # Defensive HATES high vol
        "overbought_but_all_signals_bullish": 0.5,
        "oversold_in_downtrend": 0.7,
    },
    "EventDriven": {
        "stock_rising_in_crisis": 0.3,              # Events override macro
        "stock_falling_in_bull_market": 0.5,
        "stock_outpacing_sector": 0.2,
        "stock_lagging_sector": 0.4,
        "uptrend_with_extreme_vol": 0.4,
        "overbought_but_all_signals_bullish": 0.3,   # Events matter more than RSI
        "oversold_in_downtrend": 0.5,
    },
    "Balanced": {
        "stock_rising_in_crisis": 0.5,              # Balanced weighs everything equally
        "stock_falling_in_bull_market": 0.5,
        "stock_outpacing_sector": 0.5,
        "stock_lagging_sector": 0.5,
        "uptrend_with_extreme_vol": 0.5,
        "overbought_but_all_signals_bullish": 0.5,
        "oversold_in_downtrend": 0.5,
    },
    "Adaptive": {
        "stock_rising_in_crisis": 0.6,              # Adaptive adjusts by regime
        "stock_falling_in_bull_market": 0.7,
        "stock_outpacing_sector": 0.3,
        "stock_lagging_sector": 0.6,
        "uptrend_with_extreme_vol": 0.7,
        "overbought_but_all_signals_bullish": 0.4,
        "oversold_in_downtrend": 0.6,
    },
    "Commodity": {
        "stock_rising_in_crisis": 0.2,              # Commodity often rises in crisis
        "stock_falling_in_bull_market": 0.4,
        "stock_outpacing_sector": 0.3,
        "stock_lagging_sector": 0.5,
        "uptrend_with_extreme_vol": 0.6,
        "overbought_but_all_signals_bullish": 0.4,
        "oversold_in_downtrend": 0.5,
    },
    "Mix": {
        "stock_rising_in_crisis": 0.5,              # Mix adapts — moderate on everything
        "stock_falling_in_bull_market": 0.6,
        "stock_outpacing_sector": 0.3,
        "stock_lagging_sector": 0.5,
        "uptrend_with_extreme_vol": 0.6,
        "overbought_but_all_signals_bullish": 0.4,
        "oversold_in_downtrend": 0.5,
    },
    "MixLLM": {
        "stock_rising_in_crisis": 0.5,
        "stock_falling_in_bull_market": 0.6,
        "stock_outpacing_sector": 0.3,
        "stock_lagging_sector": 0.5,
        "uptrend_with_extreme_vol": 0.6,
        "overbought_but_all_signals_bullish": 0.4,
        "oversold_in_downtrend": 0.5,
    },
}

# Strategy-specific conviction weights for the 3 signals
# Each strategy judges the same 3 signals (trend, vol, memory) but weighs them differently
STRATEGY_CONVICTION_WEIGHTS = {
    "Value":       {"market_trend": 0.2, "volatility": 0.3, "memory": 0.5},
    "Momentum":    {"market_trend": 0.5, "volatility": 0.1, "memory": 0.4},
    "Defensive":   {"market_trend": 0.3, "volatility": 0.5, "memory": 0.2},
    "EventDriven": {"market_trend": 0.2, "volatility": 0.2, "memory": 0.6},
    "Balanced":    {"market_trend": 0.33, "volatility": 0.33, "memory": 0.34},
    "Adaptive":    {"market_trend": 0.4, "volatility": 0.3, "memory": 0.3},
    "Commodity":   {"market_trend": 0.4, "volatility": 0.3, "memory": 0.3},
    "Mix":         {"market_trend": 0.35, "volatility": 0.30, "memory": 0.35},
    "MixLLM":      {"market_trend": 0.35, "volatility": 0.30, "memory": 0.35},
}


# ---------------------------------------------------------------------------
# SHARED DETECTION — same for all strategies
# ---------------------------------------------------------------------------

class RawSignalDetector:
    """Detects raw bull/bear signals and conflicts. SHARED — computed once.

    Like TradingAgents' analyst team: produces factual reports, not opinions.
    """

    SECTOR_MAP = {
        "XOM": "energy", "CVX": "energy",
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

    def detect_signals(self, ticker, tech, macro):
        """Detect raw bull/bear signals for a stock. Returns shared facts.

        Uses SPY's MA position (always available) instead of just extreme regimes.
        This ensures trend_score is non-zero even during "normal" regime periods.
        """
        regime = macro.get("regime", "normal")
        vol = tech.get("vol_20d", 0.20)
        spy = macro.get("spy_trend", {})

        # Bull signals (shared facts)
        bull = []
        # Market trend: use SPY MA position (granular, always available)
        if spy.get("above_50") and spy.get("above_200"):
            bull.append("market_strong_trend")
        elif spy.get("above_50"):
            bull.append("market_moderate_trend")
        if vol < 0.20:
            bull.append("low_volatility")

        # Bear signals (shared facts)
        bear = []
        if not spy.get("above_50") and not spy.get("above_200"):
            bear.append("market_broken_trend")
        elif not spy.get("above_50"):
            bear.append("market_weakening_trend")
        # Escalate on extreme regimes
        if regime in ("crisis", "high_volatility"):
            bear.append("market_stressed")
        if vol > 0.40:
            bear.append("high_volatility")

        return {
            "ticker": ticker,
            "bull_signals": bull,
            "bear_signals": bear,
            "regime": regime,
            "vol_20d": round(vol, 3),
        }

    def detect_conflicts(self, ticker, tech, macro):
        """Detect signal conflicts. Returns shared facts — no interpretation."""
        conflicts = []
        if not tech or not macro:
            return {"ticker": ticker, "conflicts": []}

        stock_ret_1m = tech.get("ret_1m", 0)
        regime = macro.get("regime", "normal")
        vol = tech.get("vol_20d", 0.2)
        rsi = tech.get("rsi", 50)
        macd_bull = tech.get("macd_bullish", False)
        above_50 = tech.get("sma_50") and tech.get("current_price", 0) > tech["sma_50"]
        above_200 = tech.get("sma_200") and tech.get("current_price", 0) > tech["sma_200"]

        # Bucket 1: Price vs Macro
        if stock_ret_1m > 5 and regime in ("crisis", "high_volatility"):
            conflicts.append("stock_rising_in_crisis")
        elif stock_ret_1m < -10 and regime == "bullish":
            conflicts.append("stock_falling_in_bull_market")

        # Bucket 2: Stock vs Sector
        sector = self.SECTOR_MAP.get(ticker)
        if sector:
            sector_rets = macro.get("sector_rotation", {})
            sector_ret = sector_rets.get(sector)
            if sector_ret is not None:
                if stock_ret_1m - sector_ret > 10:
                    conflicts.append("stock_outpacing_sector")
                elif sector_ret - stock_ret_1m > 10:
                    conflicts.append("stock_lagging_sector")

        # Bucket 3: Trend vs Volatility
        if above_50 and vol > 0.40:
            conflicts.append("uptrend_with_extreme_vol")

        # Bucket 4: Signal Dispersion
        if rsi > 70 and macd_bull and above_200:
            conflicts.append("overbought_but_all_signals_bullish")
        if rsi < 30 and not above_200:
            conflicts.append("oversold_in_downtrend")

        return {"ticker": ticker, "conflicts": conflicts}


# ---------------------------------------------------------------------------
# PER-STRATEGY INTERPRETATION — each judge reads shared data differently
# ---------------------------------------------------------------------------

class StrategyJudge:
    """Per-strategy interpreter. Like TradingAgents' risk analysts:
    same facts, different risk appetites, different verdicts.

    Each judge:
    1. Reads shared bull/bear signals, weighs them by strategy personality
    2. Reads shared conflicts, filters by relevance to this strategy
    3. Reads strategy memory (unique per strategy)
    4. Produces conviction score + size multiplier
    """

    def __init__(self, strategy_name, params=None):
        p = {**DEFAULT_PARAMS, **(params or {})}
        self.strategy_name = strategy_name
        self.full_threshold = p["conviction_full_threshold"]
        self.half_threshold = p["conviction_half_threshold"]
        self.reduce_pct = p["conflict_reduce_pct"]
        self.skip_threshold = p["conflict_skip_threshold"]

        self.conviction_weights = STRATEGY_CONVICTION_WEIGHTS.get(
            strategy_name, {"market_trend": 0.33, "volatility": 0.33, "memory": 0.34})
        self.conflict_relevance = STRATEGY_CONFLICT_RELEVANCE.get(
            strategy_name, {k: 0.5 for k in STRATEGY_CONFLICT_RELEVANCE.get("Balanced", {})})

    def judge_conviction(self, raw_signals, strategy_memory, ticker):
        """Interpret shared signals through this strategy's lens.

        Returns conviction score and size multiplier.
        """
        w = self.conviction_weights

        # Signal 1: Market trend (granular — uses SPY MA position)
        trend_score = 0.0
        bull_sigs = raw_signals["bull_signals"]
        bear_sigs = raw_signals["bear_signals"]
        if "market_strong_trend" in bull_sigs:
            trend_score = 1.0
        elif "market_moderate_trend" in bull_sigs:
            trend_score = 0.5
        elif "market_broken_trend" in bear_sigs:
            trend_score = -1.0
        elif "market_weakening_trend" in bear_sigs:
            trend_score = -0.5
        # Escalate if stressed on top of broken trend
        if "market_stressed" in bear_sigs:
            trend_score = min(trend_score, -1.0)
        elif "market_bearish" in raw_signals["bear_signals"]:
            trend_score = -1.0

        # Signal 2: Volatility
        vol_score = 0.0
        if "low_volatility" in raw_signals["bull_signals"]:
            vol_score = 1.0
        elif "high_volatility" in raw_signals["bear_signals"]:
            vol_score = -1.0

        # Signal 3: Memory (unique per strategy)
        memory_score = 0.0
        ticker_hist = strategy_memory.get("ticker_history", {}).get(ticker, [])
        recent = ticker_hist[-5:] if ticker_hist else []
        recent_losses = [t for t in recent if t.get("pnl", 0) < -5]
        recent_wins = [t for t in recent if t.get("pnl", 0) > 5]
        if len(recent_losses) >= 2:
            memory_score = -1.0
        elif len(recent_wins) >= 2:
            memory_score = 1.0

        # Weighted conviction (-1 to +1)
        conviction = (
            trend_score * w["market_trend"] +
            vol_score * w["volatility"] +
            memory_score * w["memory"]
        )

        # Map to size multiplier
        if conviction >= self.full_threshold:
            size_mult = 1.0
        elif conviction >= self.half_threshold:
            size_mult = 0.5
        else:
            size_mult = 0.0

        details = []
        if trend_score != 0:
            details.append(f"trend={trend_score:+.0f}*{w['market_trend']:.0%}")
        if vol_score != 0:
            details.append(f"vol={vol_score:+.0f}*{w['volatility']:.0%}")
        if memory_score != 0:
            details.append(f"mem={memory_score:+.0f}*{w['memory']:.0%}")

        return {
            "ticker": ticker,
            "strategy": self.strategy_name,
            "conviction": round(conviction, 2),
            "size_multiplier": size_mult,
            "trend_score": trend_score,
            "vol_score": vol_score,
            "memory_score": memory_score,
            "weights": w,
            "details": details,
        }

    def judge_conflicts(self, raw_conflicts):
        """Interpret shared conflicts through this strategy's relevance filter.

        Same conflicts detected for everyone, but each judge cares differently.
        """
        ticker = raw_conflicts["ticker"]
        scored_conflicts = []
        weighted_score = 0.0

        for conflict in raw_conflicts["conflicts"]:
            relevance = self.conflict_relevance.get(conflict, 0.5)
            scored_conflicts.append({
                "conflict": conflict,
                "relevance": relevance,
                "flagged": relevance >= 0.5,
            })
            weighted_score += relevance

        # Normalize: max possible is ~1.75 (7 conflicts * 0.25 weight each)
        # But use number of flagged conflicts for sizing
        flagged = [c for c in scored_conflicts if c["flagged"]]
        conflict_score = min(1.0, len(flagged) * 0.25)

        if conflict_score >= self.skip_threshold:
            size_adj = 0.0
        elif conflict_score > 0.5:
            size_adj = 1.0 - self.reduce_pct
        else:
            size_adj = 1.0

        return {
            "ticker": ticker,
            "strategy": self.strategy_name,
            "conflict_score": round(conflict_score, 2),
            "all_conflicts": scored_conflicts,
            "flagged_count": len(flagged),
            "size_adjustment": size_adj,
        }


# ---------------------------------------------------------------------------
# Consensus + Cash Floor (unchanged from before)
# ---------------------------------------------------------------------------

class ConsensusSignal:
    """Cross-strategy agreement → portfolio-level exposure cap."""

    def __init__(self, params=None):
        p = {**DEFAULT_PARAMS, **(params or {})}
        self.bearish_threshold = p["consensus_bearish_threshold"]
        self.persistence_required = p["consensus_persistence_required"]
        self.exposure_cap = p["consensus_exposure_cap"]
        self._consecutive_bearish = 0
        self._active = False
        self._history = []

    def update(self, strategies, price_data, date):
        bearish_count = 0
        details = []
        for strat in strategies:
            total_value = strat.get_portfolio_value(price_data, date, decision_time=True)
            if total_value <= 0:
                continue
            cash_ratio = strat.cash / total_value
            is_cash_heavy = cash_ratio > 0.50
            details.append({
                "strategy": strat.name,
                "cash_ratio": round(cash_ratio, 2),
                "is_cash_heavy": is_cash_heavy,
            })
            if is_cash_heavy:
                bearish_count += 1

        bearish_ratio = bearish_count / max(1, len(strategies))
        if bearish_ratio >= self.bearish_threshold:
            self._consecutive_bearish += 1
        else:
            self._consecutive_bearish = 0
        self._active = self._consecutive_bearish >= self.persistence_required

        result = {
            "date": date,
            "bearish_count": bearish_count,
            "total_strategies": len(strategies),
            "bearish_ratio": round(bearish_ratio, 2),
            "consecutive_bearish": self._consecutive_bearish,
            "is_active": self._active,
            "exposure_cap": self.exposure_cap if self._active else 1.0,
            "details": details,
        }
        self._history.append(result)
        return result

    def get_history(self):
        return self._history


class CashFloorManager:
    """Dynamic cash floor — reserves minimum cash based on conditions."""

    def __init__(self, params=None):
        p = {**DEFAULT_PARAMS, **(params or {})}
        self.base_pct = p["cash_floor_base_pct"]
        self.danger_add = p["cash_floor_danger_add_pct"]
        self.consensus_add = p["cash_floor_consensus_add_pct"]
        self.max_pct = p["cash_floor_max_pct"]

    def compute_floor(self, total_value, regime, consensus_active):
        floor_pct = self.base_pct
        reasons = [f"base({self.base_pct:.0%})"]

        if regime in ("crisis", "high_volatility", "bearish"):
            floor_pct += self.danger_add
            reasons.append(f"regime_{regime}(+{self.danger_add:.0%})")
        if consensus_active:
            floor_pct += self.consensus_add
            reasons.append(f"consensus_bearish(+{self.consensus_add:.0%})")

        floor_pct = min(floor_pct, self.max_pct)
        return {
            "floor_pct": round(floor_pct, 2),
            "floor_amount": round(total_value * floor_pct, 2),
            "reasons": reasons,
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

class RiskOverlay:
    """Wraps all components. Enforces shared detection → per-strategy interpretation."""

    def __init__(self, features=None, params=None):
        self.features = {**DEFAULT_FEATURES, **(features or {})}
        self.params = {**DEFAULT_PARAMS, **(params or {})}

        # Shared detector (one instance, used by all)
        self.detector = RawSignalDetector()

        # Per-strategy judges (one per strategy, created on demand)
        self._judges = {}

        # Shared components
        self.consensus_signal = ConsensusSignal(self.params) if self.features["cross_strategy_consensus"] else None
        self.cash_floor_mgr = CashFloorManager(self.params) if self.features["dynamic_cash_floor"] else None

        # Logs
        self.raw_signals_log = []       # shared: raw signals detected
        self.raw_conflicts_log = []     # shared: raw conflicts detected
        self.conviction_logs = {}       # per-strategy: {name: [entries]}
        self.conflict_logs = {}         # per-strategy: {name: [entries]}
        self.consensus_logs = []        # shared: consensus history

    def _get_judge(self, strategy_name):
        """Get or create the judge for a strategy."""
        if strategy_name not in self._judges:
            self._judges[strategy_name] = StrategyJudge(strategy_name, self.params)
        return self._judges[strategy_name]

    def detect_raw(self, ticker, tech, macro):
        """SHARED: detect raw signals and conflicts once for all strategies."""
        raw_signals = self.detector.detect_signals(ticker, tech, macro)
        raw_conflicts = self.detector.detect_conflicts(ticker, tech, macro)

        self.raw_signals_log.append(raw_signals)
        self.raw_conflicts_log.append(raw_conflicts)

        return raw_signals, raw_conflicts

    def judge_for_strategy(self, ticker, raw_signals, raw_conflicts, strategy):
        """PER-STRATEGY: interpret shared data through this strategy's lens."""
        if not self.features["conviction_gate"] and not self.features["contradiction_detection"]:
            return {"conviction": 0, "size_multiplier": 1.0}, {"conflict_score": 0, "size_adjustment": 1.0}

        judge = self._get_judge(strategy.name)

        # Conviction: shared signals + strategy memory + strategy weights
        conv = judge.judge_conviction(raw_signals, strategy.memory, ticker) \
            if self.features["conviction_gate"] else \
            {"conviction": 0, "size_multiplier": 1.0, "details": ["disabled"]}

        # Conflicts: shared conflicts + strategy relevance filter
        conf = judge.judge_conflicts(raw_conflicts) \
            if self.features["contradiction_detection"] else \
            {"conflict_score": 0, "size_adjustment": 1.0}

        # Log per strategy
        if strategy.name not in self.conviction_logs:
            self.conviction_logs[strategy.name] = []
        self.conviction_logs[strategy.name].append(conv)

        if strategy.name not in self.conflict_logs:
            self.conflict_logs[strategy.name] = []
        self.conflict_logs[strategy.name].append(conf)

        return conv, conf

    def compute_final_size_multiplier(self, conviction_result, conflict_result):
        """Combine conviction and conflict into one final size multiplier."""
        conv_mult = conviction_result.get("size_multiplier", 1.0)
        conf_mult = conflict_result.get("size_adjustment", 1.0)
        if conv_mult == 0.0 or conf_mult == 0.0:
            return 0.0
        return round(conv_mult * conf_mult, 2)

    def update_consensus(self, strategies, price_data, date):
        if not self.consensus_signal:
            return {"is_active": False, "exposure_cap": 1.0}
        result = self.consensus_signal.update(strategies, price_data, date)
        self.consensus_logs.append(result)
        return result

    def get_cash_floor(self, total_value, regime, consensus_active):
        if not self.cash_floor_mgr:
            return {"floor_pct": 0, "floor_amount": 0, "reasons": ["disabled"]}
        return self.cash_floor_mgr.compute_floor(total_value, regime, consensus_active)

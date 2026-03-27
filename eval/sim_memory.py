"""Memory manager — reads past experience to inform current decisions.

Makes memory actually useful instead of write-only.
"""


class SimulationMemory:
    """Reads and writes strategy memory to influence decisions."""

    @staticmethod
    def read_position_health(ticker: str, positions: dict, memory: dict) -> dict:
        """How is this position doing? What does history say?"""
        pos = positions.get(ticker)
        if not pos:
            return {"held": False}

        # Past trades on this ticker
        ticker_hist = memory.get("ticker_history", {}).get(ticker, [])
        wins = sum(1 for t in ticker_hist if t.get("pnl", 0) > 0)
        losses = sum(1 for t in ticker_hist if t.get("pnl", 0) <= 0)
        total = wins + losses

        return {
            "held": True,
            "entry_price": pos["entry_price"],
            "entry_date": pos["entry_date"],
            "past_trades": total,
            "past_win_rate": round(wins / total * 100, 0) if total > 0 else None,
            "avg_past_pnl": round(sum(t.get("pnl", 0) for t in ticker_hist) / total, 1) if total > 0 else None,
        }

    @staticmethod
    def read_regime_wisdom(regime: str, memory: dict) -> dict:
        """What has this strategy learned about this regime?"""
        perf = memory.get("regime_performance", {}).get(regime)
        if not perf or perf.get("total", 0) == 0:
            return {"known": False, "regime": regime}

        return {
            "known": True,
            "regime": regime,
            "win_rate": round(perf["wins"] / perf["total"] * 100, 0),
            "avg_pnl": round(perf.get("total_pnl", 0) / perf["total"], 1),
            "total_trades": perf["total"],
            "suggestion": "aggressive" if perf["wins"] / perf["total"] > 0.6 else
                          "cautious" if perf["wins"] / perf["total"] < 0.4 else "normal",
        }

    @staticmethod
    def read_ticker_record(ticker: str, memory: dict) -> dict:
        """Full history on this ticker."""
        hist = memory.get("ticker_history", {}).get(ticker, [])
        if not hist:
            return {"known": False, "ticker": ticker}

        pnls = [t.get("pnl", 0) for t in hist]
        regimes = [t.get("regime", "?") for t in hist]

        return {
            "known": True,
            "ticker": ticker,
            "trades": len(hist),
            "avg_pnl": round(sum(pnls) / len(pnls), 1),
            "best": round(max(pnls), 1),
            "worst": round(min(pnls), 1),
            "last_regime": regimes[-1] if regimes else None,
            "warning": "repeated_loser" if sum(1 for p in pnls[-3:] if p < 0) >= 3 else None,
        }

    @staticmethod
    def generate_insight(date: str, positions: dict, memory: dict, regime: str, news: dict) -> str:
        """Generate a one-paragraph insight for reasoning log."""
        parts = []

        # Regime awareness
        regime_wisdom = SimulationMemory.read_regime_wisdom(regime, memory)
        if regime_wisdom.get("known"):
            parts.append(f"In '{regime}' regime (past: {regime_wisdom['total_trades']} trades, "
                        f"{regime_wisdom['win_rate']}% win rate, avg {regime_wisdom['avg_pnl']:+.1f}%)")
            if regime_wisdom["suggestion"] == "cautious":
                parts.append("— history says be cautious here")
            elif regime_wisdom["suggestion"] == "aggressive":
                parts.append("— history says this regime works well for us")

        # Position health
        problem_positions = []
        for ticker in positions:
            record = SimulationMemory.read_ticker_record(ticker, memory)
            if record.get("warning") == "repeated_loser":
                problem_positions.append(ticker)
        if problem_positions:
            parts.append(f"Watch: {', '.join(problem_positions)} have been repeated losers")

        # News context
        if news.get("has_news") and news.get("geo_risk", 0) > 0.5:
            parts.append(f"Elevated geo risk ({news['geo_risk']:.2f}): {', '.join(news.get('themes', []))}")

        return ". ".join(parts) if parts else "No notable memory or context for today."

    @staticmethod
    def write_trade_outcome(ticker: str, pnl_pct: float, regime: str, date: str, memory: dict):
        """Record a completed trade in memory for future learning."""
        # Update ticker history
        if ticker not in memory["ticker_history"]:
            memory["ticker_history"][ticker] = []
        memory["ticker_history"][ticker].append({
            "pnl": round(pnl_pct, 2),
            "regime": regime,
            "date": date,
        })

        # Update regime performance
        if regime not in memory["regime_performance"]:
            memory["regime_performance"][regime] = {"wins": 0, "losses": 0, "total": 0, "total_pnl": 0}
        rp = memory["regime_performance"][regime]
        rp["total"] += 1
        rp["total_pnl"] = rp.get("total_pnl", 0) + pnl_pct
        if pnl_pct > 0:
            rp["wins"] += 1
        else:
            rp["losses"] += 1

        # Derive lesson if pattern detected
        ticker_hist = memory["ticker_history"][ticker]
        recent = ticker_hist[-3:]
        if len(recent) >= 3 and all(t["pnl"] < 0 for t in recent):
            lesson = f"{date}: {ticker} has lost money 3 times in a row — avoid or reduce size"
            if lesson not in memory.get("lessons", []):
                memory.setdefault("lessons", []).append(lesson)

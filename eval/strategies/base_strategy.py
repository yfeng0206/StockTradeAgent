"""Base strategy class for backtesting with trade reasoning logs."""

from abc import ABC, abstractmethod
from datetime import datetime
import pandas as pd


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, name: str, initial_cash: float = 100_000, max_positions: int = 5):
        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.max_positions = max_positions
        self.min_score_threshold = 4.0  # Override in subclass. Below this = hold cash instead.
        self.atr_stop_multiplier = 2.0  # Override: Momentum=2.5, Value=3.0, Defensive=1.5
        self.trim_threshold_pct = 40.0  # Override: Momentum=50, Value=30, Event=35
        self.slippage = 0.0  # Execution slippage: buy at price*(1+slip), sell at price*(1-slip)
        self._realistic = False  # Set by daily_loop — use T-1 close for signals
        self._exec_model = "open"  # Execution model: "open", "open30", "vwap"
        self.use_cooldown = False  # Set by daily_loop via improvement flags
        self.min_holding_days = 21  # Minimum days before rebalance can sell
        self.cooldown_days = 5  # Days after selling before rebuy allowed
        self._sold_cooldown = {}  # {ticker: sell_date_str}
        self.positions = {}  # {ticker: {"shares": N, "entry_price": P, "entry_date": D}}
        self.transactions = []  # list of trade records
        self.reasoning_log = []  # WHY each trade was made
        self.portfolio_history = []  # daily snapshots
        self._last_scores = {}  # cache scores from last score_stocks call
        self._last_regime = None  # cache detected regime
        self._last_news_summary = None  # cache news context
        # Per-strategy memory — what this strategy learned during the run
        self.memory = {
            "regimes_seen": [],       # timeline of regime changes
            "news_themes_seen": [],   # geopolitical context encountered
            "profitable_trades": [],  # what worked
            "losing_trades": [],      # what didn't
            "lessons": [],            # derived insights
            "best_ticker": None,
            "worst_ticker": None,
            "ticker_history": {},     # {ticker: [{regime, pnl, date}]} — learn from past trades per ticker
            "regime_performance": {}, # {regime: {wins, losses, avg_pnl}} — learn what works in each regime
        }

        # Watchnotes — active observations per position (like an analyst's notepad)
        # Each note has a condition that gets checked at every rebalance
        self.watchnotes = {}  # {ticker: [{"note": str, "condition": str, "action": str, "created": date}]}

        # Pending checks — things to look at in the future
        self.pending_checks = []  # [{"check": str, "check_date": str, "ticker": str, "created": date}]

    def _signal_mask(self, df, date):
        """Temporal mask for signal computation.

        Realistic/premarket mode: uses T-1 data (strictly before today).
        You see yesterday's close, analyze overnight, trade this morning.
        Premarket appends a 9:00 AM estimate separately in _get_signal_close().
        Standard mode: uses T data (includes today) — original behavior.
        """
        if self._realistic or self._exec_model == "premarket":
            return df.index < pd.Timestamp(date)
        return df.index <= pd.Timestamp(date)

    def _get_signal_close(self, price_data, ticker, date, lookback=252):
        """Get Close price series for signal computation.

        - Realistic mode: T-1 data (strictly before today)
        - Premarket mode: T-1 data + appended premarket price as latest point.
          This simulates seeing pre-market movement before deciding.
        """
        if ticker not in price_data or price_data[ticker].empty:
            return None
        df = price_data[ticker]
        mask = self._signal_mask(df, date)
        if not mask.any():
            return None
        series = df.loc[mask, "Close"].tail(lookback)

        # In premarket mode, append the estimated 9:00 AM price
        if self._exec_model == "premarket":
            pm_price, _ = self._get_premarket_price(price_data, ticker, date)
            if pm_price is not None:
                pm_point = pd.Series([pm_price], index=[pd.Timestamp(date)])
                series = pd.concat([series, pm_point])

        return series

    def _get_premarket_price(self, price_data, ticker, date):
        """Estimate pre-market price ~30 min before open (9:00 AM proxy).

        Uses 0.2 × T-1 Close + 0.8 × T Open. Research shows ~80% of the
        overnight gap is visible by 9:00 AM pre-market. Both values are
        known before execution — no lookahead.

        Returns (premarket_price, gap_pct) or (None, None).
        """
        if ticker not in price_data or price_data[ticker].empty:
            return None, None
        df = price_data[ticker]
        mask_t = df.index <= pd.Timestamp(date)
        if not mask_t.any():
            return None, None
        row_t = df.loc[mask_t].iloc[-1]
        if "Open" not in df.columns:
            return None, None
        t_open = float(row_t["Open"])

        # T-1 close
        mask_t1 = df.index < pd.Timestamp(date)
        if not mask_t1.any():
            return None, None
        t1_close = float(df.loc[mask_t1, "Close"].iloc[-1])

        premarket = 0.2 * t1_close + 0.8 * t_open
        gap_pct = (t_open - t1_close) / t1_close * 100 if t1_close > 0 else 0
        return premarket, gap_pct

    def _check_gap_filter(self, gap_pct, action="buy"):
        """Asymmetric gap filter for premarket model.

        Returns position size multiplier (0.0 = skip, 0.5 = half, 1.0 = full).

        Buy side:  gap UP hurts (paying more than expected)
        Sell side: gap DOWN hurts (receiving less than expected)
        """
        # Thresholds (configurable via self if needed)
        small = 1.0   # < 1% gap: full position
        medium = 3.0  # 1-3% gap: half position
        # > 3% gap: skip

        if action == "buy":
            # Gap UP is bad for buys
            if gap_pct <= small:
                return 1.0
            elif gap_pct <= medium:
                return 0.5
            else:
                return 0.0  # skip — too much overnight move
        else:
            # Gap DOWN is bad for sells (but we usually still want to sell)
            if gap_pct >= -small:
                return 1.0
            elif gap_pct >= -medium:
                return 1.0  # still sell, gap down = worse price but don't hold a loser
            else:
                return 1.0  # large gap down — still sell (stop losses must execute)

    def _get_exec_price(self, price_data, ticker, date):
        """Get execution price based on the configured model.

        Models:
          'open'      — T's Open price (standard academic, Zipline default)
          'premarket' — T's Open, with pre-market gap awareness for signals
          'open30'    — 70% Open + 30% Close (proxy, has minor lookahead)
          'vwap'      — (H+L+C)/3 typical price (has lookahead — benchmark only)
        """
        if ticker not in price_data or price_data[ticker].empty:
            return None
        df = price_data[ticker]
        mask = df.index <= pd.Timestamp(date)
        if not mask.any():
            return None
        row = df.loc[mask].iloc[-1]

        if self._exec_model in ("open", "premarket") and "Open" in df.columns:
            price = float(row["Open"])
        elif self._exec_model == "open30" and "Open" in df.columns:
            price = float(row["Open"]) * 0.7 + float(row["Close"]) * 0.3
        elif self._exec_model == "vwap" and all(c in df.columns for c in ["High", "Low", "Close"]):
            price = (float(row["High"]) + float(row["Low"]) + float(row["Close"])) / 3
        else:
            price = float(row["Close"])  # fallback

        return price  # slippage applied separately in _buy()/_sell()

    def _read_memory_for_scoring(self, ticker: str, regime: str) -> float:
        """Read memory to adjust score based on past experience.

        Returns a score adjustment (-2 to +2) based on:
        - How this ticker performed in similar regimes before
        - Whether we've been burned by this ticker recently
        - Overall regime performance history
        """
        adj = 0.0

        # 1. Check ticker history in similar regimes
        ticker_hist = self.memory["ticker_history"].get(ticker, [])
        similar = [t for t in ticker_hist if t.get("regime") == regime]
        if similar:
            avg_pnl = sum(t["pnl"] for t in similar) / len(similar)
            if avg_pnl > 10:
                adj += 1.0  # This ticker did well in this regime before
            elif avg_pnl > 0:
                adj += 0.3
            elif avg_pnl < -10:
                adj -= 1.0  # Got burned on this ticker in this regime
            elif avg_pnl < 0:
                adj -= 0.3

        # 2. Check recent losses on this ticker (avoid revenge trading)
        recent_losses = [t for t in ticker_hist if t.get("pnl", 0) < -5]
        if len(recent_losses) >= 2:
            adj -= 0.5  # Repeatedly lost on this ticker, be cautious

        # 3. Check overall regime performance
        regime_perf = self.memory["regime_performance"].get(regime)
        if regime_perf and regime_perf.get("total", 0) > 3:
            win_rate = regime_perf["wins"] / regime_perf["total"]
            if win_rate < 0.3:
                adj -= 0.5  # This regime has been bad for us overall

        return max(-2.0, min(2.0, adj))

    def _check_watchnotes(self, price_data: dict, date: str):
        """Check all active watchnotes and trigger actions if conditions are met.

        Called at the start of each rebalance. Returns list of triggered alerts.
        """
        triggered = []

        for ticker, notes in list(self.watchnotes.items()):
            remaining = []
            for note in notes:
                condition = note.get("condition", "")
                fired = False

                # Check price-based conditions (use T-1 data to avoid lookahead)
                if ticker in price_data and not price_data[ticker].empty:
                    df = price_data[ticker]
                    mask = self._signal_mask(df, date)
                    if mask.any():
                        current_price = float(df.loc[mask, "Close"].iloc[-1])

                        if "price_below:" in condition:
                            threshold = float(condition.split("price_below:")[1])
                            if current_price < threshold:
                                fired = True
                        elif "price_above:" in condition:
                            threshold = float(condition.split("price_above:")[1])
                            if current_price > threshold:
                                fired = True

                # Check regime-based conditions
                if "regime_change" in condition and self._last_regime:
                    expected = condition.split("regime_change:")[1] if ":" in condition else ""
                    if expected and expected in str(self._last_regime):
                        fired = True

                # Check news-based conditions
                if "geo_risk_drops" in condition:
                    if self._last_news_summary and "geo_risk" in str(self._last_news_summary):
                        try:
                            risk = float(str(self._last_news_summary).split("geo_risk=")[1][:4])
                            if risk < 0.3:
                                fired = True
                        except (ValueError, IndexError):
                            pass

                if "geo_risk_rises" in condition:
                    if self._last_news_summary and "geo_risk" in str(self._last_news_summary):
                        try:
                            risk = float(str(self._last_news_summary).split("geo_risk=")[1][:4])
                            if risk > 0.7:
                                fired = True
                        except (ValueError, IndexError):
                            pass

                # Check date-based conditions (pending checks)
                if "check_by:" in condition:
                    check_date = condition.split("check_by:")[1][:10]
                    if date >= check_date:
                        fired = True

                if fired:
                    triggered.append({
                        "ticker": ticker,
                        "note": note["note"],
                        "action": note.get("action", "review"),
                        "date": date,
                    })
                else:
                    remaining.append(note)

            if remaining:
                self.watchnotes[ticker] = remaining
            elif ticker in self.watchnotes:
                del self.watchnotes[ticker]

        return triggered

    def _create_watchnotes_for_buy(self, ticker: str, price: float, date: str, scores: dict):
        """Create observation notes for a new buy. NO trade actions — just reminders.

        Stop-losses and profit targets are handled by TriggerEngine, not watchnotes.
        Watchnotes are for context: "why did I buy this? what should I watch for?"
        """
        notes = []
        regime = self._last_regime or "unknown"
        news = self._last_news_summary

        # Context: what drove this buy
        notes.append({
            "note": f"Entry: ${price:.2f} on {date}. Regime: {regime}. News: {news or 'none'}.",
            "condition": "info_only",
            "action": "none",
            "created": date,
        })

        # If bought during high geo risk, note the catalyst dependency
        if news and "geo_risk" in str(news):
            try:
                risk = float(str(news).split("geo_risk=")[1][:4])
                if risk > 0.5:
                    notes.append({
                        "note": f"Bought during geo risk {risk:.2f}. If tensions ease, catalyst may weaken.",
                        "condition": "geo_risk_drops",
                        "action": "review_thesis",
                        "created": date,
                    })
            except (ValueError, IndexError):
                pass

        # If bought in volatile regime, note for rotation review
        if "defensive" in str(regime).lower() or "high_vol" in str(regime).lower() or "crisis" in str(regime).lower():
            notes.append({
                "note": f"Bought in {regime}. When regime improves, consider rotating to growth.",
                "condition": "regime_change:bullish",
                "action": "review_thesis",
                "created": date,
            })

        if notes:
            self.watchnotes[ticker] = notes

    @abstractmethod
    def score_stocks(self, universe: list, price_data: dict, date: str, **kwargs) -> list:
        """Score and rank stocks. Returns list of (ticker, score) sorted best-first.

        Subclasses MUST also populate self._last_scores with per-ticker score breakdowns:
            self._last_scores[ticker] = {"composite": X, "momentum": Y, "value": Z, ...}

        Kwargs:
            signal_engine: Optional SignalEngine instance (used by MixStrategy for breadth).
        """
        pass

    @property
    def rebalance_frequency(self) -> str:
        """Override in subclass: 'monthly' or 'quarterly'. CLI can override via _frequency_override."""
        if hasattr(self, '_frequency_override') and self._frequency_override:
            return self._frequency_override
        return "monthly"

    def _log_reasoning(self, date: str, action: str, ticker: str, price: float,
                       reason: str, score_breakdown: dict = None):
        """Log WHY a trade was made — the core audit trail."""
        entry = {
            "date": date,
            "action": action,
            "ticker": ticker,
            "price": round(price, 2),
            "reason": reason,
            "regime": self._last_regime,
            "news_context": self._last_news_summary,
        }
        if score_breakdown:
            entry["scores"] = score_breakdown
        self.reasoning_log.append(entry)

    def execute_rebalance(self, scores: list, price_data: dict, date: str):
        """Sell positions not in top picks, buy new top picks with equal weight."""
        # Step 0: Check watchnotes BEFORE making decisions
        triggered = self._check_watchnotes(price_data, date)
        for alert in triggered:
            if alert["action"] == "consider_sell" and alert["ticker"] in self.positions:
                # Watchnote says sell — force remove from top picks
                scores = [(t, s) for t, s in scores if t != alert["ticker"]]

        # Only consider stocks above minimum conviction threshold
        qualified = [(t, s) for t, s in scores if s >= self.min_score_threshold]
        if not qualified and scores:
            self._log_reasoning(date, "CASH", "", 0,
                f"No stocks above threshold ({self.min_score_threshold}). "
                f"Best: {scores[0][0]}={scores[0][1]:.1f}. Holding cash.")

        top_tickers = [t for t, s in qualified[:self.max_positions]]
        top_scores = {t: s for t, s in qualified[:self.max_positions]}
        prices_on_date = {}

        for ticker in list(self.positions.keys()) + top_tickers:
            p = self._get_exec_price(price_data, ticker, date)
            if p is not None:
                prices_on_date[ticker] = p

        # Minimum holding period: don't sell positions held less than N days
        if self.use_cooldown:
            for ticker in list(self.positions.keys()):
                if ticker not in top_tickers:
                    pos = self.positions[ticker]
                    entry = pos.get("entry_date", date)
                    days_held = (pd.Timestamp(date) - pd.Timestamp(entry)).days
                    if days_held < self.min_holding_days:
                        top_tickers.append(ticker)  # force keep
                        self._log_reasoning(date, "HOLD_MIN", ticker, 0,
                            f"Holding: only {days_held}d < {self.min_holding_days}d minimum")

        # Sell positions not in top picks
        for ticker in list(self.positions.keys()):
            if ticker not in top_tickers:
                if ticker in prices_on_date:
                    # Build sell reason
                    old_score = self._last_scores.get(ticker, {})
                    reason = f"Dropped from top {self.max_positions}."
                    if old_score:
                        reason += f" Score: {old_score.get('composite', '?')}"
                    if top_tickers:
                        reason += f" Replaced by: {', '.join(top_tickers[:3])}"
                    self._sell(ticker, prices_on_date[ticker], date, reason, old_score)

        # Calculate equal weight for new positions (using investable cash)
        num_to_buy = self.max_positions - len(self.positions)
        investable = self._get_investable_cash(price_data, date)
        if num_to_buy > 0 and investable > 0:
            per_position = investable / num_to_buy if num_to_buy > 0 else 0
            for ticker in top_tickers:
                if ticker not in self.positions and ticker in prices_on_date:
                    price = prices_on_date[ticker]
                    if price <= 0:
                        continue

                    # Cooldown: don't rebuy recently sold tickers
                    if self.use_cooldown:
                        sell_date = self._sold_cooldown.get(ticker)
                        if sell_date:
                            days_since = (pd.Timestamp(date) - pd.Timestamp(sell_date)).days
                            if days_since < self.cooldown_days:
                                self._log_reasoning(date, "SKIP_COOL", ticker, price,
                                    f"Cooldown: sold {days_since}d ago < {self.cooldown_days}d minimum")
                                continue

                    # Apply risk overlay size adjustment if available
                    size_mult = self._risk_size_multipliers.get(ticker, 1.0) if hasattr(self, '_risk_size_multipliers') else 1.0
                    adjusted_budget = per_position * size_mult

                    if adjusted_budget < price and size_mult < 1.0:
                        # Risk overlay reduced below 1 share — skip with reason
                        self._log_reasoning(date, "SKIP_RISK", ticker, price,
                            f"Risk overlay reduced size to {size_mult:.0%}, "
                            f"budget ${adjusted_budget:.0f} < price ${price:.0f}")
                        continue

                    shares = int(adjusted_budget / price)
                    if shares > 0:
                        # Build buy reason
                        score_data = self._last_scores.get(ticker, {})
                        reason = f"Ranked in top {self.max_positions}. Score: {top_scores.get(ticker, '?')}"
                        if size_mult < 1.0:
                            reason += f" [risk_overlay: {size_mult:.0%} size]"
                        if score_data:
                            parts = []
                            for k, v in score_data.items():
                                if k != "composite" and isinstance(v, (int, float)):
                                    parts.append(f"{k}={v:.1f}")
                            if parts:
                                reason += f" ({', '.join(parts)})"
                        self._buy(ticker, shares, price, date, reason, score_data,
                                 price_data=price_data)

    def _get_investable_cash(self, price_data: dict, date: str) -> float:
        """Cash available for new positions, after reserving the dynamic cash floor.

        Uses risk_overlay's CashFloorManager if attached, otherwise returns all cash.
        """
        if not hasattr(self, '_cash_floor_amount'):
            return self.cash
        return max(0, self.cash - self._cash_floor_amount)

    def _buy(self, ticker: str, shares: int, price: float, date: str,
             reason: str = "", score_breakdown: dict = None,
             price_data: dict = None):
        # Premarket gap filter: reduce or skip buys on large gap-ups
        if self._exec_model == "premarket" and price_data is not None:
            _, gap_pct = self._get_premarket_price(price_data, ticker, date)
            if gap_pct is not None:
                size_mult = self._check_gap_filter(gap_pct, action="buy")
                if size_mult == 0.0:
                    self._log_reasoning(date, "SKIP_GAP", ticker, price,
                        f"Gap +{gap_pct:.1f}% too large, skipping buy. {reason}")
                    return
                elif size_mult < 1.0:
                    shares = max(1, int(shares * size_mult))
                    reason += f" [gap {gap_pct:+.1f}%, size reduced to {size_mult:.0%}]"

        # Apply slippage: in reality you pay slightly more than close
        if self.slippage > 0:
            price = price * (1 + self.slippage)
        cost = shares * price

        # Partial fill: if not enough cash for full order, buy what we can
        if cost > self.cash:
            shares = int(self.cash / price)
            cost = shares * price
            if shares > 0:
                reason += f" [partial fill: cash limited to {shares} shares]"

        if shares <= 0:
            # Graceful skip with logging
            self._log_reasoning(date, "SKIP", ticker, price,
                f"Insufficient cash (${self.cash:,.0f}) for even 1 share at ${price:.2f}. "
                f"Original reason: {reason}")
            return

        self.cash -= cost
        self.positions[ticker] = {
            "shares": shares,
            "entry_price": price,
            "entry_date": date,
        }
        self.transactions.append({
            "date": date,
            "action": "BUY",
            "ticker": ticker,
            "shares": shares,
            "price": round(price, 2),
            "total": round(cost, 2),
            "cash_after": round(self.cash, 2),
        })
        # Check memory for past experience with this ticker
        mem_adj = self._read_memory_for_scoring(ticker, str(self._last_regime))
        if mem_adj != 0:
            reason += f" [Memory adj: {mem_adj:+.1f}]"

        self._log_reasoning(date, "BUY", ticker, price, reason, score_breakdown)

        # Create watchnotes for this new position
        self._create_watchnotes_for_buy(ticker, price, date, score_breakdown or {})

    def _sell(self, ticker: str, price: float, date: str,
              reason: str = "", score_breakdown: dict = None):
        if ticker not in self.positions:
            return
        # Apply slippage: in reality you receive slightly less than close
        if self.slippage > 0:
            price = price * (1 - self.slippage)
        pos = self.positions[ticker]
        shares = pos["shares"]
        proceeds = shares * price
        pnl = (price - pos["entry_price"]) * shares
        pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100

        self.cash += proceeds
        del self.positions[ticker]
        if self.use_cooldown:
            self._sold_cooldown[ticker] = date
        self.transactions.append({
            "date": date,
            "action": "SELL",
            "ticker": ticker,
            "shares": shares,
            "price": round(price, 2),
            "total": round(proceeds, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "cash_after": round(self.cash, 2),
        })
        full_reason = reason
        if pnl_pct != 0:
            full_reason += f" PnL: {pnl_pct:+.1f}% (held since {pos['entry_date']})"
        self._log_reasoning(date, "SELL", ticker, price, full_reason, score_breakdown)

        # Update ALL memory in one place (the only place trades are recorded)
        trade_record = {"ticker": ticker, "pnl_pct": round(pnl_pct, 2), "date": date,
                        "held_from": pos["entry_date"], "regime": self._last_regime}
        if pnl > 0:
            self.memory["profitable_trades"].append(trade_record)
        else:
            self.memory["losing_trades"].append(trade_record)

        # Also write to ticker_history and regime_performance (unified)
        from sim_memory import SimulationMemory
        SimulationMemory.write_trade_outcome(
            ticker, round(pnl_pct, 2), str(self._last_regime), date, self.memory)

    def get_portfolio_value(self, price_data: dict, date: str,
                            decision_time: bool = False) -> float:
        """Get portfolio value. Use decision_time=True for pre-rebalance calculations.

        decision_time=False (default): uses <= date close (EOD NAV, snapshots)
        decision_time=True: uses _signal_mask (T-1 in realistic mode, no lookahead)
        """
        total = self.cash
        for ticker, pos in self.positions.items():
            if ticker in price_data and not price_data[ticker].empty:
                df = price_data[ticker]
                if decision_time:
                    mask = self._signal_mask(df, date)
                else:
                    mask = df.index <= pd.Timestamp(date)
                if mask.any():
                    price = float(df.loc[mask, "Close"].iloc[-1])
                    total += pos["shares"] * price
        return total

    def snapshot(self, price_data: dict, date: str):
        value = self.get_portfolio_value(price_data, date, decision_time=False)
        self.portfolio_history.append({
            "date": date,
            "total_value": round(value, 2),
            "cash": round(self.cash, 2),
            "num_positions": len(self.positions),
            "return_pct": round((value - self.initial_cash) / self.initial_cash * 100, 2),
        })
        # Track regime changes in memory
        if self._last_regime:
            regimes = self.memory["regimes_seen"]
            if not regimes or regimes[-1]["regime"] != self._last_regime:
                regimes.append({"date": date, "regime": self._last_regime})
        if self._last_news_summary:
            themes = self.memory["news_themes_seen"]
            if not themes or themes[-1]["context"] != self._last_news_summary:
                themes.append({"date": date, "context": self._last_news_summary})

    def finalize_memory(self):
        """Call at end of run — computes summary insights for this strategy."""
        wins = self.memory["profitable_trades"]
        losses = self.memory["losing_trades"]
        if wins:
            best = max(wins, key=lambda t: t["pnl_pct"])
            self.memory["best_ticker"] = f"{best['ticker']} +{best['pnl_pct']}%"
        if losses:
            worst = min(losses, key=lambda t: t["pnl_pct"])
            self.memory["worst_ticker"] = f"{worst['ticker']} {worst['pnl_pct']}%"

        total_trades = len(wins) + len(losses)
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

        self.memory["lessons"] = [
            f"Win rate: {win_rate:.0f}% ({len(wins)}W / {len(losses)}L)",
            f"Avg win: +{avg_win:.1f}%, Avg loss: {avg_loss:.1f}%",
            f"Regimes encountered: {len(self.memory['regimes_seen'])} changes",
        ]
        # Track which regimes were profitable
        regime_pnl = {}
        for t in wins + losses:
            r = t.get("regime", "unknown")
            if r not in regime_pnl:
                regime_pnl[r] = []
            regime_pnl[r].append(t["pnl_pct"])
        for r, pnls in regime_pnl.items():
            avg = sum(pnls) / len(pnls)
            self.memory["lessons"].append(f"Regime '{r}': avg PnL {avg:+.1f}% over {len(pnls)} trades")

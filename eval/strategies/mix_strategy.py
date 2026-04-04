"""Mix Strategy — Regime-detecting multi-asset allocator.

Watches the OTHER 7 strategies running in the same simulation as live sensors.
Uses their actual performance, positions, regime labels, and cash levels
to detect the current market regime, then allocates across stocks + commodity + cash.

Sensor channels (from live strategy state):
  1. Strategy performance: which strategies are making/losing money?
  2. Commodity strategy: is it invested or in cash?
  3. Defensive strategy: what defense state is it in?
  4. Adaptive strategy: what mode did it detect?
  5. Market data: SPY trend, volatility (direct read)

Regime → Allocation:
  AGGRESSIVE:  80% stocks (momentum picks), 0% commodity, 20% cash
  CAUTIOUS:    40% stocks (low-vol), 30% commodity, 30% cash
  DEFENSIVE:   20% stocks (ultra-safe), 30% commodity, 50% cash
  RECOVERY:    70% stocks (bounce plays), 10% commodity, 20% cash
  UNCERTAIN:   50% stocks (balanced), 20% commodity, 30% cash

Runs AFTER the other 7 strategies each day in the daily loop.
Rebalances monthly. Holds up to max_positions stocks + 1 commodity slot.
"""

import numpy as np
import pandas as pd
from .base_strategy import BaseStrategy


# Oil proxy tickers (same as CommodityStrategy)
OIL_PROXIES = ["USO", "XLE", "XOM"]

# Allocation targets by regime: (stock_pct, commodity_pct, cash_pct)
# Key: commodity only in DEFENSIVE/CAUTIOUS. Bull markets = all stocks.
REGIME_ALLOCATIONS = {
    "AGGRESSIVE": (0.90, 0.00, 0.10),
    "CAUTIOUS":   (0.50, 0.20, 0.30),
    "DEFENSIVE":  (0.20, 0.30, 0.50),
    "RECOVERY":   (0.80, 0.00, 0.20),
    "UNCERTAIN":  (0.70, 0.00, 0.30),
}


class MixStrategy(BaseStrategy):
    def __init__(self, initial_cash: float = 100_000, events_calendar: dict = None,
                 max_positions: int = 10, regime_stickiness: int = 1):
        super().__init__("Mix", initial_cash, max_positions=max_positions)
        self.min_score_threshold = 4.0
        self.atr_stop_multiplier = 2.0
        self.trim_threshold_pct = 40.0
        self.events_calendar = events_calendar or {}
        self.detected_regime = "UNCERTAIN"
        self.regime_history = []
        self._sensor_readings = {}
        self._peer_strategies = []  # set by daily_loop — references to other strategy objects
        # Asymmetric regime stickiness:
        # - Going TO defensive/cautious: instant (stickiness=1) — protect capital fast
        # - Going FROM defensive back to aggressive: require N days confirmation — avoid whipsaw
        # regime_stickiness controls the "leaving defensive" delay. 1 = original behavior.
        self._regime_stickiness = regime_stickiness
        self._pending_regime = None   # what regime is building up
        self._pending_count = 0       # how many consecutive days it's been detected
        self._realistic = False       # set by daily_loop if --realistic

    def _signal_mask(self, df, date):
        """Temporal mask for signal computation. Uses T-1 in realistic/premarket mode."""
        if self._realistic or self._exec_model == "premarket":
            return df.index < pd.Timestamp(date)
        return df.index <= pd.Timestamp(date)

    @property
    def rebalance_frequency(self) -> str:
        return "monthly"

    # ================================================================
    # SENSOR: Read other strategies' live state
    # ================================================================
    def _sense_peers(self, price_data: dict, date: str) -> dict:
        """Read the other strategies' current state as regime sensors.

        Returns a dict with:
          - strategy_returns: {name: return_pct} — who's winning/losing
          - commodity_invested: bool — is Commodity strategy holding oil?
          - defensive_state: str — NORMAL/REDUCED/DEFENSE
          - adaptive_mode: str — MOMENTUM/VALUE/DEFENSIVE/RECOVERY
          - momentum_return: float — Momentum strategy's current return
          - cash_heavy_count: int — how many strategies are >50% cash
          - avg_return: float — average return across all peers
        """
        readings = {
            "strategy_returns": {},
            "commodity_invested": False,
            "commodity_return": 0.0,
            "defensive_state": "NORMAL",
            "adaptive_mode": "MOMENTUM",
            "momentum_return": 0.0,
            "value_return": 0.0,
            "cash_heavy_count": 0,
            "avg_return": 0.0,
        }

        if not self._peer_strategies:
            return readings

        returns = []
        for strat in self._peer_strategies:
            # Get current return
            if strat.portfolio_history:
                ret = strat.portfolio_history[-1].get("return_pct", 0)
            else:
                ret = 0.0
            readings["strategy_returns"][strat.name] = ret
            returns.append(ret)

            # Cash ratio
            pv = strat.get_portfolio_value(price_data, date)
            if pv > 0 and strat.cash / pv > 0.5:
                readings["cash_heavy_count"] += 1

            # Strategy-specific reads
            if strat.name == "Commodity":
                readings["commodity_invested"] = len(strat.positions) > 0
                readings["commodity_return"] = ret
            elif strat.name == "Defensive":
                readings["defensive_state"] = getattr(strat, '_defense_state', 'NORMAL')
            elif strat.name == "Adaptive":
                readings["adaptive_mode"] = getattr(strat, 'current_mode', 'MOMENTUM')
            elif strat.name == "Momentum":
                readings["momentum_return"] = ret
            elif strat.name == "Value":
                readings["value_return"] = ret

        readings["avg_return"] = sum(returns) / len(returns) if returns else 0
        return readings

    # ================================================================
    # SENSOR: Direct market data read (for early days before peers have data)
    # ================================================================
    def _sense_market(self, price_data: dict, date: str) -> dict:
        """Direct SPY/oil read — fallback when peer data is thin."""
        result = {
            "spy_above_50ma": True, "spy_above_200ma": True,
            "spy_vol_20d": 0.15, "spy_ret_1m": 0, "spy_ret_3m": 0,
            "spy_drawdown": 0, "oil_bullish": False, "oil_proxy": None,
        }

        if "SPY" in price_data and not price_data["SPY"].empty:
            df = price_data["SPY"]
            mask = self._signal_mask(df, date)
            if mask.any() and mask.sum() >= 50:
                close = df.loc[mask, "Close"].tail(252)
                current = float(close.iloc[-1])
                returns = close.pct_change().dropna()

                sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
                sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current
                vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0.15
                ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
                ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0
                peak_60d = float(close.tail(60).max())
                dd = (current - peak_60d) / peak_60d * 100

                result["spy_above_50ma"] = current > sma_50
                result["spy_above_200ma"] = current > sma_200
                result["spy_vol_20d"] = vol_20d
                result["spy_ret_1m"] = ret_1m
                result["spy_ret_3m"] = ret_3m
                result["spy_drawdown"] = dd

        # Oil signal
        for proxy in OIL_PROXIES:
            if proxy in price_data and not price_data[proxy].empty:
                df = price_data[proxy]
                mask = self._signal_mask(df, date)
                if mask.any() and mask.sum() >= 50:
                    close = df.loc[mask, "Close"].tail(252)
                    current = float(close.iloc[-1])
                    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
                    sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current
                    ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0

                    score = 0
                    if current > sma_50: score += 3
                    if current > sma_200: score += 2
                    if ret_1m > 0: score += 2

                    result["oil_bullish"] = score > 4
                    result["oil_proxy"] = proxy
                    break

        return result

    # ================================================================
    # REGIME CLASSIFIER — combines peer signals + market data
    # ================================================================
    def _detect_regime(self, price_data: dict, date: str) -> str:
        """Classify regime using other strategies as sensors + direct market read."""
        peers = self._sense_peers(price_data, date)
        market = self._sense_market(price_data, date)

        self._sensor_readings = {"peers": peers, "market": market}

        # --- Extract key signals ---
        defensive_state = peers["defensive_state"]
        adaptive_mode = peers["adaptive_mode"]
        commodity_invested = peers["commodity_invested"]
        commodity_ret = peers["commodity_return"]
        momentum_ret = peers["momentum_return"]
        value_ret = peers["value_return"]
        cash_heavy = peers["cash_heavy_count"]
        avg_ret = peers["avg_return"]

        spy_above_200 = market["spy_above_200ma"]
        spy_above_50 = market["spy_above_50ma"]
        spy_vol = market["spy_vol_20d"]
        spy_dd = market["spy_drawdown"]
        oil_bullish = market["oil_bullish"]

        # --- Decision tree using peer signals ---
        # Priority: DEFENSIVE (protect capital) > AGGRESSIVE (capture upside) > others
        # Key lesson: be FAST to go aggressive. Bull markets are the norm.
        # Only go defensive on strong, multi-signal confirmation.

        # 1. DEFENSIVE: only on strong multi-signal confirmation
        #    Need BOTH Defensive in DEFENSE AND (high vol OR Adaptive in DEFENSIVE)
        if defensive_state == "DEFENSE" and (spy_vol > 0.25 or adaptive_mode == "DEFENSIVE"):
            return "DEFENSIVE"
        if cash_heavy >= 4:  # raised from 3 — need strong consensus
            return "DEFENSIVE"

        # 2. AGGRESSIVE: be fast to recognize bull markets
        #    Any ONE of these is enough (was requiring ALL before — too strict):
        #    - Adaptive in MOMENTUM mode and SPY above 50ma
        #    - Momentum strategy making money (>0%) and SPY above 200ma
        #    - SPY above both MAs and vol is low
        if adaptive_mode == "MOMENTUM" and spy_above_50:
            return "AGGRESSIVE"
        if momentum_ret > 0 and spy_above_200 and defensive_state == "NORMAL":
            return "AGGRESSIVE"
        if spy_above_50 and spy_above_200 and spy_vol < 0.22:
            return "AGGRESSIVE"

        # 3. RECOVERY: coming out of a dip
        if adaptive_mode == "RECOVERY":
            return "RECOVERY"
        if spy_dd < -8 and market["spy_ret_1m"] > 2:
            return "RECOVERY"

        # 4. CAUTIOUS: only when commodity is clearly outperforming AND trend is broken
        #    (not just "oil is bullish" — need actual divergence)
        if commodity_invested and commodity_ret > avg_ret + 10 and not spy_above_50:
            return "CAUTIOUS"
        if defensive_state == "REDUCED" and not spy_above_200:
            return "CAUTIOUS"

        # 5. Default to AGGRESSIVE if SPY above 200ma, UNCERTAIN otherwise
        #    Key change: don't default to conservative. Markets trend up.
        if spy_above_200:
            return "AGGRESSIVE"

        return "UNCERTAIN"

    # ================================================================
    # STOCK SCORING — changes by regime
    # ================================================================
    # Defensive ordering: higher = more defensive
    _DEFENSE_ORDER = {
        "AGGRESSIVE": 0, "RECOVERY": 1, "UNCERTAIN": 2, "CAUTIOUS": 3, "DEFENSIVE": 4,
    }

    def _apply_regime_stickiness(self, raw_regime, date):
        """Asymmetric stickiness: fast to defend, slow to leave defense.

        - Escalating toward defensive (higher defense order): INSTANT switch.
          A real crash can't wait 3 days for confirmation.
        - De-escalating toward aggressive (lower defense order): require N days.
          Prevents whipsaw where 1 good day in a crisis triggers full re-entry.

        Stickiness=1 means instant switch in both directions (original behavior).
        """
        if self._regime_stickiness <= 1:
            return raw_regime

        if raw_regime == self.detected_regime:
            self._pending_regime = None
            self._pending_count = 0
            return self.detected_regime

        raw_level = self._DEFENSE_ORDER.get(raw_regime, 2)
        current_level = self._DEFENSE_ORDER.get(self.detected_regime, 2)

        # Escalating (going MORE defensive): instant switch, no delay
        if raw_level > current_level:
            self._pending_regime = None
            self._pending_count = 0
            return raw_regime

        # De-escalating (going LESS defensive): require N consecutive days
        if raw_regime == self._pending_regime:
            self._pending_count += 1
            if self._pending_count >= self._regime_stickiness:
                self._pending_regime = None
                self._pending_count = 0
                return raw_regime
            return self.detected_regime
        else:
            self._pending_regime = raw_regime
            self._pending_count = 1
            return self.detected_regime

    def score_stocks(self, universe: list, price_data: dict, date: str) -> list:
        """Score stocks based on detected regime."""
        raw_regime = self._detect_regime(price_data, date)
        new_regime = self._apply_regime_stickiness(raw_regime, date)

        if new_regime != self.detected_regime:
            self.regime_history.append({
                "date": date, "from": self.detected_regime, "to": new_regime,
                "sensors": _summarize_sensors(self._sensor_readings),
            })
        self.detected_regime = new_regime
        self._last_regime = f"mix:{new_regime}"

        if new_regime == "AGGRESSIVE":
            return self._score_momentum_stocks(universe, price_data, date)
        elif new_regime == "DEFENSIVE":
            return self._score_defensive_stocks(universe, price_data, date)
        elif new_regime == "RECOVERY":
            return self._score_recovery_stocks(universe, price_data, date)
        elif new_regime == "CAUTIOUS":
            return self._score_cautious_stocks(universe, price_data, date)
        else:
            return self._score_balanced_stocks(universe, price_data, date)

    # --- Scoring modes (same as before — these pick which stocks to buy) ---

    def _score_momentum_stocks(self, universe, price_data, date):
        """AGGRESSIVE: chase winners."""
        scores = []
        for ticker in universe:
            if ticker in OIL_PROXIES:
                continue
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            current = float(close.iloc[-1])

            ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0
            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
            ema_12 = float(close.ewm(span=12).mean().iloc[-1])
            ema_26 = float(close.ewm(span=26).mean().iloc[-1])

            mom = min(10, max(0, 5 + ret_3m / 4))
            trend = 7 if current > sma_50 else 3
            macd = 7 if ema_12 > ema_26 else 3

            composite = mom * 0.45 + trend * 0.30 + macd * 0.25
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "regime": "AGGRESSIVE",
                "momentum": round(mom, 2), "trend": round(trend, 2), "macd": round(macd, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_defensive_stocks(self, universe, price_data, date):
        """DEFENSIVE: only safest, lowest-vol names."""
        scores = []
        for ticker in universe:
            if ticker in OIL_PROXIES:
                continue
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            returns = close.pct_change().dropna()
            current = float(close.iloc[-1])

            vol = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else 0.5
            if vol == 0:
                continue
            vol_score = max(0, 10 - vol * 20)

            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
            trend = 7 if current > sma_200 else 2

            rolling_max = close.rolling(90, min_periods=1).max()
            dd = (close - rolling_max) / rolling_max
            max_dd = float(dd.min()) if not dd.empty else -0.3
            dd_score = max(0, 10 + max_dd * 20)

            composite = vol_score * 0.45 + trend * 0.30 + dd_score * 0.25
            if composite < 5:
                continue
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "regime": "DEFENSIVE",
                "low_vol": round(vol_score, 2), "trend": round(trend, 2), "drawdown": round(dd_score, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:max(2, self.max_positions // 3)]

    def _score_recovery_stocks(self, universe, price_data, date):
        """RECOVERY: buy quality stocks bouncing off lows."""
        scores = []
        for ticker in universe:
            if ticker in OIL_PROXIES:
                continue
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            current = float(close.iloc[-1])

            low_60d = float(close.tail(60).min())
            bounce = (current - low_60d) / low_60d * 100 if low_60d > 0 else 0
            bounce_score = min(10, max(0, bounce / 3))

            high_252d = float(close.max())
            upside = (high_252d - current) / current * 100
            upside_score = min(10, max(0, upside / 5))

            ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            mom_score = min(10, max(0, 5 + ret_1m / 2))

            composite = bounce_score * 0.35 + upside_score * 0.30 + mom_score * 0.35
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "regime": "RECOVERY",
                "bounce": round(bounce_score, 2), "upside": round(upside_score, 2),
                "momentum": round(mom_score, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_cautious_stocks(self, universe, price_data, date):
        """CAUTIOUS: low-vol stocks + momentum filter."""
        scores = []
        for ticker in universe:
            if ticker in OIL_PROXIES:
                continue
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            returns = close.pct_change().dropna()
            current = float(close.iloc[-1])

            vol = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else 0.5
            if vol == 0:
                continue
            vol_score = max(0, 10 - vol * 20)

            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
            sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else current
            trend = 0
            if current > sma_200: trend += 4
            if current > sma_50: trend += 3

            ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            mom = min(10, max(0, 5 + ret_1m / 3))

            composite = vol_score * 0.40 + trend * 0.30 + mom * 0.30
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "regime": "CAUTIOUS",
                "low_vol": round(vol_score, 2), "trend": round(trend, 2), "momentum": round(mom, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_balanced_stocks(self, universe, price_data, date):
        """UNCERTAIN: balanced value + momentum."""
        scores = []
        for ticker in universe:
            if ticker in OIL_PROXIES:
                continue
            if ticker not in price_data or price_data[ticker].empty:
                continue
            df = price_data[ticker]
            mask = self._signal_mask(df, date)
            if not mask.any() or mask.sum() < 60:
                continue
            close = df.loc[mask, "Close"].tail(252)
            returns = close.pct_change().dropna()
            current = float(close.iloc[-1])

            vol = float(returns.tail(90).std() * np.sqrt(252)) if len(returns) >= 90 else 0.3
            vol_score = max(0, 10 - vol * 20)

            ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0
            mom_score = min(10, max(0, 5 + ret_3m / 4))

            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else current
            trend = 7 if current > sma_50 else 3

            composite = vol_score * 0.30 + mom_score * 0.35 + trend * 0.35
            self._last_scores[ticker] = {
                "composite": round(composite, 2), "regime": "UNCERTAIN",
                "low_vol": round(vol_score, 2), "momentum": round(mom_score, 2), "trend": round(trend, 2),
            }
            scores.append((ticker, round(composite, 3)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    # ================================================================
    # EXECUTION — multi-asset: stocks + commodity + cash
    # ================================================================
    def execute_rebalance(self, scores, price_data, date):
        """Custom rebalance: stocks + commodity + cash based on regime."""
        stock_pct, commodity_pct, cash_pct = REGIME_ALLOCATIONS.get(
            self.detected_regime, (0.50, 0.20, 0.30))

        portfolio_value = self.get_portfolio_value(price_data, date)
        stock_target = portfolio_value * stock_pct
        commodity_target = portfolio_value * commodity_pct

        # --- Identify current positions ---
        commodity_positions = {t: p for t, p in self.positions.items() if t in OIL_PROXIES}
        stock_positions = {t: p for t, p in self.positions.items() if t not in OIL_PROXIES}

        # --- Handle commodity allocation ---
        market = self._sensor_readings.get("market", {})
        oil_proxy = market.get("oil_proxy")
        oil_bullish = market.get("oil_bullish", False)

        # Current commodity value
        commodity_value = 0
        for ticker, pos in commodity_positions.items():
            if ticker in price_data and not price_data[ticker].empty:
                df = price_data[ticker]
                mask = df.index <= pd.Timestamp(date)
                if mask.any():
                    commodity_value += pos["shares"] * float(df.loc[mask, "Close"].iloc[-1])

        # Sell commodity if target is 0 or oil bearish
        if commodity_target <= 0 or not oil_bullish:
            for ticker in list(commodity_positions.keys()):
                price = self._get_exec_price(price_data, ticker, date)
                if price:
                    self._sell(ticker, price, date,
                               f"Mix {self.detected_regime}: commodity target={commodity_pct:.0%}, oil bearish")
            commodity_value = 0

        # Buy commodity if target > current and oil bullish
        elif oil_proxy and commodity_target > commodity_value * 1.1:
            need = commodity_target - commodity_value
            price = self._get_exec_price(price_data, oil_proxy, date)
            if price and price > 0 and self.cash > price:
                        buy_amount = min(need, self.cash * 0.9)
                        shares = int(buy_amount / price)
                        if shares > 0:
                            if oil_proxy in self.positions:
                                # Add to existing position — route through _buy for slippage + gap filter
                                # _buy will update shares on existing position
                                old_shares = self.positions[oil_proxy]["shares"]
                                old_entry = self.positions[oil_proxy]["entry_price"]
                                # Temporarily remove to let _buy re-create with combined shares
                                del self.positions[oil_proxy]
                                combined_shares = old_shares + shares
                                self._buy(oil_proxy, combined_shares, price, date,
                                    f"Mix {self.detected_regime}: adding commodity (target={commodity_pct:.0%})",
                                    price_data=price_data)
                                # If _buy succeeded, update entry price to blended avg
                                if oil_proxy in self.positions:
                                    new_entry = (old_entry * old_shares + price * shares) / combined_shares
                                    self.positions[oil_proxy]["entry_price"] = new_entry
                                else:
                                    # _buy was skipped (gap filter etc) — restore original position
                                    self.positions[oil_proxy] = {
                                        "shares": old_shares, "entry_price": old_entry,
                                        "entry_date": date,
                                    }
                            else:
                                self._buy(oil_proxy, shares, price, date,
                                    f"Mix {self.detected_regime}: commodity allocation (target={commodity_pct:.0%})",
                                    price_data=price_data)

        # --- Handle stock allocation ---
        triggered = self._check_watchnotes(price_data, date)
        for alert in triggered:
            if alert["action"] == "consider_sell" and alert["ticker"] in self.positions:
                scores = [(t, s) for t, s in scores if t != alert["ticker"]]

        stock_scores = [(t, s) for t, s in scores
                        if t not in OIL_PROXIES and s >= self.min_score_threshold]

        if stock_pct <= 0:
            target_stock_positions = 0
        else:
            target_stock_positions = max(1, int(self.max_positions * stock_pct))

        top_tickers = [t for t, s in stock_scores[:target_stock_positions]]
        top_scores = {t: s for t, s in stock_scores[:target_stock_positions]}

        prices_on_date = {}
        for ticker in list(stock_positions.keys()) + top_tickers:
            p = self._get_exec_price(price_data, ticker, date)
            if p is not None:
                prices_on_date[ticker] = p

        # Sell stocks not in top picks
        for ticker in list(stock_positions.keys()):
            if ticker not in top_tickers and ticker in prices_on_date:
                old_score = self._last_scores.get(ticker, {})
                reason = f"Mix {self.detected_regime}: dropped from top {target_stock_positions}."
                if top_tickers:
                    reason += f" Replaced by: {', '.join(top_tickers[:3])}"
                self._sell(ticker, prices_on_date[ticker], date, reason, old_score)

        # Buy new stocks
        num_to_buy = target_stock_positions - len([t for t in self.positions if t not in OIL_PROXIES])
        if num_to_buy > 0 and self.cash > 0:
            current_stock_value = sum(
                pos["shares"] * prices_on_date.get(t, 0)
                for t, pos in self.positions.items()
                if t not in OIL_PROXIES and t in prices_on_date
            )
            stock_budget = max(0, stock_target - current_stock_value)
            stock_budget = min(stock_budget, self.cash * 0.95)

            if stock_budget > 0 and num_to_buy > 0:
                per_position = stock_budget / num_to_buy
                for ticker in top_tickers:
                    if ticker not in self.positions and ticker in prices_on_date:
                        price = prices_on_date[ticker]
                        if price <= 0:
                            continue
                        size_mult = self._risk_size_multipliers.get(ticker, 1.0) if hasattr(self, '_risk_size_multipliers') else 1.0
                        adjusted_budget = per_position * size_mult
                        shares = int(adjusted_budget / price)
                        if shares > 0:
                            score_data = self._last_scores.get(ticker, {})
                            reason = (f"Mix {self.detected_regime}: stock alloc "
                                      f"(target={stock_pct:.0%}, score={top_scores.get(ticker, '?')})")
                            if size_mult < 1.0:
                                reason += f" [risk: {size_mult:.0%}]"
                            self._buy(ticker, shares, price, date, reason, score_data,
                                     price_data=price_data)

        # Log
        self._log_reasoning(date, "REGIME", "", 0,
            f"Mix regime: {self.detected_regime} | "
            f"Alloc: stocks={stock_pct:.0%} commodity={commodity_pct:.0%} cash={cash_pct:.0%} | "
            f"Pos: {len([t for t in self.positions if t not in OIL_PROXIES])} stocks + "
            f"{len([t for t in self.positions if t in OIL_PROXIES])} commodity | "
            f"Sensors: def={self._sensor_readings.get('peers', {}).get('defensive_state', '?')}, "
            f"adapt={self._sensor_readings.get('peers', {}).get('adaptive_mode', '?')}, "
            f"comm={'IN' if self._sensor_readings.get('peers', {}).get('commodity_invested') else 'OUT'}")


def _summarize_sensors(readings: dict) -> dict:
    """Create a compact summary of sensor readings for regime history log."""
    summary = {}
    peers = readings.get("peers", {})
    market = readings.get("market", {})

    if peers:
        summary["peer_returns"] = {k: round(v, 1) for k, v in peers.get("strategy_returns", {}).items()}
        summary["defensive_state"] = peers.get("defensive_state")
        summary["adaptive_mode"] = peers.get("adaptive_mode")
        summary["commodity_invested"] = peers.get("commodity_invested")
        summary["cash_heavy_count"] = peers.get("cash_heavy_count")

    if market:
        summary["spy_above_200ma"] = market.get("spy_above_200ma")
        summary["spy_vol"] = round(market.get("spy_vol_20d", 0), 3)
        summary["oil_bullish"] = market.get("oil_bullish")

    return summary

"""Centralized signal computation engine.

THE single place all signals are computed. Both simulation and real-time
use this. It reads data through DataLoader so the source is transparent:
  - Historical: DataLoader reads from pre-downloaded files
  - Real-time: DataLoader calls tools to fetch missing data

Strict temporal gating: at date T, only uses data from dates <= T.
"""

import numpy as np
import pandas as pd
import os
import sys


class SignalEngine:
    """Computes all signals for all tickers on a given date."""

    def __init__(self, price_data: dict, events_calendar: dict, news_base_dir: str = None,
                 data_loader=None):
        self.price_data = price_data
        self.events_calendar = events_calendar
        self.news_base_dir = news_base_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "news"
        )
        self.data_loader = data_loader  # DataLoader instance (if provided)
        self._signal_cache = {}  # {(ticker, date): signals}
        self._news_history = []  # [(date, geo_risk)] for decay calculation

    def compute_all(self, ticker: str, date: str) -> dict:
        """Compute all available signals for a ticker on a date."""
        cache_key = (ticker, date)
        if cache_key in self._signal_cache:
            return self._signal_cache[cache_key]

        signals = {
            "ticker": ticker,
            "date": date,
            "technical": self.compute_technical(ticker, date),
            "valuation": self.compute_valuation_proxy(ticker, date),
            "volume": self.compute_volume_signals(ticker, date),
            "earnings": self.compute_earnings(ticker, date),
        }
        self._signal_cache[cache_key] = signals
        return signals

    def compute_macro(self, date: str) -> dict:
        """Compute market-level signals (not per-ticker)."""
        result = {
            "date": date,
            "regime": "normal",
            "spy_trend": None,
            "volatility": None,
            "sector_rotation": {},
            "news": self.compute_news_with_decay(date),
        }

        if "SPY" not in self.price_data:
            return result

        df = self.price_data["SPY"]
        close = self._get_series(df, date, 252)
        if close is None or len(close) < 50:
            return result

        current = float(close.iloc[-1])
        returns = close.pct_change().dropna()

        # Volatility
        vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0.15
        vol_60d = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d
        result["volatility"] = {"vol_20d": round(vol_20d, 3), "vol_60d": round(vol_60d, 3)}

        # Trend
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
        ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
        ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0
        result["spy_trend"] = {
            "current": round(current, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "above_50": current > sma_50,
            "above_200": current > sma_200,
            "ret_1m": round(ret_1m, 2),
            "ret_3m": round(ret_3m, 2),
        }

        # Regime
        peak_60d = float(close.tail(60).max())
        drawdown = (current - peak_60d) / peak_60d * 100

        if vol_20d > 0.30 and current < sma_50 * 0.97:
            result["regime"] = "crisis"
        elif vol_20d > 0.25:
            result["regime"] = "high_volatility"
        elif current < sma_50 * 0.97:
            result["regime"] = "bearish"
        elif current > sma_50 * 1.03 and current > sma_200:
            result["regime"] = "bullish"
        elif abs(ret_3m) < 5 and vol_20d < 0.18:
            result["regime"] = "sideways"

        # Sector rotation (using sector ETF proxies from our universe)
        sector_map = {
            "XOM": "energy", "CVX": "energy",
            "JPM": "finance", "GS": "finance", "V": "finance",
            "UNH": "healthcare", "JNJ": "healthcare", "LLY": "healthcare",
            "AAPL": "tech", "MSFT": "tech", "NVDA": "tech", "GOOGL": "tech",
            "PG": "consumer", "KO": "consumer", "WMT": "consumer",
            "CAT": "industrial", "BA": "industrial", "HON": "industrial",
        }
        sector_rets = {}
        for sym, sector in sector_map.items():
            s_close = self._get_series(self.price_data.get(sym, pd.DataFrame()), date, 30)
            if s_close is not None and len(s_close) >= 20:
                ret = (float(s_close.iloc[-1]) / float(s_close.iloc[0]) - 1) * 100
                if sector not in sector_rets:
                    sector_rets[sector] = []
                sector_rets[sector].append(ret)

        for sector in sector_rets:
            sector_rets[sector] = round(np.mean(sector_rets[sector]), 2)
        result["sector_rotation"] = sector_rets

        return result

    def compute_technical(self, ticker: str, date: str) -> dict:
        """Full technical analysis for a ticker."""
        df = self.price_data.get(ticker)
        if df is None or df.empty:
            return {}

        close = self._get_series(df, date, 252)
        if close is None or len(close) < 20:
            return {}

        current = float(close.iloc[-1])
        high = self._get_series(df, date, 252, col="High")
        low = self._get_series(df, date, 252, col="Low")
        volume = self._get_series(df, date, 252, col="Volume")

        result = {}

        # Moving averages
        for period in [10, 20, 50, 100, 200]:
            if len(close) >= period:
                result[f"sma_{period}"] = round(float(close.rolling(period).mean().iloc[-1]), 2)

        # EMA
        result["ema_12"] = round(float(close.ewm(span=12).mean().iloc[-1]), 2)
        result["ema_26"] = round(float(close.ewm(span=26).mean().iloc[-1]), 2)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        result["rsi"] = round(float(rsi_series.iloc[-1]), 2) if pd.notna(rsi_series.iloc[-1]) else 50

        # MACD
        macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        macd_signal = macd.ewm(span=9).mean()
        result["macd"] = round(float(macd.iloc[-1]), 4)
        result["macd_signal"] = round(float(macd_signal.iloc[-1]), 4)
        result["macd_bullish"] = result["macd"] > result["macd_signal"]
        # Fresh cross detection
        if len(macd) >= 2:
            prev_diff = float(macd.iloc[-2]) - float(macd_signal.iloc[-2])
            curr_diff = result["macd"] - result["macd_signal"]
            result["macd_cross_up"] = prev_diff < 0 and curr_diff > 0
            result["macd_cross_down"] = prev_diff > 0 and curr_diff < 0

        # Bollinger Bands
        if len(close) >= 20:
            sma_20 = close.rolling(20).mean()
            std_20 = close.rolling(20).std()
            result["bb_upper"] = round(float((sma_20 + 2 * std_20).iloc[-1]), 2)
            result["bb_lower"] = round(float((sma_20 - 2 * std_20).iloc[-1]), 2)

        # ADX (trend strength)
        if high is not None and low is not None and len(high) >= 14:
            try:
                tr = pd.concat([
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()
                ], axis=1).max(axis=1)
                atr = tr.rolling(14).mean()
                result["atr"] = round(float(atr.iloc[-1]), 2) if pd.notna(atr.iloc[-1]) else None
            except Exception:
                pass

        # Returns at various horizons
        for days, label in [(5, "ret_1w"), (21, "ret_1m"), (63, "ret_3m")]:
            if len(close) > days:
                result[label] = round((current / float(close.iloc[-days]) - 1) * 100, 2)

        # Volatility
        returns = close.pct_change().dropna()
        if len(returns) >= 20:
            result["vol_20d"] = round(float(returns.tail(20).std() * np.sqrt(252)), 3)
        if len(returns) >= 60:
            result["vol_60d"] = round(float(returns.tail(60).std() * np.sqrt(252)), 3)

        # Price position
        high_52w = float(close.max())
        low_52w = float(close.min())
        result["pct_from_high"] = round((current - high_52w) / high_52w * 100, 2)
        result["pct_from_low"] = round((current - low_52w) / low_52w * 100, 2)
        result["current_price"] = round(current, 2)

        return result

    def compute_valuation_proxy(self, ticker: str, date: str) -> dict:
        """Price-based valuation proxy (since we can't get historical fundamentals)."""
        df = self.price_data.get(ticker)
        if df is None or df.empty:
            return {}

        close = self._get_series(df, date, 252)
        if close is None or len(close) < 60:
            return {}

        current = float(close.iloc[-1])
        high_52w = float(close.max())
        low_52w = float(close.min())
        returns = close.pct_change().dropna()

        result = {
            "distance_from_high_pct": round((current - high_52w) / high_52w * 100, 2),
            "distance_from_low_pct": round((current - low_52w) / low_52w * 100, 2),
            "price_range_position": round((current - low_52w) / (high_52w - low_52w) * 100, 2) if high_52w != low_52w else 50,
        }

        # Volatility as quality proxy (low vol = more stable = higher quality)
        if len(returns) >= 60:
            vol = float(returns.tail(60).std() * np.sqrt(252))
            result["quality_proxy"] = round(max(0, 10 - vol * 20), 2)

        # Max drawdown as risk proxy
        rolling_max = close.rolling(90, min_periods=1).max()
        drawdown = (close - rolling_max) / rolling_max
        result["max_drawdown_90d"] = round(float(drawdown.min()) * 100, 2)

        return result

    def compute_volume_signals(self, ticker: str, date: str) -> dict:
        """Volume analysis — spikes indicate events even without news."""
        df = self.price_data.get(ticker)
        if df is None or df.empty:
            return {}

        volume = self._get_series(df, date, 60, col="Volume")
        close = self._get_series(df, date, 60)
        if volume is None or close is None or len(volume) < 20:
            return {}

        current_vol = float(volume.iloc[-1])
        avg_vol_20 = float(volume.tail(20).mean())
        avg_vol_5 = float(volume.tail(5).mean())

        result = {
            "current": int(current_vol),
            "avg_20d": int(avg_vol_20),
            "ratio_vs_avg": round(current_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1,
            "trend": "increasing" if avg_vol_5 > avg_vol_20 * 1.2 else
                     "decreasing" if avg_vol_5 < avg_vol_20 * 0.7 else "normal",
        }

        # Detect spike (potential event)
        if avg_vol_20 > 0:
            spike = current_vol / avg_vol_20
            price_move = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
            result["spike"] = spike > 2.0
            result["spike_with_move"] = spike > 2.0 and abs(price_move) > 2
            result["price_move_on_volume"] = round(price_move, 2)

        return result

    def compute_earnings(self, ticker: str, date: str) -> dict:
        """Earnings signal from events calendar."""
        if not self.events_calendar or ticker not in self.events_calendar:
            return {"has_data": False}

        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from events_data import compute_earnings_surprise_signal
            return compute_earnings_surprise_signal(self.events_calendar, ticker, date)
        except Exception:
            return {"has_data": False}

    def compute_news(self, date: str) -> dict:
        """Load geopolitical news signal for a date.

        Uses DataLoader if available (unified path for both sim and real-time).
        Falls back to direct file read if no DataLoader.
        """
        try:
            articles = []

            # Try DataLoader first (the unified path)
            if self.data_loader:
                geo = self.data_loader.get_geopolitical(date)
                if geo.get("has_data"):
                    # Convert DataLoader format to articles list
                    gdelt = geo.get("gdelt") or geo.get("data")
                    wiki = geo.get("wikipedia")
                    if gdelt and isinstance(gdelt, dict):
                        articles = gdelt.get("articles", [])
                    elif wiki and isinstance(wiki, dict):
                        events = wiki.get("events", [])
                        articles = [{"title": e.get("text", ""), "source": "wikipedia",
                                     "query": e.get("category", "")} for e in events]

            # Fallback: direct file read (backward compatible)
            if not articles:
                tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
                sys.path.insert(0, tools_dir)
                from gdelt_backfill import load_gdelt_for_sim, summarize_gdelt
                articles = load_gdelt_for_sim(date, lookback_days=14)

            if not articles:
                return {"has_news": False, "geo_risk": 0}

            # Compute geo_risk from articles (same logic regardless of source)
            tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
            sys.path.insert(0, tools_dir)
            from gdelt_backfill import summarize_gdelt
            summary = summarize_gdelt(articles)
            themes = summary.get("active_themes", [])
            risk = 0.0
            if "war/conflict" in themes: risk += 0.3
            if "sanctions/trade" in themes: risk += 0.2
            if "oil/energy" in themes: risk += 0.15
            if "pandemic" in themes: risk += 0.25
            if "geopolitical_tension" in themes: risk += 0.15
            count = summary.get("article_count", 0)
            if count > 50: risk *= 1.3
            elif count > 20: risk *= 1.1
            return {
                "has_news": True,
                "geo_risk": round(min(1.0, risk), 2),
                "themes": themes,
                "article_count": count,
                "headlines": summary.get("top_headlines", [])[:5],
            }
        except Exception:
            return {"has_news": False, "geo_risk": 0}

    def compute_news_with_decay(self, date: str) -> dict:
        """Compute news signal with time decay.

        Fresh news (today) has full impact. Old news decays:
          Day 0: weight 1.0
          Day 1: weight 0.6
          Day 3: weight 0.2
          Day 7: weight 0.05
        This prevents a one-time news spike from affecting decisions for weeks.
        """
        raw = self.compute_news(date)
        raw_risk = raw.get("geo_risk", 0)

        # Track history for decay
        self._news_history.append((date, raw_risk))
        # Keep only last 14 entries
        self._news_history = self._news_history[-14:]

        # Compute decayed risk: weighted average of recent readings
        if not self._news_history:
            return raw

        from datetime import datetime, timedelta
        current_dt = datetime.strptime(date, "%Y-%m-%d")
        weighted_sum = 0
        weight_sum = 0

        for hist_date, hist_risk in self._news_history:
            try:
                hist_dt = datetime.strptime(hist_date, "%Y-%m-%d")
                days_ago = (current_dt - hist_dt).days
                if days_ago < 0:
                    continue
                # Exponential decay: half-life of 2 days
                decay = 0.5 ** (days_ago / 2.0)
                weighted_sum += hist_risk * decay
                weight_sum += decay
            except Exception:
                continue

        decayed_risk = weighted_sum / weight_sum if weight_sum > 0 else raw_risk

        raw["geo_risk_raw"] = raw_risk  # keep original for logging
        raw["geo_risk"] = round(decayed_risk, 2)  # decayed version used for decisions
        raw["decay_applied"] = True
        return raw

    def compute_fundamentals(self, ticker: str, date: str) -> dict:
        """Load cached fundamental data for a ticker, matched to sim date.

        Uses annual statements for older periods, quarterly for recent.
        """
        import json as _json
        fund_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "data", "fundamentals", f"{ticker}.json")
        if not os.path.exists(fund_path):
            return {"available": False}

        with open(fund_path) as f:
            data = _json.load(f)

        # Find the most recent annual period BEFORE the sim date
        annual_inc = data.get("annual_income", {})
        annual_bal = data.get("annual_balance", {})
        quarterly_inc = data.get("quarterly_income", {})
        quarterly_bal = data.get("quarterly_balance", {})

        # Try quarterly first (more granular), fall back to annual
        usable_income = None
        usable_balance = None

        for periods, inc_data, bal_data in [
            (sorted(quarterly_inc.keys(), reverse=True), quarterly_inc, quarterly_bal),
            (sorted(annual_inc.keys(), reverse=True), annual_inc, annual_bal),
        ]:
            for period_date in periods:
                if period_date <= date:
                    if not usable_income and period_date in inc_data:
                        usable_income = inc_data[period_date]
                    if not usable_balance and period_date in bal_data:
                        usable_balance = bal_data[period_date]
                    if usable_income and usable_balance:
                        break
            if usable_income and usable_balance:
                break

        if not usable_income:
            return {"available": False}

        # Compute quality metrics
        ni = usable_income.get("Net Income")
        rev = usable_income.get("Total Revenue")
        gp = usable_income.get("Gross Profit")
        eq = usable_balance.get("Stockholders Equity") if usable_balance else None
        debt = usable_balance.get("Total Debt") if usable_balance else None
        assets = usable_balance.get("Total Assets") if usable_balance else None

        return {
            "available": True,
            "roe": round(ni / eq * 100, 1) if ni and eq and eq != 0 else None,
            "net_margin": round(ni / rev * 100, 1) if ni and rev and rev != 0 else None,
            "gross_margin": round(gp / rev * 100, 1) if gp and rev and rev != 0 else None,
            "debt_to_equity": round(debt / eq, 2) if debt and eq and eq != 0 else None,
            "roa": round(ni / assets * 100, 1) if ni and assets and assets != 0 else None,
        }

    def _get_series(self, df: pd.DataFrame, date: str, lookback: int, col: str = "Close") -> pd.Series:
        """Get a time series up to date with lookback, strict temporal gating."""
        if df is None or df.empty or col not in df.columns:
            return None
        mask = df.index <= pd.Timestamp(date)
        if not mask.any():
            return None
        return df.loc[mask, col].tail(lookback)

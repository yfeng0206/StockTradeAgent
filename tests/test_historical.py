"""Historical scenario tests.

These tests run the tools against known historical periods and verify
that the data returned would have supported correct analysis.
The goal is NOT to test if Claude would have made the right call,
but to verify the tools provide sufficient signal for good analysis.
"""

import json
import subprocess
import sys
import os
import pytest

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")


def run_tool(script_name: str, args: list = None) -> dict:
    cmd = [sys.executable, os.path.join(TOOLS_DIR, script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=TOOLS_DIR)
    if result.returncode != 0:
        pytest.fail(f"{script_name} failed: {result.stderr}")
    return json.loads(result.stdout)


class TestBacktestScenarios:
    """Run the built-in historical scenarios from backtest.py."""

    def test_scenarios_execute(self):
        """All historical scenarios should run without errors."""
        data = run_tool("backtest.py", ["scenarios"])
        assert data["total_scenarios"] > 0
        assert data["pass_rate_pct"] is not None

    def test_scenarios_have_returns(self):
        """Each scenario should return performance data."""
        data = run_tool("backtest.py", ["scenarios"])
        for result in data["results"]:
            assert "returns_by_horizon" in result or "error" in result

    def test_known_winners_positive(self):
        """Test that known strong buy signals show positive returns."""
        # NVDA in Jan 2023 before AI rally - should be strongly positive at 90 days
        result = run_tool("backtest.py", [
            "eval", "NVDA", "--date", "2023-01-03", "--action", "buy", "--horizon", "90"
        ])
        assert result["final_return_pct"] > 0, \
            f"NVDA Jan 2023 should have been positive, got {result['final_return_pct']}%"

    def test_known_losers_negative(self):
        """Test that known sell signals show negative returns."""
        # TSLA Nov 2021 near ATH - should drop over next 90 days
        result = run_tool("backtest.py", [
            "eval", "TSLA", "--date", "2021-11-01", "--action", "sell", "--horizon", "90"
        ])
        # For a sell recommendation, the stock going down means we were "correct"
        assert result["recommendation_correct"], \
            f"TSLA Nov 2021 sell should have been correct, return was {result['final_return_pct']}%"

    def test_benchmark_alpha_calculation(self):
        """Verify alpha is correctly computed as stock return minus SPY return."""
        result = run_tool("backtest.py", [
            "eval", "AAPL", "--date", "2024-01-02", "--action", "buy", "--horizon", "30"
        ])
        h30 = result["returns_by_horizon"].get("30d")
        if h30 and h30["spy_return_pct"] is not None:
            expected_alpha = round(h30["stock_return_pct"] - h30["spy_return_pct"], 2)
            assert h30["alpha_pct"] == expected_alpha


class TestSingleStockEval:
    """Test single stock evaluation at various horizons."""

    def test_eval_returns_multiple_horizons(self):
        result = run_tool("backtest.py", [
            "eval", "MSFT", "--date", "2024-06-01", "--action", "buy", "--horizon", "60"
        ])
        assert "5d" in result["returns_by_horizon"] or "10d" in result["returns_by_horizon"]

    def test_max_drawdown_is_negative_or_zero(self):
        result = run_tool("backtest.py", [
            "eval", "SPY", "--date", "2024-01-02", "--action", "buy", "--horizon", "30"
        ])
        assert result["max_drawdown_pct"] <= 0


class TestPortfolioBacktest:
    """Test portfolio-level backtesting with a sample recommendation set."""

    @pytest.fixture
    def sample_portfolio_file(self, tmp_path):
        recs = [
            {"ticker": "AAPL", "date": "2024-01-02", "action": "buy", "horizon": 30},
            {"ticker": "MSFT", "date": "2024-01-02", "action": "buy", "horizon": 30},
            {"ticker": "GOOGL", "date": "2024-01-02", "action": "buy", "horizon": 30},
        ]
        filepath = tmp_path / "test_recs.json"
        filepath.write_text(json.dumps(recs))
        return str(filepath)

    def test_portfolio_backtest_runs(self, sample_portfolio_file):
        result = run_tool("backtest.py", ["portfolio", "--file", sample_portfolio_file])
        assert result["total_recommendations"] == 3
        assert result["valid_evaluations"] > 0
        assert "win_rate_pct" in result
        assert "avg_return_pct" in result
        assert "sharpe_ratio_approx" in result

    def test_portfolio_has_individual_results(self, sample_portfolio_file):
        result = run_tool("backtest.py", ["portfolio", "--file", sample_portfolio_file])
        assert len(result["individual_results"]) == 3


class TestToolDataQuality:
    """Verify tools return data consistent with known facts."""

    def test_aapl_is_technology_sector(self):
        data = run_tool("fetch_fundamentals.py", ["AAPL"])
        assert "technology" in data["sector"].lower() or "tech" in data["sector"].lower()

    def test_aapl_market_cap_over_1T(self):
        data = run_tool("fetch_price_data.py", ["AAPL"])
        assert data["market_cap"] > 1_000_000_000_000  # AAPL should be > $1T

    def test_spy_has_no_fundamentals_error(self):
        """SPY is an ETF - fundamentals tool should handle gracefully."""
        data = run_tool("fetch_price_data.py", ["SPY"])
        assert data["current_price"] > 0

    def test_vix_in_macro_is_reasonable(self):
        data = run_tool("macro_data.py")
        vix = data["market_indicators"].get("vix", {}).get("value")
        if vix:
            assert 5 < vix < 90, f"VIX of {vix} seems unreasonable"

    def test_treasury_yield_is_reasonable(self):
        data = run_tool("macro_data.py")
        t10y = data["market_indicators"].get("treasury_10y_yield", {}).get("value")
        if t10y:
            assert 0.5 < t10y < 15, f"10Y yield of {t10y}% seems unreasonable"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

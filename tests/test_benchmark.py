"""Benchmark tests — compare agent-style recommendations against SPY buy-and-hold.

This file provides a framework for tracking real recommendations over time.
After running /stock-research and recording recommendations, add them to
tests/scenarios/recommendations.json and run this to see how they performed.
"""

import json
import subprocess
import sys
import os
from datetime import datetime
import pytest

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")
RECS_FILE = os.path.join(SCENARIOS_DIR, "recommendations.json")


def run_tool(script_name: str, args: list = None) -> dict:
    cmd = [sys.executable, os.path.join(TOOLS_DIR, script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=TOOLS_DIR)
    if result.returncode != 0:
        pytest.fail(f"{script_name} failed: {result.stderr}")
    return json.loads(result.stdout)


class TestBenchmarkComparison:
    """Test the built-in scenario benchmarks against real outcomes."""

    def test_historical_scenarios_beat_random(self):
        """The 'correct' calls in our scenarios should have >50% win rate.
        This validates that the backtest tool correctly identifies good signals."""
        data = run_tool("backtest.py", ["scenarios"])
        assert data["pass_rate_pct"] >= 50, \
            f"Historical scenarios should be correct >50% of the time, got {data['pass_rate_pct']}%"

    def test_buy_recommendations_show_alpha(self):
        """Test that well-known buy opportunities generated alpha vs SPY."""
        # META Nov 2022 — one of the best-known buy opportunities
        result = run_tool("backtest.py", [
            "eval", "META", "--date", "2022-11-01", "--action", "buy", "--horizon", "90"
        ])
        h = result["returns_by_horizon"]
        # Find the largest available horizon
        for key in ["90d", "60d", "30d"]:
            if key in h and h[key]["alpha_pct"] is not None:
                assert h[key]["alpha_pct"] > 0, \
                    f"META Nov 2022 should have alpha > 0, got {h[key]['alpha_pct']}%"
                break


class TestRecommendationTracking:
    """Track real recommendations from the agent over time.

    To use: after running /stock-research, add recommendations to
    tests/scenarios/recommendations.json in this format:
    [
        {
            "ticker": "AAPL",
            "date": "2026-03-24",
            "action": "buy",
            "price": 175.50,
            "horizon": 30,
            "confidence": "high",
            "thesis": "Strong fundamentals, AI catalyst"
        }
    ]
    """

    def test_recommendations_file_format(self):
        """If recommendations.json exists, verify its format."""
        if not os.path.exists(RECS_FILE):
            pytest.skip("No recommendations.json file yet — run /stock-research first")

        with open(RECS_FILE) as f:
            recs = json.load(f)

        assert isinstance(recs, list)
        for rec in recs:
            assert "ticker" in rec, "Each recommendation needs a ticker"
            assert "date" in rec, "Each recommendation needs a date"
            assert "action" in rec, "Each recommendation needs an action"

    def test_track_recommendations_performance(self):
        """Backtest all recorded recommendations."""
        if not os.path.exists(RECS_FILE):
            pytest.skip("No recommendations.json file yet")

        result = run_tool("backtest.py", ["portfolio", "--file", RECS_FILE])

        print("\n" + "=" * 60)
        print("RECOMMENDATION TRACKING REPORT")
        print("=" * 60)
        print(f"Total recommendations: {result['total_recommendations']}")
        print(f"Valid evaluations:     {result['valid_evaluations']}")
        print(f"Win rate:              {result['win_rate_pct']}%")
        print(f"Avg return:            {result['avg_return_pct']}%")
        print(f"Avg alpha vs SPY:      {result['avg_alpha_vs_spy_pct']}%")
        print(f"Sharpe ratio (approx): {result['sharpe_ratio_approx']}")
        print("=" * 60)

        # We want to track, not necessarily pass/fail
        assert result["valid_evaluations"] > 0


# Create a sample recommendations file if it doesn't exist
def create_sample_recommendations():
    """Create a sample recommendations.json for testing."""
    if not os.path.exists(SCENARIOS_DIR):
        os.makedirs(SCENARIOS_DIR)

    sample = [
        {
            "ticker": "AAPL",
            "date": "2024-06-01",
            "action": "buy",
            "price": None,
            "horizon": 60,
            "confidence": "medium",
            "thesis": "Sample test recommendation"
        },
        {
            "ticker": "MSFT",
            "date": "2024-06-01",
            "action": "buy",
            "price": None,
            "horizon": 60,
            "confidence": "medium",
            "thesis": "Sample test recommendation"
        },
    ]

    sample_file = os.path.join(SCENARIOS_DIR, "sample_recommendations.json")
    with open(sample_file, "w") as f:
        json.dump(sample, f, indent=2)
    return sample_file


if __name__ == "__main__":
    # Create sample file for manual testing
    sample = create_sample_recommendations()
    print(f"Sample recommendations written to: {sample}")
    print("\nRunning benchmark tests...")
    pytest.main([__file__, "-v", "--tb=short", "-s"])

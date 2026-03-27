"""Unit tests for all stock research tools.
Verifies each tool returns correctly structured data with valid values."""

import json
import subprocess
import sys
import os
import pytest

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
TEST_TICKER = "AAPL"  # Well-known stock with reliable data


def run_tool(script_name: str, args: list = None) -> dict:
    """Run a tool script and return parsed JSON output."""
    cmd = [sys.executable, os.path.join(TOOLS_DIR, script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=TOOLS_DIR)
    if result.returncode != 0:
        pytest.fail(f"{script_name} failed: {result.stderr}")
    return json.loads(result.stdout)


class TestFetchPriceData:
    def test_returns_valid_json(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER
        assert "error" not in data

    def test_has_current_price(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert data["current_price"] > 0
        assert isinstance(data["current_price"], (int, float))

    def test_has_52w_range(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert data["high_52w"] >= data["low_52w"]
        assert data["current_price"] <= data["high_52w"] * 1.05  # Allow small buffer
        assert data["current_price"] >= data["low_52w"] * 0.95

    def test_has_volume(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert data["volume"] > 0
        assert data["avg_volume_30d"] > 0

    def test_recent_prices_list(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert len(data["recent_prices"]) > 0
        assert "date" in data["recent_prices"][0]
        assert "close" in data["recent_prices"][0]

    def test_market_cap_exists(self):
        data = run_tool("fetch_price_data.py", [TEST_TICKER])
        assert data["market_cap"] is not None
        assert data["market_cap"] > 1_000_000_000  # AAPL > $1B


class TestFetchFundamentals:
    def test_returns_valid_json(self):
        data = run_tool("fetch_fundamentals.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER

    def test_has_key_ratios(self):
        data = run_tool("fetch_fundamentals.py", [TEST_TICKER])
        ratios = data["key_ratios"]
        assert ratios.get("pe_trailing") is not None or ratios.get("pe_forward") is not None
        assert ratios.get("market_cap") is not None

    def test_has_financial_statements(self):
        data = run_tool("fetch_fundamentals.py", [TEST_TICKER])
        assert len(data["income_statement"]) > 0
        assert len(data["balance_sheet"]) > 0
        assert len(data["cash_flow"]) > 0

    def test_revenue_is_positive(self):
        data = run_tool("fetch_fundamentals.py", [TEST_TICKER])
        ratios = data["key_ratios"]
        assert ratios.get("total_revenue") is not None
        assert ratios["total_revenue"] > 0


class TestTechnicalIndicators:
    def test_returns_valid_json(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER

    def test_rsi_in_range(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        rsi = data["momentum"]["rsi_14"]
        assert 0 <= rsi <= 100

    def test_has_moving_averages(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        ma = data["moving_averages"]
        assert ma["sma_50"] is not None
        assert ma["sma_50"] > 0

    def test_has_macd(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        macd = data["macd"]
        assert "macd_line" in macd
        assert "signal" in macd
        assert macd["signal"] in ["Bullish", "Bearish"]

    def test_has_bollinger_bands(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        bb = data["bollinger_bands"]
        assert bb["upper"] > bb["middle"] > bb["lower"]

    def test_technical_score_in_range(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        assert 0 <= data["technical_score"] <= 10

    def test_has_volume_analysis(self):
        data = run_tool("technical_indicators.py", [TEST_TICKER])
        vol = data["volume"]
        assert vol["current_volume"] > 0
        assert vol["volume_signal"] in ["High volume", "Low volume", "Normal volume"]


class TestFetchNews:
    def test_returns_articles(self):
        data = run_tool("fetch_news.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER
        assert data["article_count"] >= 0

    def test_articles_have_titles(self):
        data = run_tool("fetch_news.py", [TEST_TICKER])
        if data["article_count"] > 0:
            assert data["articles"][0].get("title") != ""


class TestEarnings:
    def test_returns_valid_data(self):
        data = run_tool("earnings.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER

    def test_has_eps(self):
        data = run_tool("earnings.py", [TEST_TICKER])
        assert data["eps_trailing"] is not None or data["eps_forward"] is not None

    def test_has_analyst_targets(self):
        data = run_tool("earnings.py", [TEST_TICKER])
        targets = data["analyst_price_target"]
        assert targets["mean"] is not None
        assert targets["mean"] > 0


class TestValuation:
    def test_returns_dcf(self):
        data = run_tool("valuation.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER
        dcf = data["dcf_valuation"]
        if "error" not in dcf:
            assert dcf["intrinsic_value_per_share"] > 0
            assert dcf["margin_of_safety_pct"] is not None

    def test_has_peer_comparison(self):
        data = run_tool("valuation.py", [TEST_TICKER])
        peers = data["peer_comparison"]
        assert peers["sector"] != ""


class TestSentiment:
    def test_returns_valid_data(self):
        data = run_tool("sentiment.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER

    def test_has_analyst_data(self):
        data = run_tool("sentiment.py", [TEST_TICKER])
        analyst = data["analyst_data"]
        assert analyst["recommendation"] != "" or analyst["recommendation_mean"] is not None

    def test_has_price_sentiment(self):
        data = run_tool("sentiment.py", [TEST_TICKER])
        ps = data["price_sentiment"]
        assert ps["returns_3m_pct"] is not None


class TestMacroData:
    def test_returns_market_indicators(self):
        data = run_tool("macro_data.py")
        assert "market_indicators" in data
        assert "sp500" in data["market_indicators"]
        assert data["market_indicators"]["sp500"]["value"] > 0

    def test_has_vix(self):
        data = run_tool("macro_data.py")
        assert "vix" in data["market_indicators"]
        vix = data["market_indicators"]["vix"]["value"]
        assert 5 < vix < 90  # VIX reasonable range

    def test_has_sector_data(self):
        data = run_tool("macro_data.py")
        assert "sector_performance_1mo" in data
        assert len(data["sector_performance_1mo"]) > 0


class TestFetchFilings:
    def test_returns_filings(self):
        data = run_tool("fetch_filings.py", [TEST_TICKER])
        assert data["ticker"] == TEST_TICKER
        assert len(data["recent_filings"]) > 0

    def test_filing_has_required_fields(self):
        data = run_tool("fetch_filings.py", [TEST_TICKER])
        filing = data["recent_filings"][0]
        assert "form" in filing
        assert "date" in filing
        assert "url" in filing

    def test_has_xbrl_data(self):
        data = run_tool("fetch_filings.py", [TEST_TICKER])
        xbrl = data["xbrl_financial_facts"]
        assert len(xbrl) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

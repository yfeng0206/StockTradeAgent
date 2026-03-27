"""Backtesting and evaluation tool.

Supports:
1. Single-stock performance tracking (did a recommendation work?)
2. Portfolio-level backtesting against SPY benchmark
3. Walk-forward signal evaluation
"""

import argparse
import json
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np


def evaluate_recommendation(ticker: str, entry_date: str, entry_price: float = None,
                            recommendation: str = "buy", horizon_days: int = 30) -> dict:
    """Evaluate a single recommendation against actual outcomes."""
    stock = yf.Ticker(ticker)

    start = pd.Timestamp(entry_date)
    end = start + timedelta(days=horizon_days + 10)  # extra buffer for trading days

    hist = stock.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    if hist.empty:
        return {"error": f"No data for {ticker} from {entry_date}"}

    if entry_price is None:
        entry_price = float(hist["Close"].iloc[0])

    # Get SPY for same period as benchmark
    spy = yf.Ticker("SPY")
    spy_hist = spy.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

    # Calculate returns at various horizons
    horizons = [5, 10, 20, 30, 60, 90]
    returns_by_horizon = {}

    for h in horizons:
        if h > len(hist) - 1:
            continue
        stock_ret = (float(hist["Close"].iloc[min(h, len(hist)-1)]) - entry_price) / entry_price * 100
        spy_ret = None
        if not spy_hist.empty and len(spy_hist) > min(h, len(spy_hist)-1):
            spy_entry = float(spy_hist["Close"].iloc[0])
            spy_ret = (float(spy_hist["Close"].iloc[min(h, len(spy_hist)-1)]) - spy_entry) / spy_entry * 100

        returns_by_horizon[f"{h}d"] = {
            "stock_return_pct": round(stock_ret, 2),
            "spy_return_pct": round(spy_ret, 2) if spy_ret is not None else None,
            "alpha_pct": round(stock_ret - spy_ret, 2) if spy_ret is not None else None,
        }

    # Max drawdown during the period
    prices = hist["Close"].values[:min(horizon_days, len(hist))]
    peak = np.maximum.accumulate(prices)
    drawdown = (prices - peak) / peak * 100
    max_drawdown = float(np.min(drawdown))

    # Was the recommendation correct?
    final_idx = min(horizon_days, len(hist) - 1)
    final_return = (float(hist["Close"].iloc[final_idx]) - entry_price) / entry_price * 100
    is_buy = recommendation.lower() in ["buy", "strong buy"]
    correct = (is_buy and final_return > 0) or (not is_buy and final_return <= 0)

    result = {
        "ticker": ticker,
        "recommendation": recommendation,
        "entry_date": entry_date,
        "entry_price": round(entry_price, 2),
        "horizon_days": horizon_days,
        "returns_by_horizon": returns_by_horizon,
        "max_drawdown_pct": round(max_drawdown, 2),
        "recommendation_correct": correct,
        "final_return_pct": round(final_return, 2),
    }
    return result


def backtest_portfolio(recommendations: list) -> dict:
    """Backtest a list of recommendations.

    Each recommendation: {"ticker": "AAPL", "date": "2025-01-15", "action": "buy", "price": 230.0}
    """
    results = []
    total_return = 0
    total_alpha = 0
    correct = 0

    for rec in recommendations:
        eval_result = evaluate_recommendation(
            ticker=rec["ticker"],
            entry_date=rec["date"],
            entry_price=rec.get("price"),
            recommendation=rec.get("action", "buy"),
            horizon_days=rec.get("horizon", 30),
        )
        results.append(eval_result)

        if "error" not in eval_result:
            total_return += eval_result["final_return_pct"]
            if eval_result["recommendation_correct"]:
                correct += 1
            # Get 30d alpha if available
            h30 = eval_result["returns_by_horizon"].get("30d", {})
            if h30.get("alpha_pct") is not None:
                total_alpha += h30["alpha_pct"]

    n = len(results)
    valid = [r for r in results if "error" not in r]
    n_valid = len(valid)

    # Calculate portfolio-level metrics
    returns_series = [r["final_return_pct"] for r in valid]
    avg_return = np.mean(returns_series) if returns_series else 0
    std_return = np.std(returns_series) if len(returns_series) > 1 else 0
    sharpe = (avg_return / std_return) if std_return > 0 else 0
    win_rate = correct / n_valid * 100 if n_valid > 0 else 0

    portfolio_summary = {
        "total_recommendations": n,
        "valid_evaluations": n_valid,
        "win_rate_pct": round(win_rate, 1),
        "avg_return_pct": round(avg_return, 2),
        "total_return_pct": round(total_return, 2),
        "avg_alpha_vs_spy_pct": round(total_alpha / n_valid, 2) if n_valid > 0 else 0,
        "sharpe_ratio_approx": round(sharpe, 2),
        "max_drawdown_worst": round(min(r["max_drawdown_pct"] for r in valid), 2) if valid else None,
        "individual_results": results,
    }
    return portfolio_summary


def run_historical_scenarios() -> dict:
    """Run pre-defined historical test scenarios to validate analysis quality.

    Tests against known market events where the 'right answer' is known in hindsight.
    """
    scenarios = [
        {
            "name": "NVDA pre-AI rally (Jan 2023)",
            "ticker": "NVDA",
            "date": "2023-01-03",
            "expected_direction": "buy",
            "horizon": 90,
            "context": "ChatGPT launched Nov 2022, AI demand for GPUs was emerging",
        },
        {
            "name": "META recovery (Nov 2022)",
            "ticker": "META",
            "date": "2022-11-01",
            "expected_direction": "buy",
            "horizon": 90,
            "context": "META at lows after metaverse spending backlash, about to cut costs",
        },
        {
            "name": "SPY post-COVID recovery (Apr 2020)",
            "ticker": "SPY",
            "date": "2020-04-01",
            "expected_direction": "buy",
            "horizon": 90,
            "context": "Markets bottomed Mar 23 2020, Fed stimulus announced",
        },
        {
            "name": "TSLA peak (Nov 2021)",
            "ticker": "TSLA",
            "date": "2021-11-01",
            "expected_direction": "sell",
            "horizon": 90,
            "context": "TSLA near ATH, extreme valuations, rate hikes coming",
        },
        {
            "name": "Banks pre-SVB crisis (Feb 2023)",
            "ticker": "KRE",
            "date": "2023-02-01",
            "expected_direction": "sell",
            "horizon": 60,
            "context": "Regional banks had unrealized bond losses, deposit risk building",
        },
    ]

    results = []
    for scenario in scenarios:
        eval_result = evaluate_recommendation(
            ticker=scenario["ticker"],
            entry_date=scenario["date"],
            recommendation=scenario["expected_direction"],
            horizon_days=scenario["horizon"],
        )
        eval_result["scenario_name"] = scenario["name"]
        eval_result["context"] = scenario["context"]
        eval_result["expected_direction"] = scenario["expected_direction"]
        results.append(eval_result)

    passed = sum(1 for r in results if r.get("recommendation_correct"))
    return {
        "total_scenarios": len(scenarios),
        "passed": passed,
        "pass_rate_pct": round(passed / len(scenarios) * 100, 1),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest stock recommendations")
    subparsers = parser.add_subparsers(dest="command")

    # Single recommendation eval
    single = subparsers.add_parser("eval", help="Evaluate a single recommendation")
    single.add_argument("ticker", help="Stock ticker")
    single.add_argument("--date", required=True, help="Entry date (YYYY-MM-DD)")
    single.add_argument("--price", type=float, default=None, help="Entry price")
    single.add_argument("--action", default="buy", help="Recommendation (buy/sell)")
    single.add_argument("--horizon", type=int, default=30, help="Days to evaluate")

    # Portfolio backtest
    portfolio = subparsers.add_parser("portfolio", help="Backtest a portfolio of recommendations")
    portfolio.add_argument("--file", required=True, help="JSON file with recommendations")

    # Historical scenarios
    subparsers.add_parser("scenarios", help="Run historical test scenarios")

    args = parser.parse_args()

    if args.command == "eval":
        result = evaluate_recommendation(args.ticker.upper(), args.date, args.price, args.action, args.horizon)
    elif args.command == "portfolio":
        with open(args.file) as f:
            recs = json.load(f)
        result = backtest_portfolio(recs)
    elif args.command == "scenarios":
        result = run_historical_scenarios()
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

"""Full parameter sweep: 7 periods × 3 position sizes × 3 cash amounts = 63 runs.

Each run uses the daily event-driven engine with all 7 strategies.
Results saved to runs/ and a master comparison CSV for analysis.

Usage:
    python eval/run_full_sweep.py              # Full sweep (63 runs, ~25 min)
    python eval/run_full_sweep.py --quick      # Quick test (7 runs, ~4 min, mp=10 cash=100k only)
    python eval/run_full_sweep.py --period recession --max-positions 10  # Single combo
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import run_daily_simulation, UNIVERSE, BENCHMARKS, MACRO_ETFS, download_data
from events_data import build_events_calendar

SWEEP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")

PERIODS = {
    "recession":         {"start": "2022-01-03", "end": "2022-10-31", "name": "2022 Bear Market"},
    "normal":            {"start": "2019-01-02", "end": "2019-12-31", "name": "2019 Steady Bull"},
    "black_swan":        {"start": "2020-01-02", "end": "2020-06-30", "name": "COVID Crash"},
    "bull":              {"start": "2023-01-02", "end": "2023-12-29", "name": "2023 AI Rally"},
    "bull_to_recession": {"start": "2021-07-01", "end": "2022-06-30", "name": "Bull to Recession"},
    "recession_to_bull": {"start": "2022-10-01", "end": "2023-06-30", "name": "Recession to Bull"},
    "2025_to_now":       {"start": "2025-01-02", "end": "2026-03-24", "name": "2025 to Now"},
}

MAX_POSITIONS = [10, 20, 30]
CASH_AMOUNTS = [10_000, 50_000, 100_000]


def run_sweep(periods=None, positions=None, cash_amounts=None):
    """Run the full parameter sweep."""
    if periods is None:
        periods = list(PERIODS.keys())
    if positions is None:
        positions = MAX_POSITIONS
    if cash_amounts is None:
        cash_amounts = CASH_AMOUNTS

    total = len(periods) * len(positions) * len(cash_amounts)
    print("=" * 80)
    print(f"FULL PARAMETER SWEEP")
    print(f"Periods: {len(periods)} | Position sizes: {positions} | Cash: {cash_amounts}")
    print(f"Total runs: {total}")
    print("=" * 80)

    # Build events calendar ONCE
    print("\nBuilding shared events calendar...")
    events_cal = build_events_calendar(UNIVERSE, cache=True)
    print(f"Calendar: {len(events_cal)} tickers\n")

    # Track all results for master comparison
    all_results = []
    run_count = 0
    start_time = time.time()

    for period_key in periods:
        p = PERIODS[period_key]

        # Download data ONCE per period
        print(f"\n{'#' * 80}")
        print(f"# PERIOD: {p['name']} ({p['start']} to {p['end']})")
        print(f"{'#' * 80}")

        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        print(f"Downloading data for {len(all_tickers)} tickers...")
        price_data = download_data(all_tickers, p["start"], p["end"])
        print(f"Got {len(price_data)} tickers\n")

        for mp in positions:
            for cash in cash_amounts:
                run_count += 1
                elapsed = time.time() - start_time
                est_remaining = (elapsed / run_count * (total - run_count)) if run_count > 0 else 0

                print(f"  [{run_count}/{total}] period={period_key} mp={mp} cash=${cash:,} "
                      f"(~{est_remaining/60:.0f}m remaining)...", end=" ", flush=True)

                try:
                    results = run_daily_simulation(
                        start=p["start"], end=p["end"],
                        initial_cash=cash, max_positions=mp,
                        period_name=p["name"],
                        shared_price_data=price_data,
                        shared_events_cal=events_cal,
                        quiet=True,
                        realistic=True,
                        slippage=0.0005,
                        exec_model="premarket",
                    )

                    # Collect summary for master comparison
                    for strat_name, strat_data in results.get("strategies", {}).items():
                        spy_ret = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
                        all_results.append({
                            "period": period_key,
                            "period_name": p["name"],
                            "max_positions": mp,
                            "cash": cash,
                            "strategy": strat_name,
                            "return_pct": strat_data.get("total_return_pct", 0),
                            "alpha_vs_spy": strat_data.get("alpha_vs_spy", 0),
                            "sharpe": strat_data.get("sharpe_ratio", 0),
                            "max_drawdown": strat_data.get("max_drawdown_pct", 0),
                            "win_rate": strat_data.get("win_rate_pct", 0),
                            "trades": strat_data.get("total_trades", 0),
                            "spy_return": spy_ret,
                            "exec_model": "premarket",
                            "slippage": 0.0005,
                        })

                    print("done")
                except Exception as e:
                    print(f"ERROR: {e}")
                    continue

    # Save master comparison CSV
    csv_path = os.path.join(SWEEP_DIR, f"sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    if all_results:
        keys = all_results[0].keys()
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\nMaster comparison saved to: {csv_path}")

    # Save JSON too
    json_path = csv_path.replace(".csv", ".json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Print summary tables
    print_summary(all_results)

    total_time = time.time() - start_time
    print(f"\nTotal time: {total_time/60:.1f} minutes for {run_count} runs")


def print_summary(results):
    """Print summary comparison tables."""
    if not results:
        return

    strategies = sorted(set(r["strategy"] for r in results))

    # Table 1: Average return by strategy across all configs
    print(f"\n{'=' * 90}")
    print("AVERAGE RETURN BY STRATEGY (across all periods, positions, cash amounts)")
    print(f"{'=' * 90}")
    print(f"{'Strategy':<14} {'Avg Return':>12} {'Avg Alpha':>12} {'Avg Sharpe':>12} {'Avg MaxDD':>12} {'Avg WinRate':>12}")
    print("-" * 74)

    strat_avgs = {}
    for s in strategies:
        s_results = [r for r in results if r["strategy"] == s]
        if not s_results:
            continue
        avg_ret = np.mean([r["return_pct"] for r in s_results])
        avg_alpha = np.mean([r["alpha_vs_spy"] for r in s_results])
        avg_sharpe = np.mean([r["sharpe"] for r in s_results])
        avg_dd = np.mean([r["max_drawdown"] for r in s_results])
        avg_wr = np.mean([r["win_rate"] for r in s_results])
        strat_avgs[s] = avg_ret
        print(f"{s:<14} {avg_ret:>11.1f}% {avg_alpha:>11.1f}% {avg_sharpe:>12.3f} {avg_dd:>11.1f}% {avg_wr:>11.1f}%")

    # Table 2: Best strategy per period
    print(f"\n{'=' * 90}")
    print("BEST STRATEGY PER PERIOD (across all position sizes and cash amounts)")
    print(f"{'=' * 90}")

    periods_seen = sorted(set(r["period"] for r in results))
    for pk in periods_seen:
        p_results = [r for r in results if r["period"] == pk]
        by_strat = {}
        for r in p_results:
            s = r["strategy"]
            if s not in by_strat:
                by_strat[s] = []
            by_strat[s].append(r["return_pct"])
        best = max(by_strat.items(), key=lambda x: np.mean(x[1]))
        pname = p_results[0]["period_name"]
        print(f"  {pname:<30} -> {best[0]:>12} (avg {np.mean(best[1]):+.1f}%)")

    # Table 3: Effect of position size
    print(f"\n{'=' * 90}")
    print("EFFECT OF MAX POSITIONS (averaged across periods and cash)")
    print(f"{'=' * 90}")
    print(f"{'Strategy':<14}", end="")
    mp_values = sorted(set(r["max_positions"] for r in results))
    for mp in mp_values:
        print(f"{'MP=' + str(mp):>12}", end="")
    print(f"{'Best':>10}")
    print("-" * (14 + 12 * len(mp_values) + 10))

    for s in strategies:
        print(f"{s:<14}", end="")
        avgs = {}
        for mp in mp_values:
            mp_results = [r for r in results if r["strategy"] == s and r["max_positions"] == mp]
            avg = np.mean([r["return_pct"] for r in mp_results]) if mp_results else 0
            avgs[mp] = avg
            print(f"{avg:>11.1f}%", end="")
        best = max(avgs, key=avgs.get) if avgs else "?"
        print(f"{'MP=' + str(best):>10}")

    # Table 4: Effect of cash amount
    print(f"\n{'=' * 90}")
    print("EFFECT OF STARTING CASH (averaged across periods and positions)")
    print(f"{'=' * 90}")
    print(f"{'Strategy':<14}", end="")
    cash_values = sorted(set(r["cash"] for r in results))
    for c in cash_values:
        print(f"{'$' + str(c//1000) + 'k':>12}", end="")
    print(f"{'Best':>10}")
    print("-" * (14 + 12 * len(cash_values) + 10))

    for s in strategies:
        print(f"{s:<14}", end="")
        avgs = {}
        for c in cash_values:
            c_results = [r for r in results if r["strategy"] == s and r["cash"] == c]
            avg = np.mean([r["return_pct"] for r in c_results]) if c_results else 0
            avgs[c] = avg
            print(f"{avg:>11.1f}%", end="")
        best = max(avgs, key=avgs.get) if avgs else "?"
        print(f"{'$' + str(best//1000) + 'k':>10}")


def main():
    parser = argparse.ArgumentParser(description="Full parameter sweep")
    parser.add_argument("--quick", action="store_true", help="Quick test: 7 periods, mp=10, cash=100k only")
    parser.add_argument("--period", choices=list(PERIODS.keys()), help="Single period")
    parser.add_argument("--max-positions", type=int, help="Single position size")
    parser.add_argument("--cash", type=int, help="Single cash amount")
    args = parser.parse_args()

    if args.quick:
        run_sweep(positions=[10], cash_amounts=[100_000])
    elif args.period or args.max_positions or args.cash:
        periods = [args.period] if args.period else None
        positions = [args.max_positions] if args.max_positions else None
        cash = [args.cash] if args.cash else None
        run_sweep(periods, positions, cash)
    else:
        run_sweep()


if __name__ == "__main__":
    main()

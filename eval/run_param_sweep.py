"""Parameter sweep: find optimal settings for each strategy.

Tests: rebalance frequency × exec model × position size × period
All with realistic=True, slippage=5bps.

Usage:
    python eval/run_param_sweep.py                # Full sweep
    python eval/run_param_sweep.py --quick        # Quick (3 periods, mp=10 only)
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from copy import deepcopy

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import run_daily_simulation, UNIVERSE, BENCHMARKS, MACRO_ETFS, download_data
from events_data import build_events_calendar

SWEEP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")

PERIODS = {
    "normal":            {"start": "2019-01-02", "end": "2019-12-31", "name": "2019 Steady Bull"},
    "black_swan":        {"start": "2020-01-02", "end": "2020-06-30", "name": "COVID Crash"},
    "recession":         {"start": "2022-01-03", "end": "2022-10-31", "name": "2022 Bear Market"},
    "bull":              {"start": "2023-01-02", "end": "2023-12-29", "name": "2023 AI Rally"},
    "recession_to_bull": {"start": "2022-10-01", "end": "2023-06-30", "name": "Recession to Bull"},
    "bull_to_recession": {"start": "2021-07-01", "end": "2022-06-30", "name": "Bull to Recession"},
    "2025_to_now":       {"start": "2025-01-02", "end": "2026-03-24", "name": "2025 Full Year"},
}

# Parameters to sweep
FREQUENCIES = ["weekly", "biweekly", "monthly"]
EXEC_MODELS = ["open", "premarket"]
MAX_POSITIONS = [10, 20]

STRATEGIES = ["Value", "Momentum", "Balanced", "Defensive", "EventDriven",
              "Adaptive", "Commodity", "Mix", "MixLLM"]


def override_frequency(freq):
    """Monkey-patch all strategies to use a given rebalance frequency."""
    from strategies.base_strategy import BaseStrategy
    from strategies.value_strategy import ValueStrategy
    from strategies.momentum_strategy import MomentumStrategy
    from strategies.balanced_strategy import BalancedStrategy
    from strategies.defensive_strategy import DefensiveStrategy
    from strategies.event_driven_strategy import EventDrivenStrategy
    from strategies.adaptive_strategy import AdaptiveStrategy
    from strategies.commodity_strategy import CommodityStrategy
    from strategies.mix_strategy import MixStrategy

    # Store originals
    originals = {}
    for cls in [ValueStrategy, MomentumStrategy, BalancedStrategy, DefensiveStrategy,
                EventDrivenStrategy, AdaptiveStrategy, CommodityStrategy, MixStrategy]:
        originals[cls.__name__] = cls.rebalance_frequency.fget

    # Override
    for cls in [ValueStrategy, MomentumStrategy, BalancedStrategy, DefensiveStrategy,
                EventDrivenStrategy, AdaptiveStrategy, CommodityStrategy, MixStrategy]:
        cls.rebalance_frequency = property(lambda self, f=freq: f)

    return originals


def restore_frequency(originals):
    """Restore original rebalance frequencies."""
    from strategies.value_strategy import ValueStrategy
    from strategies.momentum_strategy import MomentumStrategy
    from strategies.balanced_strategy import BalancedStrategy
    from strategies.defensive_strategy import DefensiveStrategy
    from strategies.event_driven_strategy import EventDrivenStrategy
    from strategies.adaptive_strategy import AdaptiveStrategy
    from strategies.commodity_strategy import CommodityStrategy
    from strategies.mix_strategy import MixStrategy

    cls_map = {
        "ValueStrategy": ValueStrategy,
        "MomentumStrategy": MomentumStrategy,
        "BalancedStrategy": BalancedStrategy,
        "DefensiveStrategy": DefensiveStrategy,
        "EventDrivenStrategy": EventDrivenStrategy,
        "AdaptiveStrategy": AdaptiveStrategy,
        "CommodityStrategy": CommodityStrategy,
        "MixStrategy": MixStrategy,
    }
    for name, fget in originals.items():
        if name in cls_map:
            cls_map[name].rebalance_frequency = property(fget)


def run_sweep(periods=None, positions=None, exec_models=None, frequencies=None, quick=False):
    """Run the parameter sweep."""
    if periods is None:
        periods = list(PERIODS.keys())
    if positions is None:
        positions = [10] if quick else MAX_POSITIONS
    if exec_models is None:
        exec_models = ["premarket"] if quick else EXEC_MODELS
    if frequencies is None:
        frequencies = FREQUENCIES

    total = len(periods) * len(positions) * len(exec_models) * len(frequencies)
    print("=" * 80)
    print(f"PARAMETER SWEEP — Finding Best Defaults")
    print(f"Periods: {len(periods)} | Positions: {positions} | "
          f"Exec: {exec_models} | Freq: {frequencies}")
    print(f"Total runs: {total}")
    print(f"All runs: realistic=True, slippage=5bps")
    print("=" * 80)

    # Build events calendar ONCE
    print("\nBuilding shared events calendar...")
    events_cal = build_events_calendar(UNIVERSE, cache=True)

    all_results = []
    run_count = 0
    start_time = time.time()

    for period_key in periods:
        p = PERIODS[period_key]
        print(f"\n{'#' * 60}")
        print(f"# PERIOD: {p['name']} ({p['start']} to {p['end']})")
        print(f"{'#' * 60}")

        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        print(f"Downloading data for {len(all_tickers)} tickers...")
        price_data = download_data(all_tickers, p["start"], p["end"])
        print(f"Got {len(price_data)} tickers\n")

        for mp in positions:
            for exec_model in exec_models:
                for freq in frequencies:
                    run_count += 1
                    elapsed = time.time() - start_time
                    rate = elapsed / run_count if run_count > 0 else 60
                    remaining = rate * (total - run_count)

                    label = f"mp={mp} exec={exec_model} freq={freq}"
                    print(f"  [{run_count}/{total}] {label} "
                          f"(~{remaining/60:.0f}m left)...", end=" ", flush=True)

                    # Override frequency
                    originals = override_frequency(freq)

                    try:
                        results = run_daily_simulation(
                            start=p["start"], end=p["end"],
                            initial_cash=100_000, max_positions=mp,
                            period_name=p["name"],
                            shared_price_data=price_data,
                            shared_events_cal=events_cal,
                            quiet=True,
                            realistic=True,
                            slippage=0.0005,
                            exec_model=exec_model,
                        )

                        spy_ret = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)

                        for strat_name, strat_data in results.get("strategies", {}).items():
                            all_results.append({
                                "period": period_key,
                                "period_name": p["name"],
                                "max_positions": mp,
                                "exec_model": exec_model,
                                "frequency": freq,
                                "strategy": strat_name,
                                "return_pct": strat_data.get("total_return_pct", 0),
                                "alpha_vs_spy": strat_data.get("alpha_vs_spy", 0),
                                "sharpe": strat_data.get("sharpe_ratio", 0),
                                "max_drawdown": strat_data.get("max_drawdown_pct", 0),
                                "win_rate": strat_data.get("win_rate_pct", 0),
                                "trades": strat_data.get("total_trades", 0),
                                "spy_return": spy_ret,
                            })
                        print("done")

                    except Exception as e:
                        print(f"ERROR: {e}")
                    finally:
                        restore_frequency(originals)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(SWEEP_DIR, f"param_sweep_{timestamp}.csv")
    json_path = csv_path.replace(".csv", ".json")

    if all_results:
        keys = all_results[0].keys()
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_results)

        with open(json_path, "w") as f:
            json.dump(all_results, f, indent=2)

        print(f"\nResults saved to: {csv_path}")

    # === ANALYSIS ===
    analyze_results(all_results)

    return all_results


def analyze_results(all_results):
    """Find the best parameters for each strategy and overall."""
    if not all_results:
        return

    df = pd.DataFrame(all_results)

    print("\n" + "=" * 80)
    print("ANALYSIS: Best Parameters Per Strategy")
    print("=" * 80)

    # For each strategy, find best combo across all periods
    for strat in STRATEGIES:
        sdf = df[df["strategy"] == strat]
        if sdf.empty:
            continue

        # Group by parameter combo, average across periods
        grouped = sdf.groupby(["exec_model", "frequency", "max_positions"]).agg({
            "return_pct": "mean",
            "alpha_vs_spy": "mean",
            "sharpe": "mean",
            "max_drawdown": "mean",
            "trades": "mean",
        }).reset_index()

        # Sort by Sharpe (risk-adjusted), then by return
        grouped = grouped.sort_values(["sharpe", "return_pct"], ascending=[False, False])
        best = grouped.iloc[0]
        worst = grouped.iloc[-1]

        print(f"\n--- {strat} ---")
        print(f"  BEST:  exec={best['exec_model']}, freq={best['frequency']}, mp={int(best['max_positions'])}")
        print(f"         Avg return={best['return_pct']:.1f}%, Sharpe={best['sharpe']:.3f}, "
              f"MaxDD={best['max_drawdown']:.1f}%, Trades={best['trades']:.0f}")
        print(f"  WORST: exec={worst['exec_model']}, freq={worst['frequency']}, mp={int(worst['max_positions'])}")
        print(f"         Avg return={worst['return_pct']:.1f}%, Sharpe={worst['sharpe']:.3f}")

        # Show top 3
        print(f"  Top 3 combos (by Sharpe):")
        for i, (_, row) in enumerate(grouped.head(3).iterrows()):
            print(f"    {i+1}. exec={row['exec_model']}, freq={row['frequency']}, "
                  f"mp={int(row['max_positions'])} -> "
                  f"ret={row['return_pct']:.1f}%, Sharpe={row['sharpe']:.3f}")

    # === Overall best default ===
    print("\n" + "=" * 80)
    print("RECOMMENDED DEFAULTS (for new users)")
    print("=" * 80)

    # Find the single best parameter combo across top strategies
    top_strats = ["EventDriven", "Balanced", "Momentum", "Adaptive", "Mix"]
    tdf = df[df["strategy"].isin(top_strats)]

    overall = tdf.groupby(["exec_model", "frequency", "max_positions"]).agg({
        "return_pct": "mean",
        "sharpe": "mean",
        "alpha_vs_spy": "mean",
        "max_drawdown": "mean",
    }).reset_index()
    overall = overall.sort_values("sharpe", ascending=False)

    print("\nBest overall parameter combo (avg across top 5 strategies, all periods):")
    for i, (_, row) in enumerate(overall.head(5).iterrows()):
        marker = " <<<" if i == 0 else ""
        print(f"  {i+1}. exec={row['exec_model']}, freq={row['frequency']}, "
              f"mp={int(row['max_positions'])} -> "
              f"ret={row['return_pct']:.1f}%, Sharpe={row['sharpe']:.3f}, "
              f"alpha={row['alpha_vs_spy']:.1f}%{marker}")

    # Best single strategy + params for "just run it"
    all_combos = df.groupby(["strategy", "exec_model", "frequency", "max_positions"]).agg({
        "return_pct": "mean",
        "sharpe": "mean",
        "alpha_vs_spy": "mean",
        "max_drawdown": "mean",
    }).reset_index()
    all_combos = all_combos.sort_values("sharpe", ascending=False)

    print("\nSingle best strategy + params ('just run it' mode):")
    for i, (_, row) in enumerate(all_combos.head(5).iterrows()):
        marker = " <<< RECOMMENDED" if i == 0 else ""
        print(f"  {i+1}. {row['strategy']} exec={row['exec_model']}, freq={row['frequency']}, "
              f"mp={int(row['max_positions'])} -> "
              f"ret={row['return_pct']:.1f}%, Sharpe={row['sharpe']:.3f}, "
              f"MaxDD={row['max_drawdown']:.1f}%{marker}")


def main():
    parser = argparse.ArgumentParser(description="Parameter sweep for best defaults")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 3 periods, premarket only, mp=10 only")
    parser.add_argument("--periods", nargs="+", choices=list(PERIODS.keys()),
                        help="Specific periods to test")
    args = parser.parse_args()

    if args.quick:
        periods = ["black_swan", "recession", "bull"]
        run_sweep(periods=periods, quick=True)
    elif args.periods:
        run_sweep(periods=args.periods)
    else:
        run_sweep()


if __name__ == "__main__":
    main()

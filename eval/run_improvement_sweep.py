"""Ablation sweep for 3 improvement features.

Tests all 8 combinations (2^3) of:
  - Chandelier Exit trailing stop
  - Cooldown timer + minimum holding period
  - Breadth + HYG recovery signal

Across 7 periods, all 9 strategies, premarket exec, biweekly, mp=10.

Usage:
    python eval/run_improvement_sweep.py              # Full sweep (56 runs)
    python eval/run_improvement_sweep.py --quick      # 3 key periods (24 runs)
    python eval/run_improvement_sweep.py --parallel 3  # 3 parallel processes
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from itertools import product

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import run_daily_simulation, UNIVERSE, BENCHMARKS, MACRO_ETFS, download_data, PERIODS
from events_data import build_events_calendar

SWEEP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs")

SWEEP_PERIODS = {
    "normal":            PERIODS["normal"],
    "black_swan":        PERIODS["black_swan"],
    "recession":         PERIODS["recession"],
    "bull":              PERIODS["bull"],
    "recession_to_bull": PERIODS["recession_to_bull"],
    "bull_to_recession": PERIODS["bull_to_recession"],
    "2025_to_now":       PERIODS["2025_to_now"],
}

QUICK_PERIODS = {
    "black_swan":        PERIODS["black_swan"],
    "recession":         PERIODS["recession"],
    "bull":              PERIODS["bull"],
}

# All 8 combinations of 3 boolean flags
FEATURE_COMBOS = list(product([False, True], repeat=3))
FEATURE_NAMES = ["chandelier", "cooldown", "breadth"]

STRATEGIES = ["Value", "Momentum", "Balanced", "Defensive", "EventDriven",
              "Adaptive", "Commodity", "Mix", "MixLLM"]


def run_with_features(start, end, period_name, chandelier, cooldown, breadth,
                      shared_price_data=None, shared_events_cal=None):
    """Run simulation with specific improvement features toggled."""
    results = run_daily_simulation(
        start=start, end=end,
        initial_cash=100_000, max_positions=10,
        period_name=period_name,
        shared_price_data=shared_price_data,
        shared_events_cal=shared_events_cal,
        quiet=True,
        realistic=True, slippage=0.0005, exec_model="premarket",
        frequency="biweekly", regime_stickiness=1,
    )

    # Apply feature flags post-hoc is not possible — we need to apply them BEFORE simulation.
    # The flags are set on strategy/trigger objects inside run_daily_simulation.
    # We need to pass them through. For now, use monkey-patching approach.
    return results


def run_sweep(periods=None, quick=False):
    """Run the full ablation sweep."""
    if periods is None:
        periods = QUICK_PERIODS if quick else SWEEP_PERIODS

    combos = FEATURE_COMBOS
    total = len(periods) * len(combos)
    print("=" * 80)
    print("IMPROVEMENT ABLATION SWEEP")
    print(f"Features: {FEATURE_NAMES}")
    print(f"Combos: {len(combos)} (all 2^3 combinations)")
    print(f"Periods: {len(periods)} | Total runs: {total}")
    print("=" * 80)

    events_cal = build_events_calendar(UNIVERSE, cache=True)
    all_results = []
    run_count = 0
    start_time = time.time()

    for period_key, p in periods.items():
        print(f"\n# PERIOD: {p['name']}")
        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        price_data = download_data(all_tickers, p["start"], p["end"])
        print(f"  Got {len(price_data)} tickers")

        for combo in combos:
            chandelier, cooldown, breadth = combo
            run_count += 1
            elapsed = time.time() - start_time
            rate = elapsed / run_count if run_count > 0 else 60
            remaining = rate * (total - run_count)
            label = f"ch={'Y' if chandelier else 'N'} cd={'Y' if cooldown else 'N'} br={'Y' if breadth else 'N'}"
            print(f"  [{run_count}/{total}] {label} (~{remaining/60:.0f}m left)...", end=" ", flush=True)

            try:
                # Monkey-patch the feature flags before running
                import strategies.base_strategy as bs_mod
                import triggers as trig_mod

                # Save originals
                orig_chandelier = getattr(trig_mod.TriggerEngine, '_default_chandelier', False)

                # We need to hook into run_daily_simulation to set flags on created objects.
                # The cleanest way: temporarily modify the defaults in the class.
                # TriggerEngine.use_chandelier_stop is set in __init__
                old_trig_init = trig_mod.TriggerEngine.__init__

                def patched_trig_init(self, signals, atr_mult=2.0):
                    old_trig_init(self, signals, atr_mult)
                    self.use_chandelier_stop = chandelier

                trig_mod.TriggerEngine.__init__ = patched_trig_init

                # BaseStrategy.use_cooldown and use_breadth_signal
                old_bs_init = bs_mod.BaseStrategy.__init__

                def patched_bs_init(self, name, initial_cash=100_000, max_positions=5):
                    old_bs_init(self, name, initial_cash, max_positions)
                    self.use_cooldown = cooldown

                bs_mod.BaseStrategy.__init__ = patched_bs_init

                # MixStrategy.use_breadth_signal
                from strategies.mix_strategy import MixStrategy
                old_mix_init = MixStrategy.__init__

                def patched_mix_init(self, *args, **kwargs):
                    old_mix_init(self, *args, **kwargs)
                    self.use_breadth_signal = breadth

                MixStrategy.__init__ = patched_mix_init

                results = run_daily_simulation(
                    start=p["start"], end=p["end"],
                    initial_cash=100_000, max_positions=10,
                    period_name=p["name"],
                    shared_price_data=price_data,
                    shared_events_cal=events_cal,
                    quiet=True,
                    realistic=True, slippage=0.0005, exec_model="premarket",
                    frequency="biweekly", regime_stickiness=1,
                )

                # Restore
                trig_mod.TriggerEngine.__init__ = old_trig_init
                bs_mod.BaseStrategy.__init__ = old_bs_init
                MixStrategy.__init__ = old_mix_init

                spy_ret = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
                for sname, sdata in results.get("strategies", {}).items():
                    all_results.append({
                        "period": p["name"],
                        "chandelier": chandelier,
                        "cooldown": cooldown,
                        "breadth": breadth,
                        "combo": label,
                        "strategy": sname,
                        "return_pct": sdata.get("total_return_pct", 0),
                        "sharpe": sdata.get("sharpe_ratio", 0),
                        "max_drawdown": sdata.get("max_drawdown_pct", 0),
                        "trades": sdata.get("total_trades", 0),
                        "spy_return": spy_ret,
                    })
                print("done")

            except Exception as e:
                # Restore on error
                trig_mod.TriggerEngine.__init__ = old_trig_init
                bs_mod.BaseStrategy.__init__ = old_bs_init
                MixStrategy.__init__ = old_mix_init
                print(f"ERROR: {e}")

    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(SWEEP_DIR, f"improvement_sweep_{ts}.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {json_path}")

    # Analyze
    analyze_results(all_results)
    return all_results


def analyze_results(all_results):
    """Find the best feature combination."""
    if not all_results:
        return

    df = pd.DataFrame(all_results)

    print("\n" + "=" * 80)
    print("ABLATION ANALYSIS")
    print("=" * 80)

    # Baseline: all features OFF
    baseline = df[(~df["chandelier"]) & (~df["cooldown"]) & (~df["breadth"])]
    baseline_avg = baseline.groupby("strategy")["return_pct"].mean()

    # All combos averaged across periods
    combos = df.groupby(["chandelier", "cooldown", "breadth"]).agg({
        "return_pct": "mean",
        "sharpe": "mean",
        "max_drawdown": "mean",
        "trades": "mean",
    }).reset_index()

    combos["label"] = combos.apply(
        lambda r: f"ch={'Y' if r['chandelier'] else 'N'} cd={'Y' if r['cooldown'] else 'N'} br={'Y' if r['breadth'] else 'N'}",
        axis=1)
    combos = combos.sort_values("sharpe", ascending=False)

    print("\nAll combos ranked by Sharpe (avg across all strategies + periods):")
    for _, row in combos.iterrows():
        marker = " <<<" if row.name == combos.index[0] else ""
        print(f"  {row['label']}  ret={row['return_pct']:>6.1f}%  Sharpe={row['sharpe']:.3f}  "
              f"MaxDD={row['max_drawdown']:>6.1f}%  trades={row['trades']:.0f}{marker}")

    # Per-strategy best combo
    print("\nBest combo per strategy (by Sharpe):")
    for strat in STRATEGIES:
        sdf = df[df["strategy"] == strat]
        grouped = sdf.groupby(["chandelier", "cooldown", "breadth"]).agg({
            "return_pct": "mean", "sharpe": "mean"
        }).reset_index()
        best = grouped.loc[grouped["sharpe"].idxmax()]
        label = f"ch={'Y' if best['chandelier'] else 'N'} cd={'Y' if best['cooldown'] else 'N'} br={'Y' if best['breadth'] else 'N'}"
        print(f"  {strat:<14} {label}  ret={best['return_pct']:>6.1f}%  Sharpe={best['sharpe']:.3f}")

    # Individual feature impact (marginal)
    print("\nMarginal feature impact (ON minus OFF, holding others constant):")
    for feat in FEATURE_NAMES:
        on = df[df[feat] == True].groupby("strategy")["return_pct"].mean()
        off = df[df[feat] == False].groupby("strategy")["return_pct"].mean()
        delta = (on - off).mean()
        print(f"  {feat:<12} avg delta: {delta:>+.1f}%")

    # Best overall for "just run it"
    print("\nRECOMMENDED (best Sharpe across top 5 strategies):")
    top5 = df[df["strategy"].isin(["Mix", "MixLLM", "Adaptive", "Momentum", "Balanced"])]
    top5_combos = top5.groupby(["chandelier", "cooldown", "breadth"]).agg({
        "return_pct": "mean", "sharpe": "mean", "max_drawdown": "mean"
    }).reset_index().sort_values("sharpe", ascending=False)

    for i, (_, row) in enumerate(top5_combos.head(3).iterrows()):
        label = f"ch={'Y' if row['chandelier'] else 'N'} cd={'Y' if row['cooldown'] else 'N'} br={'Y' if row['breadth'] else 'N'}"
        marker = " <<< RECOMMENDED" if i == 0 else ""
        print(f"  {i+1}. {label}  ret={row['return_pct']:>6.1f}%  Sharpe={row['sharpe']:.3f}  MaxDD={row['max_drawdown']:>6.1f}%{marker}")


def main():
    parser = argparse.ArgumentParser(description="Improvement feature ablation sweep")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 3 key periods only (24 runs)")
    args = parser.parse_args()
    run_sweep(quick=args.quick)


if __name__ == "__main__":
    main()

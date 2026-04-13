"""Re-run all 14 canonical periods and compare with previous results.

Use after code changes that could affect strategy behavior
(trigger fixes, rebalance logic, holiday handling, etc.).

Runs sequentially to avoid CPU contention. Saves comparison report.

Usage:
    python eval/run_revalidation.py              # Run all 14
    python eval/run_revalidation.py --quick      # Run 4 key periods only
    python eval/run_revalidation.py --dry-run    # Show plan without running
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import PERIODS, run_daily_simulation

CANONICAL_FILE = os.path.join(os.path.dirname(__file__), "..", "runs", "final_canonical_merged_20260408.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "runs")

# Key periods for --quick mode (cover bull, crash, bear, rally)
QUICK_PERIODS = ["normal", "black_swan", "recession", "bull"]

# All 14 canonical periods in chronological order
ALL_PERIODS = [
    "dotcom_crash", "post_dotcom", "housing_bull", "gfc", "post_gfc",
    "qe_bull", "pre_covid",
    "normal", "black_swan", "recession", "bull",
    "bull_to_recession", "recession_to_bull", "2025_to_now",
]

CANONICAL_CONFIG = {
    "cash": 100_000,
    "max_positions": 10,
    "realistic": True,
    "slippage": 0.0005,
    "exec_model": "premarket",
    "frequency": "biweekly",
}


def load_old_canonical():
    """Load previous canonical results for comparison."""
    if not os.path.exists(CANONICAL_FILE):
        print(f"Warning: No old canonical file at {CANONICAL_FILE}")
        return {}
    with open(CANONICAL_FILE) as f:
        data = json.load(f)
    # Build lookup: {period_name: {strategy: return_pct}}
    lookup = {}
    for entry in data:
        period = entry.get("period", "")
        strat = entry.get("strategy", "")
        ret = entry.get("return_pct", 0)
        if period not in lookup:
            lookup[period] = {}
        lookup[period][strat] = ret
    return lookup


def run_period(period_key):
    """Run a single period with canonical config. Returns results dict."""
    p = PERIODS[period_key]
    print(f"\n{'='*60}")
    print(f"Running: {p['name']} ({p['start']} to {p['end']})")
    print(f"{'='*60}")

    t0 = time.time()
    try:
        results = run_daily_simulation(
            p["start"], p["end"],
            CANONICAL_CONFIG["cash"],
            CANONICAL_CONFIG["max_positions"],
            p["name"],
            realistic=CANONICAL_CONFIG["realistic"],
            slippage=CANONICAL_CONFIG["slippage"],
            exec_model=CANONICAL_CONFIG["exec_model"],
            frequency=CANONICAL_CONFIG["frequency"],
            quiet=False,
        )
        elapsed = time.time() - t0
        print(f"Completed in {elapsed:.0f}s")
        return results
    except Exception as e:
        print(f"FAILED: {e}")
        return None


def compare_results(new_results, old_canonical, period_name):
    """Compare new results with old canonical. Returns list of deltas."""
    old = old_canonical.get(period_name, {})
    deltas = []

    strategies = new_results.get("strategies", {})
    for strat_name, data in strategies.items():
        new_ret = data.get("total_return_pct", 0)
        old_ret = old.get(strat_name, None)
        delta = new_ret - old_ret if old_ret is not None else None
        deltas.append({
            "strategy": strat_name,
            "new": round(new_ret, 1),
            "old": round(old_ret, 1) if old_ret is not None else "N/A",
            "delta": round(delta, 1) if delta is not None else "N/A",
            "flag": abs(delta) > 5 if delta is not None else False,
        })

    # Add benchmarks
    for bm_name, data in new_results.get("benchmarks", {}).items():
        new_ret = data.get("total_return_pct", 0)
        deltas.append({
            "strategy": f"{bm_name} BH",
            "new": round(new_ret, 1),
            "old": "N/A",
            "delta": "N/A",
            "flag": False,
        })

    return deltas


def main():
    parser = argparse.ArgumentParser(description="Re-run canonical periods and compare")
    parser.add_argument("--quick", action="store_true", help="Run 4 key periods only")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    parser.add_argument("--periods", nargs="+", choices=list(PERIODS.keys()),
                        help="Run specific periods")
    args = parser.parse_args()

    periods = args.periods or (QUICK_PERIODS if args.quick else ALL_PERIODS)

    print("=" * 60)
    print("REVALIDATION SWEEP")
    print(f"Periods: {len(periods)}")
    print(f"Config: mp={CANONICAL_CONFIG['max_positions']}, "
          f"exec={CANONICAL_CONFIG['exec_model']}, "
          f"freq={CANONICAL_CONFIG['frequency']}")
    print(f"Changes to validate: trigger fix, biweekly fix, holiday fix, weekend news")
    print("=" * 60)

    # Load old canonical for comparison
    old_canonical = load_old_canonical()
    if old_canonical:
        print(f"Loaded old canonical: {len(old_canonical)} periods")
    else:
        print("No old canonical — will just report new results")

    if args.dry_run:
        print(f"\nWould run {len(periods)} periods:")
        for p in periods:
            info = PERIODS[p]
            old_strats = old_canonical.get(info["name"], {})
            old_mix = old_strats.get("MixLLM", "?")
            print(f"  {info['name']:<25} {info['start']} to {info['end']}  (old MixLLM: {old_mix}%)")
        print(f"\nEstimated time: {len(periods) * 3}-{len(periods) * 8} minutes")
        return

    # Run each period and collect results
    all_results = {}
    all_comparisons = {}
    total_t0 = time.time()

    for i, period_key in enumerate(periods):
        period_name = PERIODS[period_key]["name"]
        print(f"\n[{i+1}/{len(periods)}] ", end="")

        results = run_period(period_key)
        if results is None:
            continue

        all_results[period_name] = results

        # Compare with old
        deltas = compare_results(results, old_canonical, period_name)
        all_comparisons[period_name] = deltas

        # Print comparison
        print(f"\n{'Strategy':<14} {'New':>8} {'Old':>8} {'Delta':>8} {'Flag':>6}")
        print("-" * 48)
        for d in deltas:
            flag = " !!!" if d["flag"] else ""
            print(f"{d['strategy']:<14} {d['new']:>7.1f}% {str(d['old']):>7}% "
                  f"{str(d['delta']):>7}%{flag}")

    total_elapsed = time.time() - total_t0

    # Save merged results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(OUTPUT_DIR, f"revalidation_{timestamp}.json")

    # Build flat list for canonical format
    flat_results = []
    for period_name, results in all_results.items():
        for strat_name, data in results.get("strategies", {}).items():
            flat_results.append({
                "period": period_name,
                "strategy": strat_name,
                "return_pct": data.get("total_return_pct", 0),
                "sharpe": data.get("sharpe_ratio", 0),
                "max_drawdown": data.get("max_drawdown_pct", 0),
                "trades": data.get("total_trades", 0),
                "win_rate": data.get("win_rate_pct", 0),
            })

    with open(report_file, "w") as f:
        json.dump(flat_results, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"REVALIDATION COMPLETE")
    print(f"{'='*60}")
    print(f"Periods: {len(all_results)}/{len(periods)}")
    print(f"Time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"Results: {report_file}")

    # Summary of flags
    flagged = []
    for period_name, deltas in all_comparisons.items():
        for d in deltas:
            if d["flag"]:
                flagged.append(f"  {period_name}: {d['strategy']} delta={d['delta']}%")

    if flagged:
        print(f"\nFLAGGED ({len(flagged)} strategies with >5% delta):")
        for f in flagged:
            print(f)
    else:
        print(f"\nNo strategies flagged (all deltas < 5%)")

    # Average delta per strategy
    print(f"\nAverage |delta| by strategy:")
    strat_deltas = {}
    for period_name, deltas in all_comparisons.items():
        for d in deltas:
            if d["delta"] != "N/A":
                name = d["strategy"]
                if name not in strat_deltas:
                    strat_deltas[name] = []
                strat_deltas[name].append(abs(d["delta"]))

    for name in sorted(strat_deltas.keys()):
        vals = strat_deltas[name]
        avg = sum(vals) / len(vals)
        print(f"  {name:<14} {avg:>5.1f}% avg |delta| across {len(vals)} periods")


if __name__ == "__main__":
    main()

"""Full 4-Phase Testing Pipeline.

Phase 1: SWEEP — 7 periods × 3 MP × 3 cash = 63 runs → performance grid
Phase 2: FRAMEWORK — walk-forward, ablation, slippage, false discovery
Phase 3: COMBINED — validate best/worst sweep combos with ablation+slippage
Phase 4: CONSOLIDATION — cross-check everything, final report

Usage:
    python eval/full_test.py                  # All phases (~54 min)
    python eval/full_test.py --phase 1        # Sweep only
    python eval/full_test.py --phase 2        # Framework only
    python eval/full_test.py --phase 3        # Combined (needs 1+2)
    python eval/full_test.py --phase 4        # Consolidation (needs 1+2+3)
    python eval/full_test.py --quick          # 2 periods, reduced params (~15 min)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import (run_daily_simulation, download_data, build_events_calendar,
                        UNIVERSE, BENCHMARKS, MACRO_ETFS, PERIODS)

EVAL_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(EVAL_DIR, "pipeline_results")
STRATEGY_NAMES = ["Value", "Momentum", "Balanced", "Defensive", "EventDriven", "Adaptive", "Commodity"]

ALL_PERIODS = list(PERIODS.keys())
QUICK_PERIODS = ["recession", "bull"]
ALL_MP = [10, 20, 30]
QUICK_MP = [10]
ALL_CASH = [10_000, 50_000, 100_000]
QUICK_CASH = [50_000]


def ensure_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def save_phase(phase_num, data):
    ensure_dir()
    path = os.path.join(RESULTS_DIR, f"phase{phase_num}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def load_phase(phase_num):
    path = os.path.join(RESULTS_DIR, f"phase{phase_num}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_shared_data():
    print("Loading shared data (one-time download for all phases)...")
    all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
    price_data = download_data(all_tickers, "2019-01-02", "2026-03-24")
    events_cal = build_events_calendar(UNIVERSE, cache=True)
    print(f"Loaded {len(price_data)} tickers, {len(events_cal)} event calendars\n")
    return price_data, events_cal


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: SWEEP
# ═══════════════════════════════════════════════════════════════════

def phase1_sweep(price_data, events_cal, quick=False):
    periods = QUICK_PERIODS if quick else ALL_PERIODS
    mp_list = QUICK_MP if quick else ALL_MP
    cash_list = QUICK_CASH if quick else ALL_CASH

    total = len(periods) * len(mp_list) * len(cash_list)
    print("=" * 70)
    print(f"PHASE 1: SWEEP ({len(periods)} periods × {len(mp_list)} MP × {len(cash_list)} cash = {total} runs)")
    print("=" * 70)

    results = []
    run_count = 0
    start = time.time()

    for pk in periods:
        p = PERIODS[pk]
        for mp in mp_list:
            for cash in cash_list:
                run_count += 1
                elapsed = time.time() - start
                est = (elapsed / run_count * (total - run_count)) / 60 if run_count > 0 else 0
                print(f"  [{run_count}/{total}] {pk} mp={mp} ${cash:,} (~{est:.0f}m left)...", end=" ", flush=True)

                try:
                    r = run_daily_simulation(
                        start=p["start"], end=p["end"],
                        initial_cash=cash, max_positions=mp,
                        period_name=p["name"],
                        shared_price_data=price_data, shared_events_cal=events_cal,
                        quiet=True,
                    )
                    for sname, sdata in r.get("strategies", {}).items():
                        spy_ret = r.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
                        results.append({
                            "period": pk, "max_positions": mp, "cash": cash,
                            "strategy": sname,
                            "return_pct": sdata.get("total_return_pct", 0),
                            "sharpe": sdata.get("sharpe_ratio", 0),
                            "max_drawdown": sdata.get("max_drawdown_pct", 0),
                            "trades": sdata.get("total_trades", 0),
                            "win_rate": sdata.get("win_rate_pct", 0),
                            "alpha": sdata.get("total_return_pct", 0) - spy_ret,
                            "spy_return": spy_ret,
                        })
                    print("done")
                except Exception as e:
                    print(f"ERROR: {e}")

    path = save_phase(1, results)
    print(f"\nPhase 1 done: {len(results)} data points saved to {path}")
    print(f"Time: {(time.time() - start) / 60:.1f} min\n")
    return results


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: FRAMEWORK (walk-forward, ablation, slippage, false discovery)
# ═══════════════════════════════════════════════════════════════════

def phase2_framework(price_data, events_cal, quick=False):
    print("=" * 70)
    print("PHASE 2: FRAMEWORK (robustness validation)")
    print("=" * 70)
    start = time.time()

    results = {"walk_forward": {}, "ablation": {}, "slippage": {}, "standard": {}}

    # 2A: Standard metrics on all periods
    print("\n  2A: Standard metrics...")
    periods = QUICK_PERIODS if quick else ALL_PERIODS
    for pk in periods:
        p = PERIODS[pk]
        print(f"    {p['name']}...", end=" ", flush=True)
        r = run_daily_simulation(
            start=p["start"], end=p["end"], initial_cash=100_000, max_positions=10,
            period_name=p["name"], shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
        results["standard"][pk] = {
            s: {"return": d.get("total_return_pct", 0), "sharpe": d.get("sharpe_ratio", 0),
                "max_dd": d.get("max_drawdown_pct", 0), "trades": d.get("total_trades", 0),
                "win_rate": d.get("win_rate_pct", 0)}
            for s, d in r.get("strategies", {}).items()
        }
        results["standard"][pk]["SPY"] = r.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
        print("done")

    # 2B: Walk-forward
    print("\n  2B: Walk-forward...")
    folds = [
        (["normal"], "black_swan"),
        (["normal", "black_swan"], "bull_to_recession"),
        (["normal", "black_swan", "bull_to_recession"], "recession"),
        (["normal", "black_swan", "bull_to_recession", "recession"], "recession_to_bull"),
        (["normal", "black_swan", "bull_to_recession", "recession", "recession_to_bull"], "bull"),
    ]
    if quick:
        folds = folds[:2]

    wf_folds = []
    for i, (train, test) in enumerate(folds):
        print(f"    Fold {i+1}: test={test}...", end=" ", flush=True)
        train_sharpes = {}
        for tp in train:
            r = run_daily_simulation(
                start=PERIODS[tp]["start"], end=PERIODS[tp]["end"],
                initial_cash=100_000, max_positions=10, period_name=tp,
                shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
            for s, d in r.get("strategies", {}).items():
                train_sharpes.setdefault(s, []).append(d.get("sharpe_ratio", 0))

        test_r = run_daily_simulation(
            start=PERIODS[test]["start"], end=PERIODS[test]["end"],
            initial_cash=100_000, max_positions=10, period_name=test,
            shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
        test_sharpes = {s: d.get("sharpe_ratio", 0) for s, d in test_r.get("strategies", {}).items()}

        wf_folds.append({
            "train": train, "test": test,
            "is_sharpe": {s: round(np.mean(v), 3) for s, v in train_sharpes.items()},
            "oos_sharpe": test_sharpes,
        })
        print("done")
    results["walk_forward"] = wf_folds

    # 2C: Ablation
    print("\n  2C: Ablation (recession period)...")
    test_pk = "recession"

    print("    Baseline...", end=" ", flush=True)
    baseline = run_daily_simulation(
        start=PERIODS[test_pk]["start"], end=PERIODS[test_pk]["end"],
        initial_cash=100_000, max_positions=10, period_name=test_pk,
        shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
    results["ablation"]["baseline"] = {
        s: d.get("total_return_pct", 0) for s, d in baseline.get("strategies", {}).items()}
    print("done")

    # No news
    print("    No news...", end=" ", flush=True)
    from signals import SignalEngine
    orig_news = SignalEngine.compute_news
    SignalEngine.compute_news = lambda self, date: {"has_news": False, "geo_risk": 0}
    r = run_daily_simulation(
        start=PERIODS[test_pk]["start"], end=PERIODS[test_pk]["end"],
        initial_cash=100_000, max_positions=10, period_name=test_pk,
        shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
    SignalEngine.compute_news = orig_news
    results["ablation"]["no_news"] = {
        s: d.get("total_return_pct", 0) for s, d in r.get("strategies", {}).items()}
    print("done")

    # No earnings
    print("    No earnings...", end=" ", flush=True)
    r = run_daily_simulation(
        start=PERIODS[test_pk]["start"], end=PERIODS[test_pk]["end"],
        initial_cash=100_000, max_positions=10, period_name=test_pk,
        shared_price_data=price_data, shared_events_cal={}, quiet=True)
    results["ablation"]["no_earnings"] = {
        s: d.get("total_return_pct", 0) for s, d in r.get("strategies", {}).items()}
    print("done")

    # 2D: Slippage
    print("\n  2D: Slippage test (bull-to-recession)...")
    slip_pk = "bull_to_recession"
    from strategies.base_strategy import BaseStrategy
    orig_buy = BaseStrategy._buy
    orig_sell = BaseStrategy._sell

    for name, bps, comm in [("baseline", 0, 0), ("moderate", 10, 5), ("harsh", 20, 10)]:
        if quick and name == "harsh":
            continue
        print(f"    {name}...", end=" ", flush=True)

        slip_bps = bps
        slip_comm = comm

        def make_patched_buy(s_bps, s_comm):
            def patched(self_inner, ticker, shares, price, date, reason="", score_breakdown=None):
                adj = price * (1 + s_bps / 10000)
                self_inner.cash -= s_comm
                return orig_buy(self_inner, ticker, shares, adj, date, reason, score_breakdown)
            return patched

        def make_patched_sell(s_bps, s_comm):
            def patched(self_inner, ticker, price, date, reason="", score_breakdown=None):
                adj = price * (1 - s_bps / 10000)
                self_inner.cash -= s_comm
                return orig_sell(self_inner, ticker, adj, date, reason, score_breakdown)
            return patched

        BaseStrategy._buy = make_patched_buy(bps, comm)
        BaseStrategy._sell = make_patched_sell(bps, comm)
        r = run_daily_simulation(
            start=PERIODS[slip_pk]["start"], end=PERIODS[slip_pk]["end"],
            initial_cash=100_000, max_positions=10, period_name=slip_pk,
            shared_price_data=price_data, shared_events_cal=events_cal, quiet=True)
        BaseStrategy._buy = orig_buy
        BaseStrategy._sell = orig_sell

        results["slippage"][name] = {
            s: d.get("total_return_pct", 0) for s, d in r.get("strategies", {}).items()}
        print("done")

    path = save_phase(2, results)
    print(f"\nPhase 2 done: saved to {path}")
    print(f"Time: {(time.time() - start) / 60:.1f} min\n")
    return results


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: COMBINED VALIDATION
# ═══════════════════════════════════════════════════════════════════

def phase3_combined(price_data, events_cal, quick=False):
    """Combined validation — cross-references sweep + framework results.
    No new simulations (avoids monkey-patch hang issues).
    Uses existing Phase 1+2 data for all analysis."""
    print("=" * 70)
    print("PHASE 3: COMBINED VALIDATION (computation only)")
    print("=" * 70)
    start = time.time()

    sweep = load_phase(1)
    framework = load_phase(2)
    if not sweep or not framework:
        print("ERROR: Need Phase 1 and 2 results. Run those first.")
        return {}

    results = {}

    # Find best and worst combos from sweep
    best = sorted(sweep, key=lambda x: x["return_pct"], reverse=True)[:3]
    worst = sorted(sweep, key=lambda x: x["return_pct"])[:3]

    results["best_combos"] = [{"strategy": b["strategy"], "period": b["period"],
        "mp": b["max_positions"], "cash": b["cash"], "return": b["return_pct"],
        "sharpe": b["sharpe"], "alpha": b["alpha"]} for b in best]
    results["worst_combos"] = [{"strategy": w["strategy"], "period": w["period"],
        "mp": w["max_positions"], "cash": w["cash"], "return": w["return_pct"],
        "sharpe": w["sharpe"], "alpha": w["alpha"]} for w in worst]

    print(f"\n  Top 3: {[(b['strategy'], b['period'], round(b['return_pct'],1)) for b in best]}")
    print(f"  Bottom 3: {[(w['strategy'], w['period'], round(w['return_pct'],1)) for w in worst]}")

    # Cross-reference: do framework ablation findings hold across sweep combos?
    ablation = framework.get("ablation", {})
    if ablation:
        base = ablation.get("baseline", {})
        no_news = ablation.get("no_news", {})
        print("\n  Cross-reference: ablation vs sweep performance")
        results["cross_ref_news"] = {}
        for s in STRATEGY_NAMES:
            b = base.get(s, 0)
            nn = no_news.get(s, 0)
            news_impact = b - nn
            sweep_avg = np.mean([r["return_pct"] for r in sweep if r["strategy"] == s])
            results["cross_ref_news"][s] = {
                "news_impact": round(news_impact, 1),
                "sweep_avg_return": round(sweep_avg, 1),
                "news_matters": abs(news_impact) > 2,
            }
            if abs(news_impact) > 2:
                print(f"    {s}: news impact {news_impact:+.1f}%, sweep avg {sweep_avg:+.1f}%")

    # Cross-reference: do slippage findings predict which strategies scale?
    slippage = framework.get("slippage", {})
    if slippage:
        base_sl = slippage.get("baseline", {})
        mod_sl = slippage.get("moderate", {})
        if base_sl and mod_sl:
            print("\n  Cross-reference: slippage resilience vs sweep consistency")
            results["cross_ref_slippage"] = {}
            for s in STRATEGY_NAMES:
                friction = base_sl.get(s, 0) - mod_sl.get(s, 0)
                sweep_std = np.std([r["return_pct"] for r in sweep if r["strategy"] == s])
                results["cross_ref_slippage"][s] = {
                    "friction_cost": round(friction, 1),
                    "sweep_return_std": round(sweep_std, 1),
                    "resilient": friction < 5,
                }
                print(f"    {s}: friction={friction:+.1f}%, sweep_std={sweep_std:.1f}%")

    # Deflated Sharpe across ALL sweep data points
    print("\n  Deflated Sharpe across full sweep...")
    all_sharpes = [r["sharpe"] for r in sweep if r["sharpe"] != 0]
    try:
        from scipy.stats import norm
        n = len(all_sharpes)
        if n > 1 and np.std(all_sharpes) > 0:
            best_sharpe = max(all_sharpes)
            std_sharpe = np.std(all_sharpes)
            expected_max = norm.ppf(1 - 1/n) * std_sharpe
            se = std_sharpe / np.sqrt(n)
            deflated = (best_sharpe - expected_max) / se if se > 0 else 0
            p_value = 1 - norm.cdf(deflated)
            results["deflated_sharpe"] = {
                "best_sharpe": round(best_sharpe, 3),
                "expected_max_random": round(expected_max, 3),
                "deflated_sharpe": round(deflated, 3),
                "p_value": round(p_value, 4),
                "n_trials": n,
                "pass": p_value < 0.05,
            }
            print(f"    Best Sharpe: {best_sharpe:.3f}, Expected random max: {expected_max:.3f}, p={p_value:.4f}")
    except ImportError:
        results["deflated_sharpe"] = {"error": "scipy not available"}

    path = save_phase(3, results)
    print(f"\nPhase 3 done: saved to {path}")
    print(f"Time: {(time.time() - start) / 60:.1f} min\n")
    return results


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: CONSOLIDATION
# ═══════════════════════════════════════════════════════════════════

def phase4_consolidation():
    print("=" * 70)
    print("PHASE 4: CONSOLIDATED FINAL REPORT")
    print("=" * 70)

    sweep = load_phase(1)
    framework = load_phase(2)
    combined = load_phase(3)

    if not sweep or not framework:
        print("ERROR: Need Phase 1-3 results.")
        return

    findings = []

    # 1. Sweep findings
    print("\n--- SWEEP FINDINGS (Performance Grid) ---")
    strat_avg = {}
    for s in STRATEGY_NAMES:
        rets = [r["return_pct"] for r in sweep if r["strategy"] == s]
        alphas = [r["alpha"] for r in sweep if r["strategy"] == s]
        sharpes = [r["sharpe"] for r in sweep if r["strategy"] == s]
        if rets:
            strat_avg[s] = {
                "avg_return": round(np.mean(rets), 1),
                "avg_alpha": round(np.mean(alphas), 1),
                "avg_sharpe": round(np.mean(sharpes), 3),
                "beat_spy_pct": round(sum(1 for a in alphas if a > 0) / len(alphas) * 100),
            }
            print(f"  {s:<14} avg={np.mean(rets):>+6.1f}%  alpha={np.mean(alphas):>+5.1f}%  "
                  f"sharpe={np.mean(sharpes):>6.3f}  beats_SPY={strat_avg[s]['beat_spy_pct']}%")

    best_strat = max(strat_avg.items(), key=lambda x: x[1]["avg_return"])
    findings.append(f"Best average return: {best_strat[0]} ({best_strat[1]['avg_return']:+.1f}%)")

    # 2. Walk-forward findings
    if framework and "walk_forward" in framework:
        print("\n--- WALK-FORWARD FINDINGS ---")
        wf = framework["walk_forward"]
        for s in STRATEGY_NAMES:
            is_vals = [f["is_sharpe"].get(s, 0) for f in wf]
            oos_vals = [f["oos_sharpe"].get(s, 0) for f in wf]
            is_avg = np.mean(is_vals)
            oos_avg = np.mean(oos_vals)
            decay = oos_avg / is_avg if is_avg != 0 else 0
            status = "ROBUST" if decay > 0.3 else "FRAGILE"
            print(f"  {s:<14} IS={is_avg:>+6.3f}  OOS={oos_avg:>+6.3f}  decay={decay:.2f}  [{status}]")

    # 3. Ablation findings
    if framework and "ablation" in framework:
        print("\n--- ABLATION FINDINGS ---")
        ab = framework["ablation"]
        base = ab.get("baseline", {})
        for source in ["no_news", "no_earnings"]:
            if source in ab:
                print(f"  {source}:")
                for s in STRATEGY_NAMES:
                    b = base.get(s, 0)
                    a = ab[source].get(s, 0)
                    impact = b - a
                    if abs(impact) > 1:
                        label = "HELPS" if impact > 0 else "HURTS"
                        print(f"    {s:<14} {label} {abs(impact):.1f}%")

    # 4. Slippage findings
    if framework and "slippage" in framework:
        print("\n--- SLIPPAGE FINDINGS ---")
        sl = framework["slippage"]
        base = sl.get("baseline", {})
        mod = sl.get("moderate", {})
        if base and mod:
            for s in STRATEGY_NAMES:
                b = base.get(s, 0)
                m = mod.get(s, 0)
                deg = b - m
                print(f"  {s:<14} baseline={b:>+6.1f}%  moderate={m:>+6.1f}%  friction_cost={deg:>+5.1f}%")

    # 5. Combined validation
    if combined:
        print("\n--- COMBINED VALIDATION ---")
        if "deflated_sharpe" in combined:
            ds = combined["deflated_sharpe"]
            print(f"  Deflated Sharpe: best={ds.get('best_sharpe',0):.3f}  "
                  f"random_expected={ds.get('expected_max_random',0):.3f}  "
                  f"p={ds.get('p_value',1):.4f}  {'PASS' if ds.get('pass') else 'FAIL'}")

        for label in ["best_validation", "worst_validation"]:
            if label in combined:
                for v in combined[label]:
                    print(f"  {label}: {v['strategy']} {v['period']} "
                          f"original={v['original_return']:+.1f}% "
                          f"with_slippage={v['with_slippage_return']:+.1f}% "
                          f"degradation={v['degradation']:.1f}%")

    # 6. Final strategy rankings
    print("\n" + "=" * 70)
    print("FINAL STRATEGY RANKINGS")
    print("=" * 70)

    for s in sorted(STRATEGY_NAMES, key=lambda x: strat_avg.get(x, {}).get("avg_return", -999), reverse=True):
        avg = strat_avg.get(s, {})
        beat_pct = avg.get("beat_spy_pct", 0)
        avg_ret = avg.get("avg_return", 0)
        avg_sharpe = avg.get("avg_sharpe", 0)

        # Determine rating
        if beat_pct >= 60 and avg_sharpe > 0.3:
            rating = "STRONG"
        elif beat_pct >= 40 and avg_sharpe > 0:
            rating = "MODERATE"
        elif beat_pct >= 30:
            rating = "WEAK"
        else:
            rating = "POOR"

        print(f"  [{rating:>8}] {s:<14} avg={avg_ret:>+6.1f}%  sharpe={avg_sharpe:>6.3f}  beats_SPY={beat_pct}%")

    # Save final
    final = {
        "strategy_rankings": strat_avg,
        "findings": findings,
        "timestamp": datetime.now().isoformat(),
    }
    path = save_phase(4, final)
    print(f"\nFinal report saved to {path}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Full 4-Phase Testing Pipeline")
    parser.add_argument("--phase", choices=["1", "2", "3", "4", "all"], default="all")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    overall_start = time.time()

    # Load data once
    price_data, events_cal = load_shared_data()

    if args.phase in ("1", "all"):
        phase1_sweep(price_data, events_cal, args.quick)

    if args.phase in ("2", "all"):
        phase2_framework(price_data, events_cal, args.quick)

    if args.phase in ("3", "all"):
        phase3_combined(price_data, events_cal, args.quick)

    if args.phase in ("4", "all"):
        phase4_consolidation()

    total = (time.time() - overall_start) / 60
    print(f"\n{'=' * 70}")
    print(f"TOTAL TIME: {total:.1f} minutes")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

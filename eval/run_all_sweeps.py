"""Run ALL sweeps sequentially: frequency → LLM ablation → improvement → final canonical.

Designed to run overnight. Each phase saves results independently.
If a phase fails, subsequent phases still run.

Usage:
    python eval/run_all_sweeps.py
"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import (run_daily_simulation, PERIODS, UNIVERSE, BENCHMARKS, MACRO_ETFS,
                        download_data)
from events_data import build_events_calendar
from strategies.mix_llm_strategy import MixLLMStrategy
from strategies.mix_llm_v1_strategy import MixLLMV1Strategy
from strategies.mix_llm_v2_strategy import MixLLMV2Strategy
from strategies.mix_llm_v3_strategy import MixLLMV3Strategy

import pandas as pd
import numpy as np

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
    "black_swan":  PERIODS["black_swan"],
    "recession":   PERIODS["recession"],
    "bull":        PERIODS["bull"],
}


def save_results(all_results, prefix):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SWEEP_DIR, f"{prefix}_{ts}.json")
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"  Saved to {path}")
    return path


def load_period_data(periods, events_cal):
    """Pre-load data for all periods."""
    period_data = {}
    for key, p in periods.items():
        print(f"  Loading {p['name']}...")
        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        period_data[key] = download_data(all_tickers, p["start"], p["end"])
        print(f"    Got {len(period_data[key])} tickers")
    return period_data


def run_sim(p, price_data, events_cal, **kwargs):
    """Run a single simulation, return results."""
    return run_daily_simulation(
        start=p["start"], end=p["end"],
        initial_cash=100_000, max_positions=10,
        period_name=p["name"],
        shared_price_data=price_data,
        shared_events_cal=events_cal,
        quiet=True,
        realistic=True, slippage=0.0005, exec_model="premarket",
        regime_stickiness=1,
        **kwargs,
    )


def extract(results, extra_fields=None):
    """Extract strategy results into flat records."""
    records = []
    spy_ret = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
    qqq_ret = results.get("benchmarks", {}).get("QQQ", {}).get("total_return_pct", 0)
    for sname, sdata in results.get("strategies", {}).items():
        rec = {
            "strategy": sname,
            "return_pct": sdata.get("total_return_pct", 0),
            "sharpe": sdata.get("sharpe_ratio", 0),
            "max_drawdown": sdata.get("max_drawdown_pct", 0),
            "trades": sdata.get("total_trades", 0),
            "spy_return": spy_ret, "qqq_return": qqq_ret,
        }
        if extra_fields:
            rec.update(extra_fields)
        records.append(rec)
    return records


# ============================================================
# PHASE 1: FREQUENCY SWEEP (7 periods × 3 freq = 21 runs)
# ============================================================
def phase1_frequency(events_cal, period_data):
    print("\n" + "=" * 80)
    print("PHASE 1: FREQUENCY SWEEP (7 periods x 3 frequencies)")
    print("=" * 80)

    all_results = []
    freqs = ["weekly", "biweekly", "monthly"]
    total = len(SWEEP_PERIODS) * len(freqs)
    count = 0

    for key, p in SWEEP_PERIODS.items():
        for freq in freqs:
            count += 1
            print(f"  [{count}/{total}] {p['name']} freq={freq}...", end=" ", flush=True)
            try:
                results = run_sim(p, period_data[key], events_cal, frequency=freq)
                all_results.extend(extract(results, {"period": p["name"], "frequency": freq}))
                print("done")
            except Exception as e:
                print(f"ERROR: {e}")

    path = save_results(all_results, "phase1_frequency")

    # Quick analysis
    df = pd.DataFrame(all_results)
    print("\nFrequency Summary (avg across all strategies):")
    for freq in freqs:
        fdf = df[df["frequency"] == freq]
        print(f"  {freq:<10} ret={fdf['return_pct'].mean():.1f}%  Sharpe={fdf['sharpe'].mean():.3f}")

    # Find best frequency
    best = df.groupby("frequency")["sharpe"].mean().idxmax()
    print(f"\n  BEST FREQUENCY: {best}")
    return best, path


# ============================================================
# PHASE 2: LLM ABLATION (3 periods × 7 configs = 21 runs)
# ============================================================
def phase2_llm_ablation(events_cal, period_data, best_freq):
    print("\n" + "=" * 80)
    print(f"PHASE 2: LLM ABLATION (3 periods x 7 configs, freq={best_freq})")
    print("=" * 80)

    configs = {
        "NoLLM":  None,  # just use default MixLLMStrategy but compare Mix column
        "V0":     MixLLMStrategy,
        "V1":     MixLLMV1Strategy,
        "V2":     MixLLMV2Strategy,
        "V3":     MixLLMV3Strategy,
        "V1+V2":  MixLLMV1Strategy,  # TODO: combo not fully implemented
        "V2+V3":  MixLLMV3Strategy,  # TODO: combo not fully implemented
    }

    all_results = []
    total = len(QUICK_PERIODS) * len(configs)
    count = 0

    for key, p in QUICK_PERIODS.items():
        for config_name, llm_cls in configs.items():
            count += 1
            print(f"  [{count}/{total}] {p['name']} {config_name}...", end=" ", flush=True)
            try:
                results = run_sim(p, period_data[key], events_cal,
                                  frequency=best_freq, mixllm_class=llm_cls)
                all_results.extend(extract(results, {
                    "period": p["name"], "llm_config": config_name
                }))
                print("done")
            except Exception as e:
                print(f"ERROR: {e}")

    path = save_results(all_results, "phase2_llm_ablation")

    # Quick analysis
    df = pd.DataFrame(all_results)
    print("\nLLM Config Summary (MixLLM returns, avg across periods):")
    for config in configs:
        cdf = df[(df["llm_config"] == config) & (df["strategy"].str.startswith("MixLLM"))]
        if cdf.empty:
            cdf = df[(df["llm_config"] == config) & (df["strategy"] == "Mix")]
        if not cdf.empty:
            print(f"  {config:<8} ret={cdf['return_pct'].mean():.1f}%  Sharpe={cdf['sharpe'].mean():.3f}")

    best = df[df["strategy"].str.startswith("MixLLM")].groupby("llm_config")["sharpe"].mean()
    if not best.empty:
        best_config = best.idxmax()
        print(f"\n  BEST LLM CONFIG: {best_config}")
    else:
        best_config = "V0"
    return best_config, path


# ============================================================
# PHASE 3: IMPROVEMENT ABLATION (3 periods × 4 combos = 12 runs)
# ============================================================
def phase3_improvements(events_cal, period_data, best_freq, best_llm):
    print("\n" + "=" * 80)
    print(f"PHASE 3: IMPROVEMENT ABLATION (3 periods x 4 combos, freq={best_freq})")
    print("=" * 80)

    combos = [
        ("none",    False, False),
        ("ch",      True,  False),
        ("cd",      False, True),
        ("ch+cd",   True,  True),
    ]

    llm_cls_map = {
        "V0": MixLLMStrategy, "V1": MixLLMV1Strategy,
        "V2": MixLLMV2Strategy, "V3": MixLLMV3Strategy,
    }
    llm_cls = llm_cls_map.get(best_llm, MixLLMStrategy)

    all_results = []
    total = len(QUICK_PERIODS) * len(combos)
    count = 0

    for key, p in QUICK_PERIODS.items():
        for label, ch, cd in combos:
            count += 1
            print(f"  [{count}/{total}] {p['name']} {label}...", end=" ", flush=True)
            try:
                results = run_sim(p, period_data[key], events_cal,
                                  frequency=best_freq, chandelier=ch, cooldown=cd,
                                  mixllm_class=llm_cls)
                all_results.extend(extract(results, {
                    "period": p["name"], "combo": label
                }))
                print("done")
            except Exception as e:
                print(f"ERROR: {e}")

    path = save_results(all_results, "phase3_improvements")

    # Quick analysis
    df = pd.DataFrame(all_results)
    print("\nImprovement Combo Summary (avg across top 5 strategies):")
    top5 = df[df["strategy"].isin(["Mix", "MixLLM", "Balanced", "Momentum", "Adaptive"])]
    for label, _, _ in combos:
        cdf = top5[top5["combo"] == label]
        if not cdf.empty:
            print(f"  {label:<8} ret={cdf['return_pct'].mean():.1f}%  Sharpe={cdf['sharpe'].mean():.3f}")

    best = top5.groupby("combo")["sharpe"].mean().idxmax()
    print(f"\n  BEST IMPROVEMENT: {best}")
    return best, path


# ============================================================
# PHASE 4: FINAL 14-PERIOD CANONICAL SWEEP
# ============================================================
def phase4_canonical(events_cal, best_freq, best_llm, best_improvement):
    print("\n" + "=" * 80)
    print(f"PHASE 4: FINAL 14-PERIOD CANONICAL SWEEP")
    print(f"  freq={best_freq}, llm={best_llm}, improvements={best_improvement}")
    print("=" * 80)

    llm_cls_map = {
        "V0": MixLLMStrategy, "V1": MixLLMV1Strategy,
        "V2": MixLLMV2Strategy, "V3": MixLLMV3Strategy,
        "NoLLM": MixLLMStrategy,
    }
    llm_cls = llm_cls_map.get(best_llm, MixLLMStrategy)

    ch = "ch" in best_improvement
    cd = "cd" in best_improvement

    all_results = []
    total = len(PERIODS)
    count = 0

    for key, p in PERIODS.items():
        count += 1
        print(f"  [{count}/{total}] {p['name']}...", end=" ", flush=True)
        all_tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
        price_data = download_data(all_tickers, p["start"], p["end"])
        try:
            results = run_sim(p, price_data, events_cal,
                              frequency=best_freq, chandelier=ch, cooldown=cd,
                              mixllm_class=llm_cls)
            all_results.extend(extract(results, {"period": p["name"]}))
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")

    path = save_results(all_results, "phase4_canonical")

    # Final summary
    df = pd.DataFrame(all_results)
    print("\n" + "=" * 80)
    print("FINAL CANONICAL RESULTS")
    print(f"Config: freq={best_freq}, llm={best_llm}, improvements={best_improvement}")
    print("=" * 80)
    for strat in ["Mix", "MixLLM", "Adaptive", "Momentum", "Balanced", "Value",
                   "EventDriven", "Defensive", "Commodity"]:
        sdf = df[df["strategy"] == strat]
        if sdf.empty:
            continue
        r = sdf["return_pct"].mean()
        s = sdf["sharpe"].mean()
        d = sdf["max_drawdown"].min()
        beats = (sdf["return_pct"] > sdf["spy_return"]).sum()
        print(f"  {strat:<14} ret={r:>6.1f}%  Sharpe={s:.3f}  MaxDD={d:.1f}%  beatsSPY={beats}/{total}")
    spy_avg = df.groupby("period")["spy_return"].first().mean()
    qqq_avg = df.groupby("period")["qqq_return"].first().mean()
    print(f"  SPY            ret={spy_avg:>6.1f}%")
    print(f"  QQQ            ret={qqq_avg:>6.1f}%")
    return path


# ============================================================
# MAIN
# ============================================================
def main():
    start_time = time.time()
    print("=" * 80)
    print("OVERNIGHT SWEEP — ALL PHASES")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 80)

    # Build shared events calendar
    print("\nBuilding events calendar...")
    events_cal = build_events_calendar(UNIVERSE, cache=True)

    # Pre-load data for 7-period sweeps
    print("\nPre-loading data for 7 periods...")
    period_data = load_period_data(SWEEP_PERIODS, events_cal)

    # Phase 1: Frequency
    best_freq, _ = phase1_frequency(events_cal, period_data)

    # Phase 2: LLM ablation
    best_llm, _ = phase2_llm_ablation(events_cal, period_data, best_freq)

    # Phase 3: Improvements
    best_improvement, _ = phase3_improvements(events_cal, period_data, best_freq, best_llm)

    # Phase 4: Final canonical (all 14 periods)
    phase4_canonical(events_cal, best_freq, best_llm, best_improvement)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"ALL DONE in {elapsed/60:.0f} minutes")
    print(f"Best config: freq={best_freq}, llm={best_llm}, improvements={best_improvement}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()

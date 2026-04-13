"""LLM version ablation sweep.

Tests all MixLLM variants and combinations across periods.

Configs tested:
  V0:    Original MixLLM (escalate-only) — baseline
  V1:    Recovery detector (de-escalate-only)
  V2:    News interpreter (LLM scoring, coded regime)
  V3:    Event-triggered (bidirectional, rare calls)
  V1+V2: Recovery regime + news scoring
  V2+V3: Event regime + news scoring
  NoLLM: Plain Mix (no LLM at all)

Each config also tested with/without Chandelier+Cooldown improvements.

Usage:
    python eval/run_llm_ablation.py              # Full (7 periods × 7 configs × 2 = 98 runs)
    python eval/run_llm_ablation.py --quick      # Quick (3 periods × 7 configs = 21 runs, no ch/cd toggle)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import (run_daily_simulation, UNIVERSE, BENCHMARKS, MACRO_ETFS,
                        download_data, PERIODS)
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
    "black_swan":  PERIODS["black_swan"],
    "recession":   PERIODS["recession"],
    "bull":        PERIODS["bull"],
}

# LLM configs to test
# NoLLM uses MixStrategy as the "LLM" slot — pure coded rules, no API calls.
# Combos (V1+V2, V2+V3) removed — they were never actually combined in code.
LLM_CONFIGS = {
    "NoLLM":  {"use_llm": False, "version": "nollm"},
    "V0":     {"use_llm": True,  "version": "v0"},
    "V1":     {"use_llm": True,  "version": "v1"},
    "V2":     {"use_llm": True,  "version": "v2"},
    "V3":     {"use_llm": True,  "version": "v3"},
}

STRATEGIES_TO_TRACK = ["Mix", "MixLLM", "Balanced", "Momentum", "Adaptive", "Value"]


def get_mixllm_class(version):
    """Get the MixLLM class for a given version.

    NoLLM returns MixStrategy (coded rules only, no API calls).
    This replaces the MixLLM slot in the simulation — the "9th strategy"
    runs as a second Mix instead of MixLLM.
    """
    from strategies.mix_strategy import MixStrategy
    from strategies.mix_llm_strategy import MixLLMStrategy
    from strategies.mix_llm_v1_strategy import MixLLMV1Strategy
    from strategies.mix_llm_v2_strategy import MixLLMV2Strategy
    from strategies.mix_llm_v3_strategy import MixLLMV3Strategy

    VERSION_MAP = {
        "nollm": MixStrategy,  # coded rules only, no LLM
        "v0": MixLLMStrategy,
        "v1": MixLLMV1Strategy,
        "v2": MixLLMV2Strategy,
        "v3": MixLLMV3Strategy,
    }
    return VERSION_MAP.get(version, MixLLMStrategy)


def run_sweep(periods=None, quick=False):
    """Run the full LLM ablation sweep."""
    if periods is None:
        periods = QUICK_PERIODS if quick else SWEEP_PERIODS

    configs = LLM_CONFIGS
    ch_cd_options = [(False, False)] if quick else [(False, False), (True, True)]
    total = len(periods) * len(configs) * len(ch_cd_options)

    print("=" * 80)
    print("LLM VERSION ABLATION SWEEP")
    print(f"Configs: {list(configs.keys())}")
    print(f"Periods: {len(periods)} | Ch/Cd options: {len(ch_cd_options)} | Total runs: {total}")
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

        for config_name, config in configs.items():
            for ch, cd in ch_cd_options:
                run_count += 1
                elapsed = time.time() - start_time
                rate = elapsed / run_count if run_count > 0 else 60
                remaining = rate * (total - run_count)
                ch_label = "+ch+cd" if ch else ""
                print(f"  [{run_count}/{total}] {config_name}{ch_label} "
                      f"(~{remaining/60:.0f}m left)...", end=" ", flush=True)

                # Get the right MixLLM class (or None for NoLLM)
                llm_cls = get_mixllm_class(config["version"])

                try:
                    results = run_daily_simulation(
                        start=p["start"], end=p["end"],
                        initial_cash=100_000, max_positions=10,
                        period_name=p["name"],
                        shared_price_data=price_data,
                        shared_events_cal=events_cal,
                        quiet=True,
                        realistic=True, slippage=0.0005, exec_model="premarket",
                        frequency="biweekly", regime_stickiness=1,
                        chandelier=ch, cooldown=cd, breadth=False,
                        mixllm_class=llm_cls,
                    )

                    spy_ret = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
                    for sname, sdata in results.get("strategies", {}).items():
                        all_results.append({
                            "period": p["name"],
                            "llm_config": config_name,
                            "chandelier": ch,
                            "cooldown": cd,
                            "strategy": sname,
                            "return_pct": sdata.get("total_return_pct", 0),
                            "sharpe": sdata.get("sharpe_ratio", 0),
                            "max_drawdown": sdata.get("max_drawdown_pct", 0),
                            "trades": sdata.get("total_trades", 0),
                            "spy_return": spy_ret,
                        })
                    print("done")

                except Exception as e:
                    print(f"ERROR: {e}")

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(SWEEP_DIR, f"llm_ablation_{ts}.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {json_path}")

    # Analyze
    analyze_results(all_results)
    return all_results


def analyze_results(all_results):
    """Find the best LLM config."""
    if not all_results:
        return

    df = pd.DataFrame(all_results)

    print("\n" + "=" * 80)
    print("LLM ABLATION ANALYSIS")
    print("=" * 80)

    # Focus on MixLLM and Mix results
    print("\nMixLLM performance by config (avg across periods):")
    for config in LLM_CONFIGS:
        cdf = df[(df["llm_config"] == config) & (df["strategy"] == "MixLLM")]
        if cdf.empty:
            # NoLLM doesn't have MixLLM — use Mix instead
            cdf = df[(df["llm_config"] == config) & (df["strategy"] == "Mix")]
            if cdf.empty:
                continue
            label = f"  {config:<10} (Mix)"
        else:
            label = f"  {config:<10}"
        r = cdf["return_pct"].mean()
        s = cdf["sharpe"].mean()
        d = cdf["max_drawdown"].min()
        beats = (cdf["return_pct"] > cdf["spy_return"]).sum()
        total_p = len(cdf)
        print(f"{label} ret={r:>6.1f}%  Sharpe={s:.3f}  MaxDD={d:.1f}%  beatsSPY={beats}/{total_p}")

    # Does LLM help Mix at all?
    print("\nMix (no LLM) vs each MixLLM config:")
    mix_base = df[(df["llm_config"] == "NoLLM") & (df["strategy"] == "Mix")]
    mix_avg = mix_base["return_pct"].mean() if not mix_base.empty else 0
    mix_sharpe = mix_base["sharpe"].mean() if not mix_base.empty else 0
    print(f"  Mix (NoLLM)  ret={mix_avg:>6.1f}%  Sharpe={mix_sharpe:.3f}")

    for config in ["V0", "V1", "V2", "V3", "V1+V2", "V2+V3"]:
        cdf = df[(df["llm_config"] == config) & (df["strategy"] == "MixLLM")]
        if cdf.empty:
            continue
        r = cdf["return_pct"].mean()
        s = cdf["sharpe"].mean()
        delta = r - mix_avg
        print(f"  MixLLM {config:<6} ret={r:>6.1f}%  Sharpe={s:.3f}  vs Mix: {delta:>+5.1f}%")

    # Best overall config (considering all top strategies)
    print("\nBest config across top 5 strategies:")
    top5 = df[df["strategy"].isin(["Mix", "MixLLM", "Balanced", "Momentum", "Adaptive"])]
    grouped = top5.groupby(["llm_config", "chandelier", "cooldown"]).agg({
        "return_pct": "mean", "sharpe": "mean"
    }).reset_index().sort_values("sharpe", ascending=False)

    for i, (_, row) in enumerate(grouped.head(5).iterrows()):
        ch_label = "+ch+cd" if row["chandelier"] else ""
        marker = " <<< RECOMMENDED" if i == 0 else ""
        print(f"  {i+1}. {row['llm_config']}{ch_label}  "
              f"ret={row['return_pct']:>6.1f}%  Sharpe={row['sharpe']:.3f}{marker}")


def main():
    parser = argparse.ArgumentParser(description="LLM version ablation sweep")
    parser.add_argument("--quick", action="store_true",
                        help="Quick: 3 periods, no ch/cd toggle (21 runs)")
    args = parser.parse_args()
    run_sweep(quick=args.quick)


if __name__ == "__main__":
    main()

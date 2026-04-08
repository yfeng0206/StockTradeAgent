"""Run canonical sweep for a batch of periods. Designed for parallel execution."""
import sys, os, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from daily_loop import run_daily_simulation, PERIODS, UNIVERSE, BENCHMARKS, MACRO_ETFS, download_data
from events_data import build_events_calendar

periods = sys.argv[1:]  # period keys as args
if not periods:
    print("Usage: python run_canonical_batch.py period1 period2 ...")
    sys.exit(1)

events_cal = build_events_calendar(UNIVERSE, cache=True)
all_results = []

for key in periods:
    p = PERIODS[key]
    print(f'{p["name"]}...', end=' ', flush=True)
    tickers = list(set(UNIVERSE + BENCHMARKS + MACRO_ETFS))
    price_data = download_data(tickers, p["start"], p["end"])
    results = run_daily_simulation(
        start=p["start"], end=p["end"], initial_cash=100000, max_positions=10,
        period_name=p["name"], shared_price_data=price_data, shared_events_cal=events_cal,
        quiet=True, realistic=True, slippage=0.0005, exec_model="premarket",
        frequency="biweekly", regime_stickiness=1,
        chandelier=False, cooldown=False, breadth=False,
    )
    spy = results.get("benchmarks", {}).get("SPY", {}).get("total_return_pct", 0)
    qqq = results.get("benchmarks", {}).get("QQQ", {}).get("total_return_pct", 0)
    for sname, sdata in results.get("strategies", {}).items():
        all_results.append({
            "period": p["name"], "strategy": sname,
            "return_pct": sdata.get("total_return_pct", 0),
            "sharpe": sdata.get("sharpe_ratio", 0),
            "max_drawdown": sdata.get("max_drawdown_pct", 0),
            "trades": sdata.get("total_trades", 0),
            "spy_return": spy, "qqq_return": qqq,
        })
    print("done")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
batch_name = "_".join(periods[:2])
path = f"runs/canonical_batch_{batch_name}_{ts}.json"
with open(path, "w") as f:
    json.dump(all_results, f, indent=2)
print(f"Saved to {path}")

<p align="center">
  <h1 align="center">StockTradeAgent</h1>
  <p align="center">
    <b>9 Trading Strategies + LLM Risk Monitor | Free Data | 93 Stocks | 25 Years Backtested</b>
  </p>
</p>

---

## Why This Exists

Most trading agents cost $5-100/day, test on 3 months of data, and use LLM-only reasoning. This system is **free**, tested across **14 market regimes over 25 years** (2000-2026), and uses **coded rules** where they work best with an **LLM risk monitor** (Claude Opus) that only intervenes during genuine crises.

| | StockTradeAgent | Typical LLM Trading Agent |
|:--|:---:|:---:|
| **Cost** | $0 | $5-100/day |
| **Test duration** | 25 years, 14 regimes | 3 months |
| **Crash tested** | Dot-com, GFC, COVID, 2022 | Usually not |
| **Beats SPY** | 12 of 14 periods | Unknown |

---

## Key Results

**Mix strategy: +36.7% average return, beats SPY in 12 of 14 periods.**

| Strategy | Avg Return | vs SPY | Worst Drawdown | When to Use |
|:---------|:---------:|:------:|:--------------:|:------------|
| **Mix** | **+36.7%** | **+19.4%** | -25.0% | Max returns |
| **MixLLM** | +33.9% | +12.6% | -22.9% | Crash protection |
| QQQ (buy & hold) | +24.4% | — | **-82.9%** | If you can stomach -82% |
| SPY (buy & hold) | +17.5% | — | -55.1% | Passive baseline |

**During the 4 worst crashes**, MixLLM averaged **+6.4% gains** while SPY averaged -25.5% and QQQ -32.7%.

> Full results across all 9 strategies, 14 periods, position sizes, and model comparisons: **[Detailed Results](docs/RESULTS.md)**

---

## Quick Start

```bash
pip install -r requirements.txt

# Run one period (~2 min, no API keys needed)
python eval/daily_loop.py --period 2025_to_now --max-positions 10

# Run all 14 periods
for period in dotcom_crash post_dotcom housing_bull gfc post_gfc qe_bull pre_covid \
  normal black_swan recession bull bull_to_recession recession_to_bull 2025_to_now; do
  python eval/daily_loop.py --period $period --max-positions 10
done

# Live research on a stock (requires Claude CLI)
/stock-research AAPL
```

### Recommended Settings

| Setting | Default | Notes |
|:--------|:--------|:------|
| `--max-positions` | 10 | Tested 10/20/30. 10 is best for Mix/MixLLM (concentration = alpha) |
| `--regime-stickiness` | 1 | Tested 1/3/5. Instant switching is best overall |
| `MIXLLM_MODEL` | opus | Tested Opus vs Sonnet. Opus better in crashes |
| `--cash` | 100000 | Scales linearly |

---

## How It Works

**Daily event-driven simulation.** Not calendar-driven rebalancing -- reacts when something happens.

```
  Signal Engine (macro + technicals)
       |
  Trigger Engine (stop-loss, earnings, volume, regime change, news)
       |
  9 Strategies score 93 stocks independently
       |
  Risk Overlay (cash floor, conflict detection)
       |
  Execution (buy/sell/hold, partial fill, reasoning log)
```

### The 9 Strategies

| Strategy | Approach | Avg Return | Best At |
|:---------|:---------|:---------:|:--------|
| **Mix** | Uses 7 peers as live sensors, allocates stocks + commodity + cash | +36.7% | Best overall, 12/14 beat SPY |
| **MixLLM** | Mix + Claude Opus risk monitor (escalate-only) | +33.9% | Crash protection (+6.4% in crashes) |
| **Adaptive** | Switches mode by regime (momentum/value/defensive/recovery) | +32.1% | Strong trends |
| **Momentum** | Academic 12-minus-1 month signal, trend following | +29.2% | Bull markets |
| **Balanced** | Regime-weighted blend of value + momentum | +25.8% | All-weather |
| **Value** | Low volatility, beaten-down quality stocks, quarterly rebalance | +21.5% | Steady markets |
| **EventDriven** | Only trades around earnings and 8-K filings | +15.7% | Catalyst-rich periods |
| **Defensive** | 3-state exposure (100%/50%/20%), tightest stops | +13.9% | Limiting drawdowns |
| **Commodity** | Oil tracker (USO/XLE), binary signal | +5.7% | Bear markets, inflation |

> Strategy deep dives with exact formulas and thresholds: **[Strategy Details](docs/strategies/README.md)** | Glossary: **[Terms & Definitions](docs/GLOSSARY.md)** | Example outputs: **[Sample Logs](docs/EXAMPLES.md)**

### Two Runtime Modes

| | Simulation | Live Research |
|:--|:-----------|:-------------|
| **Engine** | Coded Python rules | Claude Opus 4.6 (LLM) |
| **Cost** | $0 | Included in Claude CLI |
| **Deterministic** | Yes | No (LLM varies) |
| **Speed** | ~2 min per period | ~3 min per stock |
| **Use case** | Backtest + validate | Deep single-stock analysis |

---

## Live Research: Adversarial Debate

The `/stock-research` skill runs a 13-turn structured debate on any stock:

1. **Bull vs Bear debate** (5 turns) -- thesis, counter-thesis, rebuttals, moderator summary
2. **7-strategy judge panel** -- each strategy rates the stock through its own lens
3. **Chief Strategist synthesis** -- weighs all judges, produces final recommendation

All turns logged as structured JSON for full auditability.

---

## Stock Universe

**93 stocks + SPY/QQQ across 15 sectors** -- mega-cap tech to biotech to oil.
Earlier periods (2000-2007) use ~66 stocks (those that existed at the time).

---

## Data Sources (All Free)

| Source | What We Pull | API Key? |
|:-------|:-------------|:--------:|
| **yfinance** | OHLCV prices, fundamentals, earnings, 11 sector ETFs, VIX, commodities, analyst recs, insider trades | No |
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings + XBRL structured financials | No (needs User-Agent) |
| **Wikipedia** | Daily world events from Current Events portal, categorized (geopolitical, business, health, etc.) | No |
| **GDELT** | Global news monitoring: war/conflict, sanctions, OPEC, pandemic, rates — 6 query categories | No |
| **Google News RSS** | Macro headlines: Fed policy, trade/tariffs, economic data | No |
| **FRED** | Treasury yields, Fed funds rate, CPI, unemployment, GDP (optional) | Free key |

> Full details on every API endpoint, field, rate limit, and storage format: **[Data Sources Deep Dive](docs/DATA_SOURCES.md)**

---

## Folder Structure

```
StockTradeAgent/
├── eval/                        # Simulation engine
│   ├── daily_loop.py                Daily event loop (main entry point)
│   ├── signals.py                   Macro, technical, volume signals
│   ├── triggers.py                  6 trigger types
│   ├── risk_overlay.py              Cash floor + conflict logging
│   ├── sim_memory.py                Strategy learning
│   ├── events_data.py               Earnings calendar
│   └── strategies/                  9 strategies (~100-350 lines each)
├── tools/                       # Data collection (all free)
├── data/                        # Fundamentals + news archive
├── docs/                        # Detailed results and analysis
│   └── RESULTS.md                   Full 14-period breakdown
├── runs/                        # Simulation output (per-strategy logs)
├── .claude/skills/              # LLM research skills
└── requirements.txt
```

---

## License

MIT

*This is a research project, not financial advice. Past performance does not predict future results.*

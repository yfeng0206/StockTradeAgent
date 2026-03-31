<p align="center">
  <h1 align="center">📈 StockTradeAgent</h1>
  <p align="center">
    <b>9 Trading Strategies + LLM Risk Monitor | Free Data | 93 Stocks | 25 Years Backtested</b>
    <br><br>
    <a href="#-key-results">Results</a> &bull;
    <a href="#-quick-start">Quick Start</a> &bull;
    <a href="#-how-it-works">How It Works</a> &bull;
    <a href="#-the-9-strategies">Strategies</a> &bull;
    <a href="#-live-research-adversarial-debate">Live Research</a> &bull;
    <a href="docs/strategies/README.md">Strategy Deep Dives</a> &bull;
    <a href="docs/RESULTS.md">Full Results</a>
  </p>
</p>

---

## 💡 Why This Exists

Most trading agents cost $5-100/day, test on 3 months of data, and use LLM-only reasoning. This system is **free**, tested across **14 market regimes over 25 years** (2000-2026), and uses **coded rules** where they work best with an **LLM risk monitor** (Claude Opus) that only intervenes during genuine crises.

| | 🏆 StockTradeAgent | Typical LLM Agent |
|:--|:---:|:---:|
| **💰 Cost** | Free | $5-100/day |
| **📊 Test duration** | 25 years, 14 regimes | 3 months |
| **💥 Crash tested** | Dot-com, GFC, COVID, 2022 | Usually not |
| **📈 Beats SPY** | 12 of 14 periods | Unknown |

---

## 🏆 Key Results

> **Mix strategy: +36.7% average return, beats SPY in 12 of 14 periods.**

| Strategy | Avg Return | vs SPY | Worst Drawdown | When to Use |
|:---------|:---------:|:------:|:--------------:|:------------|
| 🥇 **Mix** | **+36.7%** | **+19.4%** | -25.0% | Max returns |
| 🥈 **MixLLM** | +33.9% | +12.6% | -22.9% | Crash protection |
| 📉 QQQ (buy & hold) | +24.4% | — | **-82.9%** | If you can stomach -82% |
| 📉 SPY (buy & hold) | +17.5% | — | -55.1% | Passive baseline |

### 🛡️ Crash Protection

**During the 4 worst crashes**, MixLLM averaged **+6.4% gains** while SPY averaged -25.5% and QQQ -32.7%.

| Strategy | Dot-com '00 | GFC '08 | COVID '20 | 2022 Bear | Avg |
|:---------|:----------:|:-------:|:---------:|:---------:|:---:|
| 🛡️ **MixLLM** | ✅ +20.4% | ✅ +8.9% | -0.2% | -3.5% | **+6.4%** |
| 🛢️ **Commodity** | -14.1% | +22.7% | -2.4% | ✅ +24.7% | +7.7% |
| 📉 SPY | -33.1% | -45.9% | -5.3% | -17.6% | -25.5% |
| 📉 QQQ | -77.2% | -37.0% | +12.8% | -29.6% | -32.7% |

> 📊 Full results across all 9 strategies, 14 periods, position sizes, and model comparisons: **[Detailed Results](docs/RESULTS.md)**

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt

# ⚡ Run one period (~2 min, no API keys needed)
python eval/daily_loop.py --period 2025_to_now --max-positions 10

# 🔄 Run all 14 periods
for period in dotcom_crash post_dotcom housing_bull gfc post_gfc qe_bull pre_covid \
  normal black_swan recession bull bull_to_recession recession_to_bull 2025_to_now; do
  python eval/daily_loop.py --period $period --max-positions 10
done

# 🔍 Live research on a stock (requires Claude CLI)
/stock-research AAPL

# 📰 Collect today's market news
python tools/daily_collect.py
```

### ⚙️ Recommended Settings

| Setting | Default | Notes |
|:--------|:--------|:------|
| `--max-positions` | **10** | Tested 10/20/30. 10 is best for Mix/MixLLM |
| `--regime-stickiness` | **1** | Tested 1/3/5. Instant switching wins |
| `MIXLLM_MODEL` | **opus** | Tested Opus vs Sonnet. Opus better in crashes |
| `--cash` | **100000** | Scales linearly |

---

## 🔧 How It Works

**Daily event-driven simulation.** Not calendar-driven rebalancing — reacts when something happens.

```
  📡 Signal Engine (macro regime, technicals, news)
       │
  ⚡ Trigger Engine (stop-loss, earnings, volume, regime change, news spike)
       │
  🧠 9 Strategies score 93 stocks independently
       │
  🛡️ Risk Overlay (cash floor, conflict detection)
       │
  💼 Execution (buy/sell/hold, partial fill, reasoning log)
```

### 🧠 The 9 Strategies

| | Strategy | Approach | Avg Return | Best At |
|:--|:---------|:---------|:---------:|:--------|
| 🥇 | **Mix** | Uses 7 peers as live sensors, multi-asset allocation | +36.7% | Best overall (12/14 beat SPY) |
| 🛡️ | **MixLLM** | Mix + Claude Opus risk monitor (escalate-only) | +33.9% | Crash protection (+6.4% in crashes) |
| 🦎 | **Adaptive** | Switches mode by regime | +32.1% | Strong trends |
| 🚀 | **Momentum** | 12-minus-1 month signal, trend following | +29.2% | Bull markets |
| ⚖️ | **Balanced** | Regime-weighted value + momentum blend | +25.8% | All-weather |
| 🏛️ | **Value** | Low vol, beaten-down quality, quarterly rebalance | +21.5% | Steady markets |
| ⚡ | **EventDriven** | Trades only around earnings and 8-K filings | +15.7% | Catalyst-rich periods |
| 🔒 | **Defensive** | 3-state exposure (100%/50%/20%) | +13.9% | Limiting drawdowns |
| 🛢️ | **Commodity** | Oil tracker (USO/XLE), binary signal | +5.7% | Bear markets, inflation |

> 🔎 Strategy deep dives with exact formulas: **[Strategy Details](docs/strategies/README.md)** | 📖 **[Glossary](docs/GLOSSARY.md)** | 📋 **[Example Logs](docs/EXAMPLES.md)**

### 🔀 Two Runtime Modes

| | 🖥️ Simulation | 🔍 Live Research |
|:--|:-----------|:-------------|
| **Engine** | Coded Python rules | Claude Opus 4.6 (LLM) |
| **Cost** | $0 | Included in Claude CLI |
| **Deterministic** | Yes | No (LLM varies) |
| **Speed** | ~2 min per period | ~3 min per stock |
| **Use case** | Backtest + validate | Deep single-stock analysis |

---

## 🔍 Live Research: Adversarial Debate

The `/stock-research` skill runs a **13-turn structured debate** on any stock:

```
🐂 BULL vs BEAR DEBATE (5 turns)          ⚖️ STRATEGY JUDGES (7 turns)
================================           ================================
Turn 1  Bull Analyst                       Turn 6   🏛️ Value Judge
        thesis + 3 facts                   Turn 7   🚀 Momentum Judge
Turn 2  Bear Analyst                       Turn 8   🔒 Defensive Judge
        counter + 3 facts                  Turn 9   ⚡ EventDriven Judge
Turn 3  Bull Rebuttal                      Turn 10  ⚖️ Balanced Judge
Turn 4  Bear Rebuttal                      Turn 11  🦎 Adaptive Judge
Turn 5  Moderator Summary                  Turn 12  🛢️ Commodity Judge

                    🧠 SYNTHESIS (Turn 13)
                    Chief Strategist weighs all 7 judges
```

All turns logged as structured JSON for full auditability.

---

## 🌐 Stock Universe

**93 stocks + SPY/QQQ across 15 sectors** — mega-cap tech to biotech to oil.

<details>
<summary>📋 Click to see all 93 stocks</summary>

| Sector | # | Tickers |
|:-------|:-:|:--------|
| 💻 Tech | 12 | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, CRM, NFLX, AMD, ADBE, INTC |
| 🔌 Semis | 9 | AVGO, QCOM, TXN, MU, LRCX, AMAT, KLAC, MRVL, ON |
| ☁️ Software | 5 | NOW, PANW, ZS, CRWD, DDOG |
| 🌐 Internet | 7 | SHOP, UBER, ABNB, DASH, PYPL, COIN, PLTR |
| 🏦 Finance | 8 | JPM, V, MA, GS, BAC, WFC, MS, AXP |
| 🏥 Healthcare | 10 | UNH, JNJ, LLY, ABBV, MRK, PFE, TMO, AMGN, REGN, VRTX |
| 💊 Pharma | 3 | ABT, ISRG, MRNA |
| 🛒 Staples | 6 | PG, KO, PEP, COST, WMT, SBUX |
| 🛍️ Consumer | 7 | HD, MCD, NKE, LULU, TGT, ROKU, SPOT |
| ⛽ Energy | 5 | XOM, CVX, COP, SLB, OXY |
| 🏭 Industrial | 8 | CAT, BA, HON, UPS, DE, LMT, RTX, GE |
| 📺 Media | 4 | DIS, CMCSA, TMUS, CHTR |
| ⚡ Utilities | 2 | NEE, SO |
| 🏠 Real Estate | 3 | AMT, PLD, D |
| 📦 Other | 4 | BLK, FIS, EMR, MMM |

Earlier periods (2000-2007) use ~66 stocks (those that existed at the time).

</details>

---

## 📡 Data Sources (All Free)

| Source | What We Pull | 🔑 API Key? |
|:-------|:-------------|:----------:|
| 📊 **yfinance** | OHLCV prices, fundamentals, earnings, sector ETFs, VIX, analyst recs, insider trades | No |
| 📄 **SEC EDGAR** | 10-K, 10-Q, 8-K filings + XBRL structured financials | No |
| 🌍 **Wikipedia** | Daily world events, categorized (geopolitical, business, health) | No |
| 🔔 **GDELT** | Global news: war/conflict, sanctions, OPEC, pandemic — 6 categories | No |
| 📰 **Google News RSS** | Macro headlines: Fed policy, trade/tariffs, economic data | No |
| 📉 **FRED** | Treasury yields, Fed funds rate, CPI, unemployment (optional) | Free |

> 📖 Every API endpoint, field, rate limit, and storage format: **[Data Sources Deep Dive](docs/DATA_SOURCES.md)**

---

## 📁 Folder Structure

```
StockTradeAgent/
├── 🧪 eval/                         # Simulation engine
│   ├── daily_loop.py                    Daily event loop (main entry point)
│   ├── signals.py                       Macro, technical, volume signals
│   ├── triggers.py                      6 trigger types
│   ├── risk_overlay.py                  Cash floor + conflict logging
│   ├── sim_memory.py                    Strategy learning
│   ├── events_data.py                   Earnings calendar
│   └── strategies/                      9 strategies (~100-350 lines each)
├── 🔧 tools/                         # Data collection (all free)
├── 💾 data/                           # Fundamentals + news archive
├── 📖 docs/                           # Documentation
│   ├── RESULTS.md                       Full 14-period breakdown
│   ├── GLOSSARY.md                      Terms & definitions
│   ├── EXAMPLES.md                      Sample logs & outputs
│   ├── DATA_SOURCES.md                  Data source deep dive
│   ├── strategies/                      9 strategy deep dives
│   └── experiments/                     What we tested & learned
├── 📊 runs/                           # Simulation output
├── 🤖 .claude/skills/                 # LLM research skills
└── 📋 requirements.txt
```

---

## 📖 Documentation

| Page | What's In It |
|:-----|:------------|
| 📊 [**Detailed Results**](docs/RESULTS.md) | All 9 strategies x 14 periods, drawdowns, position size comparison |
| 🧠 [**Strategy Deep Dives**](docs/strategies/README.md) | Exact scoring formulas, thresholds, trigger reactions for each strategy |
| 📖 [**Glossary**](docs/GLOSSARY.md) | What is alpha? Regime? Stickiness? ATR? All terms defined |
| 📋 [**Example Outputs**](docs/EXAMPLES.md) | Sample trade logs, LLM calls, portfolio snapshots |
| 📡 [**Data Sources**](docs/DATA_SOURCES.md) | Every API, field, rate limit, and storage format |
| 🧪 [**Experiments**](docs/experiments/README.md) | What we tested (Opus vs Sonnet, stickiness, multi-commodity) and what we learned |

---

## 📜 License

MIT

<p align="center">
  <i>This is a research project, not financial advice. Past performance does not predict future results.</i>
</p>

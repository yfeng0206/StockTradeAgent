<p align="center">
  <h1 align="center">StockTradeAgent</h1>
  <p align="center">
    <b>9 Trading Strategies + LLM Adversarial Debate | Free Data | 93 Stocks | 7 Years Tested</b>
  </p>
  <p align="center">
    <a href="#results">Results</a> &bull;
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#how-it-works">How It Works</a> &bull;
    <a href="#strategies">Strategies</a> &bull;
    <a href="#live-research">Live Research</a>
  </p>
</p>

---

## Results

### 2024 Performance

| Strategy | Return | Sharpe | Max Drawdown |
|:---------|:------:|:------:|:------------:|
| **EventDriven** | **+34.3%** | 2.22 | -4.9% |
| **Momentum** | **+33.5%** | 2.04 | -8.8% |
| QQQ | +28.8% | 1.51 | -13.5% |
| SPY | +26.0% | 1.92 | -8.4% |
| ONEQ | +25.4% | 1.68 | -12.1% |

### Crash Protection

| Strategy | COVID Max Drawdown | 2022 Bear Max Drawdown |
|:---------|:------------------:|:----------------------:|
| **Commodity** | -3.8% | -8.2% |
| **Defensive** | -14.2% | -10.1% |
| SPY | -33.6% | -24.4% |
| QQQ | -28.6% | -34.7% |

---

### Full Results: 9 Strategies x 7 Market Regimes

$100K starting capital | 10 max positions | 93-stock universe | Daily event-driven simulation

#### Return %

| Strategy | 2019 Bull | COVID | 2023 AI | Bull-Rec | 2022 Bear | Rec-Bull | 2025-Now |
|:---------|:---------:|:-----:|:-------:|:--------:|:---------:|:--------:|:--------:|
| **Value** | **+38.9%** | **+16.0%** | +40.4% | -8.2% | -18.1% | +20.2% | -0.0% |
| **Momentum** | +35.5% | +5.2% | +42.1% | -16.4% | -19.2% | +22.9% | +12.6% |
| **Balanced** | +19.8% | -1.8% | +39.8% | +1.6% | -17.6% | +35.2% | +5.1% |
| **Defensive** | +21.6% | -5.7% | -6.4% | **+15.2%** | **-3.4%** | -1.6% | +11.6% |
| **EventDriven** | +15.4% | -2.8% | **+64.5%** | -7.6% | -27.0% | +27.5% | +13.2% |
| **Adaptive** | +23.0% | +12.2% | **+57.0%** | -4.3% | -21.1% | +25.2% | **+28.2%** |
| **Commodity** | -3.2% | -2.4% | +1.2% | +15.9% | **+24.7%** | -4.2% | +23.4% |
| **Mix** | +17.9% | +7.5% | +35.5% | +9.9% | -4.9% | +28.8% | **+28.1%** |
| **MixLLM** | +24.1% | -0.2% | +30.9% | +7.7% | -3.5% | +26.7% | +27.1% |
| SPY | +30.7% | -5.3% | +27.0% | -10.3% | -17.6% | +20.9% | +13.7% |
| QQQ | +38.1% | +12.8% | +56.5% | -19.5% | -29.6% | +33.7% | +15.9% |
| ONEQ | +36.1% | +8.8% | +47.2% | -21.8% | -29.0% | +26.8% | +14.6% |

#### Average Performance

| Strategy | Avg Return | Avg Alpha vs SPY | Beats SPY |
|:---------|:---------:|:----------------:|:---------:|
| **Mix** | **+17.5%** | **+9.1%** | **6 of 7** |
| **Adaptive** | +17.2% | +8.7% | 5 of 7 |
| **MixLLM** | +16.1% | +7.7% | **6 of 7** |
| Value | +12.7% | +4.3% | 4 of 7 |
| EventDriven | +11.9% | +3.4% | 4 of 7 |
| QQQ | +15.4% | — | — |
| SPY | +8.4% | — | — |

#### Max Drawdown

| Strategy | Worst Ever |
|:---------|:---------:|
| **Commodity** | -11.6% |
| **Defensive** | -14.4% |
| **MixLLM** | -21.0% |
| **Mix** | -24.0% |
| SPY | -33.6% |
| QQQ | -34.7% |

---

## Quick Start

```bash
pip install -r requirements.txt

# Run one period (~2 min)
python eval/daily_loop.py --period recession --max-positions 10

# Run all 7 periods
for period in normal black_swan bull bull_to_recession recession recession_to_bull 2025_to_now; do
  python eval/daily_loop.py --period $period --max-positions 10
done

# Live research on a stock (requires Claude CLI)
/stock-research AAPL
```

---

## How It Works

### Daily Decision Flow

```
  EVERY MORNING
  =============
  Signal Engine                    Trigger Engine
  +------------------+            +------------------+
  | Macro regime     |            | Stop-loss (ATR)  |
  | SPY trend + vol  |----------->| Earnings release |
  | Sector rotation  |            | Volume anomaly   |
  | News (geo_risk)  |            | Regime change    |
  | Per-stock tech   |            | News spike       |
  +------------------+            | Profit target    |
                                  +--------+---------+
                                           |
                            triggers fire? -+- yes --> react (strategy-specific)
                                           |
  MONTHLY REBALANCE                        |
  =================                        v
  9 Strategies score all 93 stocks    Risk Overlay
  each through their own lens    +--> Cash floor (2%)
  Value | Momentum | Balanced    |    Conflict logging
  Defensive | EventDriven        |
  Adaptive | Commodity           |
  Mix | MixLLM (Claude Opus)     |
                                 v
                            EXECUTION
                            Buy / Sell / Hold
                            Partial fill if low cash
                            Log reasoning + memory
```

### Two Runtime Modes

| | Simulation | Live Research |
|:--|:-----------|:-------------|
| **Engine** | Coded rules (Python) | Claude Opus 4.6 (LLM) |
| **Cost** | $0 | Included in Claude CLI |
| **Deterministic** | Yes | No (LLM varies) |
| **Speed** | ~2 min per period | ~3 min per stock |
| **Use case** | Backtest + validate | Deep single-stock analysis |

### What Data Each Strategy Reads

Every strategy sees the same market data but focuses on different signals:

| | Price MAs | Volatility | Returns | Volume | Earnings | News | Regime | Peers |
|:--|:---------:|:----------:|:-------:|:------:|:--------:|:----:|:------:|:-----:|
| **Value** | 52wk | 90d | -- | -- | 45-day | -- | -- | -- |
| **Momentum** | 50, 200 | RSI-14 | 12m-1m | ratio | 20d/3d | -- | -- | -- |
| **Balanced** | 50 | 90d | 3m | cv | 30d+8K | geo | SPY | -- |
| **Defensive** | 50, 200 | 20d, 60d | -- | -- | beat/miss | -- | SPY | -- |
| **EventDriven** | 20 | -- | 1d, 5d | spike | 45-day | -- | -- | -- |
| **Adaptive** | 50, 200 | 20d | 1m, 3m | -- | -- | geo | SPY+news | -- |
| **Commodity** | 50, 200 | 20d | 1m, 3m | -- | -- | -- | -- | -- |
| **Mix** | 50, 200 | 20d | 1m, 3m | -- | -- | -- | SPY+oil | 7 strats |
| **MixLLM** | 50, 200 | 20d | 1m, 3m | -- | -- | geo | SPY+oil+sectors+havens | 7 strats |

### How Each Strategy Scores

```
Value        [volatility 30%] [52wk distance 30%] [RSI 20%] [drawdown 20%]
Momentum     [12m-1m signal 40%] [trend 25%] [MACD 20%] [volume 15%]
Balanced     adapts by regime: bull -> momentum-heavy, bear -> value-heavy
Defensive    [low-vol 40%] [trend 30%] [drawdown 30%] + 3-state exposure scaling
EventDriven  [event score 55%] [volume spike 25%] [momentum 20%] (events only)
Adaptive     switches mode: MOMENTUM / VALUE / DEFENSIVE / RECOVERY
Commodity    binary: buy oil if score > 4, sell if < 3
Mix          detects regime from 7 peers -> allocates stocks + commodity + cash
MixLLM       coded rules + Opus risk monitor (can only escalate defensiveness)
```

### How Each Strategy Reacts to Triggers

| Trigger | Value | Momentum | Balanced | Defensive | EventDriven | Adaptive | Commodity | Mix |
|:--------|:-----:|:--------:|:--------:|:---------:|:-----------:|:--------:|:---------:|:---:|
| **Stop-loss** | sell | sell | sell | sell | sell | sell | sell | sell |
| **Regime danger** | hold | sell 1/3 | sell 1/4 | sell ALL | sell worst | sell 1/4 | log | sell 1/4 |
| **News spike** | hold | ignore | sell hiVol | sell hiVol | sell worst | sell hiVol | hold | sell hiVol |
| **Earnings beat** | ignore | buy | buy* | buy* | buy | buy* | ignore | buy* |
| **Earnings miss** | ignore | sell | sell* | sell | sell | sell* | ignore | sell* |
| **Volume spike** | watch | buy | cautious | exit | buy | cautious | ignore | cautious |
| **Profit target** | trim 1/3 | trim 1/3 | trim 1/3 | trim 1/3 | trim 1/3 | trim 1/3 | trim 1/3 | trim 1/3 |

*\* = regime-gated: won't buy earnings during crisis/bear market*

---

## Strategies

### Value
> *Patient. Ignores short-term noise. Waits for price to catch up to quality.*

Buy fundamentally cheap stocks. Rebalances **quarterly**. ATR stop 3.0x (widest).
Best: 2019 bull (+38.9%), COVID (+16.0%).

### Momentum
> *Aggressive. Chases winners. Cuts losers fast.*

Follow price using academic **12-minus-1 month** signal. ATR stop 2.5x.
Best: 2019 (+35.5%), recovery (+28.5%), full year 2024 (+33.5%).

### Balanced
> *Diplomatic. Captures a bit of everything.*

Adapts weights by regime: momentum-heavy in bull, value-heavy in bear. ATR stop 2.0x.
Best: Recovery (+21.5%), 2019 (+18.6%).

### Defensive
> *Paranoid. Always watching for the next crash.*

3-state exposure: NORMAL (100%) / REDUCED (50%) / DEFENSE (20%). ATR stop 1.5x (tightest).
Best: Bull-to-recession (+16.1% -- only strategy positive). Worst drawdown ever: -14.2%.

### EventDriven
> *Opportunistic. Waits for events, then pounces.*

ONLY scores stocks with recent earnings or 8-K filing. Regime-gated. ATR stop 2.0x.
Best: 2023 AI rally (+37.9%), full year 2024 (+34.3%).

### Adaptive
> *Chameleon. Changes strategy when the market changes.*

4 modes: MOMENTUM / VALUE / DEFENSIVE / RECOVERY. ATR stop 2.0x.
Best: 2023 AI rally (+47.2%), COVID (+5.7% while SPY lost -5.3%).

### Commodity
> *Specialist. One job, does it well.*

Tracks oil (USO/XLE). 50% max allocation. Can go 100% cash.
Best: 2022 bear (+24.7%), 2025 tariffs (+23.4%).

### Mix
> *The conductor. Watches everyone else, then decides.*

Uses the other 7 strategies as live sensors to detect the market regime,
then allocates across stocks + commodity + cash simultaneously. 5 regimes:
AGGRESSIVE (90% stocks) / CAUTIOUS (50% stocks + 20% commodity) /
DEFENSIVE (20% stocks + 30% commodity + 50% cash) / RECOVERY / UNCERTAIN.
Best: beats SPY in 6 of 7 periods. Avg alpha: +8.0%.

### MixLLM
> *The risk manager. Coded rules drive, Opus pulls the emergency brake.*

Hybrid architecture: coded Mix rules run first (bias AGGRESSIVE), then Claude Opus
reviews with rich data the coded rules can't see — sector rotation, gold/treasury trends,
bond stress, oil return magnitude, geo_risk scores, and its own regime history.
The LLM can only ESCALATE to more defensive regimes, never less.

Avg return +16.1%, avg alpha +7.7%, beats SPY in 6 of 7 periods. Worst drawdown -21.0%.
Caught Russia-Ukraine invasion risk in Feb 2022, correctly identified bear rally traps.
Non-deterministic, requires Claude CLI.

---

## Live Research: 13-Turn Adversarial Debate

The `/stock-research` skill runs a structured debate on any stock:

```
SHARED DEBATE (5 turns)                    PER-STRATEGY JUDGES (7 turns)
================================           ================================
Turn 1  Bull Analyst                       Turn 6   Value Judge
        thesis + 3 facts + invalidation             "P/E and margins matter most"
Turn 2  Bear Analyst                       Turn 7   Momentum Judge
        counter + 3 facts + concessions              "Price trend is truth"
Turn 3  Bull Rebuttal                      Turn 8   Defensive Judge
        addresses bear's strongest point             "High vol = dealbreaker"
Turn 4  Bear Rebuttal                      Turn 9   EventDriven Judge
        addresses bull's strongest point             "When's the next catalyst?"
Turn 5  Moderator                          Turn 10  Balanced Judge
        agreements / disagreements                   "Show me the composite"
                                           Turn 11  Adaptive Judge
                                                    "What regime are we in?"
                                           Turn 12  Commodity Judge
                                                    "How does this relate to oil?"

                    SYNTHESIS (Turn 13)
                    Chief Strategist weighs all 7 judges
```

All turns logged to `runs/research/{ticker}_{date}/` as structured JSON.

---

## Stock Universe

**93 stocks across 15 sectors** -- from mega-cap tech to biotech to oil:

| Sector | # | Tickers |
|:-------|:-:|:--------|
| Tech | 12 | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, CRM, NFLX, AMD, ADBE, INTC |
| Semis | 9 | AVGO, QCOM, TXN, MU, LRCX, AMAT, KLAC, MRVL, ON |
| Software | 5 | NOW, PANW, ZS, CRWD, DDOG |
| Internet | 7 | SHOP, UBER, ABNB, DASH, PYPL, COIN, PLTR |
| Finance | 8 | JPM, V, MA, GS, BAC, WFC, MS, AXP |
| Healthcare | 10 | UNH, JNJ, LLY, ABBV, MRK, PFE, TMO, AMGN, REGN, VRTX |
| Pharma | 3 | ABT, ISRG, MRNA |
| Staples | 6 | PG, KO, PEP, COST, WMT, SBUX |
| Consumer | 7 | HD, MCD, NKE, LULU, TGT, ROKU, SPOT |
| Energy | 5 | XOM, CVX, COP, SLB, OXY |
| Industrial | 8 | CAT, BA, HON, UPS, DE, LMT, RTX, GE |
| Media | 4 | DIS, CMCSA, TMUS, CHTR |
| Utilities | 2 | NEE, SO |
| Real Estate | 3 | AMT, PLD, D |
| Other | 4 | BLK, FIS, EMR, MMM |

---

## Comparison with Related Work

| | [TradingAgents](https://github.com/TauricResearch/TradingAgents) | [AI-Trader](https://github.com/HKUDS/AI-Trader) | **StockTradeAgent** |
|:--|:------|:------|:------|
| **Cost** | $5-100/day | $5-50/day | **$0** |
| **Deterministic** | No | No | **Yes** |
| **Test duration** | 3 months | 5 weeks | **7 years** |
| **Universe** | 3 stocks | NASDAQ-100 | **93 stocks** |
| **Strategies** | LLM-only | LLM-only | **9 (7 coded + Mix + MixLLM)** |
| **Ablation tested** | No | No | **Yes** |
| **Beats QQQ (2024)** | Not tested | Not tested | **2 of 9** |

---

## Data Sources (All Free)

| Source | What It Provides |
|:-------|:-----------------|
| **yfinance** | Prices, fundamentals, earnings, company news |
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings |
| **Wikipedia** | Historical world events (backfilled 2019-2026) |
| **GDELT** | Real-time geopolitical events |

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
├── data/                        # 96 fundamentals + 405 news dates
├── runs/                        # Simulation output (per-strategy logs)
├── .claude/skills/              # LLM research skills
└── requirements.txt
```

---

## License

MIT

*This is a research project, not financial advice. Past performance does not predict future results.*

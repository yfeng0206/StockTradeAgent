# StockTradeAgent

**7 deterministic trading strategies + LLM-powered adversarial analysis.** Free data, reproducible results, tested across 7 market regimes (2019-2026).

> Value +38.9% in 2019 bull. Adaptive +47.2% in 2023 AI rally. Commodity +24.7% in 2022 bear. Defensive max drawdown -14.2% vs SPY -33.6%.

Inspired by [TradingAgents](https://github.com/TauricResearch/TradingAgents) (UCLA/MIT) and [AI-Trader](https://github.com/HKUDS/AI-Trader) (HKU) — but deterministic, free, and tested over years instead of weeks.

---

## Architecture

```
+------------------------------------------------------------------+
|                         DAILY FLOW                                |
|                                                                   |
|  MORNING                                                          |
|  +------------------+    +------------------+                     |
|  | Signal Engine    |    | Trigger Engine   |                     |
|  | - Macro regime   |    | - Stop-loss (ATR)|                     |
|  | - SPY trend/vol  |--->| - Earnings       |                     |
|  | - Sector rotation|    | - Volume anomaly |                     |
|  | - News (geo_risk)|    | - Regime change  |                     |
|  | - Per-stock tech |    | - News spike     |                     |
|  +------------------+    | - Profit target  |                     |
|                          +--------+---------+                     |
|                                   |                               |
|                          triggers fire?                            |
|                          yes -> react (strategy-specific)         |
|                          no  -> wait                              |
|                                   |                               |
|  MONTHLY REBALANCE                |                               |
|  +----------------------------+   |                               |
|  | 7 Strategies score stocks  |<--+                               |
|  | each with different lens:  |                                   |
|  | Value, Momentum, Balanced, |   +------------------+            |
|  | Defensive, EventDriven,    |-->| Risk Overlay     |            |
|  | Adaptive, Commodity        |   | - Cash floor (2%)|            |
|  +----------------------------+   | - Conflict log   |            |
|                                   +--------+---------+            |
|                                            |                      |
|  EXECUTION                                 v                      |
|  +----------------------------+   +------------------+            |
|  | Buy / Sell / Hold          |<--| Position sizing  |            |
|  | Partial fill if low cash   |   | Per-stock scores |            |
|  | Log reasoning + memory     |   +------------------+            |
|  +----------------------------+                                   |
+------------------------------------------------------------------+
```

**Two runtime modes:**

| | Simulation (`eval/`) | Live Research (`/stock-research`) |
|--|---------------------|----------------------------------|
| Engine | Coded rules (Python) | LLM (Claude Opus 4.6) |
| Cost | $0 | Included in Claude CLI |
| Deterministic | Yes — same input, same output | No — LLM varies |
| Speed | ~2 min per period | ~3 min per stock |
| Use case | Backtest, validate, compare | Deep single-stock analysis |

---

## How Each Strategy Makes Decisions

Every strategy reads the same market data but weighs it differently — like 7 analysts in a room looking at the same Bloomberg terminal.

### Data Each Strategy Uses

```
                 Price    Volatility  Returns   Volume  Earnings  News    Regime
                 MAs      (days)     horizon   data    events    geo     detect
                 ------   ---------  --------  ------  --------  ------  ------
Value            52wk     90d          -         -     45-day      -       -
Momentum         50,200   RSI-14     12m-1m    ratio   20d/3d      -       -
Balanced         50       90d        3m        cv      30d+8K    geo_risk SPY
Defensive        50,200   20d,60d      -         -     beat/miss   -      SPY
EventDriven      20         -        1d,5d     spike   45-day      -       -
Adaptive         50,200   20d        1m,3m       -       -       geo_risk SPY+news
Commodity        50,200   20d        1m,3m       -       -       removed    -
```

### Scoring Weights

```
Value:       vol 30%  |  52wk distance 30%  |  RSI 20%  |  drawdown 20%
Momentum:    12m-1m momentum 40%  |  trend 25%  |  MACD 20%  |  volume 15%
Balanced:    ADAPTS BY REGIME:
               Bull:   value 20% | momentum 45% | stability 35%
               Bear:   value 45% | momentum 15% | stability 40%
               Normal: value 30% | momentum 35% | stability 35%
Defensive:   low-vol 40%  |  trend 30%  |  drawdown 30%  (+ 3-state scaling)
EventDriven: event score 55%  |  volume spike 25%  |  momentum 20%
Adaptive:    SWITCHES MODE:
               Bull  -> momentum 45% | trend 30% | MACD 25%
               Bear  -> vol 50% | trend 50% (max 2-3 positions)
               Value -> vol 35% | 52wk 35% | RSI 30%
               Recovery -> bounce 35% | upside 30% | momentum 35%
Commodity:   Binary: buy oil if score>4, sell if <3
```

### Trigger Reactions

When events fire between rebalances, each strategy reacts differently:

```
Trigger           Value     Momentum  Balanced  Defensive  EventDriven  Adaptive  Commodity
STOP_LOSS         sell      sell      sell      sell       sell         sell      sell
REGIME -> danger  hold      sell 1/3  sell 1/4  sell ALL   sell worst   sell 1/4  log only
NEWS escalation   hold      ignore    sell hiV  sell hiV   sell worst   sell hiV  hold(oil)
EARNINGS beat     ignore    buy       buy*      buy*       buy          buy*      ignore
EARNINGS miss     ignore    sell      sell*     sell       sell         sell*     ignore
VOLUME spike      watch     buy       cautious  exit       buy          cautious  ignore
PROFIT TARGET     trim 1/3  trim 1/3  trim 1/3  trim 1/3   trim 1/3    trim 1/3  trim 1/3

* = regime-gated: won't buy earnings during crisis/bear market
```

### Risk Overlay (Post-Scoring)

The risk overlay sits between scoring and execution. Currently only cash floor is active:

```
Feature             Status        What it does
Cash floor (2%)     ON            Always keep 2% cash (8% more during danger regimes)
Conflict logging    LOGGING ONLY  Detects signal contradictions, logs but doesn't change size
Conviction gate     OFF           Was costing 14% in bull to save 5% in bear
Consensus           OFF           Strategies should run independently
```

---

## The 7 Strategies

### Value
Buy fundamentally cheap stocks. Hold through volatility — the market will come to you.
- Rebalances **quarterly** (least frequent)
- ATR stop: 3.0x (widest — gives positions room)
- Best: 2019 bull (+38.9%), COVID (+16.0%)
- Personality: Patient. Ignores short-term noise. Waits for price to catch up to quality.

### Momentum
Follow price. Stocks going up tend to keep going up.
- Uses academic **12-minus-1 month** signal (skip recent month to avoid reversal)
- ATR stop: 2.5x
- Best: 2019 (+35.5%), Rec-Bull recovery (+28.5%)
- Personality: Aggressive. Chases winners. Cuts losers fast.

### Balanced
No single factor dominates. Adapts weights by market regime.
- Shifts between value-heavy (bear) and momentum-heavy (bull) automatically
- ATR stop: 2.0x
- Best: Rec-Bull (+21.5%), 2019 (+18.6%)
- Personality: Diplomatic. Tries to capture a bit of everything.

### Defensive
Capital preservation first. Miss gains rather than take losses.
- **3-state exposure**: NORMAL (100%), REDUCED (50%), DEFENSE (20%)
- Counts danger signals (vol, trend break, drawdown) to scale down
- ATR stop: 1.5x (tightest)
- Best: Bull-Rec transition (+16.1% — only strategy positive)
- Personality: Paranoid. Always watching for the next crash.

### EventDriven
Trade catalysts. Earnings surprises move prices.
- **Hard gate**: ONLY scores stocks with recent earnings or 8-K filing
- Regime-gated: won't buy earnings during crisis
- ATR stop: 2.0x
- Best: 2023 AI rally (+37.9%), Rec-Bull (+28.9%)
- Personality: Opportunistic. Waits for events, then pounces.

### Adaptive
What regime are we in? That determines everything.
- 4 modes: MOMENTUM / VALUE / DEFENSIVE / RECOVERY
- Detects regime via SPY MAs + volatility + sector rotation
- ATR stop: 2.0x
- Best: 2023 AI rally (+47.2%), COVID (+5.7% while SPY lost -5.3%)
- Personality: Chameleon. Changes strategy when the market changes.

### Commodity
Track oil. When inflation/geopolitics spike, oil outperforms everything.
- Single instrument (USO/XLE), 50% max allocation, rest in cash
- Can go 100% cash if oil signal is bearish
- Best: 2022 bear (+24.7%), 2025 tariffs (+23.4%)
- Personality: Specialist. One job, does it well.

---

## Results

### 7 Strategies x 7 Market Regimes

$100K starting capital, 10 max positions, 93-stock universe.

**Return %**

| Strategy | 2019 Bull | COVID | 2023 AI | Bull-Rec | 2022 Bear | Rec-Bull | 2025-Now |
|----------|----------|-------|---------|----------|-----------|----------|----------|
| **Value** | **+38.9%** | **+16.0%** | +30.4% | -7.2% | -15.5% | +18.4% | -5.4% |
| **Momentum** | +35.5% | +9.5% | +20.1% | -19.3% | -24.9% | +28.5% | +4.5% |
| **Balanced** | +18.6% | -7.2% | +15.0% | -7.7% | -9.4% | +21.5% | -4.1% |
| **Defensive** | +21.6% | -7.2% | -2.4% | **+16.1%** | **-3.4%** | +0.8% | +5.6% |
| **EventDriven** | +14.0% | -5.3% | **+37.9%** | -19.5% | -18.7% | **+28.9%** | +11.9% |
| **Adaptive** | +23.0% | +5.7% | **+47.2%** | -0.2% | -24.5% | +21.3% | +13.6% |
| **Commodity** | -3.2% | -2.4% | +1.2% | +15.9% | **+24.7%** | -4.2% | **+23.4%** |
| SPY | +30.7% | -5.3% | +27.0% | -10.3% | -17.6% | +20.9% | +13.7% |
| QQQ | +38.1% | +12.8% | +56.5% | -19.5% | -29.6% | +33.7% | +15.9% |
| ONEQ | +36.1% | +8.8% | +47.2% | -21.8% | -29.0% | +26.8% | +14.6% |

**Max Drawdown %**

| Strategy | Worst Ever | When | vs SPY (-33.6%) |
|----------|-----------|------|-----------------|
| **Defensive** | -14.2% | COVID | **2.4x better** |
| **Commodity** | -11.6% | Bull-Rec | **2.9x better** |
| **Value** | -22.1% | Recession | 1.5x better |
| SPY | -33.6% | COVID | -- |
| QQQ | -34.7% | Recession | -- |

### Paper Period Comparison

We ran the same periods used by TradingAgents and AI-Trader:

**TradingAgents period (Jan-Mar 2024):** Our Momentum +16.8% vs QQQ +10.4% (+6.4% alpha)

**AI-Trader period (Oct-Nov 2025):** Our EventDriven +3.3% vs QQQ +1.4% (+1.9% alpha)

**Full year 2024:** Momentum +33.5% and EventDriven +34.3% both beat SPY (+26%) and QQQ (+28.8%)

---

## Stock Universe (93 stocks, 15 sectors)

| Sector | Count | Tickers |
|--------|-------|---------|
| Tech Mega-Cap | 12 | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, CRM, NFLX, AMD, ADBE, INTC |
| Semiconductors | 9 | AVGO, QCOM, TXN, MU, LRCX, AMAT, KLAC, MRVL, ON |
| Software/Cloud | 5 | NOW, PANW, ZS, CRWD, DDOG |
| Internet/Fintech | 7 | SHOP, UBER, ABNB, DASH, PYPL, COIN, PLTR |
| Finance | 8 | JPM, V, MA, GS, BAC, WFC, MS, AXP |
| Healthcare/Biotech | 10 | UNH, JNJ, LLY, ABBV, MRK, PFE, TMO, AMGN, REGN, VRTX |
| Pharma/MedDev | 3 | ABT, ISRG, MRNA |
| Consumer Staples | 6 | PG, KO, PEP, COST, WMT, SBUX |
| Consumer Disc. | 7 | HD, MCD, NKE, LULU, TGT, ROKU, SPOT |
| Energy | 5 | XOM, CVX, COP, SLB, OXY |
| Industrials/Defense | 8 | CAT, BA, HON, UPS, DE, LMT, RTX, GE |
| Telecom/Media | 4 | DIS, CMCSA, TMUS, CHTR |
| Utilities | 2 | NEE, SO |
| Real Estate | 3 | AMT, PLD, D |
| Other | 4 | BLK, FIS, EMR, MMM |

Later-IPO stocks (CRWD, UBER, ABNB, DASH, COIN, PLTR) are automatically skipped for periods before their IPO.

---

## Live Research: 13-Turn Adversarial Debate

The `/stock-research` skill uses Claude for deep single-stock analysis:

```
SHARED DEBATE (5 turns about the stock)
  Turn 1: Bull Analyst     thesis + 3 facts + invalidation criteria
  Turn 2: Bear Analyst     counter-thesis + 3 facts + concessions
  Turn 3: Bull Rebuttal    addresses bear's strongest point
  Turn 4: Bear Rebuttal    addresses bull's strongest point
  Turn 5: Moderator        summarizes agreements/disagreements

PER-STRATEGY JUDGES (7 turns, same data, different lens)
  Turn 6:  Value Judge     "P/E and margins matter most"
  Turn 7:  Momentum Judge  "Price trend is truth"
  Turn 8:  Defensive Judge "High vol is a dealbreaker"
  Turn 9:  EventDriven     "When's the next catalyst?"
  Turn 10: Balanced Judge  "Show me the composite"
  Turn 11: Adaptive Judge  "What regime are we in?"
  Turn 12: Commodity Judge "How does this relate to oil?"

SYNTHESIS (1 turn)
  Turn 13: Chief Strategist weighs all 7 judges, picks most relevant
```

All 13 turns logged to `runs/research/{ticker}_{date}/` with structured JSON.

---

## Quick Start

```bash
pip install -r requirements.txt

# Run a single period
python eval/daily_loop.py --period recession --max-positions 10

# Run all 7 periods
for period in normal black_swan bull bull_to_recession recession recession_to_bull 2025_to_now; do
  python eval/daily_loop.py --period $period --max-positions 10
done

# Live stock research (requires Claude CLI)
/stock-research AAPL
/portfolio-watch
```

### Simulation Periods

| Period | Dates | What It Tests |
|--------|-------|---------------|
| `normal` | 2019-01 to 2019-12 | Steady bull market |
| `black_swan` | 2020-01 to 2020-06 | COVID crash + recovery |
| `bull` | 2023-01 to 2023-12 | AI rally |
| `bull_to_recession` | 2021-07 to 2022-06 | Bull-to-bear transition |
| `recession` | 2022-01 to 2022-10 | Sustained bear market |
| `recession_to_bull` | 2022-10 to 2023-06 | Bear-to-bull recovery |
| `2025_to_now` | 2025-01 to 2026-03 | Current market |

---

## Folder Structure

```
StockTradeAgent/
├── eval/                           # Simulation engine
│   ├── daily_loop.py                   Main daily event loop
│   ├── signals.py                      Signal computation (macro, technical, volume)
│   ├── triggers.py                     6 trigger types (stop, earnings, regime, news, volume, profit)
│   ├── risk_overlay.py                 Cash floor + conflict logging (feature-flagged)
│   ├── sim_memory.py                   Per-strategy learning from past trades
│   ├── events_data.py                  Earnings calendar via yfinance
│   └── strategies/                     7 strategies (each ~100-250 lines)
│
├── tools/                          # Data tools (all free sources)
│   ├── fetch_price_data.py             OHLCV via yfinance
│   ├── fetch_fundamentals.py           Financials, ratios
│   ├── technical_indicators.py         RSI, MACD, Bollinger, ADX, ATR
│   ├── earnings.py                     EPS, surprises, analyst targets
│   ├── sentiment.py                    Analyst consensus, short interest
│   ├── news_collector.py              7-category daily news
│   ├── wiki_news_backfill.py          Wikipedia events (2019-2026)
│   └── data_loader.py                 Unified cache-then-fetch
│
├── data/
│   ├── fundamentals/                  96 stock financial files
│   └── news/                          405+ dates of archived events
│
├── runs/                           # Output per simulation run
│   └── {timestamp}_{period}/
│       ├── config.json                 Full params + feature flags
│       ├── shared/                     Market-level (regime, signals, conflicts)
│       └── portfolios/{Strategy}/      Trades, reasoning, memory, history
│
├── .claude/skills/
│   ├── stock-research.md              13-turn adversarial analysis
│   └── portfolio-watch.md             Daily portfolio monitoring
└── requirements.txt
```

---

## Comparison with Related Work

| | TradingAgents | AI-Trader | **StockTradeAgent** |
|--|--------------|-----------|---------------------|
| Cost | $5-100/day | $5-50/day | **$0** (simulation) |
| Deterministic | No | No | **Yes** |
| Test duration | 3 months | 5 weeks | **7 years, 7 regimes** |
| Universe | 3 stocks | NASDAQ-100 | **93 stocks, 15 sectors** |
| Strategies | LLM-only | LLM-only | **7 coded + LLM research** |
| Ablation | No | No | **Yes** |
| Beat QQQ (their period) | Claimed | 1 of 6 LLMs | **4 of 7 strategies** |
| Benchmarks | None | QQQ | **SPY + QQQ + ONEQ** |

## Data Sources (All Free)

| Source | Data |
|--------|------|
| yfinance | Prices, fundamentals, earnings, news |
| SEC EDGAR | 10-K, 10-Q, 8-K filings |
| Wikipedia | Historical world events (2019-2026) |
| GDELT | Real-time geopolitical events |

## License

MIT

---

*This is a research project, not financial advice. Past performance does not predict future results.*

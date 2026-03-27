# StockTradeAgent

A hybrid stock trading research system that combines **coded deterministic strategies** for backtesting with **LLM-powered adversarial debate** for live research. Built with Claude CLI (Opus 4.6) + Python, using only free data sources.

> **Key finding**: Our strategies don't beat QQQ in bull markets — but they cut drawdowns by 50-70% in crashes. The real value is downside protection, not alpha generation.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  TWO RUNTIME MODES                    │
├─────────────────────┬────────────────────────────────┤
│   SIMULATION        │   LIVE RESEARCH                │
│   (eval/)           │   (/stock-research skill)      │
│                     │                                │
│   Deterministic     │   LLM-powered                  │
│   Coded rules       │   Claude Opus 4.6              │
│   Free (no API)     │   13-turn debate               │
│   Reproducible      │   7 strategy judges            │
│   7 strategies      │   Structured audit trail       │
│   Daily event loop  │   Per-stock analysis           │
└─────────────────────┴────────────────────────────────┘
```

**Why the split?** Inspired by [TradingAgents](https://github.com/TauricResearch/TradingAgents) (UCLA/MIT) and [AI-Trader](https://github.com/HKUDS/AI-Trader) (HKU), but we keep simulation deterministic and free. LLM reasoning is reserved for live research where the adversarial debate structure genuinely improves analysis quality.

## Results: 7 Strategies × 7 Market Periods

All runs use $100K starting capital, 10 max positions, daily event-driven simulation.

### Return %

| Strategy | 2019 Bull | COVID Crash | 2023 AI Rally | Bull→Recession | 2022 Bear | Recession→Bull | 2025-Now |
|----------|----------|-------------|---------------|----------------|-----------|----------------|----------|
| **Value** | +3.8% | -7.1% | +4.6% | -4.9% | -4.5% | +0.3% | -1.0% |
| **Momentum** | +6.7% | -1.1% | +20.9% | -9.4% | +3.4% | +26.6% | +24.3% |
| **Balanced** | +9.1% | -3.5% | +13.4% | -10.6% | -11.3% | +8.3% | +3.4% |
| **Defensive** | +16.4% | -4.4% | +0.4% | **+13.6%** | -6.3% | -0.7% | +13.1% |
| **EventDriven** | +4.3% | -8.5% | +25.3% | -11.8% | -7.5% | +24.3% | +6.8% |
| **Adaptive** | +8.2% | **+5.2%** | +9.1% | -9.4% | -12.7% | +7.6% | **+25.7%** |
| **Commodity** | -3.2% | -2.4% | +1.2% | +15.9% | **+24.7%** | -4.2% | +23.4% |
| SPY B&H | +30.7% | -5.3% | +27.0% | -10.3% | -18.1% | +20.9% | +13.7% |
| QQQ B&H | +38.1% | +12.8% | +56.5% | -19.5% | -30.4% | +33.7% | +15.9% |

### Max Drawdown %

| Strategy | 2019 | COVID | 2023 | Bull→Rec | Recession | Rec→Bull | 2025 | **Worst Ever** |
|----------|------|-------|------|----------|-----------|----------|------|----------------|
| **Defensive** | -3.1% | -10.8% | -10.6% | **-6.7%** | -8.6% | -6.6% | **-5.1%** | **-10.8%** |
| **Value** | -3.6% | -8.8% | -4.5% | -7.7% | -6.2% | -2.7% | -5.5% | **-8.8%** |
| **Commodity** | -8.3% | -3.8% | -5.7% | -11.6% | -8.2% | -6.6% | -9.9% | **-11.6%** |
| SPY B&H | -6.6% | **-33.6%** | -9.9% | -22.9% | -24.4% | -7.5% | -18.7% | **-33.6%** |
| QQQ B&H | -11.0% | -28.6% | -10.8% | -32.6% | **-34.7%** | -11.2% | -22.7% | **-34.7%** |

**Defensive worst drawdown (-10.8%) is 3x better than SPY (-33.6%) and QQQ (-34.7%).**

## The 7 Strategies

| Strategy | Philosophy | Rebalance | Best Period | Worst Period |
|----------|-----------|-----------|-------------|--------------|
| **Value** | Buy cheap quality, hold through volatility | Quarterly | Steady markets | Bear (too slow) |
| **Momentum** | Follow price trends, ride winners | Monthly | AI Rally (+20.9%) | Bear transitions |
| **Balanced** | Equal weight fundamentals + momentum + stability | Monthly | Steady growth | Bear markets |
| **Defensive** | Minimize volatility, 3-state exposure scaling | Monthly | Bull→Rec (+13.6%) | Bull markets (+0.4%) |
| **EventDriven** | Trade earnings surprises and catalysts | Monthly | AI Rally (+25.3%) | Bear (-7.5%) |
| **Adaptive** | Switch modes by regime (momentum/value/defensive/recovery) | Monthly | COVID (+5.2%) | Deep bear (-12.7%) |
| **Commodity** | Track oil via USO/XLE, 50% max allocation | Monthly | 2022 Bear (+24.7%) | Bull markets (-3.2%) |

## Ablation Tests: What Actually Helps

We tested 5 risk overlay features individually. Each was turned on alone while all others were off.

### 2019 Bull Market (overlays should NOT hurt)

| Config | Avg Return | Cost vs Baseline |
|--------|-----------|-----------------|
| **Baseline (overlays off)** | +24.2% | — |
| + Cash floor only | +21.3% | -2.9% |
| + Conviction gate only | +10.1% | **-14.1%** |
| + Conflict detection only | +24.2% | 0.0% |
| All overlays on | +8.8% | -15.4% |

### 2022 Bear Market (overlays should help)

| Config | Avg Return | Benefit vs Baseline |
|--------|-----------|-------------------|
| **Baseline (overlays off)** | -12.3% | — |
| + Cash floor only | -11.0% | +1.3% |
| + Conviction gate only | -6.8% | +5.5% |
| + Conflict detection only | -12.0% | +0.3% |
| All overlays on | -6.3% | +6.0% |

### Decision: What We Keep

| Feature | Status | Reason |
|---------|--------|--------|
| **Partial fill** | ON | Bug fix, zero cost |
| **Cash floor (2%)** | ON | Minimal drag, small insurance |
| **Conflict detection** | LOGGING ONLY | Useful for debugging, zero cost when not sizing |
| **Conviction gate** | OFF | Costs 14% in bull to save 5% in bear — bad trade |
| **Consensus** | OFF | Strategies should be independent |

## Bugs Found & Fixed

Through 3 parallel audit agents (log audit, code flow trace, 7-period test):

| Bug | Impact | Fix |
|-----|--------|-----|
| `rebalance_frequency` never used | Value ran monthly instead of quarterly | Respects per-strategy frequency |
| `score_stocks()` corrupts `_last_regime` | Memory recorded fake regime names | Save/restore macro regime |
| 4/7 strategies buy NFLX earnings beat during bear market, lose 21.8% | Defensive buying high-vol earnings in crisis | Regime gate on earnings buys |
| Consensus never fires (persistence=2 too strict) | Safety mechanism provided zero protection | Lowered to 1 (then disabled) |
| `detect_raw()` called 7x per stock | 7x computation waste | Per-day cache |
| `_check_watchnotes()` called twice | Second call sees stale data | Removed daily call |
| Single trim blocks monthly rebalance | Strategy misses rebalance after profit-taking | Only SELL blocks rebalance |
| Bull/bear signals only fire on extreme regimes | Conviction gate dead during "normal" periods | Granular SPY MA signals |

## Live Research: 13-Turn Adversarial Debate

When you run `/stock-research AAPL`, Claude performs a structured analysis:

**Shared debate (5 turns about the stock):**
1. **Bull Analyst** — thesis + 3 facts + invalidation criteria
2. **Bear Analyst** — counter-thesis + 3 facts + concessions
3. **Bull Rebuttal** — addresses bear's strongest point
4. **Bear Rebuttal** — addresses bull's strongest point
5. **Moderator** — summarizes agreements/disagreements

**Per-strategy judges (7 turns, same data, different lens):**

| Judge | Weighs Heavily | Ignores |
|-------|---------------|---------|
| Value | P/E, margins, book value | Short-term price action |
| Momentum | Price trend, volume, breakouts | Valuation multiples |
| Defensive | Volatility, drawdown risk | Growth potential |
| EventDriven | Earnings dates, catalysts | Long-term fundamentals |
| Balanced | Everything equally | Nothing |
| Adaptive | Current market regime | Static analysis |
| Commodity | Energy/oil correlation | Stock-specific fundamentals |

**Synthesis (1 turn):** Cross-strategy verdict — which judges agree, who's most relevant.

All 13 turns are logged to `runs/research/{ticker}_{date}/` with structured JSON audit trails.

## Folder Structure

```
StockTradeAgent/
├── eval/                           # Simulation engine
│   ├── daily_loop.py                   Daily event-driven simulation
│   ├── signals.py                      Centralized signal computation
│   ├── triggers.py                     Event trigger detection (stops, earnings, volume)
│   ├── risk_overlay.py                 Conviction gate, consensus, conflict detection
│   ├── sim_memory.py                   Strategy memory (learns from past trades)
│   ├── events_data.py                  Earnings + SEC filing events
│   └── strategies/                     7 trading strategies
│       ├── base_strategy.py                Base class (partial fill, cash floor)
│       ├── value_strategy.py               Quarterly, contrarian
│       ├── momentum_strategy.py            12-minus-1 month signal
│       ├── balanced_strategy.py            Multi-factor adaptive weights
│       ├── defensive_strategy.py           3-state min-vol (NORMAL/REDUCED/DEFENSE)
│       ├── event_driven_strategy.py        Earnings drift + catalyst
│       ├── adaptive_strategy.py            4-mode regime switching
│       └── commodity_strategy.py           Oil tracking via USO/XLE
│
├── tools/                          # Data tools (all free sources)
│   ├── fetch_price_data.py             OHLCV via yfinance
│   ├── fetch_fundamentals.py           Income stmt, balance sheet
│   ├── technical_indicators.py         RSI, MACD, Bollinger, ADX
│   ├── fetch_news.py                   Company news (yfinance)
│   ├── fetch_filings.py               SEC EDGAR 10-K, 10-Q, 8-K
│   ├── macro_data.py                   S&P, VIX, yields, sector ETFs
│   ├── insider_activity.py             Insider buys/sells
│   ├── earnings.py                     EPS, surprises, analyst targets
│   ├── valuation.py                    DCF, peer comparison
│   ├── sentiment.py                    Analyst recs, short interest
│   ├── news_collector.py              Daily news collection (7 categories)
│   ├── wiki_news_backfill.py          Wikipedia historical events
│   ├── gdelt_backfill.py              GDELT geopolitical events
│   └── data_loader.py                 Unified data access (cache → fetch)
│
├── data/                           # Cached data
│   ├── news/{YYYY-MM-DD}/             Per-date news archive (380+ dates)
│   │   ├── geopolitical/                  GDELT + Wikipedia events
│   │   └── commodities/                   Oil, gold, copper
│   └── fundamentals/                  50 stock JSON files
│
├── runs/                           # All output
│   ├── {timestamp}_{period}_mp{N}/    Simulation runs
│   │   ├── config.json                    Params + feature flags
│   │   ├── summary.json                   Results table
│   │   ├── shared/                        Market-level data (same for all)
│   │   │   ├── regime_log.json
│   │   │   ├── signals_raw.json
│   │   │   └── conflicts_raw.json
│   │   └── portfolios/{Strategy}/         Per-strategy decisions
│   │       ├── transactions.csv
│   │       ├── reasoning.json
│   │       ├── conviction_log.json
│   │       ├── conflicts.json
│   │       └── memory.json
│   └── research/{ticker}_{date}/      Live research output
│       ├── debate/turns.json              5-turn bull/bear debate
│       ├── judges/{Strategy}.json         7 strategy verdicts
│       └── report.md                      Human-readable report
│
├── .claude/skills/                 # Claude CLI skills
│   ├── stock-research.md              13-turn adversarial analysis
│   └── portfolio-watch.md             Daily portfolio monitoring
│
├── portfolio/watchlist.json        # Real positions (for live agent)
├── tests/                          # Unit + integration tests
├── requirements.txt
└── CLAUDE.md                       # Claude CLI project instructions
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Collect today's news
python tools/daily_collect.py

# Run a single simulation period
python eval/daily_loop.py --period recession --max-positions 10

# Run all 7 periods
python eval/daily_loop.py --period normal --max-positions 10
python eval/daily_loop.py --period black_swan --max-positions 10
python eval/daily_loop.py --period bull --max-positions 10
python eval/daily_loop.py --period bull_to_recession --max-positions 10
python eval/daily_loop.py --period recession --max-positions 10
python eval/daily_loop.py --period recession_to_bull --max-positions 10
python eval/daily_loop.py --period 2025_to_now --max-positions 10

# Live stock research (requires Claude CLI)
/stock-research AAPL
```

### Simulation Periods

| Period | Dates | Regime | What It Tests |
|--------|-------|--------|---------------|
| `normal` | 2019-01-02 to 2019-12-31 | Steady bull | Baseline performance |
| `black_swan` | 2020-01-02 to 2020-06-30 | COVID crash | Crisis response |
| `bull` | 2023-01-02 to 2023-12-29 | AI rally | Growth capture |
| `bull_to_recession` | 2021-07-01 to 2022-06-30 | Transition | Regime detection |
| `recession` | 2022-01-03 to 2022-10-31 | Bear market | Capital preservation |
| `recession_to_bull` | 2022-10-01 to 2023-06-30 | Recovery | Re-entry timing |
| `2025_to_now` | 2025-01-02 to 2026-03-24 | Current | Real-world validation |

## Data Sources (All Free)

| Source | What | Rate Limits |
|--------|------|-------------|
| **yfinance** | Prices, fundamentals, earnings, news | None |
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings, XBRL | 10 req/sec |
| **Wikipedia Current Events** | Historical world events (backfilled 2019-2026) | None |
| **GDELT** | Real-time geopolitical events | Moderate |
| **Google News RSS** | Macro/economic headlines | None |

## Design Decisions

### Why not pure LLM trading?
Both [TradingAgents](https://arxiv.org/abs/2412.20138) and [AI-Trader](https://arxiv.org/abs/2512.10971) use LLMs as the entire trading brain. Our testing found:
- LLM calls are expensive ($0.50-2/ticker/day)
- Non-deterministic (same data → different decisions each run)
- AI-Trader found "general intelligence ≠ trading capability" — GPT-5 and Gemini failed to generate alpha

Our approach: **coded strategies for deterministic backtesting, LLM only for live research analysis.**

### Why are most overlays disabled?
Ablation proved the conviction gate (market timing via MA position) costs 14% in bull markets to save 5% in bear markets. That's a bad trade. Simple strategies with minimal filtering outperform over-engineered meta-filters.

### Shared detection → per-strategy interpretation
Inspired by TradingAgents' architecture: analyst reports are shared facts, risk personas interpret them differently. Same market data, same conflicts detected — but each strategy judge weighs them through its own lens (Value ignores RSI, Momentum ignores valuation).

## Comparison with Related Work

| Aspect | TradingAgents | AI-Trader | **StockTradeAgent** |
|--------|--------------|-----------|---------------------|
| LLM cost/day | $5-100 | $5-50 | **$0** (simulation) |
| Deterministic | No | No | **Yes** |
| Backtest periods | 3 months | 5 weeks | **7 periods, 2019-2026** |
| Walk-forward test | No | No | **Yes** |
| Ablation testing | No | No | **Yes (5 features)** |
| Strategies | LLM-only | LLM-only | **7 coded + LLM research** |
| Drawdown control | LLM reasoning | LLM cash mgmt | **ATR stops + 3-state defense** |

## License

MIT

## Disclaimer

This is a research project, not financial advice. Past backtest performance does not predict future results. Always do your own research before making investment decisions.

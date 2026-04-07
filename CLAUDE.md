# ConsensusAITrader

9-strategy consensus trading system with LLM risk monitor. Claude Opus 4.6 does reasoning, Python tools handle data.

## Skills
- `/stock-research TICKER` — Deep analysis of a single stock
- `/portfolio-watch` — Daily check on all portfolio positions

## Architecture

```
Stock Research/
├── .claude/skills/           # Claude CLI skills (the live agent)
│   ├── stock-research.md
│   └── portfolio-watch.md
│
├── tools/                    # Python data tools (shared, all free)
│   ├── fetch_price_data.py       OHLCV, 52w range, volatility
│   ├── fetch_fundamentals.py     Income stmt, balance sheet, ratios
│   ├── technical_indicators.py   RSI, MACD, MAs, Bollinger, ADX
│   ├── fetch_news.py             Company news (yfinance)
│   ├── fetch_filings.py          SEC EDGAR 10-K, 10-Q, 8-K, XBRL
│   ├── macro_data.py             S&P, VIX, yields, sector ETFs
│   ├── insider_activity.py       Insider buys/sells
│   ├── earnings.py               EPS, surprises, analyst targets
│   ├── valuation.py              DCF, peer comparison
│   ├── sentiment.py              Analyst recs, short interest
│   ├── backtest.py               Walk-forward eval, scenarios
│   ├── news_collector.py         Daily news collection (7 categories)
│   ├── daily_collect.py          Auto-fill gaps + collect today
│   ├── article_summarizer.py     Extract article summaries from URLs
│   ├── wiki_news_backfill.py     Wikipedia historical events (free)
│   ├── gdelt_backfill.py         GDELT geopolitical events
│   └── config.py                 SEC User-Agent, optional FRED key
│
├── data/news/                # Shared news archive (381+ dates)
│   └── {YYYY-MM-DD}/            Per-date folders
│       ├── company/                Per-ticker news (AAPL.json, etc.)
│       ├── geopolitical/           GDELT + Wikipedia events
│       ├── macro/                  Fed, rates, inflation (RSS)
│       ├── commodities/            Oil, gold, copper prices + news
│       ├── currencies/             USD, EUR/USD, yields
│       ├── sectors/                11 sector ETFs + rotation
│       └── sentiment/              VIX, market breadth
│
├── eval/                     # Simulation engine
│   ├── daily_loop.py             Daily event-driven simulation
│   ├── run_full_sweep.py         Parameter sweep (periods × positions × cash)
│   ├── signals.py                Centralized signal computation
│   ├── triggers.py               Event trigger detection
│   ├── risk_overlay.py           Conviction gate, consensus, conflict detection
│   ├── sim_memory.py             Memory read/write for learning
│   ├── events_data.py            Earnings + SEC filing events
│   ├── prefetch_prices.py        Pre-fetch and cache price data
│   ├── run_param_sweep.py        Frequency/exec/mp parameter sweep
│   ├── run_improvement_sweep.py  Ablation sweep for improvement features
│   ├── validate_premarket_proxy.py  Validate premarket price proxy
│   ├── validate_premarket_e2e.py    End-to-end proxy validation
│   └── strategies/               9 trading strategies
│       ├── base_strategy.py          Base class (partial fill, cash floor, reasoning)
│       ├── value_strategy.py         Low-vol, beaten-down quality
│       ├── momentum_strategy.py      Price trend, MACD, volume
│       ├── balanced_strategy.py      Adaptive weights + news-aware
│       ├── defensive_strategy.py     Rotates to cash on danger
│       ├── event_driven_strategy.py  Reacts to earnings/events
│       ├── adaptive_strategy.py      Switches modes by regime
│       ├── commodity_strategy.py     Oil tracking
│       ├── mix_strategy.py           Regime-detecting multi-asset allocator
│       └── mix_llm_strategy.py       LLM-powered regime detection (Claude Haiku)
│
├── runs/                     # ALL output (sim + research)
│   │
│   ├── {timestamp}_{period}_mp{N}/      # SIMULATION RUNS
│   │   ├── config.json                      Run params + feature flags
│   │   ├── summary.json                     Results comparison
│   │   ├── trigger_log.json                 All triggers that fired
│   │   ├── shared/                          SHARED (computed once for all strategies)
│   │   │   ├── regime_log.json                Daily macro regime + news
│   │   │   ├── consensus_log.json             Cross-strategy consensus signal
│   │   │   └── conflict_log.json              Per-ticker signal contradictions
│   │   └── portfolios/                      PER-STRATEGY
│   │       └── {Strategy}/
│   │           ├── state.json                   Final portfolio
│   │           ├── transactions.csv             Every trade (incl partial fills)
│   │           ├── reasoning.json               WHY each trade + risk overlay notes
│   │           ├── conviction_log.json          Bull/bear signal tally per stock
│   │           ├── memory.json                  What strategy learned
│   │           ├── history.json                 Daily value snapshots
│   │           └── watchnotes.json              Active observations
│   │
│   └── research/                            # LIVE RESEARCH RUNS
│       └── {ticker}_{date}/
│           ├── report.md                        Full analysis (human-readable)
│           ├── debate.json                      5-turn bull/bear/judge debate log
│           ├── data_collected.json              Raw tool outputs
│           └── contradiction_scan.json          Signal conflicts found
│
├── portfolio/watchlist.json  # Your real positions (for live agent)
├── tests/                    # Unit + integration tests
├── requirements.txt
└── CLAUDE.md
```

## Running

```bash
# Daily news collection
python tools/daily_collect.py

# Pre-fetch price data (run once, future sims load from cache)
python eval/prefetch_prices.py

# Single simulation (defaults: premarket exec, biweekly, mp=10)
python eval/daily_loop.py --start 2025-01-02 --end 2026-03-24 --max-positions 10

# Override frequency
python eval/daily_loop.py --period 2025_to_now --frequency monthly

# Legacy mode (no realism, for comparison)
python eval/daily_loop.py --period normal --no-realistic --exec-model open

# Full parameter sweep (7 periods x 3 positions x 3 cash = 63 runs)
python eval/run_full_sweep.py

# Quick sweep (7 periods, mp=10, $100k only)
python eval/run_full_sweep.py --quick

# Frequency/param sweep
python eval/run_param_sweep.py --quick

# Improvement feature ablation (Chandelier, cooldown, breadth)
python eval/run_improvement_sweep.py --quick

# Tests
python -m pytest tests/ -v
```

## Data Sources (all free)
- **yfinance** — prices, fundamentals, earnings, news
- **SEC EDGAR** — filings, XBRL structured data
- **Wikipedia Current Events** — historical world events (backfilled 2019-2026)
- **GDELT** — real-time geopolitical events
- **Google News RSS** — macro/economic headlines
- **FRED** — macro data (optional, needs free API key)

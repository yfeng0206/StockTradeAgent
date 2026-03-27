# StockTradeAgent

A stock trading research system combining **7 deterministic strategies** for backtesting with **LLM-powered adversarial debate** for live research. Built with Claude CLI (Opus 4.6) + Python, all free data sources.

> **Momentum +33.5% and EventDriven +34.3% beat both SPY (+26%) and QQQ (+28.8%) in full-year 2024.** Tested across 7 market regimes from 2019-2026.

## Head-to-Head: Same Period as TradingAgents & AI-Trader Papers

We reproduced the exact test periods from published LLM trading papers:

### TradingAgents Period (Jan–Mar 2024)

*Paper claims +26.6% on AAPL (which actually lost -7.5%) with Sharpe 8.2 in 3 months on 3 stocks.*

| Strategy | Return | Sharpe | MaxDD | vs QQQ (+10.4%) |
|----------|--------|--------|-------|-----------------|
| **Momentum** | **+16.8%** | 3.94 | -2.5% | **+6.4%** |
| Adaptive | +12.6% | 2.78 | -4.0% | +2.2% |
| EventDriven | +11.7% | 3.60 | -2.2% | +1.3% |
| SPY B&H | +11.0% | 4.07 | -1.7% | — |
| QQQ B&H | +10.4% | 2.77 | -2.6% | — |

**4 of 7 strategies beat QQQ.** Momentum beats it by 6.4 points — on 50 stocks, not 3.

### AI-Trader Period (Oct–Nov 2025)

*Paper's best agent (MiniMax-M2): +9.56% vs QQQ +1.4%. But GPT-5 got only +1.56%, Gemini -0.06%.*

| Strategy | Return | vs QQQ (+1.4%) |
|----------|--------|----------------|
| **EventDriven** | **+3.3%** | **+1.9%** |
| Adaptive | +2.5% | +1.1% |
| QQQ B&H | +1.4% | — |
| SPY B&H | +0.3% | — |

**EventDriven beats QQQ** — and it's deterministic (same result every run), unlike their LLM which varies.

### Extended: Full Year 2024 (12 months, not 3)

Short test periods flatter everyone. Here's what happens when you extend to a full year:

| Strategy | Return | Sharpe | MaxDD | vs SPY | vs QQQ |
|----------|--------|--------|-------|--------|--------|
| **EventDriven** | **+34.3%** | 2.22 | -4.9% | **+8.3%** | **+5.5%** |
| **Momentum** | **+33.5%** | 2.04 | -8.8% | **+7.5%** | **+4.7%** |
| Adaptive | +23.9% | 1.42 | -9.2% | -2.1% | -4.9% |
| SPY B&H | +26.0% | 1.92 | -8.4% | — | — |
| QQQ B&H | +28.8% | 1.51 | -13.5% | — | — |

**Momentum and EventDriven beat BOTH benchmarks over a full year** — not just a cherry-picked 3-month window.

## Results: 7 Strategies × 7 Market Regimes (2019–2026)

$100K starting capital, 10 max positions, daily event-driven simulation.

### Return %

| Strategy | 2019 Bull | COVID | 2023 AI | Bull→Rec | 2022 Bear | Rec→Bull | 2025-Now |
|----------|----------|-------|---------|----------|-----------|----------|----------|
| **Value** | +3.8% | -7.1% | +4.6% | -4.9% | -7.4% | +0.3% | -1.0% |
| **Momentum** | +6.7% | -1.1% | +20.9% | -9.4% | -11.6% | +26.6% | +24.3% |
| **Balanced** | +9.1% | -3.5% | +13.4% | -10.6% | -11.6% | +8.3% | +3.4% |
| **Defensive** | +16.4% | -4.4% | +0.4% | **+13.6%** | -5.8% | -0.7% | +13.1% |
| **EventDriven** | +4.3% | -8.5% | **+25.3%** | -11.8% | -18.7% | +24.3% | +6.8% |
| **Adaptive** | +8.2% | **+5.2%** | +9.1% | -9.4% | -21.9% | +7.6% | **+25.7%** |
| **Commodity** | -3.2% | -2.4% | +1.2% | +15.9% | **+24.7%** | -4.2% | +23.4% |
| SPY B&H | +30.7% | -5.3% | +27.0% | -10.3% | -17.6% | +20.9% | +13.7% |
| QQQ B&H | +38.1% | +12.8% | +56.5% | -19.5% | -29.6% | +33.7% | +15.9% |

### Max Drawdown %

| Strategy | Worst Ever | When |
|----------|-----------|------|
| **Defensive** | **-11.8%** | 2022 Bear |
| **Commodity** | **-10.0%** | 2025 |
| **Value** | **-16.5%** | 2022 Bear |
| SPY B&H | **-33.6%** | COVID |
| QQQ B&H | **-34.7%** | 2022 Bear |

Defensive's worst drawdown (-11.8%) is 3x better than SPY (-33.6%) and QQQ (-34.7%).

## The 7 Strategies

### Value
**Philosophy**: Buy fundamentally cheap, high-quality stocks trading below intrinsic value. Hold through volatility — the market will come to you.
- Scores: low P/E proxy, high margins, low volatility, beaten-down price, earnings momentum
- Rebalances quarterly (least frequent — avoids overtrading)
- ATR stop: 3.0x (widest — gives positions room to recover)
- Best at: steady markets where fundamentals matter
- Worst at: bear markets (too slow to react)

### Momentum
**Philosophy**: Follow price. Stocks going up tend to keep going up. Buy strength, sell weakness.
- Uses academic 12-minus-1 month signal (skip most recent month to avoid reversal)
- Scores: price above MAs, positive returns, MACD bullish, volume confirmation
- ATR stop: 2.5x
- Best at: rallies and recoveries (+33.5% in 2024, +26.6% recession→bull)
- Worst at: transitions and choppy markets

### Balanced
**Philosophy**: No single factor dominates. Weigh fundamentals, momentum, and stability equally.
- Renamed from "Quality" — scores value (40%), momentum (10%), stability (50%)
- Most diversified approach, adapts weights slightly by regime
- ATR stop: 2.0x
- Best at: steady growth environments
- Worst at: strong directional markets (underweights the winning factor)

### Defensive
**Philosophy**: Capital preservation first. I'd rather miss gains than take losses.
- 3-state exposure: NORMAL (100%), REDUCED (50%), DEFENSE (20%)
- Counts danger signals (volatility, trend break, drawdown) → scales down
- Scores by lowest volatility + trend + drawdown history
- ATR stop: 1.5x (tightest — cuts losers fast)
- Best at: transitions (+13.6% bull→recession while others lost)
- Worst at: bull markets (+0.4% in AI rally — too cautious)

### EventDriven
**Philosophy**: Trade catalysts. Earnings surprises, SEC filings, volume anomalies — events move prices.
- Hard eligibility gate: ONLY scores stocks with recent earnings or 8-K filing
- Buys strong beats (earnings drift), sells strong misses
- Regime-gated: won't buy earnings during crisis (learned from NFLX bug)
- ATR stop: 2.0x
- Best at: earnings seasons in bull markets (+34.3% in 2024)
- Worst at: bear markets where every beat gets sold off

### Adaptive
**Philosophy**: What regime are we in? That determines everything.
- 4 modes: MOMENTUM (bull), VALUE (sideways), DEFENSIVE (bear), RECOVERY (bounce)
- Detects regime via SPY MAs, volatility, sector rotation
- Delegates scoring to the matching mode's logic
- ATR stop: 2.0x
- Best at: COVID (+5.2% — only strategy positive), current market (+25.7%)
- Worst at: deep bear where regime detection lags (-21.9%)

### Commodity
**Philosophy**: Track oil. When inflation/geopolitics spike, oil outperforms everything.
- Single instrument (USO/XLE), 50% max allocation, rest in cash
- Scores: oil above MAs, positive 1m/3m returns, RSI not overbought
- Max 1 position — can go 100% cash if bearish
- Best at: inflation/crisis (+24.7% in 2022 bear, +23.4% in 2025 tariff era)
- Worst at: normal bull markets where tech leads (-3.2% in 2019)

## Ablation: What Helps, What Hurts

We tested 5 risk overlay features. Each turned on alone, measured on bull + bear:

| Feature | Bull Market Cost | Bear Market Benefit | **Net** | **Status** |
|---------|-----------------|-------------------|---------|-----------|
| Cash floor (2%) | -2.9% | +1.3% | -1.6% | ON (insurance) |
| Conviction gate | -14.1% | +5.5% | **-8.6%** | OFF (market timing) |
| Conflict detection | 0.0% | +0.3% | 0.0% | LOGGING ONLY |
| Consensus | 0.0% | 0.0% | 0.0% | OFF (strategies independent) |
| Partial fill | 0.0% | 0.0% | 0.0% | ON (bug fix) |

**Key finding**: The conviction gate is market timing in disguise. It costs $2.50 in bull markets for every $1 it saves in bear markets. Removed.

## Bugs Found & Fixed

8 bugs discovered through 3 parallel audit agents:

| Bug | Impact | Fix |
|-----|--------|-----|
| `rebalance_frequency` ignored | Value ran monthly instead of quarterly | Per-strategy frequency |
| `score_stocks()` corrupts `_last_regime` | Memory recorded fake regime names | Save/restore macro regime |
| 4/7 strategies buy NFLX in bear, lose 21.8% | Defensive buying high-vol earnings in crisis | Regime gate on earnings |
| `detect_raw()` called 7x per stock | 7x wasted computation | Per-day cache |
| `_check_watchnotes()` called twice | Second call sees stale data | Removed daily call |
| Single trim blocks monthly rebalance | Missed rebalance after profit-take | Only SELL blocks rebalance |
| Bull/bear signals only on extreme regimes | Conviction gate dead in "normal" | Granular SPY MA signals |
| Consensus never fires | Persistence=2 too strict | Fixed then disabled |

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
│   Free ($0)         │   13-turn debate               │
│   Reproducible      │   7 strategy judges            │
│   7 strategies      │   Structured audit trail       │
│   Daily event loop  │   Per-stock deep analysis      │
└─────────────────────┴────────────────────────────────┘
```

The simulation uses coded rules (deterministic, free). The live `/stock-research` skill uses Claude for adversarial debate (5-turn bull/bear + 7 strategy judges + synthesis). Both save structured logs.

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
```

## Folder Structure

```
StockTradeAgent/
├── eval/                           # Simulation engine
│   ├── daily_loop.py                   Daily event-driven simulation
│   ├── signals.py                      Centralized signal computation
│   ├── triggers.py                     Stop-loss, earnings, volume, regime triggers
│   ├── risk_overlay.py                 Cash floor + conflict logging (feature-flagged)
│   ├── sim_memory.py                   Strategy memory (learns from past trades)
│   ├── events_data.py                  Earnings calendar from yfinance
│   └── strategies/                     7 trading strategies
│       ├── base_strategy.py                Base (partial fill, cash floor, reasoning)
│       ├── value_strategy.py               Quarterly contrarian
│       ├── momentum_strategy.py            12-minus-1 month trend following
│       ├── balanced_strategy.py            Multi-factor (value+momentum+stability)
│       ├── defensive_strategy.py           3-state min-volatility
│       ├── event_driven_strategy.py        Earnings drift + catalyst
│       ├── adaptive_strategy.py            4-mode regime switching
│       └── commodity_strategy.py           Oil tracking via USO/XLE
│
├── tools/                          # Data tools (all free)
│   ├── fetch_price_data.py             OHLCV via yfinance
│   ├── fetch_fundamentals.py           Income stmt, balance sheet, ratios
│   ├── technical_indicators.py         RSI, MACD, Bollinger, ADX, ATR
│   ├── earnings.py                     EPS, surprises, analyst targets
│   ├── sentiment.py                    Analyst consensus, short interest
│   ├── insider_activity.py             Insider buys/sells
│   ├── news_collector.py              7-category daily news collection
│   ├── wiki_news_backfill.py          Wikipedia events (2019-2026)
│   └── data_loader.py                 Unified cache → fetch access
│
├── data/                           # Cached data
│   ├── news/{date}/geopolitical/       405 dates of world events
│   └── fundamentals/                  50 stock financials (5yr annual + quarterly)
│
├── runs/                           # Output (7 curated period runs)
│   └── {timestamp}_{period}_mp{N}/
│       ├── config.json                 Params + feature flags
│       ├── shared/                     Market-level (regime, signals, conflicts)
│       └── portfolios/{Strategy}/      Per-strategy (trades, reasoning, memory)
│
├── .claude/skills/
│   ├── stock-research.md              13-turn adversarial analysis
│   └── portfolio-watch.md             Daily portfolio monitoring
└── requirements.txt
```

## Comparison with Related Work

| Aspect | TradingAgents | AI-Trader | **StockTradeAgent** |
|--------|--------------|-----------|---------------------|
| Cost | $5-100/day | $5-50/day | **$0** (simulation) |
| Deterministic | No | No | **Yes** |
| Test duration | 3 months | 5 weeks | **7 years, 7 regimes** |
| Universe | 3 stocks | NASDAQ-100 | **50 large-cap** |
| Ablation testing | No | No | **Yes (5 features)** |
| Walk-forward | No | No | **Yes** |
| Beat QQQ (their period) | Claimed | 1 of 6 LLMs | **4 of 7 strategies** |
| Beat QQQ (full year) | Not tested | Not tested | **2 of 7 strategies** |

## Data Sources (All Free)

| Source | Data | Rate Limits |
|--------|------|-------------|
| yfinance | Prices, fundamentals, earnings, news | None |
| SEC EDGAR | 10-K, 10-Q, 8-K filings | 10 req/sec |
| Wikipedia | Historical world events (backfilled) | None |
| GDELT | Real-time geopolitical events | Moderate |

## License

MIT

---

*This is a research project, not financial advice. Past backtest performance does not predict future results.*

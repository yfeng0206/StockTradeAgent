# StockTradeAgent

A stock trading research system combining **7 deterministic strategies** for backtesting with **LLM-powered adversarial debate** for live research. Built with Claude CLI (Opus 4.6) + Python, all free data sources.

> **93-stock universe across 15 sectors.** Value +38.9% in 2019, Adaptive +47.2% in 2023 AI Rally, Commodity +24.7% in 2022 bear. Tested across 7 market regimes from 2019-2026.

## Head-to-Head: Same Period as TradingAgents and AI-Trader Papers

We reproduced the exact test periods from published LLM trading papers:

### TradingAgents Period (Jan-Mar 2024)

*Paper claims +26.6% on AAPL (which actually lost -7.5%) with Sharpe 8.2 in 3 months on 3 stocks.*

| Strategy | Return | Sharpe | MaxDD | vs QQQ (+10.4%) |
|----------|--------|--------|-------|-----------------|
| **Momentum** | **+16.8%** | 3.94 | -2.5% | **+6.4%** |
| Adaptive | +12.6% | 2.78 | -4.0% | +2.2% |
| EventDriven | +11.7% | 3.60 | -2.2% | +1.3% |
| SPY B&H | +11.0% | 4.07 | -1.7% | -- |
| QQQ B&H | +10.4% | 2.77 | -2.6% | -- |

**4 of 7 strategies beat QQQ.** Momentum beats it by 6.4 points -- on 93 stocks, not 3.

### AI-Trader Period (Oct-Nov 2025)

*Paper's best agent (MiniMax-M2): +9.56% vs QQQ +1.4%. But GPT-5 got only +1.56%, Gemini -0.06%.*

| Strategy | Return | vs QQQ (+1.4%) |
|----------|--------|----------------|
| **EventDriven** | **+3.3%** | **+1.9%** |
| Adaptive | +2.5% | +1.1% |
| QQQ B&H | +1.4% | -- |
| SPY B&H | +0.3% | -- |

**EventDriven beats QQQ** -- and it's deterministic (same result every run), unlike their LLM which varies.

### Extended: Full Year 2024 (12 months, not 3)

Short test periods flatter everyone. Here's what happens when you extend to a full year:

| Strategy | Return | Sharpe | MaxDD | vs SPY | vs QQQ |
|----------|--------|--------|-------|--------|--------|
| **EventDriven** | **+34.3%** | 2.22 | -4.9% | **+8.3%** | **+5.5%** |
| **Momentum** | **+33.5%** | 2.04 | -8.8% | **+7.5%** | **+4.7%** |
| Adaptive | +23.9% | 1.42 | -9.2% | -2.1% | -4.9% |
| SPY B&H | +26.0% | 1.92 | -8.4% | -- | -- |
| QQQ B&H | +28.8% | 1.51 | -13.5% | -- | -- |

**Momentum and EventDriven beat BOTH benchmarks over a full year.**

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

Some later-IPO stocks (CRWD, UBER, ABNB, DASH, COIN, PLTR) have no data for early periods -- the engine skips unavailable tickers gracefully.

## Results: 7 Strategies x 7 Market Regimes (2019-2026)

$100K starting capital, 10 max positions, 93-stock universe, daily event-driven simulation.

### Return %

| Strategy | 2019 Bull | COVID | 2023 AI | Bull-Rec | 2022 Bear | Rec-Bull | 2025-Now |
|----------|----------|-------|---------|----------|-----------|----------|----------|
| **Value** | **+38.9%** | **+16.0%** | +30.4% | -7.2% | -15.5% | +18.4% | -5.4% |
| **Momentum** | +35.5% | +9.5% | +20.1% | -19.3% | -24.9% | +28.5% | +4.5% |
| **Balanced** | +18.6% | -7.2% | +15.0% | -7.7% | -9.4% | +21.5% | -4.1% |
| **Defensive** | +21.6% | -7.2% | -2.4% | **+16.1%** | **-3.4%** | +0.8% | +5.6% |
| **EventDriven** | +14.0% | -5.3% | **+37.9%** | -19.5% | -18.7% | **+28.9%** | +11.9% |
| **Adaptive** | +23.0% | +5.7% | **+47.2%** | -0.2% | -24.5% | +21.3% | +13.6% |
| **Commodity** | -3.2% | -2.4% | +1.2% | +15.9% | **+24.7%** | -4.2% | **+23.4%** |
| SPY B&H | +30.7% | -5.3% | +27.0% | -10.3% | -17.6% | +20.9% | +13.7% |
| QQQ B&H | +38.1% | +12.8% | +56.5% | -19.5% | -29.6% | +33.7% | +15.9% |
| ONEQ B&H | +36.1% | +8.8% | +47.2% | -21.8% | -29.0% | +26.8% | +14.6% |

### Max Drawdown %

| Strategy | 2019 | COVID | 2023 | Bull-Rec | Recess | Rec-Bull | 2025 | **Worst** |
|----------|------|-------|------|----------|--------|----------|------|-----------|
| **Defensive** | -3.0% | -14.2% | -10.3% | **-5.5%** | **-10.1%** | -10.0% | -13.0% | **-14.2%** |
| **Commodity** | -8.3% | **-3.8%** | -5.7% | -11.6% | -8.2% | -6.6% | -9.9% | **-11.6%** |
| **Value** | -8.9% | -11.7% | -6.7% | -16.0% | -22.1% | -6.5% | -13.1% | **-22.1%** |
| SPY B&H | -6.6% | **-33.6%** | -9.9% | -22.9% | -24.4% | -7.5% | -18.7% | **-33.6%** |
| QQQ B&H | -11.0% | -28.6% | -10.8% | -32.6% | **-34.7%** | -11.2% | -22.7% | **-34.7%** |
| ONEQ B&H | -10.1% | -30.2% | -11.9% | -32.9% | -33.9% | -11.1% | -23.6% | **-33.9%** |

Defensive worst drawdown (-14.2%) is 2.4x better than SPY (-33.6%) and QQQ (-34.7%).

### Sharpe Ratio

| Strategy | 2019 | COVID | 2023 | Bull-Rec | Recess | Rec-Bull | 2025 |
|----------|------|-------|------|----------|--------|----------|------|
| **Value** | **2.63** | **1.55** | **2.19** | -0.65 | -1.25 | 1.58 | -0.32 |
| **Momentum** | 1.96 | 0.80 | 1.14 | -0.73 | -1.35 | **1.93** | 0.28 |
| **Defensive** | **2.34** | -1.26 | -0.20 | **1.49** | -0.38 | 0.15 | 0.49 |
| **Adaptive** | 1.42 | 0.62 | **2.05** | 0.08 | -1.84 | 1.30 | 0.62 |
| **Commodity** | -0.33 | -1.30 | 0.21 | 0.87 | **1.82** | -0.95 | **1.18** |
| SPY B&H | 2.22 | -0.03 | 1.92 | -0.45 | -0.84 | 1.49 | 0.67 |
| QQQ B&H | 2.09 | 0.78 | 2.64 | -0.68 | -1.16 | 1.74 | 0.66 |
| ONEQ B&H | 2.07 | 0.61 | 2.38 | -0.82 | -1.16 | 1.50 | 0.60 |

## The 7 Strategies

### Value
**Philosophy**: Buy fundamentally cheap, high-quality stocks trading below intrinsic value. Hold through volatility.
- Scores: low P/E proxy, high margins, low volatility, beaten-down price, earnings momentum
- Rebalances quarterly (avoids overtrading)
- ATR stop: 3.0x (widest -- gives positions room)
- Best at: bull markets with the expanded universe (+38.9% in 2019, +30.4% in 2023)
- Worst at: bear markets (-15.5% in recession)

### Momentum
**Philosophy**: Follow price. Stocks going up tend to keep going up. Buy strength, sell weakness.
- Academic 12-minus-1 month signal (skip most recent month to avoid reversal)
- Scores: price above MAs, positive returns, MACD bullish, volume confirmation
- ATR stop: 2.5x
- Best at: rallies and recoveries (+35.5% in 2019, +28.5% recession-to-bull)
- Worst at: bear markets and transitions (-24.9% recession)

### Balanced
**Philosophy**: No single factor dominates. Weigh fundamentals, momentum, and stability equally.
- Scores value (40%), momentum (10%), stability (50%)
- ATR stop: 2.0x
- Best at: steady growth (+21.5% recovery)
- Worst at: bear markets (-9.4% recession)

### Defensive
**Philosophy**: Capital preservation first. Miss gains rather than take losses.
- 3-state exposure: NORMAL (100%), REDUCED (50%), DEFENSE (20%)
- Counts danger signals (volatility, trend break, drawdown) to scale down
- ATR stop: 1.5x (tightest)
- Best at: transitions (+16.1% bull-to-recession, only strategy positive)
- Worst at: strong bull markets (-2.4% AI rally)

### EventDriven
**Philosophy**: Trade catalysts. Earnings surprises move prices.
- Hard eligibility gate: ONLY scores stocks with recent earnings or 8-K filing
- Regime-gated: won't buy earnings during crisis (NFLX bug fix)
- ATR stop: 2.0x
- Best at: earnings seasons in growth markets (+37.9% AI rally, +34.3% full 2024)
- Worst at: bear markets (-18.7% recession)

### Adaptive
**Philosophy**: What regime are we in? That determines everything.
- 4 modes: MOMENTUM (bull), VALUE (sideways), DEFENSIVE (bear), RECOVERY (bounce)
- Detects regime via SPY MAs, volatility, sector rotation
- ATR stop: 2.0x
- Best at: AI rally (+47.2%), COVID (+5.7% while SPY lost -5.3%)
- Worst at: deep bear where detection lags (-24.5% recession)

### Commodity
**Philosophy**: Track oil. When inflation/geopolitics spike, oil outperforms everything.
- Single instrument (USO/XLE), 50% max allocation, rest in cash
- Max 1 position -- can go 100% cash if bearish
- Best at: inflation (+24.7% recession, +23.4% tariff era 2025)
- Worst at: normal bull markets (-3.2% in 2019)

## Ablation: What Helps, What Hurts

Tested on 93-stock universe. Each overlay turned on alone:

### 2019 Bull Market

| Config | Avg Return | Cost vs Baseline |
|--------|-----------|-----------------|
| **Baseline (overlays off)** | +26.5% | -- |
| + Cash floor (2%) | +25.3% | -1.2% |
| Default (cash floor only) | +25.3% | -1.2% |

### 2022 Bear Market

| Config | Avg Return | Benefit vs Baseline |
|--------|-----------|-------------------|
| **Baseline (overlays off)** | -16.2% | -- |
| + Cash floor (2%) | -16.1% | +0.1% |
| Default (cash floor only) | -16.1% | +0.1% |

Cash floor now costs only 1.2% in bull (was 2.9% with old 5% floor). Conviction gate and consensus remain OFF -- they were proven harmful in earlier ablation with 50-stock universe.

## Bugs Found and Fixed

8 bugs discovered through 3 parallel audit agents:

| Bug | Impact | Fix |
|-----|--------|-----|
| `rebalance_frequency` ignored | Value ran monthly instead of quarterly | Per-strategy frequency |
| `score_stocks()` corrupts `_last_regime` | Memory recorded fake regime names | Save/restore macro regime |
| 4/7 strategies buy NFLX in bear, lose 21.8% | Defensive buying high-vol earnings in crisis | Regime gate on earnings |
| `detect_raw()` called 7x per stock | 7x wasted computation | Per-day cache |
| `_check_watchnotes()` called twice | Second call sees stale data | Removed daily call |
| Single trim blocks monthly rebalance | Missed rebalance after profit-take | Only SELL blocks rebalance |
| Bull/bear signals only on extreme regimes | Conviction gate dead in normal periods | Granular SPY MA signals |
| Consensus never fires | Persistence=2 too strict | Fixed then disabled |

## Architecture

```
+------------------------------------------------------+
|                  TWO RUNTIME MODES                    |
+---------------------+--------------------------------+
|   SIMULATION        |   LIVE RESEARCH                |
|   (eval/)           |   (/stock-research skill)      |
|                     |                                |
|   Deterministic     |   LLM-powered                  |
|   Coded rules       |   Claude Opus 4.6              |
|   Free ($0)         |   13-turn debate               |
|   Reproducible      |   7 strategy judges            |
|   7 strategies      |   Structured audit trail       |
|   Daily event loop  |   Per-stock deep analysis      |
+---------------------+--------------------------------+
```

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

## Comparison with Related Work

| Aspect | TradingAgents | AI-Trader | **StockTradeAgent** |
|--------|--------------|-----------|---------------------|
| Cost | $5-100/day | $5-50/day | **$0** (simulation) |
| Deterministic | No | No | **Yes** |
| Test duration | 3 months | 5 weeks | **7 years, 7 regimes** |
| Universe | 3 stocks | NASDAQ-100 | **93 stocks, 15 sectors** |
| Ablation testing | No | No | **Yes (5 features)** |
| Walk-forward | No | No | **Yes** |
| Beat QQQ (their period) | Claimed | 1 of 6 LLMs | **4 of 7 strategies** |
| Beat QQQ (full year) | Not tested | Not tested | **2 of 7 strategies** |
| Benchmarks | None | QQQ | **SPY + QQQ + ONEQ** |

## Data Sources (All Free)

| Source | Data | Rate Limits |
|--------|------|-------------|
| yfinance | Prices, fundamentals, earnings, news | None |
| SEC EDGAR | 10-K, 10-Q, 8-K filings | 10 req/sec |
| Wikipedia | Historical world events (backfilled 2019-2026) | None |
| GDELT | Real-time geopolitical events | Moderate |

## License

MIT

---

*This is a research project, not financial advice. Past backtest performance does not predict future results.*

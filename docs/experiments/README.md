# Experiments Log

Record of experiments that were tested and what we learned. Runs are archived in `runs/archive/` so we can revisit the data later.

---

## Experiment 1: Opus vs Sonnet for MixLLM (2026-03-30)

**Question:** Which LLM model is better as the MixLLM risk monitor?

**Setup:** Ran all 7 recent periods (2019-2026) with both Opus and Sonnet, stickiness=1, mp=10.

**Result:** Opus wins 3/7 periods, Sonnet 2/7, Tie 2/7. Opus avg +16.1% vs Sonnet +15.0%.

| Period | Opus | Sonnet | Winner |
|:-------|:----:|:------:|:------:|
| 2019 Steady Bull | +24.1% | +24.1% | TIE |
| COVID Crash | -0.2% | +0.6% | Sonnet |
| 2022 Bear Market | -3.5% | -8.8% | **Opus** |
| 2023 AI Rally | +30.9% | +30.9% | TIE |
| Bull to Recession | +7.7% | +9.6% | Sonnet |
| Recession to Bull | +26.7% | +25.8% | **Opus** |
| 2025 Full Year | +27.1% | +23.2% | **Opus** |

**Decision:** Use Opus as default. Better in bear markets where crash protection matters most.

**Archived runs:** `runs/archive/sonnet_comparison/`

---

## Experiment 2: Multi-Commodity Strategy (2026-03-30)

**Question:** Can we beat the oil-only Commodity strategy by trading 10 commodities (oil, gas, gold, silver, copper, iron, aluminum, soybean, wheat, platinum)?

**Setup:** Built MultiCommodityStrategy with CTA-style signals (multi-timeframe MAs, Donchian breakout, RSI, seasonality, cross-commodity ratios, inverse-vol sizing). Ran ablation: all, energy, metals, precious, industrial, food.

**Result:** No group beat the top stock strategies on average. Precious metals (+9.7%) was best but still below Mix (+36.7%). Food was useless (-0.4%). "All" diversification (+2.2%) was worse than focused groups.

| Group | Avg Return | vs Old Oil-Only |
|:------|:---------:|:---------------:|
| precious | +9.7% | +1.8% better |
| industrial | +9.3% | +1.4% better |
| metals | +7.6% | -0.3% |
| oil-only (current) | +7.9% | baseline |
| energy | +4.1% | -2.5% worse (nat gas too volatile) |
| all | +2.2% | -4.4% worse |
| food | -0.4% | -8.0% worse |

**Decision:** Keep oil-only Commodity strategy. Multi-commodity doesn't add enough value. Code was removed.

**Lessons:**
- Commodity ETFs are too different to blend into one strategy
- Nat gas (UNG) adds massive downside volatility
- Food/agriculture has no edge with trend-following signals

---

## Experiment 3: Regime Stickiness (2026-03-30)

**Question:** Does requiring N consecutive days of a new regime before switching reduce whipsaw in recoveries?

**Setup:** Tested stickiness=1 (instant, original), 3, and 5 across all 14 periods.

**Result:** Stickiness helped recoveries but hurt crashes equally.

### Symmetric stickiness (slow both ways)

| Period | Sticky=1 Mix | Sticky=3 Mix | Type |
|:-------|:-----------:|:------------:|:-----|
| Post GFC | +9.4% | +52.4% | Recovery (helped!) |
| GFC | +0.3% | -34.6% | Crash (hurt badly!) |
| Bull-Rec | +9.9% | -8.4% | Transition (hurt) |

### Asymmetric stickiness (fast to defend, slow to leave)

Tried making it asymmetric: instant switch to DEFENSIVE, but require 3 days to leave DEFENSIVE.

| Period | Sticky=1 | Asymmetric=3 | Type |
|:-------|:--------:|:------------:|:-----|
| Post GFC | +9.4% | +56.4% | Recovery (even better!) |
| GFC | +0.3% | -38.7% | Crash (even worse!) |

**Root cause found:** The GFC got worse because Mix's `_detect_regime` never returned DEFENSIVE during the GFC — the Defensive peer strategy stayed in NORMAL mode (SPY declined gradually). With stickiness, Mix stayed AGGRESSIVE longer. The original's flip-flopping accidentally created defensive behavior through trigger-driven sells.

**Decision:** Keep stickiness=1 (original). The parameter is available (`--regime-stickiness`) for future experiments.

**Lessons:**
- The recovery problem is real (+9.4% vs SPY +90.2% in Post GFC)
- But fixing it with stickiness hurts crash protection equally
- The root cause is deeper: stop-losses are too tight (93 stops in Post GFC = $79k in losses), monthly rotation kills compounding, and regime detection depends on peer consensus that's too slow

**Archived runs:** `runs/archive/stickiness_tests/`

---

## Experiment 4: Fixed Regime Detection (2026-03-30)

**Question:** Can we add direct market damage triggers (SPY below both MAs + drawdown > 15%) to catch the GFC without needing peer consensus?

**Setup:** Added Path B (SPY below both MAs + deep drawdown) and Path C (high vol + below trend + peers losing) to `_detect_regime`. Also moved CAUTIOUS before AGGRESSIVE in priority. Ran 42 runs: 14 periods x 3 position sizes (10/20/30).

**Result:** Mixed. Helped some periods, hurt others. Net negative for Mix.

| Period | Original Mix | Fixed Mix | Change |
|:-------|:-----------:|:---------:|:------:|
| Post GFC | +9.4% | +52.4% | +43.0% (helped) |
| Pre-COVID | +92.0% | +114.8% | +22.8% (helped) |
| Dot-com | -4.2% | +17.7% | +22.0% (helped) |
| GFC | +0.3% | -35.4% | -35.7% (hurt!) |
| QE Bull | +129.1% | +95.8% | -33.3% (hurt) |
| Post Dot-com | +115.0% | +85.5% | -29.5% (hurt) |

The new CAUTIOUS trigger (`SPY below 200MA + vol > 22%`) fired too aggressively during normal corrections, causing unnecessary defensive positioning in bull markets.

**Decision:** Reverted to original regime detection. The CAUTIOUS trigger sensitivity needs more work.

**Lessons:**
- Direct market damage triggers help in some crashes but hurt in bull markets
- The threshold (vol > 22%, drawdown > 15%) is too sensitive — normal corrections trigger it
- The original peer-consensus approach, while slow, avoids false alarms better

---

## Experiment 5: Position Size (2026-03-30)

**Question:** Is mp=10, mp=20, or mp=30 best?

**Setup:** Ran all position sizes across available periods with fixed regime.

**Result:** mp=10 is best for Mix/MixLLM. mp=20 is best for Value/Momentum/Balanced.

| Strategy | mp=10 | mp=20 | mp=30 |
|:---------|:-----:|:-----:|:-----:|
| Mix | **+33.2%** | +22.7% | +13.7% |
| MixLLM | **+30.3%** | +14.8% | +8.0% |
| Momentum | +30.3% | **+31.1%** | +6.9% |
| Value | +23.5% | **+24.8%** | +6.0% |

**Decision:** Default to mp=10. Concentration drives alpha for the top strategies (Mix, MixLLM).

**Lessons:**
- More positions = more dilution for strategies that make concentrated bets
- mp=30 is terrible across the board — too much dilution
- Diversified strategies (Value, Momentum) benefit slightly from mp=20

---

## Known Issues (Not Yet Fixed)

From deep-dive analysis of Post GFC decision logs:

1. **Stop-losses too tight:** 93 stop-loss triggers at avg -7.9% = $79k losses in Post GFC recovery. Normal 5-10% dips in a recovery trigger exits that would have recovered in days.

2. **Sell-low-rebuy-high cycle:** 127 instances of selling a stock then rebuying it at 11% higher average. REGN: sold at $26.48, rebought at $66.60 (+151% higher).

3. **Monthly rotation kills compounding:** Full portfolio rotation every month resets positions to day-zero, making them vulnerable to stops before gains compound.

4. **LLM defensive bias in recoveries:** All 5 MixLLM escalations in Post GFC were toward defensive. Every one was wrong — elevated vol in a recovery is normal, not a sell signal.

5. **Regime detection is backward-looking:** The `cash_heavy_count >= 4` rule means Mix sells when peers sell — by definition at the worst time.

These are potential areas for future improvement.

---

## Experiment 6: Congressional Stock Trading (Pelosi Tracker) (2026-03-30)

**Question:** Can we use congressional stock trading data (Nancy Pelosi, etc.) as an alpha signal?

This comes up a lot — "just copy what Pelosi buys" is a popular idea. We researched it thoroughly.

**What We Found:**

The data exists (Capitol Trades, QuiverQuant, Unusual Whales) but has a fatal flaw: **20-45 day disclosure delay**. Under the STOCK Act, trades must be reported within 45 days. Average actual delay is ~28 days. By the time you see the trade, the stock has already moved.

**The ETFs prove it doesn't work:**

| | Return/yr | vs SPY | Sharpe |
|:--|:--------:|:------:|:------:|
| NANC (copy Democrats) | +18.0% | +1.1% | 1.07 |
| KRUZ (copy Republicans) | +13.5% | -3.4% | 0.97 |
| SPY | +16.9% | -- | 1.11 |
| **Our Mix** | **+36.7%** | **+19.4%** | **0.94** |

NANC and KRUZ are real ETFs that systematically copy congressional trades. Neither beats SPY on a risk-adjusted basis (lower Sharpe ratios). Our Mix strategy returns 2x what NANC does.

**Why it doesn't work:**

1. **20-45 day delay** — you're buying after the move happened
2. **Amount ranges only** — disclosures say "$100K-$250K" not exact values
3. **Only ~50% of congress members beat SPY** — Pelosi stories are survivorship bias
4. **Academics confirm** — post-STOCK Act (2012), no statistically significant alpha (NBER Working Paper w26975)
5. **Sector tilt explains "alpha"** — congress members are heavy in tech/NVDA, which did well in 2023-2024 regardless

**Decision:** Not worth integrating. The signal is too delayed, too noisy, and academically debunked. Our coded strategies already beat congressional trading by 2x.

**Sources:**
- NANC/KRUZ ETF data (etf.com, Morningstar)
- Unusual Whales 2024 Congress Trading Report
- Capitol Trades (capitoltrades.com)
- NBER Working Paper w26975: "No evidence of superior investment performance"
- Belmont et al. (2022): Congress underperforms post-STOCK Act

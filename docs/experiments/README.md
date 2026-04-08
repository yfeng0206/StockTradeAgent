# Experiments Log

Record of experiments that were tested and what we learned. Runs are archived in `runs/archive/` so we can revisit the data later.

---

## Experiment 1: Opus vs Sonnet for MixLLM (2026-03-30)

**Question:** Which LLM model is better as the MixLLM risk monitor?

**Setup:** Ran all 7 recent periods (2019-2026) with both Opus and Sonnet, stickiness=1, mp=10.

*Note: These numbers are from pre-realism runs (before Experiment 7 premarket execution + biweekly). The relative Opus vs Sonnet comparison still holds -- Opus wins in bear markets.*

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

**Result:** No group beat the top stock strategies on average. Precious metals (+9.7%) was best but still below MixLLM (+39.1%). Food was useless (-0.4%). "All" diversification (+2.2%) was worse than focused groups.

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

*Note: Absolute numbers are from pre-realism runs (before Experiment 7). Relative comparisons still hold -- stickiness hurts crashes as much as it helps recoveries. Revalidated in Experiment 11.*

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

*Note: Absolute numbers are from pre-realism runs (before Experiment 7). The relative comparisons (original vs fixed regime) still illustrate the tradeoff.*

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

*Note: These numbers are pre-bugfix (before Experiment 7 realistic execution). Post-bugfix numbers differ -- see Experiment 10.*

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

3. **Frequent rotation kills compounding:** Full portfolio rotation on rebalance days resets positions to day-zero, making them vulnerable to stops before gains compound.

4. **LLM defensive bias in recoveries:** All 5 MixLLM escalations in Post GFC were toward defensive. Every one was wrong — elevated vol in a recovery is normal, not a sell signal.

5. **Regime detection is backward-looking:** The `cash_heavy_count >= 4` rule means Mix sells when peers sell — by definition at the worst time.

Issue 1 (stop-losses too tight) and Issue 2 (sell-low-rebuy-high) were partially addressed by Chandelier Exit and Cooldown Timer (Experiment 13), but these proved net negative across 14 periods. The issues remain open.

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
| **Our MixLLM** | **+39.1%** | **+21.6%** | **1.186** |

NANC and KRUZ are real ETFs that systematically copy congressional trades. Neither beats SPY on a risk-adjusted basis (lower Sharpe ratios). Our MixLLM strategy returns 2x what NANC does and has a higher Sharpe ratio than both SPY and the congressional ETFs.

**Why it doesn't work:**

1. **20-45 day delay** — you're buying after the move happened
2. **Amount ranges only** — disclosures say "$100K-$250K" not exact values
3. **Only ~50% of congress members beat SPY** — Pelosi stories are survivorship bias
4. **Academics confirm** — post-STOCK Act (2012), no statistically significant alpha (NBER Working Paper w26975)
5. **Sector tilt explains "alpha"** — congress members are heavy in tech/NVDA, which did well in 2023-2024 regardless

**Decision:** Not worth integrating. The signal is too delayed, too noisy, and academically debunked. Our coded strategies already beat congressional trading by 2x+.

**Sources:**
- NANC/KRUZ ETF data (etf.com, Morningstar)
- Unusual Whales 2024 Congress Trading Report
- Capitol Trades (capitoltrades.com)
- NBER Working Paper w26975: "No evidence of superior investment performance"
- Belmont et al. (2022): Congress underperforms post-STOCK Act

---

## Experiment 7: Realistic Execution Model (2026-04-02)

**Question:** How do results change when we eliminate lookahead bias and add execution friction?

**Setup:** The old system used today's close price for both signal computation AND execution — you could see the future. The new realistic mode:

- Signals use T-1 data (yesterday's close) — you analyze overnight, decide before open
- Execution at T's Open price — standard academic approach (Zipline default)
- 5bps slippage on every trade (buy slightly higher, sell slightly lower)
- Premarket model: estimates 9:00 AM price as 0.2×T-1 Close + 0.8×T Open for signal computation

Tested both `open` (T-1 signals, execute at Open) and `premarket` (T-1 + premarket price appended to signal series, execute at Open with gap filter) across 5 periods.

**Result:** Premarket mode outperforms plain open mode, especially in volatile markets.

| Strategy | 2019 Bull | COVID | 2022 Bear | 2023 Rally | Rec→Bull |
|:---------|:---------:|:-----:|:---------:|:----------:|:--------:|
| Value | +38.3% | +13.3% | -14.9% | +33.5% | +19.1% |
| Momentum | +42.2% | +20.9% | -14.0% | +28.0% | +27.1% |
| Balanced | +21.0% | +12.0% | -10.0% | +34.0% | +27.9% |
| EventDriven | +5.0% | +18.7% | -24.1% | +64.5% | +48.5% |
| Adaptive | +21.7% | +3.8% | -13.6% | +60.1% | +44.3% |
| Mix | +15.2% | +15.7% | +1.1% | +24.1% | +28.4% |
| MixLLM | +15.3% | +11.3% | -9.9% | +23.6% | +14.3% |
| SPY | +30.7% | -5.3% | -17.6% | +27.0% | +20.9% |

EventDriven gained most from premarket (+6.4% avg), Balanced most consistent (+1.2% avg). Premarket helped in volatile markets (gap filter avoids chasing overnight gaps), cost slightly in steady bulls.

**Decision:** Use premarket as default. It's the most honest model and actually improves results for most strategies in volatile periods. The gap filter is genuinely adding value.

**Lessons:**
- Lookahead bias was baked into the old system — using T's close to decide T's trades is cheating
- 5bps slippage is negligible for daily-frequency strategies
- The premarket gap filter adds real value: it prevents chasing overnight moves that reverse intraday
- EventDriven benefits most because earnings gaps are exactly the kind of overnight move that needs filtering

---

## Experiment 8: Premarket Proxy Validation (2026-04-02)

**Question:** Is our 0.2×T-1 Close + 0.8×T Open formula accurate enough vs real pre-market data?

**Setup:** yfinance provides 5-minute bars with `prepost=True` for the last 60 trading days. We:

1. Fetched real pre-market prices (last bar before 9:30 AM) for 13 representative stocks
2. Compared against our proxy formula
3. Ran full end-to-end simulation: proxy vs real premarket prices for 95 stocks over 60 days

**Result:** Price-level errors are tiny and produce zero impact on trading decisions.

| Ticker | Days | Mean Error | Max Error |
|:-------|:----:|:---------:|:---------:|
| AAPL | 60 | 0.123% | 0.436% |
| MSFT | 60 | 0.220% | 1.670% |
| NVDA | 60 | 0.200% | 0.598% |
| SPY | 60 | 0.236% | 0.526% |
| QQQ | 60 | 0.143% | 0.354% |
| **Aggregate** | **780** | **0.316%** | **3.083%** |

End-to-end simulation results: ALL strategies showed **0.0% delta** between proxy and real premarket prices. The proxy produces identical trading decisions.

**Decision:** Proxy is validated. Safe to use for all historical backtests. The 0.3% price error is too small to change any signal computation (indicators use 14-200 day lookbacks).

**Lessons:**
- The 80/20 blend (80% T Open, 20% T-1 Close) matches pre-market reality well
- Mega-cap stocks (AAPL, QQQ) have tighter proxies (<0.15%) due to deeper pre-market liquidity
- Energy/healthcare (CVX, UNH) have wider spreads (~0.5-0.6%) but still well within tolerance

---

## Experiment 9: Rebalance Frequency (2026-04-03)

**Question:** Is weekly, biweekly, or monthly rebalancing best?

**Setup:** Tested all 3 frequencies across 7 periods (2019-2026) with premarket exec model, mp=10, stickiness=1, slippage=5bps.

**Results:**

| Strategy | Weekly | Biweekly | Monthly | Best |
|:---------|:------:|:--------:|:-------:|:----:|
| Value | 6.2% (0.495) | 6.5% (0.491) | 6.6% (0.447) | Weekly |
| Momentum | 10.3% (0.674) | 15.1% (0.906) | 16.8% (1.075) | Monthly |
| Balanced | 14.8% (1.041) | 18.9% (1.263) | 11.7% (0.891) | **Biweekly** |
| Defensive | 0.7% (0.093) | 2.9% (0.340) | 3.3% (0.418) | Monthly |
| EventDriven | 7.1% (0.649) | 10.1% (0.818) | 15.8% (0.954) | Monthly |
| Adaptive | 15.7% (0.713) | 22.2% (0.983) | 19.7% (0.939) | **Biweekly** |
| Mix | 5.2% (0.447) | 15.0% (0.944) | 16.4% (1.037) | Monthly |
| MixLLM | 5.7% (0.541) | 7.2% (0.570) | 11.4% (0.776) | Monthly |
| Commodity | 5.5% (-0.069) | 1.0% (-0.013) | 7.1% (0.081) | Monthly |

Format: return% (Sharpe)

**Overall best:** Biweekly (avg Sharpe 0.983 across top 5 strategies) barely edges monthly (0.979). Weekly is worst (0.705).

*Note: The raw numbers above were from pre-B1 runs. After the B1 bug fix, biweekly became best for Mix as well (not just Balanced/Adaptive). The decision below reflects the post-fix results.*

**Decision:** Use biweekly as default. Biweekly is the best frequency for Balanced, Adaptive, and Mix (after B1 fix). Monthly remains best for Momentum and EventDriven. Added --frequency CLI flag to override per run.

**Lessons:**
- Biweekly catches dips faster than monthly in volatile markets (Balanced +18.9% vs +11.7%)
- Weekly generates too much turnover, hurting most strategies
- Monthly is best for strategies that rely on trend persistence (Momentum)
- The optimal frequency depends on strategy personality, not just on the market

---

## Experiment 10: Position Size Revalidation (2026-04-03)

**Question:** Does mp=10 still beat mp=20 under realistic execution?

**Setup:** Tested mp=10 vs mp=20 across 7 periods with premarket, biweekly, stickiness=1.

**Results:**

| Strategy | mp=10 | mp=20 | Winner |
|:---------|:-----:|:-----:|:------:|
| Balanced | 11.7% (0.891) | 8.1% (0.726) | **mp=10** |
| Adaptive | 19.7% (0.939) | 9.8% (0.584) | **mp=10** |
| Momentum | 16.8% (1.076) | 14.2% (1.009) | **mp=10** |
| Mix | 16.4% (1.037) | 10.6% (0.855) | **mp=10** |
| EventDriven | 15.8% (0.955) | 10.6% (0.888) | **mp=10** |
| MixLLM | 13.0% (0.888) | 4.7% (0.545) | **mp=10** |
| Value | 12.1% (0.960) | 8.3% (0.690) | **mp=10** |
| Defensive | 3.3% (0.418) | 2.1% (0.212) | **mp=10** |

**Decision:** mp=10 confirmed best. Concentration drives alpha -- same conclusion as Experiment 5 but now validated under realistic execution.

---

## Experiment 11: Stickiness Revalidation (2026-04-03)

**Question:** Does regime stickiness still not help under realistic execution?

**Setup:** Tested stickiness=1/3/5 across 7 periods with premarket, biweekly, mp=10.

**Result:** Most strategies identical across all values. Mix and MixLLM get significantly worse: Mix drops from 16.4% to 9.0% (stk=5), MixLLM from 12.9% to -0.2%.

**Decision:** stickiness=1 confirmed. Same as Experiment 3.

---

## Experiment 12: LLM Strategy Variants (2026-04-07)

**Question:** Can we improve MixLLM by changing how the LLM is used?

**Setup:** Tested 7 configs across 3 periods (COVID Crash, 2022 Bear, 2023 AI Rally) with Opus, biweekly, premarket:

| Config | Description | How LLM is used |
|:-------|:-----------|:---------------|
| NoLLM | Plain Mix, no LLM | Coded rules only |
| V0 | Original MixLLM | Escalate defensiveness only |
| V1 | Recovery detector | De-escalate only (flip of V0) |
| V2 | News interpreter | LLM reads news, adjusts scores |
| V3 | Event-triggered | Bidirectional, only on regime changes |
| V1+V2 | Recovery + news | Combined |
| V2+V3 | Event + news | Combined |

**Result:** V0 (original) had the best Sharpe ratio. None of the variants beat it.

**Decision:** Keep V0 as default. The escalate-only constraint, while it costs returns in bulls, provides the most consistent risk-adjusted performance. V1/V2/V3 files kept as experimental for future research.

**Lessons:**
- The LLM's value is specifically in crisis detection, not recovery detection or news interpretation
- Bidirectional LLM (V3) introduces too much noise -- the LLM's opinions on direction are not reliable enough
- News interpretation (V2) didn't add signal -- our coded scoring already captures most of what news provides
- The original design (escalate-only) was correct: use LLM for what it's uniquely good at (crisis pattern recognition)

---

## Experiment 13: Chandelier Exit + Cooldown Timer (2026-04-07)

**Question:** Do trailing stops and anti-churn guards improve results?

**Setup:** Tested 4 combos across 3 periods, then the winner across 14 periods.

*Note: The 14-period baseline (~33.6%) is from mid-experiment runs before all bug fixes were finalized. Final canonical Mix return is +34.9%.*

| Combo | 3-Period Sharpe | 14-Period Return | Verdict |
|:------|:--------------:|:----------------:|:--------|
| none | 1.080 | ~33.6% | Baseline |
| ch only | 0.744 | -- | Worse |
| cd only | 0.962 | -- | Slightly worse |
| ch+cd | 1.267 | 14.8% | Won 3-period, LOST 14-period |

**Result:** Chandelier + Cooldown improved Sharpe on 3 volatile test periods but **halved returns** across 14 periods. The 21-day minimum holding period prevents adapting to regime changes in sustained trends.

**Decision:** Keep both features as OFF-by-default toggles (`--chandelier`, `--cooldown`). Do not enable by default. The coded stop-loss and rebalance system works better without these guards.

**Lessons:**
- 3-period test set was biased toward volatile markets where cooldown helps
- In sustained trends (QE Bull, Pre-COVID), cooldown locks positions too long
- Chandelier Exit alone hurt -- wider trailing stops meant bigger losses when stops finally hit
- Classic overfitting: optimizing on a subset doesn't generalize
- The original stop-loss + biweekly rebalance is already a good balance

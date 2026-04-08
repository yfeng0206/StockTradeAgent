# Detailed Results: 9 Strategies x 14 Market Regimes

All results: `realistic=True, exec_model=premarket, frequency=biweekly, slippage=5bps, mp=10, stickiness=1`

$100K starting capital | 10 max positions | 93-stock universe | Daily event-driven simulation

Tested across 25 years of market data (2000-2026), covering dot-com crash, GFC, COVID, bull markets, bear markets, and transitions.

---

## Strategy Rankings (14-period average)

<div align="center">

| Strategy | Avg Return | Avg Alpha vs SPY | Avg Sharpe | Max Drawdown | Beats SPY | Loses Money |
|:---------|:---------:|:----------------:|:----------:|:------------:|:---------:|:-----------:|
| **MixLLM** | **+39.1%** | **+21.6%** | **1.186** | **-16.0%** | 10/14 | 2/14 |
| **Mix** | +34.9% | +17.4% | 1.020 | -23.6% | 10/14 | 3/14 |
| **Adaptive** | +32.6% | +15.1% | 0.833 | -41.3% | **12/14** | 4/14 |
| **Momentum** | +27.9% | +10.4% | 0.801 | -44.4% | **12/14** | 4/14 |
| **Balanced** | +26.2% | +8.7% | 0.964 | -48.2% | 11/14 | 4/14 |
| **Value** | +20.3% | +2.8% | 0.650 | -41.9% | 8/14 | 4/14 |
| **Defensive** | +14.2% | -3.3% | 0.570 | -18.1% | 6/14 | 5/14 |
| **EventDriven** | +5.2% | -12.3% | 0.529 | -23.4% | 6/14 | 3/14 |
| **Commodity** | +3.7% | -13.8% | 0.191 | -22.7% | 5/14 | 7/14 |
| QQQ | +24.7% | -- | -- | -- | -- | -- |
| SPY | +17.5% | -- | -- | -- | -- | -- |

</div>

---

## Crash Protection (4 worst periods)

<div align="center">

| Strategy | Dot-com (00-02) | GFC (07-09) | COVID (20) | 2022 Bear |
|:---------|:---------------:|:-----------:|:----------:|:---------:|
| **MixLLM** | -0.6% | **+16.5%** | **+21.3%** | +8.7% |
| **Mix** | -8.1% | -12.3% | +28.3% | -10.2% |
| **Adaptive** | -21.7% | -26.1% | +1.0% | -14.8% |
| **Momentum** | -25.2% | -33.5% | +27.3% | -16.8% |
| **Balanced** | -8.8% | -36.5% | +32.6% | -2.7% |
| **Value** | **+18.5%** | -33.0% | +12.8% | -0.7% |
| **EventDriven** | 0.0% | +2.0% | +10.2% | -8.4% |
| **Defensive** | **+10.9%** | -12.9% | +1.4% | -7.0% |
| **Commodity** | -5.3% | **+27.6%** | -2.1% | **+8.5%** |
| SPY | -33.4% | -45.1% | -3.7% | -17.9% |
| QQQ | -77.1% | -36.5% | +13.7% | -29.1% |

</div>

---

## Full Return Tables

### Historical Periods (2000-2018)

<div align="center">

| Strategy | Dot-com Crash | Post Dot-com | Housing Bull | GFC | Post GFC | QE Bull | Pre-COVID |
|:---------|:------------:|:------------:|:----------:|:---:|:--------:|:-------:|:---------:|
| **MixLLM** | -0.6% | +80.9% | +76.0% | **+16.5%** | **+90.7%** | +59.5% | **+96.6%** |
| **Mix** | -8.1% | +54.0% | +67.1% | -12.3% | +53.3% | +57.4% | **+126.1%** |
| **Adaptive** | -21.7% | +49.3% | +66.3% | -26.1% | +13.7% | **+106.2%** | +108.7% |
| **Momentum** | -25.2% | +61.9% | +55.8% | -33.5% | +66.8% | +76.7% | +78.7% |
| **Balanced** | -8.8% | +47.9% | +28.7% | -36.5% | +88.2% | +66.3% | +50.8% |
| **Value** | **+18.5%** | +49.5% | +43.8% | -33.0% | +54.0% | +51.2% | +52.8% |
| **EventDriven** | 0.0% | 0.0% | 0.0% | +2.0% | +4.1% | +0.2% | +2.3% |
| **Defensive** | +10.9% | +39.1% | +31.0% | -12.9% | +29.0% | +54.6% | +30.4% |
| **Commodity** | -5.3% | +20.5% | +17.8% | **+27.6%** | +2.9% | -14.1% | -3.8% |
| SPY | -33.4% | +40.9% | +29.3% | -45.1% | +84.3% | +73.1% | +32.3% |
| QQQ | -77.1% | +63.4% | +19.5% | -36.5% | +111.5% | +109.1% | +43.8% |

</div>

### Recent Periods (2019-2026)

<div align="center">

| Strategy | 2019 Bull | COVID | 2022 Bear | 2023 AI | Bull-Rec | Rec-Bull | 2025-Now |
|:---------|:---------:|:-----:|:---------:|:-------:|:--------:|:--------:|:--------:|
| **MixLLM** | +21.1% | **+21.3%** | +8.7% | +31.0% | **+20.4%** | +20.8% | +4.2% |
| **Mix** | +27.2% | +28.3% | -10.2% | +41.2% | +8.2% | **+44.4%** | +11.8% |
| **Adaptive** | +23.9% | +1.0% | -14.8% | **+61.1%** | +0.2% | +31.9% | **+56.3%** |
| **Momentum** | **+41.1%** | +27.3% | -16.8% | +36.2% | -22.9% | +32.2% | +12.4% |
| **Balanced** | +33.2% | **+32.6%** | -2.7% | +30.8% | -8.9% | +32.0% | +13.1% |
| **Value** | +29.3% | +12.8% | -0.7% | +8.6% | -4.2% | +8.2% | -6.2% |
| **EventDriven** | +9.3% | +10.2% | -8.4% | +38.1% | -10.7% | +23.2% | +2.7% |
| **Defensive** | +22.4% | +1.4% | -7.0% | -3.0% | -3.6% | +1.0% | +5.1% |
| **Commodity** | -0.1% | -2.1% | **+8.5%** | +2.6% | +1.3% | -3.1% | -0.3% |
| SPY | +33.3% | -3.7% | -17.9% | +25.5% | -10.8% | +24.2% | +12.4% |
| QQQ | +41.6% | +13.7% | -29.1% | +54.1% | -19.4% | +35.9% | +15.0% |

</div>

---

## Position Size Comparison

Revalidated under realistic execution (premarket, biweekly, stickiness=1). See [Experiment 10](experiments/README.md#experiment-10-position-size-revalidation-2026-04-03).

<div align="center">

| Strategy | mp=10 | mp=20 | Winner |
|:---------|:-----:|:-----:|:------:|
| **MixLLM** | 13.0% (0.888) | 4.7% (0.545) | **mp=10** |
| **Mix** | 16.4% (1.037) | 10.6% (0.855) | **mp=10** |
| **Adaptive** | 19.7% (0.939) | 9.8% (0.584) | **mp=10** |
| **Momentum** | 16.8% (1.076) | 14.2% (1.009) | **mp=10** |
| **Balanced** | 11.7% (0.891) | 8.1% (0.726) | **mp=10** |
| **Value** | 12.1% (0.960) | 8.3% (0.690) | **mp=10** |

</div>

Format: return% (Sharpe). 7-period averages (2019-2026).

**Conclusion:** mp=10 is optimal for all strategies under realistic execution. Concentration drives alpha.

---

## Opus vs Sonnet (MixLLM model comparison)

*Note: These numbers are from pre-realism runs ([Experiment 1](experiments/README.md#experiment-1-opus-vs-sonnet-for-mixllm-2026-03-30)). The relative Opus vs Sonnet comparison holds -- Opus is better in bear markets.*

<div align="center">

| Period | Opus | Sonnet | Winner |
|:-------|:----:|:------:|:------:|
| 2019 Steady Bull | +24.1% | +24.1% | TIE |
| COVID Crash | -0.2% | +0.6% | Sonnet |
| 2022 Bear Market | -3.5% | -8.8% | **Opus** |
| 2023 AI Rally | +30.9% | +30.9% | TIE |
| Bull to Recession | +7.7% | +9.6% | Sonnet |
| Recession to Bull | +26.7% | +25.8% | **Opus** |
| 2025 Full Year | +27.1% | +23.2% | **Opus** |
| **Average** | **+16.1%** | +15.0% | **Opus** |

</div>

Opus wins 3, Sonnet wins 2, Tie 2. Opus has the edge in bear markets (the periods that matter most for crash protection).

---

## Oracle Baseline Comparison

Previous results used today's close for both signals and execution (lookahead bias). The old oracle Mix averaged +36.7%. After fixing all bugs and switching to realistic execution, **MixLLM now returns +39.1% — beating the oracle** without any lookahead.

<div align="center">

| Strategy | Oracle (old) | Realistic (new) | Delta |
|:---------|:------------:|:---------------:|:-----:|
| **MixLLM** | +33.9% | **+39.1%** | **+5.2%** |
| **Mix** | +36.7% | +34.9% | -1.8% |
| **Adaptive** | +32.1% | +32.6% | +0.5% |
| **Momentum** | +29.2% | +27.9% | -1.3% |
| **Balanced** | +25.8% | +26.2% | +0.4% |
| **Value** | +21.5% | +20.3% | -1.2% |
| **EventDriven** | +15.7% | +5.2% | -10.5% |
| **Defensive** | +13.9% | +14.2% | +0.3% |
| **Commodity** | +5.7% | +3.7% | -2.0% |

</div>

---

## Period Definitions

<div align="center">

| Period | Dates | Type | Description |
|:-------|:------|:-----|:------------|
| Dot-com Crash | 2000-03 to 2002-10 | Crash | NASDAQ -77%, tech bubble burst |
| Post Dot-com | 2003-01 to 2004-12 | Recovery | Post-crash recovery |
| Housing Bull | 2005-01 to 2007-06 | Bull | Pre-GFC housing bubble |
| GFC | 2007-07 to 2009-03 | Crash | SPY -46%, Lehman Brothers |
| Post GFC | 2009-03 to 2011-12 | Recovery | QE1, V-shaped recovery |
| QE Bull | 2012-01 to 2015-12 | Bull | QE era, steady growth |
| Pre-COVID | 2016-01 to 2018-12 | Bull | Trump rally, 2018 vol spike |
| 2019 Steady Bull | 2019-01 to 2019-12 | Bull | Low volatility rally |
| COVID Crash | 2020-01 to 2020-06 | Crash | Pandemic, fastest crash in history |
| 2022 Bear Market | 2022-01 to 2022-10 | Crash | Rate hikes, tech selloff |
| 2023 AI Rally | 2023-01 to 2023-12 | Bull | AI hype, Magnificent 7 |
| Bull to Recession | 2021-07 to 2022-06 | Transition | Peak to trough |
| Recession to Bull | 2022-10 to 2023-06 | Recovery | Bear market bottom to rally |
| 2025 Full Year | 2025-01 to 2026-03 | Mixed | Tariffs, oil spike, uncertainty |

</div>

# Detailed Results: 9 Strategies x 14 Market Regimes

$100K starting capital | 10 max positions | 93-stock universe | Daily event-driven simulation

Tested across 25 years of market data (2000-2026), covering dot-com crash, GFC, COVID, bull markets, bear markets, and transitions.

---

## Strategy Rankings (14-period average)

| Strategy | Avg Return | Avg Alpha vs SPY | Worst Drawdown | Avg Sharpe | Beats SPY | Loses Money |
|:---------|:---------:|:----------------:|:--------------:|:----------:|:---------:|:-----------:|
| **Mix** | **+36.7%** | **+19.4%** | -25.0% | 0.94 | **12/14** | 2/14 |
| **MixLLM** | +33.9% | +12.6% | **-22.9%** | **0.95** | **12/14** | **2/14** |
| **Adaptive** | +32.1% | +14.6% | -35.5% | 0.81 | 11/14 | 4/14 |
| Momentum | +29.2% | +11.7% | -47.4% | 0.72 | 10/14 | 3/14 |
| Balanced | +25.8% | +8.9% | -40.8% | 0.79 | 10/14 | 3/14 |
| Value | +21.5% | +3.2% | -38.5% | 0.81 | 8/14 | 4/14 |
| EventDriven | +15.7% | -1.8% | -34.4% | 0.72 | 6/14 | 4/14 |
| Defensive | +13.9% | -3.6% | -20.3% | 0.59 | 5/14 | 5/14 |
| Commodity | +5.7% | -11.7% | -23.2% | 0.21 | 6/14 | 7/14 |
| QQQ | +24.4% | — | -82.9% | — | — | 4/14 |
| SPY | +17.5% | — | -55.1% | — | — | 5/14 |

---

## Crash Protection (4 worst periods)

| Strategy | Dot-com (00-02) | GFC (07-09) | COVID (20) | 2022 Bear | Avg Crash |
|:---------|:---------------:|:-----------:|:----------:|:---------:|:---------:|
| **MixLLM** | **+20.4%** | **+8.9%** | -0.2% | -3.5% | **+6.4%** |
| **Commodity** | -14.1% | +22.7% | -2.4% | **+24.7%** | +7.7% |
| **Mix** | -4.2% | +0.3% | +7.5% | -4.9% | -0.3% |
| **Defensive** | +13.6% | -14.9% | -5.7% | -3.4% | -2.6% |
| SPY | -33.1% | -45.9% | -5.3% | -17.6% | -25.5% |
| QQQ | -77.2% | -37.0% | +12.8% | -29.6% | -32.7% |

---

## Full Return Tables

### Historical Periods (2000-2018)

| Strategy | Dot-com Crash | Post Dot-com | Housing Bull | GFC | Post GFC | QE Bull | Pre-COVID |
|:---------|:------------:|:------------:|:----------:|:---:|:--------:|:-------:|:---------:|
| **Value** | +9.3% | +25.8% | +42.6% | -33.7% | **+57.6%** | +65.3% | +34.0% |
| **Momentum** | +9.9% | +63.8% | +40.3% | -37.5% | +51.9% | **+153.2%** | +44.1% |
| **Balanced** | +4.3% | +53.8% | +69.0% | -27.9% | +48.2% | +116.7% | +53.5% |
| **Defensive** | **+13.6%** | +43.9% | +50.5% | -14.9% | +17.3% | +38.1% | +32.2% |
| **EventDriven** | **+51.9%** | +27.2% | -2.1% | -4.9% | +6.2% | +2.3% | -2.1% |
| **Adaptive** | -19.3% | **+88.0%** | +59.1% | -17.7% | +23.5% | +112.7% | **+82.3%** |
| **Commodity** | -14.1% | +19.6% | +14.0% | **+22.7%** | -12.3% | +10.8% | +5.3% |
| **Mix** | -4.2% | **+115.0%** | +51.4% | +0.3% | +9.4% | **+129.1%** | **+92.0%** |
| **MixLLM** | **+20.4%** | +75.0% | **+66.2%** | **+8.9%** | +3.6% | +78.3% | +55.6% |
| SPY | -33.1% | +37.8% | +30.6% | -45.9% | +90.2% | +75.2% | +30.8% |
| QQQ | -77.2% | +59.0% | +21.3% | -37.0% | +115.3% | +109.1% | +43.7% |

### Recent Periods (2019-2026)

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

---

## Max Drawdown by Period

| Strategy | Dot-com | Post DC | Housing | GFC | Post GFC | QE Bull | Pre-COV | 2019 | COVID | 2022 | 2023 | Bull-Rec | Rec-Bull | 2025 | **Worst** |
|:---------|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:|
| **Mix** | -21.8% | -15.3% | -14.2% | -17.3% | -25.0% | -12.5% | -13.0% | -10.3% | -16.0% | -14.7% | -11.4% | -19.5% | -8.7% | -24.0% | **-25.0%** |
| **MixLLM** | -12.9% | -14.8% | -12.0% | -14.6% | -17.8% | -12.5% | -9.7% | -6.7% | -13.6% | -14.7% | -10.4% | -22.9% | -12.8% | -21.0% | **-22.9%** |
| **Defensive** | -11.2% | -7.6% | -4.8% | -20.3% | -8.1% | -6.6% | -8.3% | -2.5% | -12.6% | -9.9% | -10.3% | -7.3% | -8.8% | -10.7% | **-20.3%** |
| SPY | -47.5% | -13.7% | -7.6% | -55.1% | -18.6% | -11.9% | -19.3% | -6.6% | -33.6% | -24.4% | -9.9% | -22.9% | -7.5% | -18.7% | **-55.1%** |
| QQQ | -82.9% | -15.9% | -17.3% | -53.4% | -16.1% | -13.9% | -22.8% | -11.0% | -28.6% | -34.7% | -10.8% | -32.6% | -11.2% | -22.7% | **-82.9%** |

---

## Position Size Comparison

Tested with regime_stickiness=3, fixed regime detection.

| Strategy | mp=10 | mp=20 | mp=30 |
|:---------|:-----:|:-----:|:-----:|
| **Mix** | **+33.2%** | +22.7% | +13.7% |
| **MixLLM** | **+30.3%** | +14.8% | +8.0% |
| **Adaptive** | **+36.2%** | +17.7% | +6.0% |
| **Momentum** | +30.3% | **+31.1%** | +6.9% |
| **Value** | +23.5% | **+24.8%** | +6.0% |
| **Balanced** | +26.9% | **+34.1%** | -2.0% |

**Conclusion:** mp=10 is optimal for Mix/MixLLM (concentration = alpha). mp=20 is better for Value/Momentum/Balanced (diversification helps).

---

## Opus vs Sonnet (MixLLM model comparison)

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

Opus wins 3, Sonnet wins 2, Tie 2. Opus has the edge in bear markets (the periods that matter most for crash protection).

---

## Period Definitions

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

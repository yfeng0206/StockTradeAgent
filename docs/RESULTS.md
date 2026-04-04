# Detailed Results: 9 Strategies x 14 Market Regimes

All results: `realistic=True, exec_model=premarket, frequency=biweekly, slippage=5bps, mp=10, stickiness=1`

$100K starting capital | 10 max positions | 93-stock universe | Daily event-driven simulation

Tested across 25 years of market data (2000-2026), covering dot-com crash, GFC, COVID, bull markets, bear markets, and transitions.

---

## Strategy Rankings (14-period average)

<div align="center">

| Strategy | Avg Return | Avg Alpha vs SPY | Avg Sharpe | Max Drawdown | Beats SPY | Loses Money |
|:---------|:---------:|:----------------:|:----------:|:------------:|:---------:|:-----------:|
| **Mix** | **+33.6%** | **+16.1%** | **0.973** | -34.0% | **10/14** | 3/14 |
| **Adaptive** | +29.2% | +11.7% | 0.814 | -43.2% | 10/14 | 4/14 |
| **Momentum** | +27.8% | +10.3% | 0.884 | -40.3% | **12/14** | 4/14 |
| **MixLLM** | +26.0% | +8.6% | 0.781 | -32.4% | 8/14 | 3/14 |
| **Balanced** | +23.8% | +6.4% | 0.808 | -42.0% | 10/14 | 4/14 |
| **Value** | +18.0% | +0.6% | 0.781 | -37.6% | 8/14 | 3/14 |
| **Defensive** | +13.7% | -3.8% | 0.604 | **-17.9%** | 5/14 | 4/14 |
| **EventDriven** | +8.0% | -9.5% | 0.574 | -31.1% | 5/14 | 3/14 |
| **Commodity** | +7.6% | -9.8% | 0.226 | **-17.1%** | 6/14 | 6/14 |
| QQQ | +24.4% | -- | -- | -- | -- | -- |
| SPY | +17.5% | -- | -- | -- | -- | -- |

</div>

---

## Crash Protection (4 worst periods)

<div align="center">

| Strategy | Dot-com (00-02) | GFC (07-09) | COVID (20) | 2022 Bear |
|:---------|:---------------:|:-----------:|:----------:|:---------:|
| **Mix** | -18.6% | -10.7% | **+15.6%** | +0.5% |
| **MixLLM** | -26.0% | -28.2% | +11.3% | -4.7% |
| **Adaptive** | -32.4% | -6.9% | +3.8% | -13.8% |
| **Momentum** | -5.1% | -29.8% | **+20.9%** | -14.8% |
| **Balanced** | -2.3% | -29.2% | +12.8% | -10.2% |
| **Value** | **+10.5%** | -31.4% | +13.2% | -14.9% |
| **EventDriven** | 0.0% | **+3.9%** | +18.5% | -23.9% |
| **Defensive** | **+14.5%** | -13.3% | -0.2% | -6.2% |
| **Commodity** | -7.4% | **+22.5%** | -2.1% | **+22.5%** |
| SPY | -33.1% | -45.9% | -5.3% | -17.6% |
| QQQ | -77.2% | -37.0% | +12.8% | -29.6% |

</div>

---

## Full Return Tables

### Historical Periods (2000-2018)

<div align="center">

| Strategy | Dot-com Crash | Post Dot-com | Housing Bull | GFC | Post GFC | QE Bull | Pre-COVID |
|:---------|:------------:|:------------:|:----------:|:---:|:--------:|:-------:|:---------:|
| **Mix** | -18.6% | **+92.3%** | +68.7% | -10.7% | +48.5% | **+94.7%** | +81.8% |
| **MixLLM** | -26.0% | +88.0% | +71.4% | -28.2% | +33.9% | +71.4% | +79.9% |
| **Adaptive** | -32.4% | +64.8% | **+75.8%** | -6.9% | +22.6% | +64.2% | **+92.9%** |
| **Momentum** | -5.1% | +76.6% | +49.8% | -29.8% | +59.3% | +80.6% | +60.0% |
| **Balanced** | -2.3% | +57.3% | +14.7% | -29.2% | +66.5% | +101.3% | +45.1% |
| **Value** | **+10.5%** | +31.2% | +23.4% | -31.4% | +48.2% | +78.4% | +7.3% |
| **EventDriven** | 0.0% | 0.0% | 0.0% | **+3.9%** | +7.7% | +0.6% | -1.6% |
| **Defensive** | **+14.5%** | +37.5% | +25.4% | -13.3% | +29.2% | +52.2% | +25.9% |
| **Commodity** | -7.4% | +22.7% | +12.6% | **+22.5%** | +18.4% | -15.4% | +4.2% |
| SPY | -33.1% | +37.8% | +30.6% | -45.9% | **+90.2%** | +75.2% | +30.8% |
| QQQ | -77.2% | +59.0% | +21.3% | -37.0% | **+115.3%** | +109.1% | +43.7% |

</div>

### Recent Periods (2019-2026)

<div align="center">

| Strategy | 2019 Bull | COVID | 2022 Bear | 2023 AI | Bull-Rec | Rec-Bull | 2025-Now |
|:---------|:---------:|:-----:|:---------:|:-------:|:--------:|:--------:|:--------:|
| **Mix** | +15.2% | **+15.6%** | +0.5% | +26.0% | **+26.4%** | +30.7% | -1.0% |
| **MixLLM** | +15.3% | +11.3% | -4.7% | +25.6% | +16.9% | +8.9% | +0.8% |
| **Adaptive** | +21.7% | +3.8% | -13.8% | **+60.1%** | -12.3% | **+44.3%** | **+23.5%** |
| **Momentum** | **+42.2%** | **+20.9%** | -14.8% | +28.0% | -7.9% | +27.1% | +2.5% |
| **Balanced** | +21.2% | +12.8% | -10.2% | +34.0% | -9.9% | +27.9% | +4.4% |
| **Value** | +38.2% | +13.2% | -14.9% | +33.5% | -6.9% | +19.1% | +2.8% |
| **EventDriven** | +5.0% | +18.5% | -23.9% | **+64.8%** | -18.8% | **+48.9%** | +6.6% |
| **Defensive** | +19.1% | -0.2% | -6.2% | -2.0% | +3.7% | +3.3% | +2.1% |
| **Commodity** | -2.5% | -2.1% | **+22.5%** | -1.8% | +19.9% | -4.5% | +17.8% |
| SPY | +30.7% | -5.3% | -17.6% | +27.0% | -10.3% | +20.9% | +13.7% |
| QQQ | +38.1% | +12.8% | -29.6% | +56.5% | -19.5% | +33.7% | +15.9% |

</div>

---

## Position Size Comparison

Tested with regime_stickiness=3, fixed regime detection.

<div align="center">

| Strategy | mp=10 | mp=20 | mp=30 |
|:---------|:-----:|:-----:|:-----:|
| **Mix** | **+33.2%** | +22.7% | +13.7% |
| **MixLLM** | **+30.3%** | +14.8% | +8.0% |
| **Adaptive** | **+36.2%** | +17.7% | +6.0% |
| **Momentum** | +30.3% | **+31.1%** | +6.9% |
| **Value** | +23.5% | **+24.8%** | +6.0% |
| **Balanced** | +26.9% | **+34.1%** | -2.0% |

</div>

**Conclusion:** mp=10 is optimal for Mix/MixLLM (concentration = alpha). mp=20 is better for Value/Momentum/Balanced (diversification helps).

---

## Opus vs Sonnet (MixLLM model comparison)

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

Previous results used today's close for both signals and execution (lookahead bias). The numbers below show old oracle mode vs current realistic mode.

<div align="center">

| Strategy | Oracle (old) | Realistic (new) | Delta |
|:---------|:------------:|:---------------:|:-----:|
| **Mix** | +36.7% | +33.6% | -3.1% |
| **MixLLM** | +33.9% | +26.0% | -7.9% |
| **Adaptive** | +32.1% | +29.2% | -2.9% |
| **Momentum** | +29.2% | +27.8% | -1.4% |
| **Balanced** | +25.8% | +23.8% | -2.0% |
| **Value** | +21.5% | +18.0% | -3.5% |
| **EventDriven** | +15.7% | +8.0% | -7.7% |
| **Defensive** | +13.9% | +13.7% | -0.2% |
| **Commodity** | +5.7% | +7.6% | +1.9% |

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

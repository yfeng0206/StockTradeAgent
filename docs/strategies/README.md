# Strategy Deep Dives

Click any strategy to see its exact scoring formula, signal thresholds, trigger reactions, and parameter settings.

| Strategy | Approach | Avg Return | Best At |
|:---------|:---------|:---------:|:--------|
| [**Mix**](mix.md) | Uses 7 peers as live sensors, multi-asset allocation | +33.6% | Best overall |
| [**MixLLM**](mix_llm.md) | Mix + Claude Opus risk monitor | +26.0% | Crash protection |
| [**Adaptive**](adaptive.md) | Switches mode by market regime | +29.2% | Trend transitions |
| [**Momentum**](momentum.md) | 12-minus-1 month signal, trend following | +27.8% | Bull markets |
| [**Balanced**](balanced.md) | Regime-weighted blend of value + momentum | +23.8% | All-weather |
| [**Value**](value.md) | Low volatility, beaten-down quality | +18.0% | Steady markets |
| [**EventDriven**](event_driven.md) | Trades only around earnings and 8-K filings | +8.0% | Catalyst periods |
| [**Defensive**](defensive.md) | 3-state exposure scaling | +13.7% | Crash protection |
| [**Commodity**](commodity.md) | Oil tracker, binary signal | +7.6% | Bear markets |

## Trading Frequency

| Strategy | Avg Trades/Week | Style |
|:---------|:--------------:|:------|
| Commodity | 0.1 | Holds or cash, rarely trades |
| Value | 1.4 | Patient, quarterly rebalance |
| Defensive | 2.0 | Moderate, sells on danger |
| EventDriven | 2.9 | Active around earnings |
| Balanced | 3.3 | Moderate-active |
| Adaptive | 3.3 | Active, mode-switching |
| Mix | 3.3 | Active, multi-asset |
| MixLLM | 3.3 | Same as Mix + LLM calls |
| Momentum | 3.7 | Most active, chases trends |

## Quick Comparison

| | Rebalance | ATR Stop | Max Pos | Scoring |
|:--|:---------:|:--------:|:-------:|:--------|
| **Value** | Quarterly | 3.0x | 5 | 30% low-vol + 30% distance-from-high + 20% RSI + 20% stability |
| **Momentum** | Monthly | 2.5x | 5 | 40% 12m-1m + 25% trend + 20% MACD + 15% volume |
| **Balanced** | Monthly | 2.0x | 5 | Regime-weighted: bull=60% momentum, bear=70% value |
| **Defensive** | Monthly | 1.5x | 5 | 40% low-vol + 30% trend + 30% drawdown |
| **EventDriven** | Monthly | 2.0x | 5 | 55% event + 25% volume spike + 20% momentum |
| **Adaptive** | Monthly | 2.0x | 5 | Mode-dependent (4 modes, 4 scoring formulas) |
| **Commodity** | Monthly | 2.5x | 1 | Binary: oil score > 4 = buy, < 3 = cash |
| **Mix** | Monthly | 2.0x | 10 | Regime from 7 peers -> 5 allocation profiles |
| **MixLLM** | Monthly | 2.0x | 10 | Mix regime + Opus can escalate defensiveness |

# Strategy Deep Dives

Click any strategy to see its exact scoring formula, signal thresholds, trigger reactions, and parameter settings.

| Strategy | Approach | Avg Return | Best At |
|:---------|:---------|:---------:|:--------|
| [**MixLLM**](mix_llm.md) | Mix + Claude Opus risk monitor | +39.1% | Best overall |
| [**Mix**](mix.md) | Uses 7 peers as live sensors, multi-asset allocation | +34.9% | Multi-asset allocation |
| [**Adaptive**](adaptive.md) | Switches mode by market regime | +32.6% | Trend transitions |
| [**Momentum**](momentum.md) | 12-minus-1 month signal, trend following | +27.9% | Bull markets |
| [**Balanced**](balanced.md) | Regime-weighted blend of value + momentum | +26.2% | All-weather |
| [**Value**](value.md) | Low volatility, beaten-down quality | +20.3% | Steady markets |
| [**Defensive**](defensive.md) | 3-state exposure scaling | +14.2% | Crash protection |
| [**EventDriven**](event_driven.md) | Trades only around earnings and 8-K filings | +5.2% | Catalyst periods |
| [**Commodity**](commodity.md) | Oil tracker, binary signal | +3.7% | Bear markets |

## Trading Frequency

| Strategy | Avg Trades/Week | Style |
|:---------|:--------------:|:------|
| Commodity | 0.1 | Holds or cash, rarely trades |
| Value | 1.4 | Patient, low turnover |
| Defensive | 2.0 | Moderate, sells on danger |
| EventDriven | 2.9 | Active around earnings |
| Balanced | 3.3 | Moderate-active |
| Adaptive | 3.3 | Active, mode-switching |
| Mix | 3.3 | Active, multi-asset |
| MixLLM | 3.3 | Same as Mix + LLM calls |
| Momentum | 3.7 | Most active, chases trends |

## Quick Comparison

Default config uses `--frequency biweekly` which overrides all strategies' built-in defaults.

| | Rebalance | ATR Stop | Max Pos | Scoring |
|:--|:---------:|:--------:|:-------:|:--------|
| **Value** | Biweekly* | 3.0x | 5 | 30% low-vol + 30% distance-from-high + 20% RSI + 20% stability |
| **Momentum** | Biweekly | 2.5x | 5 | 40% 12m-1m + 25% trend + 20% MACD + 15% volume |
| **Balanced** | Biweekly | 2.0x | 5 | Regime-weighted: bull=60% momentum, bear=70% value |
| **Defensive** | Biweekly | 1.5x | 5 | 40% low-vol + 30% trend + 30% drawdown |
| **EventDriven** | Biweekly | 2.0x | 5 | 55% event + 25% volume spike + 20% momentum |
| **Adaptive** | Biweekly | 2.0x | 5 | Mode-dependent (4 modes, 4 scoring formulas) |
| **Commodity** | Biweekly | 2.5x | 1 | Binary: oil score > 4 = buy, < 3 = cash |
| **Mix** | Biweekly | 2.0x | 10 | Regime from 7 peers -> 5 allocation profiles |
| **MixLLM** | Biweekly | 2.0x | 10 | Mix regime + Opus can escalate defensiveness |

*Value's code default is quarterly; all others default to monthly. The `--frequency biweekly` flag overrides all strategies in canonical results.

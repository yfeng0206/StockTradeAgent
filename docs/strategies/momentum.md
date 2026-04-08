# Momentum Strategy

> *Aggressive. Chases winners. Cuts losers fast.*

**14-period average: +27.9% | Beats SPY 12/14 | Worst drawdown: -44.4%**

## Scoring Formula

```
composite = mom_score * 0.40 + trend_score * 0.25 + macd_score * 0.20 + vol_score * 0.15 + event_boost
```

| Signal | Weight | How It's Calculated | What It Means |
|:-------|:------:|:-------------------|:-------------|
| 12m-1m Return | 40% | `min(10, max(0, 5 + ret_12m1 / 6))` | Academic momentum: 12-month return excluding last month. +30% -> 10 pts |
| Trend | 25% | Base 5 + 2 (above 200MA) + 2 (above 50MA) + 1 (golden cross) | Price above key MAs = strong trend |
| MACD | 20% | 7 if MACD > signal, 9 if fresh bullish cross, 3 if bearish | Momentum confirmation |
| Volume | 15% | `min(10, max(0, vol_ratio * 5))` | Volume confirms the move |
| Event Boost | +/- | strong_beat within 20 days -> +1.5; pre-earnings (<=3 days) -> -0.5 | Post-earnings drift play |

## Filters

- **RSI > 78**: Multiply mom_score by 0.6 (overbought exhaustion risk)
- **Pre-earnings <= 3 days**: -0.5 penalty (don't buy into uncertainty)

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | **2.5x** (faster exit than Value) |
| Trim Target | **50%** (takes profits early) |
| Max Positions | 5 |
| Min Score | 5.0 (highest threshold) |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell |
| Regime danger | Sell 1/3 of positions |
| News spike | Ignore |
| Earnings beat | **Buy** (ride post-earnings drift) |
| Earnings miss | Sell |
| Volume spike | **Buy aggressively** |
| Profit target | Trim 1/3 at +50% |

## When It Works Best

- **Strong bull markets** (QE Bull: +153.2%, 2023 AI: +42.1%)
- **Clear trends** where winners keep winning
- Post-earnings drift opportunities

## When It Struggles

- **Crashes** (GFC: -37.5%, 2022: -19.2%) -- trend reversal kills it
- **Choppy/sideways** markets -- false breakouts trigger stops
- Worst drawdown of all strategies: -47.4%

# Value Strategy

> *Patient. Ignores short-term noise. Waits for price to catch up to quality.*

**14-period average: +18.0% | Beats SPY 8/14 | Worst drawdown: -37.6%**

## Scoring Formula

```
composite = vol_score * 0.30 + value_score * 0.30 + rsi_score * 0.20 + stability_score * 0.20 + event_adj
```

| Signal | Weight | How It's Calculated | What It Means |
|:-------|:------:|:-------------------|:-------------|
| Volatility | 30% | `max(0, 10 - vol_90d * 20)` | Low vol = quality. 10% vol -> 8 pts, 25% vol -> 5 pts |
| Distance from High | 30% | `min(10, pct_from_high * 0.4)` if >5% off, else `* 0.2` | Beaten-down stocks. 20% off 52-week high = good |
| RSI | 20% | `max(0, (60 - current_rsi) / 6)` | Oversold preferred. RSI 30 -> 5 pts, RSI 60 -> 0 pts |
| Stability | 20% | `max(0, 10 + max_drawdown * 20)` | Low drawdown = quality. -10% dd -> 8 pts, -25% dd -> 5 pts |
| Event Adj | +/- | strong_beat -> +1.5, strong_miss -> -1.5 | Within 45 days of earnings |

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | **Quarterly** (every 3 months) |
| ATR Stop | **3.0x** (widest -- very patient) |
| Trim Target | 30% profit |
| Max Positions | 5 |
| Min Score | 3.5 |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell (but 3.0x ATR = wide stop, rarely fires) |
| Regime danger | **Hold** (ignores short-term regime shifts) |
| News spike | **Hold** |
| Earnings beat | Ignore (scores handle it over 45 days) |
| Earnings miss | Ignore |
| Volume spike | Watch only |
| Profit target | Trim 1/3 at +30% |

## When It Works Best

- **Steady bull markets** (2019: +38.9%)
- **Post-crash recoveries** (Post GFC: +57.6%)
- Markets where quality companies are temporarily cheap

## When It Struggles

- **Fast crashes** (GFC: -33.7%) -- holds through the fall
- **Momentum-driven markets** (2023 AI: underperforms Momentum)
- Quarterly rebalance means slow to react

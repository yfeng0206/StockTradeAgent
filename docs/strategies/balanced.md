# Balanced Strategy

> *Diplomatic. Captures a bit of everything.*

**14-period average: +23.8% | Beats SPY 10/14 | Worst drawdown: -42.0%**

## Scoring Formula

```
composite = value_score * w_value + momentum_score * w_momentum + stability_score * w_quality + event_adj
```

**Weights adapt by regime and geopolitical risk:**

| Condition | Value Weight | Momentum Weight | Quality Weight |
|:----------|:-----------:|:---------------:|:--------------:|
| High vol OR geo_risk > 0.6 | 40% | 10% | 50% |
| Bearish OR geo_risk > 0.4 | 45% | 15% | 40% |
| Bullish AND geo_risk < 0.2 | 20% | 45% | 35% |
| Normal | 30% | 35% | 35% |

**Component scores:**

| Component | Calculation |
|:----------|:-----------|
| Value | distance_from_high * 0.5 + low_vol * 0.5 |
| Momentum | 3m_return * 0.45 + trend * 0.30 + MACD * 0.25 |
| Stability | sharpe_proxy * 0.40 + max_drawdown * 0.35 + vol_consistency * 0.25 |
| Event Adj | strong_beat (30 days) -> +2.0, miss -> -1.0, 8-K + positive momentum -> +0.5 |

**Regime detection:** High vol if vol > 0.25, Bearish if price < 50MA * 0.95, Bullish if price > 50MA * 1.05

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | 2.0x |
| Trim Target | 40% |
| Max Positions | 5 |
| Min Score | 4.5 |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell |
| Regime danger | Sell 1/4 of positions |
| News spike | Sell highest-volatility position |
| Earnings beat | Buy (regime-gated) |
| Earnings miss | Sell (regime-gated) |
| Volume spike | Cautious (small position) |
| Profit target | Trim 1/3 at +40% |

## When It Works Best

- **Recoveries** (Rec-Bull: +35.2%, Post GFC: +48.2%)
- **Transitions** where regime detection helps adapt
- **Geopolitical uncertainty** -- shifts to quality/stability automatically

## When It Struggles

- **Deep crashes** (GFC: -27.9%) -- still exposed
- **Strong momentum** markets -- conservative weighting caps upside

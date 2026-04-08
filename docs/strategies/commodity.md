# Commodity Strategy

> *Specialist. One job, does it well.*

**14-period average: +3.7% | Beats SPY 5/14 | Worst drawdown: -22.7%**

## How It Works

Tracks oil using a single proxy. Either invested in oil or 100% cash. No stocks.

**Oil proxy priority:** USO -> XLE -> XOM (uses first available)

## Scoring Formula

```
trend_score = 0
if above 50MA:  +3
if above 200MA: +2
if ret_1m > 0:  +2
if ret_3m > 0:  +1
if RSI > 75:    -2  (overbought)
if RSI < 30:    +2  (oversold bounce)

Decision: score > 4 = BUY, score < 3 = CASH
```

## Allocation

- **Max 1 position** (oil proxy only)
- **Capped at 50%** of portfolio (rest stays cash as buffer)
- All-or-nothing: either in oil or fully in cash

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Biweekly (code default: monthly) |
| ATR Stop | 2.5x |
| Trim Target | 50% |
| Max Positions | 1 |
| Min Score | 4.0 |

## When It Works Best

- **Bear markets** (GFC: +27.6%, 2022: +8.5%) -- oil often moves opposite to stocks
- **Post Dot-com** recovery (+20.5%)
- As a **hedge** against stock-heavy strategies

## When It Struggles

- **Bull markets** (2019: -0.1%, QE Bull: -14.1%) -- oil lags stocks
- **Oil crashes** (when stocks AND oil fall together)
- Low returns on average (+3.7%) -- it's a hedge, not a growth strategy

## Note

Geopolitical news signal was **removed via ablation** (it hurt returns by -6.5%). The strategy is now purely price-driven.

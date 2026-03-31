# Adaptive Strategy

> *Chameleon. Changes strategy when the market changes.*

**14-period average: +32.1% | Beats SPY 11/14 | Worst drawdown: -35.5%**

## Mode Detection

Reads SPY data on each rebalance day and switches scoring mode:

```
if (vol > 0.28 AND price < 50MA * 0.97) OR drawdown < -12% OR (geo_risk > 0.5 AND vol > 0.22):
    -> DEFENSIVE

elif vol > 0.22 AND ret_1m > 3% AND price > 50MA * 0.98:
    -> RECOVERY

elif price > 50MA AND price > 200MA AND ret_3m > 0% AND vol < 0.25:
    -> MOMENTUM (bullish)

elif abs(ret_3m) < 5% AND vol < 0.20:
    -> VALUE (sideways)

else:
    -> MOMENTUM (default)
```

## Scoring by Mode

### MOMENTUM Mode
```
mom * 0.45 + trend * 0.30 + macd * 0.25
```
- mom = `min(10, max(0, 5 + ret_3m / 4))`
- trend = 7 if above MA, 3 if below
- macd = 7 if EMA12 > EMA26, 3 if below

### DEFENSIVE Mode
```
vol_score * 0.50 + trend * 0.50
```
- Only keeps top 2-3 positions (strict composite >= 5)
- Lowest-volatility names only

### VALUE Mode
```
vol_score * 0.35 + value_dist * 0.35 + rsi_score * 0.30
```

### RECOVERY Mode
```
bounce_score * 0.35 + upside_score * 0.30 + mom_score * 0.35
```
- bounce = `(current - low_60d) / low_60d * 100`
- Targets stocks bouncing hardest off their lows

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | 2.0x |
| Trim Target | 40% |
| Max Positions | 5 |
| Min Score | 4.0 |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell |
| Regime danger | Sell 1/4 of positions |
| News spike | Sell highest-volatility position |
| Earnings beat | Buy (regime-gated) |
| Earnings miss | Sell (regime-gated) |
| Volume spike | Cautious |
| Profit target | Trim 1/3 at +40% |

## When It Works Best

- **Strong trends** (2023 AI: +57.0%, QE Bull: +112.7%)
- **Regime transitions** (Pre-COVID: +82.3%)
- Markets where mode-switching captures the right approach

## When It Struggles

- **Sudden crashes** (GFC: -17.7%) -- mode switches monthly, crash happens in days
- **Whipsaw** between modes in volatile sideways markets
- Mode detection uses only SPY -- misses sector-specific signals

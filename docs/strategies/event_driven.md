# EventDriven Strategy

> *Opportunistic. Waits for events, then pounces.*

**14-period average: +8.0% | Beats SPY 5/14 | Worst drawdown: -31.1%**

## Hard Event Gate

This strategy **only scores stocks with a recent event** (earnings or 8-K filing). No event = not scored at all. This is the key differentiator.

## Scoring Formula

```
composite = event_score * 0.55 + vol_score * 0.25 + mom_score * 0.20
```

**Event scoring (by days since earnings):**

| Window | strong_beat | beat | miss | strong_miss |
|:-------|:----------:|:----:|:----:|:-----------:|
| 0-25 days | 9 | 7.5 | 2 | 0.5 |
| 26-45 days | 6.5 | 6.5 | 3.5 | 3.5 |
| Upcoming (<=3 days) | 4 | 4 | 4 | 4 |

**8-K filing response:** 5-day return > +3% -> +1.5 to event_score; < -3% -> -1.5

**Volume confirmation:** vol_ratio > 2.0x + positive return -> 8 pts; negative return -> 2 pts

**Momentum:** above 20-day SMA -> 7 pts; below -> 3 pts

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly + weekly event checks |
| ATR Stop | 2.0x |
| Trim Target | 35% |
| Max Positions | 5 |
| Min Score | **3.0** (lowest threshold -- aggressive) |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell |
| Regime danger | Sell worst performer |
| News spike | Sell worst performer |
| Earnings beat | **Buy** (core signal) |
| Earnings miss | **Sell** |
| Volume spike | **Buy** (with lower threshold) |
| Profit target | Trim 1/3 at +35% |

## When It Works Best

- **Catalyst-rich periods** (2023 AI: +64.5%, Dot-com: +51.9%)
- **Earnings season** -- highest trading frequency of all strategies
- Markets with clear beat/miss patterns

## When It Struggles

- **Bear markets** (2022: -27.0%) -- events don't help when everything drops
- **Quiet periods** with few earnings (returns near zero)
- Hard event gate means often sitting in cash

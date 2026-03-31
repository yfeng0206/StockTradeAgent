# Defensive Strategy

> *Paranoid. Always watching for the next crash.*

**14-period average: +13.9% | Beats SPY 5/14 | Worst drawdown: -20.3%**

## 3-State Exposure Model

The key feature: exposure scales with danger level, not binary in/out.

| State | Danger Signals | Exposure | Effective Max Positions |
|:------|:--------------:|:--------:|:----------------------:|
| **NORMAL** | 0-1 | 100% | max_positions (5) |
| **REDUCED** | 2 | 50% | max_positions / 2 |
| **DEFENSE** | 3+ | 20% | max_positions / 5 (1) |

**Danger signals (counted from SPY):**
1. High volatility: `vol_20d > 0.28`
2. Below trend: `price < 50MA * 0.97`
3. Deep drawdown: `drawdown < -10%`

## Scoring Formula

```
composite = vol_score * 0.40 + trend_score * 0.30 + dd_score * 0.30 + event_adj
```

| Signal | Weight | Calculation |
|:-------|:------:|:-----------|
| Low Volatility | 40% | `max(0, 10 - vol_60d * 20)` |
| Trend | 30% | 7 if above 200MA, 3 if below |
| Max Drawdown | 30% | `max(0, 10 + max_dd * 20)` |
| Event Adj | +/- | strong_miss -> -3, strong_beat -> +1 |

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | **1.5x** (tightest of all strategies) |
| Trim Target | 35% |
| Max Positions | 5 |
| Min Score | 4.0 |

## Trigger Reactions

| Trigger | Action |
|:--------|:-------|
| Stop-loss | Sell (fires often due to tight 1.5x stop) |
| Regime danger | **Sell ALL positions** (most aggressive response) |
| News spike | Sell highest-volatility position |
| Earnings beat | Buy (regime-gated) |
| Earnings miss | Sell |
| Volume spike | **Exit** (views spikes as danger) |
| Profit target | Trim 1/3 at +35% |

## When It Works Best

- **Transitions into crashes** (Bull-Rec: +15.2%, only strategy positive)
- **Limiting drawdowns** (worst ever: -20.3% vs SPY -55.1%)
- Capital preservation

## When It Struggles

- **Bull markets** (2023 AI: -6.4%, missed the entire rally)
- **Recoveries** (Post GFC: +17.3% vs SPY +90.2%)
- Tight stops cause frequent whipsaw in volatile markets

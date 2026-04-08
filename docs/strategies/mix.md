# Mix Strategy

> *The conductor. Watches everyone else, then decides.*

**14-period average: +34.9% | Beats SPY 10/14 | Worst drawdown: -23.6%**

**Second-best strategy.** Uses the other 7 strategies as live sensors to detect the market regime, then allocates across stocks + commodity + cash simultaneously.

## How It Works

### Step 1: Read Peer Sensors

On each rebalance day, Mix reads the live state of all 7 other strategies:

| Sensor | What It Reads | Why It Matters |
|:-------|:-------------|:---------------|
| Strategy returns | Each strategy's current P&L | Who's winning = what's working |
| Defensive state | NORMAL / REDUCED / DEFENSE | Danger level from Defensive's 3-state model |
| Adaptive mode | MOMENTUM / VALUE / DEFENSIVE / RECOVERY | Regime classification from Adaptive |
| Commodity invested | Is oil strategy holding USO? | Inflation/geopolitical signal |
| Cash heavy count | How many strategies are >50% cash | Consensus fear level |

### Step 2: Read Market Directly

| Signal | Threshold |
|:-------|:---------|
| SPY above 50-day MA | Boolean |
| SPY above 200-day MA | Boolean |
| SPY 20-day volatility | > 0.22 = elevated, > 0.25 = high |
| SPY 1m/3m returns | Direction + magnitude |
| SPY drawdown from 60-day peak | < -8% = significant dip |
| Oil signal | Bullish/bearish from oil proxy |

### Step 3: Classify Regime (Decision Tree)

```
1. DEFENSIVE (protect capital — highest priority):
   - Defensive in DEFENSE AND (vol > 0.25 OR Adaptive in DEFENSIVE)
   - OR 4+ strategies heavy in cash

2. AGGRESSIVE (capture upside — fast to recognize):
   - Adaptive in MOMENTUM AND SPY above 50MA
   - OR Momentum making money AND SPY above 200MA AND Defensive in NORMAL
   - OR SPY above both MAs AND vol < 0.22

3. RECOVERY:
   - Adaptive in RECOVERY OR (SPY drawdown < -8% AND 1m return > +2%)

4. CAUTIOUS:
   - Commodity outperforming average by >10% AND SPY below 50MA
   - OR Defensive in REDUCED AND SPY below 200MA

5. Default: AGGRESSIVE if SPY above 200MA, else UNCERTAIN
```

### Step 4: Allocate

| Regime | Stocks | Commodity | Cash |
|:-------|:------:|:---------:|:----:|
| **AGGRESSIVE** | 90% | 0% | 10% |
| **RECOVERY** | 80% | 0% | 20% |
| **UNCERTAIN** | 70% | 0% | 30% |
| **CAUTIOUS** | 50% | 20% | 30% |
| **DEFENSIVE** | 20% | 30% | 50% |

### Step 5: Pick Stocks by Regime

| Regime | Stock Scoring |
|:-------|:-------------|
| AGGRESSIVE | Momentum stocks (3m return, trend, MACD) |
| DEFENSIVE | Lowest-volatility names only (vol * 0.45 + trend * 0.30 + dd * 0.25) |
| RECOVERY | Bounce + upside + momentum |
| CAUTIOUS | Low-vol + trend + momentum blend |
| UNCERTAIN | Balanced value + momentum + trend |

## Asymmetric Regime Stickiness

Configurable via `--regime-stickiness` (default: 1 = instant switch).

When stickiness > 1:
- **Escalating toward defensive:** Instant (no delay -- protect capital fast)
- **De-escalating toward aggressive:** Require N consecutive days (prevent whipsaw)

After testing stickiness=1/3/5 across all 14 periods, **stickiness=1 is best overall** for Mix.

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | 2.0x |
| Trim Target | 40% |
| Max Positions | **10** (highest -- for diversified allocation) |
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

- **Almost always** (beats SPY in 10 of 14 periods)
- **Bull markets** (QE Bull: +94.7%, Post Dot-com: +92.3%, Pre-COVID: +81.8%)
- **Transitions** (Bull-Rec: +26.4% while SPY lost -10.3%)

## When It Struggles

- **V-shaped recoveries** (Post GFC: +48.5% vs SPY +90.2%) -- slow to re-enter after going defensive
- The recovery problem is documented in [experiments](../experiments/README.md#experiment-3-regime-stickiness)

## Why It Beats Individual Strategies

1. **Consensus detection** -- when 4 of 7 strategies go to cash, that's a danger signal no single strategy has
2. **Best of both** -- scores stocks using Momentum+Value blend, sizes by regime
3. **Multi-asset** -- can hold commodity (oil) during commodity-led crises
4. **Timing edge** -- sees peers panicking before SPY fully crashes

# MixLLM Strategy

> *The risk manager. Coded rules drive, Opus pulls the emergency brake.*

**14-period average: +33.9% | Beats SPY 12/14 | Worst drawdown: -22.9%**

**Best crash protection.** Averages **+6.4% gains during the 4 worst crashes** while SPY averages -25.5% and QQQ -32.7%.

## Architecture

```
1. Coded Mix rules compute baseline regime (AGGRESSIVE, CAUTIOUS, etc.)
2. Rich sensor data compiled (SPY, sectors, safe havens, oil, bonds, news)
3. Claude Opus called to CONFIRM or ESCALATE
4. LLM can ONLY escalate (make more defensive), never reduce
5. Falls back to coded regime if LLM fails
```

## What the LLM Sees

On each rebalance day (~10-15 calls per backtest period), Opus receives:

| Data Category | Specific Signals |
|:-------------|:-----------------|
| Peer strategies | 7 strategies' returns, Defensive state, Adaptive mode, cash counts |
| SPY | Above/below 50MA and 200MA, volatility, 1m/3m returns, drawdown |
| Sector rotation | 1m/3m returns for energy, tech, finance, healthcare, staples, consumer, industrial |
| Market breadth | How many sectors positive on 3-month basis |
| Safe havens | Gold (GLD), Long-term Treasuries (TLT) -- 1m/3m returns |
| Risk appetite | High Yield bonds (HYG), Investment Grade (LQD) -- 1m/3m returns |
| Energy detail | Oil (USO), Energy sector (XLE) -- 1m/3m returns, oil vs SPY divergence |
| News | Geopolitical risk score, signal engine regime |
| History | Last 5 regime classifications |
| Pattern alerts | Commodity dominance, momentum+value both negative, narrow breadth |

## LLM Escalation Rules

The system prompt instructs Opus:

**CONFIRM (80%+ of the time):**
- SPY above both MAs and vol is low -> CONFIRM
- Mixed signals with no clear crisis -> CONFIRM
- Rising geo_risk alone is NOT enough (needs market damage)

**ESCALATE to CAUTIOUS (rare):**
- SPY below 50MA AND oil outperforming SPY by >15%
- Gold up >15% AND safe havens rising AND breadth < 3 sectors
- Clear structural shift, not just a dip

**ESCALATE to DEFENSIVE (very rare):**
- Oil surging >30% AND SPY below both MAs
- Gold AND treasuries surging AND HYG falling (flight to safety)
- Energy is the ONLY positive sector AND geo_risk > 0.5 AND SPY in drawdown > -5%

## Key Lesson from Backtesting

> "The cost of false alarms is HIGHER than the cost of late detection."

- In 2025, coded rules stayed AGGRESSIVE and earned +24.4%. An LLM that constantly worried about gold and geo_risk would have earned only +7.3%.
- In Q1 2026, DEFENSIVE captured the +28% oil trade that coded rules missed.
- The LLM's value is ONLY in catching genuine crises.

## GFC Case Study (the LLM's finest hour)

During the 2007-2009 GFC, the LLM made 13 escalation overrides. The 3 most valuable:

1. **April 2008**: Blocked AGGRESSIVE re-entry during bear market rally. Saved ~$6,500.
2. **September 2008**: Blocked AGGRESSIVE allocation 2 weeks before Lehman. Saved ~$2,000.
3. **January 2009**: Blocked false RECOVERY signal. Prevented $8,000 drawdown.

The LLM identified **credit market stress** (HY bonds falling, financial sector diverging, gold/treasuries surging) that the coded rules couldn't see.

## Opus vs Sonnet

Tested both models across 7 periods:

| | Opus | Sonnet |
|:--|:---:|:-----:|
| Average return | **+16.1%** | +15.0% |
| Wins | **3 periods** | 2 periods |
| Best at | Bear markets | Transitions |

Opus is the default. Better in crashes where it matters most.

## Parameters

| Setting | Value |
|:--------|:------|
| Rebalance | Monthly |
| ATR Stop | 2.0x |
| Trim Target | 40% |
| Max Positions | 10 |
| Min Score | 4.0 |
| LLM Model | Opus (configurable via MIXLLM_MODEL env var) |
| LLM Calls | ~10-15 per backtest period (rebalance days only) |
| Fallback | Coded regime if LLM fails |

## When It Works Best

- **Crashes** (Dot-com: +20.4%, GFC: +8.9%) -- the LLM catches what rules miss
- **Bull markets** (+78.3% in QE Bull) -- confirms AGGRESSIVE, stays out of the way
- **Geopolitical crises** -- reads credit stress, safe-haven flows

## When It Struggles

- **Recoveries** (Post GFC: +3.6%) -- LLM has defensive bias, slow to re-enter
- **Cost**: -6.8% annual "insurance premium" vs Mix (the price of crash protection)
- Non-deterministic (LLM varies between runs)

## The Tradeoff

| | Mix | MixLLM |
|:--|:---:|:-----:|
| Avg return | **+36.7%** | +33.9% |
| Crash avg | -0.3% | **+6.4%** |
| Worst DD | -25.0% | **-22.9%** |
| Sleep at night | Good | **Best** |

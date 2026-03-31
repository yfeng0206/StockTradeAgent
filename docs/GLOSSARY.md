# Glossary

Terms used throughout this project.

## Performance Metrics

| Term | Definition |
|:-----|:----------|
| **Alpha** | Returns above the benchmark (SPY). +10% alpha means the strategy returned 10% more than SPY over the same period. |
| **Sharpe Ratio** | Risk-adjusted return. (Return - Risk-free rate) / Volatility. Higher = better. >1.0 is good, >2.0 is excellent. |
| **Max Drawdown (DD)** | Largest peak-to-trough drop. If portfolio went from $120k to $90k, max DD = -25%. Measures worst-case pain. |
| **Win Rate** | Percentage of trades that made money. 50% win rate with 2:1 reward/risk is profitable. |
| **Beats SPY** | How many test periods the strategy returned more than SPY buy-and-hold. 12/14 means it beat SPY in 12 of 14 periods. |

## Regime Detection

| Term | Definition |
|:-----|:----------|
| **Regime** | The current market environment. Our system detects: bullish, bearish, crisis, high_volatility, sideways, recovery, normal. |
| **AGGRESSIVE** | Mix/MixLLM allocation: 90% stocks, 0% commodity, 10% cash. Used when market is healthy. |
| **CAUTIOUS** | 50% stocks, 20% commodity, 30% cash. Used when oil is outperforming or early warning signals appear. |
| **DEFENSIVE** | 20% stocks, 30% commodity, 50% cash. Used during confirmed crises. |
| **RECOVERY** | 80% stocks, 0% commodity, 20% cash. Used when market is bouncing off a dip. |
| **UNCERTAIN** | 70% stocks, 0% commodity, 30% cash. Default when signals are mixed. |
| **Regime Stickiness** | How many consecutive days a new regime must be detected before switching. Stickiness=1 means instant switch. Higher values reduce whipsaw but delay reactions. Default: 1. |
| **Asymmetric Stickiness** | Fast to go defensive (instant), slow to leave defensive (requires N days). Prevents panic-selling in recoveries while maintaining crash protection. |

## Strategy Terms

| Term | Definition |
|:-----|:----------|
| **Peer Sensors** | Mix/MixLLM read the other 7 strategies' live state (returns, cash levels, modes) as signals for regime detection. |
| **Escalation** | MixLLM's LLM can only make the regime MORE defensive, never less. This prevents the LLM from overriding crash protection. |
| **3-State Exposure** | Defensive strategy's model: NORMAL (100% invested), REDUCED (50%), DEFENSE (20%). Scales exposure with danger level. |
| **Mode Switching** | Adaptive strategy changes its entire scoring formula based on detected mode: MOMENTUM, VALUE, DEFENSIVE, or RECOVERY. |
| **Hard Event Gate** | EventDriven strategy only scores stocks with a recent earnings or 8-K filing. No event = not considered at all. |

## Technical Signals

| Term | Definition |
|:-----|:----------|
| **ATR** | Average True Range. Measures daily price volatility in dollars. A $100 stock with 2% ATR moves ~$2/day on average. |
| **ATR Stop** | Stop-loss set at entry price minus (ATR x multiplier). 2.0x ATR stop on a $100 stock with $2 ATR = stop at $96. Wider multiplier = more patient. |
| **RSI** | Relative Strength Index (0-100). Below 30 = oversold (potential buy). Above 70 = overbought (potential sell). |
| **MACD** | Moving Average Convergence Divergence. When MACD line crosses above signal line = bullish momentum. |
| **Golden Cross** | 50-day MA crosses above 200-day MA. Classic bullish signal. |
| **Death Cross** | 50-day MA crosses below 200-day MA. Classic bearish signal. |
| **12m-1m Signal** | Academic momentum factor: 12-month return excluding the most recent month. Avoids short-term reversal while capturing trend. |
| **Bollinger Bands** | Price channel: 20-day MA +/- 2 standard deviations. Price touching upper band = overbought, lower = oversold. |
| **Volume Ratio** | Current volume / 20-day average volume. >2.0 = significant volume spike. |

## Trigger Types

| Term | Definition |
|:-----|:----------|
| **Stop-Loss** | Automatic sell when price drops below ATR-based stop level. Each strategy has different ATR multipliers (1.5x to 3.0x). |
| **Profit Target (Trim)** | Sell 1/3 of position when profit exceeds threshold (30-50% depending on strategy). Lock in gains while keeping exposure. |
| **Regime Change** | Market regime shifted (e.g., bullish -> bearish). Different strategies react differently (some sell, some hold). |
| **News Spike** | Geopolitical risk score jumped significantly. Measured via GDELT events with exponential decay (half-life 2 days). |
| **Volume Anomaly** | Unusual trading volume (>2x average) combined with significant price move (>5%). Can signal institutional activity. |
| **Earnings Release** | Company reported earnings within +/-3 days. Signal strength depends on beat/miss magnitude. |

## Data Terms

| Term | Definition |
|:-----|:----------|
| **Universe** | The 93 stocks + SPY/QQQ that strategies can buy. Spans 15 sectors from tech to energy to healthcare. |
| **Temporal Gating** | On date T, the simulation only uses data from dates <= T. Prevents look-ahead bias (cheating with future data). |
| **Partial Fill** | If cash < full position size, buy what you can afford instead of skipping entirely. |
| **Cash Floor** | Minimum cash held at all times. Base 2% + up to 8% during danger regimes. Max 15%. |

## Period Types

| Term | Definition |
|:-----|:----------|
| **Bull Market** | Sustained uptrend. SPY above 200-day MA, low volatility, positive returns. |
| **Bear Market** | Sustained downtrend. SPY below key MAs, high volatility, negative returns. |
| **Crash** | Sharp, sudden decline (>20% drawdown). Examples: dot-com (-77% QQQ), GFC (-46% SPY), COVID (-34% SPY). |
| **Recovery** | Bounce back after a crash. Often V-shaped. SPY rising from lows but may still be below pre-crash peak. |
| **Transition** | Market shifting from one regime to another (e.g., bull -> bear). Hardest periods for all strategies. |

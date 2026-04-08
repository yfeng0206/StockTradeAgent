# Credits & References

This project was inspired by and builds upon several existing works. We give credit where it's due, and show how our approach compares on their own test periods.

---

## TradingAgents (TauricResearch)

**Paper:** [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)
**GitHub:** [github.com/TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)

### What We Borrowed

Their **shared detection + per-strategy interpretation** architecture directly inspired our risk overlay design:

- **Their approach:** LLM analyst team produces shared reports, then bull/bear agents debate, then a risk manager decides.
- **Our approach:** `RawSignalDetector` produces shared market facts (like their analyst team), then `StrategyJudge` interprets per strategy (like their risk manager), and our `/stock-research` skill uses their bull vs bear adversarial debate format.

Specific code influenced by their paper:
- `eval/risk_overlay.py` — shared detection + per-strategy interpretation pattern
- `.claude/skills/stock-research.md` — 5-turn bull/bear debate + judge panel

### How We Compare

TradingAgents tested on **3 months of data (Jan-Mar 2024)** with **3 stocks (TSLA, NVDA, AAPL)**.

We ran our strategies on that same period for direct comparison:

| System | Period | Universe | Return | Cost |
|:-------|:-------|:---------|:------:|:----:|
| **TradingAgents** | Jan-Mar 2024 (3 months) | 3 stocks | Not published (qualitative results) | $5-100/day |
| **ConsensusAITrader** | 25 years (14 periods) | 93 stocks | MixLLM: +39.1% avg, Mix: +34.9% avg | $0 |

### Key Differences

| Feature | TradingAgents | ConsensusAITrader |
|:--------|:-------------|:------------------|
| Architecture | LLM-only (all reasoning via GPT-4) | Hybrid (coded rules + LLM risk monitor) |
| Cost | $5-100/day (GPT-4 API calls) | $0 (coded rules) or included in Claude CLI |
| Deterministic | No | Yes (except MixLLM) |
| Test duration | 3 months | 25 years, 14 regimes |
| Crash tested | No | Yes (dot-com, GFC, COVID, 2022) |
| Strategies | 1 (LLM-driven) | 9 (7 coded + Mix + MixLLM) |
| Ablation tested | No | Yes (stickiness, position size, model, commodities) |

---

## AI-Trader (HKUDS)

**Paper:** [AI-Trader: An Agent-based Stock Trading Framework](https://arxiv.org/abs/2502.14401)
**GitHub:** [github.com/HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader)

### What We Learned From

Their work on **LLM-driven portfolio management** and **multi-agent debate** frameworks influenced our thinking about how to structure the adversarial debate in `/stock-research`. Their approach uses multiple LLM agents debating investment decisions.

### How We Compare

AI-Trader tested on **5 weeks of NASDAQ-100 data**.

| System | Period | Universe | Approach | Cost |
|:-------|:-------|:---------|:---------|:----:|
| **AI-Trader** | 5 weeks | NASDAQ-100 | LLM multi-agent debate | $5-50/day |
| **ConsensusAITrader** | 25 years | 93 stocks | Coded rules + LLM escalation | $0 |

### Key Differences

| Feature | AI-Trader | ConsensusAITrader |
|:--------|:---------|:------------------|
| Engine | LLM-only | Coded rules (deterministic) |
| LLM role | All decisions | Risk monitor only (escalation) |
| Test duration | 5 weeks | 25 years |
| Reproducibility | No (LLM varies) | Yes (coded strategies are deterministic) |
| Cost | $5-50/day | $0 |

---

## Academic Influences

### Momentum Factor (Jegadeesh & Titman, 1993)

Our **Momentum strategy** uses the academic **12-minus-1 month** signal from the foundational momentum factor paper. This skips the most recent month (short-term reversal) while capturing the 2-12 month trend.

- **Paper:** "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency"
- **Our implementation:** `eval/strategies/momentum_strategy.py` — `ret_12m1` signal with 40% weight

### CTA Trend Following (Multiple Sources)

Our **commodity strategy research** (documented in `docs/experiments/README.md`) drew on CTA (Commodity Trading Advisor) research:

- CFA Institute: "Decoding CTA Allocations by Trend Horizon" (Jan 2026) — multi-timeframe signal blending
- QuantifiedStrategies.com — backtested dual MA crossover (100/350 day) on 27 commodity futures
- Turtle Trading Rules (1983) — Donchian channel breakout with ATR-based position sizing

### Risk Parity Concepts

Our **inverse-volatility position sizing** and **dynamic cash floor** draw on risk parity principles from Bridgewater's All Weather portfolio concept, adapted for an event-driven system.

---

## Tools & Libraries

| Library | How We Use It | License |
|:--------|:-------------|:--------|
| [yfinance](https://github.com/ranaroussi/yfinance) | Price data, fundamentals, earnings, news | Apache 2.0 |
| [ta](https://github.com/bukosabino/ta) | Technical indicator computation | MIT |
| [pandas](https://pandas.pydata.org/) | Data manipulation throughout | BSD 3 |
| [numpy](https://numpy.org/) | Numerical computation | BSD 3 |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Claude API for MixLLM (optional) | MIT |

---

## Data Sources

| Source | License/Terms | How We Use It |
|:-------|:-------------|:-------------|
| [Yahoo Finance](https://finance.yahoo.com/) (via yfinance) | Yahoo Terms of Service | Prices, fundamentals, earnings |
| [SEC EDGAR](https://www.sec.gov/edgar) | Public domain (US government) | 10-K, 10-Q, 8-K filings |
| [Wikipedia Current Events](https://en.wikipedia.org/wiki/Portal:Current_events) | CC BY-SA 3.0 | Historical world events |
| [GDELT Project](https://www.gdeltproject.org/) | Open access | Geopolitical event monitoring |
| [FRED](https://fred.stlouisfed.org/) | Public domain (US government) | Macro economic data (optional) |

---
name: stock-research
description: Deep stock research analysis on a single ticker
user_invocable: true
arguments:
  - name: ticker
    description: Stock ticker symbol (e.g., AAPL, NVDA, MSFT)
    required: true
---

# Stock Research Agent

You are a professional stock research analyst. Perform a comprehensive multi-horizon analysis of **{ticker}** using the Python tools available, then synthesize everything into an actionable research report.

## Phase 0: Load Context from Past Runs

Check the most recent simulation run for context:

```bash
# Find most recent run
ls -t runs/ | head -1
# If a recent run exists, check its memory and results:
# cat runs/{latest}/portfolios/Balanced/memory.json
```

Also check today's news briefing for market context:
```bash
python tools/news_collector.py --briefing --date $(date +%Y-%m-%d)
```

## Phase 1: Data Collection

### 1a. News & Market Context (collect if missing, then read briefing)

```bash
# Collect any missing news categories for today (skips what's already collected)
python tools/news_collector.py
# Generate compact briefing with this ticker's company news
python tools/news_collector.py --briefing --ticker {ticker}
```

The briefing gives you: market mood (VIX), commodities (oil/gold), currencies, sector rotation,
geopolitical events, macro/policy headlines, and company-specific news — all in summary format.

If the briefing shows a specific area needs more detail (e.g., oil crisis impacting energy stocks),
you can pull that category's full data: `python tools/news_collector.py --category commodities --force`

### 1b. Stock-Specific Data (run in parallel)

```bash
python tools/fetch_price_data.py {ticker}
python tools/fetch_fundamentals.py {ticker}
python tools/technical_indicators.py {ticker}
python tools/earnings.py {ticker}
python tools/valuation.py {ticker}
python tools/sentiment.py {ticker}
python tools/insider_activity.py {ticker}
```

Optionally, if the company is U.S.-listed, also run:
```bash
python tools/fetch_filings.py {ticker}
```

## Phase 2: Long-Horizon Fundamental Analysis

Using the fundamentals, valuation, earnings, and filings data, analyze:

1. **Business Quality**: What does this company do? Is revenue growing? Are margins expanding or contracting? How is the balance sheet (debt levels, cash position)?
2. **Profitability**: ROE, ROA, profit margins — is this a high-quality business?
3. **Valuation**: What does the DCF say? How do multiples (P/E, EV/EBITDA, P/S) compare to the sector? Is there a margin of safety?
4. **Earnings Trajectory**: Are earnings estimates going up or down? Any recent surprises?
5. **Score this 1-10** with explicit reasoning.

## Phase 3: Short-Horizon Technical & Event Analysis

Using technical indicators, news, sentiment, and insider data, analyze:

1. **Trend**: Is the stock in an uptrend, downtrend, or sideways? What do moving averages say?
2. **Momentum**: RSI, MACD — is momentum building or fading?
3. **Volume**: Is volume confirming the trend? Any unusual activity?
4. **Events & Catalysts**: Upcoming earnings? Recent news? Insider buying/selling? SEC filings?
5. **Sentiment**: What do analysts say? How's the short interest? Social buzz?
6. **Score this 1-10** with explicit reasoning.

## Phase 4: Macro Context

Using macro data, assess:
- How does the current macro environment (rates, inflation, VIX, sector rotation) affect this stock?
- Is the sector this stock belongs to in favor or out of favor?
- Any macro headwinds or tailwinds?

## Phase 4b: Contradiction Scan

Before synthesizing, explicitly check for CONFLICTS across your data sources:

1. **Technical vs Fundamentals**: Does the price action agree with the financial health? (e.g., RSI says overbought but earnings are accelerating — note the tension)
2. **News vs Price**: Does sentiment agree with price action? (e.g., news is bearish but stock is at ATH — which side is wrong?)
3. **Insiders vs Analysts**: Are insiders selling while analysts say "buy"? That is a red flag.
4. **Stock vs Sector**: Is this stock rising in a falling sector (genuine outperformer or last holdout?) or falling in a rising sector (genuine underperformer or rotation candidate)?
5. **Short-term vs Long-term**: Do daily/weekly signals conflict with monthly/quarterly trends?

For each contradiction found:
- State which signal you trust MORE and why
- State how it affects your confidence level
- Contradictions reduce confidence and position size, but don't automatically mean "don't trade"

## Phase 5: Adversarial Debate (5 shared turns)

This debate is about THE STOCK — same arguments regardless of strategy.
Like TradingAgents: the analyst reports and bull/bear debate are shared facts.
What differs is how each strategy JUDGE interprets them (Phase 6).

Every turn uses the same structure. Every turn gets logged.

### Turn 1: Bull Analyst Opens

Adopt the mindset of a **senior growth fund analyst** whose job is to find reasons to BUY.

Produce exactly this structure:
- **Thesis**: One sentence on why this stock should be bought now
- **3 strongest facts**: Cite specific numbers from the data you collected
- **2 risks the bears will raise**: Preemptively address the strongest counter-arguments
- **What would change my mind**: The ONE data point that would invalidate the bull case
- **Conviction**: HIGH / MEDIUM / LOW

### Turn 2: Bear Analyst Responds

Adopt the mindset of a **senior short-seller** who finds overvalued stocks.

- **Thesis**: One sentence on why this stock should be avoided or sold
- **3 strongest facts**: Cite specific numbers the bull downplayed or ignored
- **2 things the bull got right**: Be fair
- **What would change my mind**: The ONE data point that would make you cover the short
- **Conviction**: HIGH / MEDIUM / LOW

### Turn 3: Bull Rebuttal

- **Bear's strongest point**: Quote the most damaging argument
- **Rebuttal**: Why is this wrong? Cite data.
- **New evidence**: One additional supporting fact held in reserve

### Turn 4: Bear Rebuttal

- **Bull's strongest point**: Quote the most compelling argument
- **Rebuttal**: Why is this misleading, temporary, or priced in? Cite data.
- **New evidence**: One additional risk held in reserve

### Turn 5: Debate Moderator Summary

Neutral summary of the debate (NOT a verdict — that comes from the judges):
- **Key agreement**: What did both sides agree on?
- **Key disagreement**: The one thing they could NOT resolve
- **Strongest evidence from each side**: One fact each that was hardest to rebut

## Phase 6: Strategy Judge Panel (7 turns)

Each of our 7 strategy judges reads the SAME debate and SAME data from Phases 1-5.
But each judge evaluates through their own lens — different priorities, different risk tolerance.

Every judge produces the SAME structured output:

- **Verdict**: BUY / HOLD / SELL from this strategy's perspective
- **Debate winner**: Bull or Bear — from this strategy's lens
- **Key evidence**: The 1-2 data points that matter MOST to this strategy
- **Irrelevant to me**: The 1-2 data points that this strategy intentionally IGNORES
- **Conflicts that matter**: Which contradictions from Phase 4b concern this judge
- **What would change my mind**: Strategy-specific invalidation
- **Confidence**: HIGH / MEDIUM / LOW
- **Position sizing**: Full / Half / Skip — and why

### Turn 6: Value Judge
"I care about fundamentals: P/E, margins, book value, dividend yield. Short-term price action is noise. I want to buy cheap quality and hold."

### Turn 7: Momentum Judge
"I follow price. Above the MAs with volume = buy. Below = sell. I don't care what the P/E is. Trend is truth."

### Turn 8: Defensive Judge
"I care about not losing money. High volatility is a dealbreaker. I'd rather miss gains than take losses. Capital preservation first."

### Turn 9: EventDriven Judge
"When is the next earnings report? Any upcoming catalysts? That's all I care about. Everything else is noise until the event passes."

### Turn 10: Balanced Judge
"I weigh everything equally — fundamentals, technicals, macro, sentiment. No single factor dominates. Show me the composite picture."

### Turn 11: Adaptive Judge
"What regime are we in? Bull market = I favor growth signals. Crisis = I favor defensive signals. The regime decides which data matters."

### Turn 12: Commodity Judge
"How correlated is this stock with oil/energy/commodities? If it's an energy stock, the commodity cycle trumps everything. If not, I defer to other judges."

## Phase 6b: Cross-Strategy Synthesis (Turn 13)

Now evaluate all 7 judges as the **Chief Strategist**:
- **Consensus**: How many judges said BUY vs HOLD vs SELL?
- **Agreement areas**: Where did most judges agree?
- **Disagreement areas**: Where did judges split, and why?
- **Most relevant judge**: For THIS stock in THIS environment, which strategy perspective is most applicable?
- **Final recommendation**: Synthesize across all 7 into one verdict

### File Structure

Save ALL outputs into `runs/research/{ticker}_{date}/`:

```
runs/research/{ticker}_{date}/
├── data/
│   └── collected.json              # Raw tool outputs (SHARED)
├── debate/
│   ├── turns.json                  # 5-turn bull/bear debate (SHARED)
│   └── contradictions.json         # Signal conflicts (SHARED)
├── judges/
│   ├── Value.json                  # Value judge verdict (PER-STRATEGY)
│   ├── Momentum.json
│   ├── Defensive.json
│   ├── EventDriven.json
│   ├── Balanced.json
│   ├── Adaptive.json
│   └── Commodity.json
├── synthesis.json                  # Cross-strategy verdict + final rec
└── report.md                       # Human-readable report
```

### JSON Schemas

**debate/turns.json:**
```json
{
  "ticker": "{ticker}",
  "date": "YYYY-MM-DD",
  "total_turns": 5,
  "turns": [
    {"turn": 1, "speaker": "bull", "thesis": "...", "facts": [], "risks_addressed": [], "invalidation": "...", "conviction": "..."},
    {"turn": 2, "speaker": "bear", "thesis": "...", "facts": [], "bull_concessions": [], "invalidation": "...", "conviction": "..."},
    {"turn": 3, "speaker": "bull_rebuttal", "bear_strongest_point": "...", "rebuttal": "...", "new_evidence": "..."},
    {"turn": 4, "speaker": "bear_rebuttal", "bull_strongest_point": "...", "rebuttal": "...", "new_evidence": "..."},
    {"turn": 5, "speaker": "moderator", "key_agreement": "...", "key_disagreement": "...", "strongest_evidence": {"bull": "...", "bear": "..."}}
  ]
}
```

**judges/{Strategy}.json:**
```json
{
  "strategy": "Value",
  "ticker": "{ticker}",
  "verdict": "BUY/HOLD/SELL",
  "debate_winner": "bull/bear",
  "key_evidence": ["...", "..."],
  "irrelevant_to_me": ["...", "..."],
  "conflicts_that_matter": ["..."],
  "invalidation": "...",
  "confidence": "HIGH/MEDIUM/LOW",
  "position_sizing": "full/half/skip",
  "reasoning": "..."
}
```

**synthesis.json:**
```json
{
  "ticker": "{ticker}",
  "date": "YYYY-MM-DD",
  "judge_votes": {"BUY": 0, "HOLD": 0, "SELL": 0},
  "agreement_areas": ["..."],
  "disagreement_areas": ["..."],
  "most_relevant_judge": "...",
  "final_recommendation": {
    "action": "STRONG BUY/BUY/HOLD/SELL/STRONG SELL",
    "score": 0.0,
    "confidence": "HIGH/MEDIUM/LOW",
    "price_target": {"low": 0, "high": 0}
  }
}
```

## Phase 6: Synthesis & Recommendation

1. **Weight Assignment**: Explicitly state your weights for this specific stock in this context:
   - Fundamentals: X%
   - Technical/Momentum: X%
   - News/Events: X%
   - Sentiment: X%
   - Macro: X%
   Explain WHY you chose these weights. (e.g., "Earnings in 5 days, so I'm weighting news/events higher at 30%")

2. **Composite Score**: Calculate a weighted score (1-10).

3. **Recommendation**: One of: **Strong Buy | Buy | Hold | Sell | Strong Sell**

4. **Confidence**: **High | Medium | Low** — informed by the contradiction scan and debate verdict.

5. **Key Risks**: Top 3 risks that could invalidate this thesis.

6. **Review Triggers**: What events would cause you to revisit? (e.g., "Review after Q2 earnings on July 25" or "Review if price breaks below $150")

## Output Format

Structure your report with clear headers:

```
# {ticker} Research Report — [Date]

## Summary
[2-3 sentence executive summary with recommendation]

## Fundamental Analysis (Score: X/10)
[Analysis with specific numbers]

## Technical Analysis (Score: X/10)
[Analysis with specific levels and signals]

## Macro Context
[Brief macro assessment]

## Contradictions Found
[List each conflict and which side you trust]

## Debate (5 shared turns)
### Turn 1: Bull Opens
### Turn 2: Bear Responds
### Turn 3: Bull Rebuttal
### Turn 4: Bear Rebuttal
### Turn 5: Moderator Summary

## Strategy Judge Panel (7 turns)
### Value Judge: [VERDICT]
### Momentum Judge: [VERDICT]
### Defensive Judge: [VERDICT]
### EventDriven Judge: [VERDICT]
### Balanced Judge: [VERDICT]
### Adaptive Judge: [VERDICT]
### Commodity Judge: [VERDICT]

## Cross-Strategy Synthesis
- Votes: X buy, Y hold, Z sell
- Agreement: ...
- Disagreement: ...
- Most relevant judge: ...

## Signal Weights
[Table of weights with reasoning]

## Recommendation: [STRONG BUY/BUY/HOLD/SELL/STRONG SELL]
- Composite Score: X/10
- Confidence: [HIGH/MEDIUM/LOW]
- Price Target Range: $X - $Y
- Key Risks: [1, 2, 3]
- Review Triggers: [events/dates/levels]

---
*This is research, not financial advice. Past performance does not predict future results.*
```

Save ALL files into `runs/research/{ticker}_{date}/`:

| File | Purpose |
|------|---------|
| `report.md` | Human-readable markdown report (the full analysis above) |
| `debate.json` | Structured 5-turn debate log (exact JSON schema above) |
| `data_collected.json` | Raw outputs from all tools (price, fundamentals, technicals, etc.) |
| `contradiction_scan.json` | Signal conflicts found in Phase 4b |

This keeps each research session self-contained and separate from simulation runs.

## Phase 7: Update Memory

After generating the report, update the persistent memory files so future sessions have context:

1. **Save news data** — Run `python tools/news_collector.py` to ensure today's data is archived in `data/news/` for future backtests.

2. **Save the research folder** — Everything goes into `runs/research/{ticker}_{date}/`.

3. **Check past research** — Look for `runs/research/{ticker}_*/debate.json` to see if this ticker was analyzed before. If so:
   - Did the bull/bear balance shift since last time?
   - Were any previous invalidation criteria triggered?
   - Note what changed in the new report.

4. **Check past sim runs** — If this ticker appeared in a simulation run, compare the strategy's reasoning log with your analysis. Note any differences.

## Important Guidelines

- **Cite specific numbers**. Don't say "revenue is growing" — say "revenue grew 12.3% YoY to $94.9B."
- **Be honest about uncertainty**. If data is conflicting, say so. Don't force a narrative.
- **Consider what you DON'T know**. News can be stale. Fundamentals are quarterly. Insider data has delays.
- **This is research, not financial advice.** Always include the disclaimer.
- **Ground every claim in tool data.** Do not hallucinate numbers.
- **The debate must be genuine.** If you find yourself writing a weak bear case just to check a box, stop and think harder about what could actually go wrong.

# Example Outputs

What the simulation actually produces. Every trade is logged with reasoning.

---

## Trading Frequency

Average trades per week across different periods:

| Strategy | Trades/Week | Style |
|:---------|:----------:|:------|
| **Commodity** | 0.1 | Holds or cash, rarely trades |
| **Value** | 1.4 | Patient, quarterly rebalance |
| **Defensive** | 2.0 | Moderate, sells on danger signals |
| **EventDriven** | 2.9 | Active around earnings |
| **Balanced** | 3.3 | Moderate-active, regime-aware |
| **Adaptive** | 3.3 | Active, mode-switching |
| **Mix** | 3.3 | Active, multi-asset allocation |
| **MixLLM** | 3.3 | Active, same as Mix + LLM calls |
| **Momentum** | 3.7 | Most active, chases trends |

---

## Sample: Buy Decision (Mix Strategy)

When Mix buys a stock, here's what gets logged:

```json
{
  "date": "2019-01-02",
  "action": "BUY",
  "ticker": "KO",
  "price": 37.58,
  "reason": "Mix DEFENSIVE: stock alloc (target=20%, score=6.782)",
  "regime": "high_volatility",
  "news_context": "geo_risk=0.65",
  "scores": {
    "composite": 6.78,
    "regime": "DEFENSIVE",
    "low_vol": 6.36,
    "trend": 7,
    "drawdown": 7.27
  }
}
```

**Reading this:** On Jan 2, 2019, Mix was in DEFENSIVE regime (only 20% in stocks). It bought KO (Coca-Cola) at $37.58 because it scored 6.78 — driven by low volatility (6.36), above 200-day MA (trend=7), and small drawdown (7.27). The market had high volatility and geopolitical risk was elevated at 0.65.

---

## Sample: Regime Change

When Mix detects a regime shift:

```json
{
  "date": "2019-01-02",
  "action": "REGIME",
  "reason": "Mix regime: DEFENSIVE | Alloc: stocks=20% commodity=30% cash=50% | Pos: 2 stocks + 0 commodity | Sensors: def=DEFENSE, adapt=DEFENSIVE, comm=OUT"
}
```

```json
{
  "date": "2019-02-01",
  "action": "REGIME",
  "reason": "Mix regime: UNCERTAIN | Alloc: stocks=70% commodity=0% cash=30% | Pos: 7 stocks + 0 commodity | Sensors: def=NORMAL, adapt=VALUE, comm=IN"
}
```

```json
{
  "date": "2019-03-01",
  "action": "REGIME",
  "reason": "Mix regime: AGGRESSIVE | Alloc: stocks=90% commodity=0% cash=10% | Pos: 9 stocks + 0 commodity | Sensors: def=NORMAL, adapt=MOMENTUM, comm=IN"
}
```

**Reading this:** Over Jan-Mar 2019, Mix went from DEFENSIVE (20% stocks, 50% cash) to AGGRESSIVE (90% stocks). The Defensive peer went from DEFENSE to NORMAL, Adaptive went from DEFENSIVE to MOMENTUM — consensus said danger passed.

---

## Sample: Stop-Loss Trigger

```json
{
  "date": "2019-05-13",
  "action": "SELL",
  "ticker": "AAPL",
  "price": 38.43,
  "reason": "STOP LOSS triggered (-6.12% loss) PnL: -6.1% (held since 2019-04-01)",
  "regime": "bearish"
}
```

**Reading this:** AAPL hit its ATR-based stop-loss, dropping 6.1% from entry. Automatic sell — no human decision needed.

---

## Sample: MixLLM LLM Call

What Claude Opus sees and decides on a rebalance day:

```json
{
  "date": "2019-01-02",
  "source": "llm",
  "regime": "DEFENSIVE",
  "confidence": 0.95,
  "reasoning": "All extended signals reinforce DEFENSIVE: classic flight-to-safety confirmed (gold +8.3%, treasuries +6.8%, high-yield -4.5%), oil in freefall (-35.5% 3m) signaling economic slowdown, only 1/7 sectors positive, and 29.2% annualized vol with rising trend - this is the Q4 2018 selloff aftermath with no contradictory recovery signals present.",
  "action": "CONFIRM"
}
```

**Reading this:** Coded rules said DEFENSIVE. Opus agreed (CONFIRM) with 0.95 confidence, citing gold/treasury surge (flight to safety), oil collapse, and only 1 of 7 sectors positive.

### When the LLM Overrides (Escalation)

```json
{
  "date": "2007-08-01",
  "source": "llm",
  "regime": "CAUTIOUS",
  "confidence": 0.92,
  "reasoning": "August 2007 credit stress is unmistakable: high-yield bonds crashing (-4.8% 1m), financials -8.7%, flight to Treasuries.",
  "action": "ESCALATE",
  "note": "Overrode AGGRESSIVE -> CAUTIOUS (more defensive)"
}
```

**Reading this:** Coded rules said AGGRESSIVE. Opus saw credit market stress the rules couldn't and escalated to CAUTIOUS. This was August 2007 — the beginning of the GFC. The LLM caught it 14 months before Lehman collapsed.

### When the LLM Gets Rejected

```json
{
  "date": "2019-02-01",
  "source": "llm",
  "regime": "RECOVERY",
  "confidence": 0.85,
  "reasoning": "Strong RECOVERY signal: SPY above 50d MA with +10.6% 1-month bounce, volatility falling 20%+, high-yield bonds surging.",
  "action": "REJECTED",
  "note": "LLM wanted RECOVERY but coded=UNCERTAIN is more defensive, keeping coded"
}
```

**Reading this:** Opus wanted to go LESS defensive (RECOVERY), but the system only allows escalation. The coded UNCERTAIN regime is more defensive than RECOVERY, so the system kept UNCERTAIN. This is the safety constraint in action.

---

## Sample: Daily Portfolio Snapshot

```json
{
  "date": "2019-06-28",
  "total_value": 115432.50,
  "cash": 11543.25,
  "num_positions": 9,
  "return_pct": 15.43
}
```

**Reading this:** On June 28, the portfolio was worth $115,432 (up 15.43% from $100k start). $11,543 in cash (10%), 9 stock positions.

---

## Sample: Strategy Memory (What It Learned)

After a simulation run, each strategy records what it learned:

```json
{
  "lessons": [
    "Win rate: 55% (44W / 36L)",
    "Avg win: +12.3%, Avg loss: -6.8%",
    "Regimes encountered: 8 changes",
    "Regime 'bullish': avg PnL +8.2% over 22 trades",
    "Regime 'bearish': avg PnL -3.1% over 14 trades"
  ],
  "best_ticker": "NVDA +45.2%",
  "worst_ticker": "INTC -18.3%",
  "ticker_history": {
    "AAPL": [
      {"pnl_pct": 12.3, "regime": "bullish", "date": "2019-04-01"},
      {"pnl_pct": -6.1, "regime": "bearish", "date": "2019-05-13"}
    ]
  }
}
```

**Reading this:** The strategy won 55% of trades with 12.3% average win vs 6.8% average loss. It performs best in bullish regimes (+8.2% per trade) and worst in bearish (-3.1%). NVDA was its best trade (+45.2%), INTC its worst (-18.3%). It remembers per-ticker history to avoid "revenge trading" on repeated losers.

---

## Output Structure

Every simulation run produces this folder structure:

```
runs/{timestamp}_{period}_mp{N}_daily/
  config.json                    # Run parameters and feature flags
  summary.json                   # Final returns, Sharpe, max drawdown per strategy
  trigger_log.json               # Every trigger that fired (1000-3000 per period)
  shared/
    regime_log.json              # Daily macro regime classification
  portfolios/
    Mix/
      state.json                 # Final portfolio (positions, cash, value)
      transactions.csv           # Every trade: date, action, ticker, shares, price, PnL
      reasoning.json             # WHY each trade was made (the examples above)
      memory.json                # What the strategy learned
      history.json               # Daily portfolio value snapshots
      conviction_log.json        # Per-stock conviction levels
      watchnotes.json            # Active observations per position
    MixLLM/
      (same as Mix, plus:)
      llm_calls.json             # Every LLM call with reasoning and confidence
    Value/
      (same structure)
    ... (9 strategy folders total)
```

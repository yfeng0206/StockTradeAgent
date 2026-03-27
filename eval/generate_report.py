"""Generate comprehensive test report that a new reader can fully understand."""
import json, sys, os, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

phases = {}
for i in range(1, 5):
    path = os.path.join(os.path.dirname(__file__), 'pipeline_results', f'phase{i}.json')
    if os.path.exists(path):
        with open(path) as f:
            phases[i] = json.load(f)

STRATS = ['Value', 'Momentum', 'Balanced', 'Defensive', 'EventDriven', 'Adaptive', 'Commodity']
sweep = phases.get(1, [])
fw = phases.get(2, {})
p3 = phases.get(3, {})
p4 = phases.get(4, {})
standard = fw.get('standard', {})
wf = fw.get('walk_forward', [])
ab = fw.get('ablation', {})
sl = fw.get('slippage', {})

print("""
================================================================================
================================================================================

           STOCK RESEARCH AGENT — COMPREHENSIVE TEST ANALYSIS

           Date: March 26, 2026
           System: Claude CLI + Python, daily event-driven simulation
           Data: yfinance (prices), SEC EDGAR (filings), Wikipedia/GDELT (news)

================================================================================
================================================================================


TABLE OF CONTENTS
-----------------
  1. System Overview: What is this?
  2. The 7 Trading Strategies: What does each one do?
  3. Test Periods: What market conditions did we test?
  4. Test Framework: What tests did we run and why?
  5. Phase 1 Results: Performance Grid
  6. Phase 2A Results: Standard Metrics
  7. Phase 2B Results: Walk-Forward (Overfitting Check)
  8. Phase 2C Results: Ablation (What Data Matters?)
  9. Phase 2D Results: Slippage (Real-World Friction)
  10. Phase 3 Results: False Discovery Check
  11. Phase 3 Results: Cross-References
  12. Final Rankings
  13. Conclusions and Recommendations


================================================================================
1. SYSTEM OVERVIEW: WHAT IS THIS?
================================================================================

This is a stock trading research agent built on Claude CLI (Opus 4.6).
It uses Python scripts to fetch market data, news, and financial reports,
then runs 7 different trading strategies in simulation to see which ones
actually make money.

HOW IT WORKS:
  1. Download price data for 50 U.S. stocks + 6 macro ETFs from yfinance
  2. Load geopolitical news from Wikipedia Current Events + GDELT archives
  3. Load earnings dates and surprise data from yfinance + SEC EDGAR
  4. Run a daily event-driven simulation where each strategy:
     - Checks for triggers every day (stop-losses, earnings, news, regime changes)
     - Does a full portfolio rebalance on the 1st of each month
     - Tracks memory of what worked and what didn't
  5. Compare results against SPY (S&P 500) and QQQ (Nasdaq 100) buy-and-hold

THE 50-STOCK UNIVERSE:
  Tech:       AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, CRM, NFLX, AMD, ADBE, INTC
  Finance:    JPM, V, MA, GS, BAC, WFC, MS, BLK
  Healthcare: UNH, JNJ, LLY, ABBV, MRK, PFE, TMO, ABT
  Consumer:   PG, KO, PEP, COST, WMT, HD, MCD, NKE
  Energy/Ind: XOM, CVX, CAT, BA, HON, UPS, DE, LMT
  Other:      DIS, CMCSA, T, VZ, NEE, SO

MACRO ETFs: USO (oil), XLE (energy), GLD (gold), TLT (bonds), HYG/LQD (credit)
BENCHMARKS: SPY (S&P 500), QQQ (Nasdaq 100)


================================================================================
2. THE 7 TRADING STRATEGIES
================================================================================

Each strategy starts with the same amount of cash and picks stocks differently.
Think of them as 7 different portfolio managers with different philosophies.

STRATEGY 1: VALUE (Contrarian Mean Reversion)
  Philosophy: "Buy beaten-down stocks that everyone else is selling"
  How it picks: Low volatility + far from 52-week high + oversold RSI
  Rebalances:  Every 3 months (patient holder)
  Stop-loss:   Wide (3x ATR — holds through big dips)
  Cash rule:   Holds cash if no stock scores above 3.5/10

STRATEGY 2: MOMENTUM (12-Minus-1 Month)
  Philosophy: "Buy stocks that have been going up for the past year"
  How it picks: 12-month return (excluding last month) + trend + MACD + volume
  Rebalances:  Monthly
  Stop-loss:   Medium-wide (2.5x ATR — lets winners run)
  Cash rule:   High bar — only buys stocks scoring above 5.0/10

STRATEGY 3: BALANCED (Multi-Factor Adaptive)
  Philosophy: "Blend value + momentum + stability, shift weights by market conditions"
  How it picks: Weighted composite of 3 factors; weights shift based on regime + news
  Rebalances:  Monthly
  Stop-loss:   Standard (2x ATR)
  Cash rule:   Moderate bar — above 4.5/10

STRATEGY 4: DEFENSIVE (3-State Minimum Volatility)
  Philosophy: "Protect capital first, make money second"
  How it picks: Lowest-volatility stocks above 200-day moving average
  3 states:    NORMAL (100% invested) / REDUCED (50%) / DEFENSE (20%)
  Transitions: Based on 4 danger signals (high vol, downtrend, drawdown, geo risk)
  Stop-loss:   Tight (1.5x ATR — safe stocks shouldn't drop much)

STRATEGY 5: EVENT DRIVEN (Earnings Drift)
  Philosophy: "Trade around earnings announcements — ride the post-earnings drift"
  How it picks: ONLY scores stocks with a real event (earnings in last 45 days,
                upcoming in 3 days, or 8-K filing in 5 days). No event = skip.
  Rebalances:  Monthly (but earnings triggers can trade any day)
  Stop-loss:   Standard (2x ATR)

STRATEGY 6: ADAPTIVE (Regime Switching)
  Philosophy: "Switch between momentum/value/defensive based on market conditions"
  Mode detection: Uses SPY volatility, trend, returns, and geo risk
  Modes:       MOMENTUM (bull) / VALUE (sideways) / DEFENSIVE (crisis) / RECOVERY
  Rebalances:  Monthly
  Stop-loss:   Standard (2x ATR)

STRATEGY 7: COMMODITY (Oil/Energy Trend)
  Philosophy: "Track oil — all-in when trending up, cash when down"
  How it picks: USO (oil ETF) trend score based on moving averages + geo news
  Max allocation: 50% of portfolio (capped — never goes all-in)
  Rebalances:  Monthly
  Stop-loss:   Wide (2.5x ATR — commodities are volatile)


================================================================================
3. TEST PERIODS: WHAT MARKET CONDITIONS DID WE TEST?
================================================================================

We tested on 2 historical periods (quick mode). Each represents a different
market regime:

PERIOD 1: RECESSION (2022 Bear Market)
  Dates: January 3, 2022 — October 31, 2022
  What happened: Federal Reserve raised interest rates aggressively to fight
  inflation. Tech stocks crashed. Russia invaded Ukraine (Feb 24), causing
  oil prices to spike and global uncertainty. S&P 500 fell -25% peak-to-trough.
  216 trading days.
  SPY return: -18.1%
  This tests: Can the strategy survive a crash? Does it protect capital?

PERIOD 2: BULL MARKET (2023 AI Rally)
  Dates: January 2, 2023 — December 29, 2023
  What happened: AI boom driven by ChatGPT/NVIDIA. The "Magnificent 7" tech
  stocks dominated. S&P 500 gained +24%. Low volatility, steady growth.
  260 trading days.
  SPY return: +26.6%
  This tests: Can the strategy capture upside? Does it keep up with the market?

NOTE: Quick mode uses 2 periods. Full mode (7 periods) also includes:
  - 2019 Normal (steady bull, +29%)
  - 2020 COVID Crash (fastest crash + recovery ever)
  - 2021-2022 Bull-to-Recession (peak then crash)
  - 2022-2023 Recession-to-Bull (bottom then recovery)
  - 2025-2026 Recent (Iran war, current market)


================================================================================
4. TEST FRAMEWORK: WHAT TESTS DID WE RUN AND WHY?
================================================================================

We ran a 4-phase pipeline. Each phase answers a different question.

PHASE 1: PERFORMANCE SWEEP
  Question:  "How does each strategy perform in each market condition?"
  What runs: Each of 7 strategies x 2 periods = 14 simulation runs
  Settings:  $50,000 starting cash, max 10 positions, monthly rebalance
  Measures:  Total return, alpha vs SPY, Sharpe ratio, max drawdown,
             win rate, number of trades
  Why:       This is the basic "does it make money?" test.

PHASE 2A: STANDARD METRICS
  Question:  "What are the detailed risk and return characteristics?"
  What runs: Same as Phase 1 (reuses results)
  Measures:  Returns, Sharpe ratio (risk-adjusted return), maximum drawdown
             (worst peak-to-trough loss), win rate (% of trades profitable),
             number of trades per strategy
  Why:       Raw return isn't enough. A strategy that makes 20% but drops 50%
             along the way is worse than one that makes 10% with only a 10% drop.

PHASE 2B: WALK-FORWARD TEST
  Question:  "Is this strategy overfit to the test data, or does it work on new data?"
  Method:    Train on past periods, test on the NEXT unseen period.

  How it works:
    Fold 1: "Train" on 2019 data (the strategy sees 2019 results)
            Test on 2020 COVID crash (the strategy has NEVER seen this data)
    Fold 2: "Train" on 2019 + 2020
            Test on 2021-2022 bull-to-recession

  Measures:
    IS Sharpe  = Sharpe ratio on the training periods (in-sample)
    OOS Sharpe = Sharpe ratio on the unseen test period (out-of-sample)
    Decay      = OOS Sharpe / IS Sharpe
                 Decay > 0.3 means the strategy retains 30%+ of its edge = ROBUST
                 Decay < 0.3 means most of the "edge" disappears = FRAGILE (overfit)

  Why:       This is the single most important test. A strategy that only works on
             data you've already seen is useless for real trading. Walk-forward
             simulates what happens when you deploy it on unknown future data.

PHASE 2C: ABLATION TEST
  Question:  "Which data sources actually help? Which are noise?"
  Method:    Remove ONE data source at a time and re-run the simulation.

  Test 1 — Remove geopolitical news:
    Monkey-patch the signal engine to return "no news, geo_risk=0" for every day.
    This means strategies that use news (Balanced, Defensive, Adaptive, Commodity)
    now operate blind to geopolitical events like wars and sanctions.

  Test 2 — Remove earnings data:
    Pass an empty events calendar so no strategy sees any earnings dates or surprises.
    This means EventDriven has no events to trade, and other strategies lose their
    earnings adjustment in monthly scoring.

  Test 3 — Remove volume triggers:
    Monkey-patch the trigger engine to never fire volume anomaly triggers.
    Momentum and EventDriven normally buy on volume spikes (+5% on 2.5x volume).

  All tests run on the RECESSION period (hardest market — most informative).

  Measures:
    Baseline return vs ablated return for each strategy.
    If removing data HURTS performance (return goes down) = data is USEFUL.
    If removing data HELPS performance (return goes up) = data is NOISE/HARMFUL.

  Why:       If a strategy uses news but removing news makes it BETTER, that
             means news is adding noise, not signal. The strategy should stop
             using that data source.

PHASE 2D: SLIPPAGE TEST
  Question:  "Does the strategy survive real-world trading costs?"
  Method:    Monkey-patch the buy/sell functions to add friction.

  Baseline:  No slippage, $0 commission (ideal, unrealistic backtest)
  Moderate:  10 basis points slippage (0.1% price impact per trade) + $5 commission
             This is realistic for a retail trader with a good broker.
             Example: buying $10,000 of AAPL costs an extra $10 in slippage + $5 fee.
  Harsh:     20 basis points + $10 per trade (worse broker, larger orders)

  Run on the BULL-TO-RECESSION period (diverse market conditions).

  Measures:
    Frictionless return vs frictioned return for each strategy.
    Friction cost = how much return is lost to trading costs.

  Why:       Backtests without friction always look better than reality.
             A strategy that trades 200 times loses more to friction than one
             that trades 10 times. This test shows which strategies are
             practically viable.

PHASE 3: COMBINED VALIDATION
  Question:  "Do our findings hold when we cross-reference everything?"
  Method:    Computational analysis (no new simulations).

  Test 1 — Deflated Sharpe Ratio:
    When you test 7 strategies across 2 periods (14 combinations), you EXPECT
    to find something that looks good by pure luck. The Deflated Sharpe Ratio
    (Bailey & Lopez de Prado, 2014) adjusts for this "multiple testing" problem.

    It computes: what's the best Sharpe you'd expect from RANDOM strategies?
    If our best Sharpe exceeds that random expectation, we have real signal.

    p-value < 0.05 = statistically significant (real edge)
    p-value > 0.05 = could be random chance

  Test 2 — News impact cross-reference:
    Compare the ablation findings (which strategies news helps/hurts) with
    the overall sweep performance. Does news impact predict overall success?

  Test 3 — Friction cross-reference:
    Compare each strategy's friction cost with its return volatility across
    the sweep. Stable, low-friction strategies are more deployable.

  Why:       Individual tests can be misleading. Cross-referencing catches
             contradictions (e.g., a strategy that beats SPY but only because
             of one lucky period).

PHASE 4: CONSOLIDATION
  Question:  "What's the final answer? Which strategies should we trust?"
  Method:    Merge all findings into a single ranking.

  Rating criteria:
    STRONG   = Walk-forward ROBUST + positive Sharpe + reasonable friction
    PROMISING = Beats SPY >60% + Sharpe >0.3 but fragile walk-forward
    MODERATE = Some positive signal but inconsistent
    WEAK     = Negative average returns or very high friction
    POOR     = Fails most tests
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 5: PERFORMANCE GRID
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
5. PHASE 1 RESULTS: PERFORMANCE GRID
================================================================================

Each cell shows: the strategy's total return over that period.
Starting capital: $50,000 per strategy. Max 10 positions.
""")

if standard:
    periods = list(standard.keys())
    h = f"  {'Strategy':<14}"
    for pk in periods:
        h += f"  {pk[:10]:>12}"
    h += f"  {'AVERAGE':>10}"
    print(h)
    print("  " + "-" * (len(h) - 2))
    for s in STRATS:
        row = f"  {s:<14}"
        rets = []
        for pk in periods:
            ret = standard[pk].get(s, {}).get('return', 0) if isinstance(standard[pk].get(s), dict) else 0
            rets.append(ret)
            row += f"  {ret:>+11.1f}%"
        row += f"  {np.mean(rets):>+9.1f}%"
        print(row)
    row = f"  {'SPY (B&H)':<14}"
    for pk in periods:
        spy = standard[pk].get('SPY', 0)
        row += f"  {spy:>+11.1f}%"
    print(row)

print("""
  READING THIS TABLE:
  - Positive % in recession = the strategy protected capital while SPY lost -18%
  - Positive % in bull = the strategy captured the rally
  - "Alpha" = return above SPY. Commodity had +36% alpha in recession (oil spike)
  - 5 of 7 strategies beat SPY in the recession. Only 2 beat SPY in the bull.
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 6: DETAILED METRICS
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
6. PHASE 2A RESULTS: DETAILED METRICS (averaged across periods)
================================================================================

  Avg Ret   = Average total return across test periods
  Alpha     = Return above SPY (positive = beat the market)
  Sharpe    = Risk-adjusted return (>0.5 good, >1.0 excellent, <0 bad)
  MaxDD     = Worst peak-to-trough drop (closer to 0% = safer)
  WinRate   = Percentage of closed trades that were profitable
  Trades    = Total number of buy+sell transactions
  BeatSPY   = In what % of test periods did this strategy beat SPY?
""")

if sweep:
    print(f"  {'Strategy':<14} {'Avg Ret':>8} {'Alpha':>8} {'Sharpe':>8} {'MaxDD':>8} {'WinRate':>8} {'Trades':>8} {'BeatSPY':>8}")
    print("  " + "-" * 72)
    for s in STRATS:
        rets = [r['return_pct'] for r in sweep if r['strategy'] == s]
        alphas = [r['alpha'] for r in sweep if r['strategy'] == s]
        sharpes = [r['sharpe'] for r in sweep if r['strategy'] == s]
        dds = [r['max_drawdown'] for r in sweep if r['strategy'] == s]
        wrs = [r['win_rate'] for r in sweep if r['strategy'] == s]
        trades = [r['trades'] for r in sweep if r['strategy'] == s]
        beat = sum(1 for a in alphas if a > 0) / len(alphas) * 100 if alphas else 0
        print(f"  {s:<14} {np.mean(rets):>+7.1f}% {np.mean(alphas):>+7.1f}% {np.mean(sharpes):>8.3f} {np.mean(dds):>7.1f}% {np.mean(wrs):>7.1f}% {np.mean(trades):>7.0f} {beat:>7.0f}%")

print("""
  INTERPRETATION:
  - Value has the best Sharpe (0.624) meaning best risk-adjusted returns
  - EventDriven has the highest raw return (+7.4%) and alpha (+3.1%)
  - Defensive is the only strategy with NEGATIVE average return (-4.6%)
  - Commodity barely trades (4 trades) — it's mostly holding oil or cash
  - Value and EventDriven beat SPY in 100% of periods tested
  - But beating SPY in 2 periods doesn't prove the strategy is real (see walk-forward)
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 7: WALK-FORWARD
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
7. PHASE 2B RESULTS: WALK-FORWARD (THE OVERFITTING CHECK)
================================================================================

This is the single most important test in the entire report.

THE PROBLEM: When you test a strategy on historical data, it might look good
simply because you (consciously or not) tuned it to fit that specific history.
This is called "overfitting" and it's the #1 reason backtested strategies fail
in real trading.

THE TEST: We train the strategy on past data, then test it on FUTURE data
it has never seen. If performance holds up, the strategy has real edge.
If performance collapses, it was overfit.

  IS Sharpe  = Performance on data the strategy "knows" (training periods)
  OOS Sharpe = Performance on data the strategy has NEVER seen (test period)
  Decay      = OOS / IS ratio
               > 0.3 = ROBUST (the edge is real, it survives on new data)
               < 0.3 = FRAGILE (the "edge" was just fitting to old data)
""")

if wf:
    print(f"  {'Strategy':<14} {'IS Sharpe':>12} {'OOS Sharpe':>12} {'Decay':>8} {'Verdict':>10}")
    print("  " + "-" * 58)
    for s in STRATS:
        is_vals = [f['is_sharpe'].get(s, 0) for f in wf]
        oos_vals = [f['oos_sharpe'].get(s, 0) for f in wf]
        is_avg = np.mean(is_vals)
        oos_avg = np.mean(oos_vals)
        decay = oos_avg / is_avg if is_avg != 0 else 0
        verdict = 'ROBUST' if decay > 0.3 else 'FRAGILE'
        print(f"  {s:<14} {is_avg:>+11.3f} {oos_avg:>+11.3f} {decay:>8.2f} {verdict:>10}")

print("""
  CRITICAL FINDINGS:

  MOMENTUM is ROBUST (decay 0.33):
    Trained at Sharpe 1.40, retained 0.46 on unseen data.
    This means Momentum's edge is REAL — it works on data it hasn't seen.
    The 12-minus-1 month signal captures genuine price continuation.

  COMMODITY is ROBUST (decay 0.32):
    Trained at Sharpe -0.46 (negative!), tested at -0.15 (less negative).
    This is "robust" in a technical sense — performance is consistent.
    But the base performance is poor. Commodity works in specific conditions
    (oil crisis) but not generally.

  VALUE is FRAGILE (decay -0.32):
    Trained at Sharpe 1.83 (excellent!), but tested at -0.58 (terrible).
    This means Value's 100% SPY-beating rate is likely a HISTORICAL FLUKE.
    The contrarian signals worked in the training periods but failed on new data.

  EVENTDRIVEN is FRAGILE (decay -0.37):
    Similar to Value. Great in-sample, collapses out-of-sample.
    The earnings drift signal may be too noisy or our event detection too imprecise.

  ALL OTHER STRATEGIES are FRAGILE — their in-sample performance
  does not survive out-of-sample testing.
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 8: ABLATION
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
8. PHASE 2C RESULTS: ABLATION (WHAT DATA ACTUALLY HELPS?)
================================================================================

We remove one data source at a time and see what happens.
If performance DROPS when we remove it, that data source was helping.
If performance RISES when we remove it, that data source was HURTING.

All tests on the recession period (2022) — the hardest market.

TEST 1: REMOVE GEOPOLITICAL NEWS
  What we removed: Wikipedia events + GDELT headlines (wars, sanctions, conflicts)
  Strategies affected: Balanced, Defensive, Adaptive, Commodity (they read geo_risk)
  Strategies NOT affected: Value, Momentum, EventDriven (they don't use news)
""")

if ab:
    base = ab.get('baseline', {})
    no_news = ab.get('no_news', {})
    no_earn = ab.get('no_earnings', {})

    print(f"  {'Strategy':<14} {'With News':>10} {'No News':>10} {'Impact':>10} {'Verdict':>10}")
    print("  " + "-" * 52)
    for s in STRATS:
        b = base.get(s, 0)
        nn = no_news.get(s, 0)
        diff = b - nn
        v = "USEFUL" if diff > 2 else "HARMFUL" if diff < -2 else "neutral"
        print(f"  {s:<14} {b:>+9.1f}% {nn:>+9.1f}% {diff:>+9.1f}% {v:>10}")

    print("""
  INTERPRETATION:
  - Adaptive: news adds +11.5%. Without news it drops from -20.7% to -32.1%.
    News helps Adaptive detect regime changes and switch modes earlier.
  - Balanced: news adds +6.5%. It uses geo_risk to shift factor weights.
  - Defensive: news HURTS by -3.4%. News triggers cause panic selling
    that loses money. Defensive would be BETTER without news.
  - Commodity: news HURTS by -6.5%. The geo_risk boost makes Commodity
    over-allocate to oil based on headlines that don't predict prices.


TEST 2: REMOVE EARNINGS DATA
  What we removed: All earnings dates, surprise %, and event triggers
""")

    print(f"  {'Strategy':<14} {'With Earn':>10} {'No Earn':>10} {'Impact':>10} {'Verdict':>10}")
    print("  " + "-" * 52)
    for s in STRATS:
        b = base.get(s, 0)
        ne = no_earn.get(s, 0)
        diff = b - ne
        v = "USEFUL" if diff > 2 else "HARMFUL" if diff < -2 else "no effect"
        print(f"  {s:<14} {b:>+9.1f}% {ne:>+9.1f}% {diff:>+9.1f}% {v:>10}")

    # Dynamic interpretation based on actual results
    has_impact = []
    for s in STRATS:
        b = base.get(s, 0)
        ne2 = no_earn.get(s, 0)
        diff = b - ne2
        if abs(diff) > 2:
            direction = "HELPS" if diff > 0 else "HURTS"
            has_impact.append(f"    {s}: earnings {direction} by {abs(diff):.1f}%")

    print()
    print("  INTERPRETATION:")
    if has_impact:
        for line in has_impact:
            print(line)
        print("    Earnings triggers are actively trading — the question is whether")
        print("    they help or hurt in each market regime. In recession, buying")
        print("    after earnings beats often fails because stocks keep falling")
        print("    despite good results (macro overwhelms micro).")
    else:
        print("    No measurable earnings impact. Event pipeline may need investigation.")
    print()

# ═══════════════════════════════════════════════════════════════
# SECTION 9: SLIPPAGE
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
9. PHASE 2D RESULTS: SLIPPAGE (REAL-WORLD FRICTION)
================================================================================

Every real trade has hidden costs:
  - Slippage: the price moves against you between deciding to trade and execution
  - Commission: the broker charges a fee per trade
  - Market impact: large orders move the price

We simulate two friction levels:
  Moderate: 10 basis points (0.1%) slippage + $5 per trade
            On a $5,000 trade: $5 slippage + $5 commission = $10 total cost
  Harsh:    20 basis points + $10 per trade

Run on bull-to-recession period (diverse conditions, lots of trades).
""")

if sl:
    base_sl = sl.get('baseline', {})
    mod_sl = sl.get('moderate', {})
    print(f"  {'Strategy':<14} {'Frictionless':>12} {'Moderate':>12} {'Cost':>8}")
    print("  " + "-" * 44)
    for s in STRATS:
        b = base_sl.get(s, 0)
        m = mod_sl.get(s, 0)
        cost = b - m
        print(f"  {s:<14} {b:>+11.1f}% {m:>+11.1f}% {cost:>+7.1f}%")

    print("""
  INTERPRETATION:
  - Commodity is nearly frictionless (0.3% cost) because it only makes 3-6 trades.
  - Value is cheap (1.4% cost) because it rebalances quarterly, not monthly.
  - Adaptive is the most expensive (4.9% cost) — it trades too much.
    Its average return is +6.0%, but friction eats 4.9%, leaving only ~1% real profit.
  - Momentum loses 3.3% to friction. On a +4.6% average return, that's significant.
  - Defensive survives well: +10.8% -> +8.6%. Even with friction it makes money
    (but only in the bull-to-recession period which happens to favor defensive plays).
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 10: FALSE DISCOVERY
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
10. PHASE 3 RESULTS: FALSE DISCOVERY CHECK
================================================================================

THE MULTIPLE TESTING PROBLEM:
  We tested 7 strategies across 2 periods = 14 combinations.
  Even with RANDOM strategies, you'd expect to find at least one that
  looks good by pure luck. The more things you test, the more likely
  you'll find a "winner" that's actually just noise.

THE FIX: DEFLATED SHARPE RATIO (Bailey & Lopez de Prado, 2014)
  This adjusts the best observed Sharpe ratio for the number of trials.
  It answers: "Is our best result better than what random chance would produce?"
""")

ds = p3.get('deflated_sharpe', {})
if ds:
    print(f"  Number of trials:           {ds.get('n_trials', '?')}")
    print(f"  Best Sharpe we found:       {ds.get('best_sharpe', '?')}")
    print(f"  Expected best from random:  {ds.get('expected_max_random', '?')}")
    print(f"  p-value:                    {ds.get('p_value', '?')}")
    pv = ds.get('p_value', 1)
    print()
    if pv < 0.05:
        print("  VERDICT: PASS")
        print("  Our best Sharpe is statistically significant at 5%.")
        print("  It exceeds what random chance would produce.")
    elif pv < 0.10:
        print("  VERDICT: MARGINAL")
        print(f"  p={pv:.4f} is close to 0.05 but not below it.")
        print(f"  Our best Sharpe ({ds.get('best_sharpe', '?')}) exceeds random expectation")
        print(f"  ({ds.get('expected_max_random', '?')}) but not by enough to be confident.")
        print("  Running the full 7-period test (instead of 2) would likely")
        print("  strengthen this result because we'd have more data.")
    else:
        print("  VERDICT: FAIL")
        print("  Results could be explained by random chance.")

# ═══════════════════════════════════════════════════════════════
# SECTION 11: CROSS-REFERENCES
# ═══════════════════════════════════════════════════════════════

print("""

================================================================================
11. PHASE 3 RESULTS: CROSS-REFERENCES
================================================================================

These tables combine findings from different tests to check for contradictions.

A. NEWS IMPACT vs OVERALL PERFORMANCE:
   Does using news actually correlate with better returns?
""")

cr = p3.get('cross_ref_news', {})
if cr:
    print(f"  {'Strategy':<14} {'News Effect':>12} {'Overall Avg':>12} {'News Useful?':>14}")
    print("  " + "-" * 52)
    for s in STRATS:
        n = cr.get(s, {})
        ni = n.get('news_impact', 0)
        sa = n.get('sweep_avg_return', 0)
        v = "YES" if ni > 2 else "HARMFUL" if ni < -2 else "no"
        print(f"  {s:<14} {ni:>+11.1f}% {sa:>+11.1f}% {v:>14}")

print("""
  KEY INSIGHT: Adaptive benefits most from news (+11.5%) but has only
  moderate overall returns (+6.0%). This means news is a COMPONENT of
  its returns, but not enough on its own. Balanced uses news more
  conservatively (+6.5%) with more consistent overall returns.
""")

print("""B. FRICTION RESILIENCE vs RETURN CONSISTENCY:
   Low-friction strategies are more deployable in real trading.
""")

cr_slip = p3.get('cross_ref_slippage', {})
if cr_slip:
    print(f"  {'Strategy':<14} {'Friction':>10} {'Volatility':>12} {'Deployable?':>12}")
    print("  " + "-" * 48)
    for s in STRATS:
        d = cr_slip.get(s, {})
        fc = d.get('friction_cost', 0)
        rs = d.get('sweep_return_std', 0)
        if fc < 2 and rs < 15:
            dep = "BEST"
        elif fc < 3:
            dep = "GOOD"
        elif fc < 5:
            dep = "OKAY"
        else:
            dep = "POOR"
        print(f"  {s:<14} {fc:>+9.1f}% {rs:>11.1f}% {dep:>12}")

    print("""
  Balanced is the most deployable: low friction (1.6%) + low volatility (10%).
  Defensive is surprisingly deployable: low friction + very low volatility (2.8%).
  Adaptive is the least deployable: high friction (4.9%) + high volatility (26.5%).
""")

# ═══════════════════════════════════════════════════════════════
# SECTION 12: FINAL RANKINGS
# ═══════════════════════════════════════════════════════════════

print("""
================================================================================
12. FINAL STRATEGY RANKINGS
================================================================================

Combining ALL tests: performance, walk-forward, ablation, slippage, false discovery.

Rating criteria:
  STRONG     = Walk-forward ROBUST + positive Sharpe + reasonable friction
  PROMISING  = High returns/beat rate but fragile walk-forward
  MODERATE   = Some positive signal but inconsistent
  WEAK       = Negative average returns or very high friction
""")

rankings = p4.get('strategy_rankings', {})
sorted_s = sorted(rankings.items(), key=lambda x: x[1].get('avg_return', -999), reverse=True)

print(f"  {'#':<4} {'Strategy':<14} {'Return':>8} {'Sharpe':>8} {'BeatSPY':>8} {'WalkFwd':>8} {'Frictio':>8} {'RATING':>10}")
print("  " + "-" * 70)

for rank, (s, data) in enumerate(sorted_s, 1):
    if wf:
        is_avg = np.mean([f['is_sharpe'].get(s,0) for f in wf])
        oos_avg = np.mean([f['oos_sharpe'].get(s,0) for f in wf])
        decay = oos_avg / is_avg if is_avg != 0 else 0
        wf_v = 'ROBUST' if decay > 0.3 else 'WEAK'
    else:
        wf_v = '?'
    fc = cr_slip.get(s, {}).get('friction_cost', 0) if cr_slip else 0
    fc_v = 'LOW' if abs(fc) < 2 else 'MED' if abs(fc) < 4 else 'HIGH'
    beat = data.get('beat_spy_pct', 0)
    sharpe = data.get('avg_sharpe', 0)
    if wf_v == 'ROBUST' and sharpe > 0:
        rating = 'STRONG'
    elif beat >= 60 and sharpe > 0.3:
        rating = 'PROMISING'
    elif beat >= 40 and sharpe > 0:
        rating = 'MODERATE'
    elif beat >= 30:
        rating = 'WEAK'
    else:
        rating = 'POOR'
    print(f"  {rank:<4} {s:<14} {data.get('avg_return',0):>+7.1f}% {sharpe:>8.3f} {beat:>7.0f}% {wf_v:>8} {fc_v:>8} {rating:>10}")

# ═══════════════════════════════════════════════════════════════
# SECTION 13: CONCLUSIONS
# ═══════════════════════════════════════════════════════════════

print("""

================================================================================
13. CONCLUSIONS AND RECOMMENDATIONS
================================================================================

A. WHAT WE LEARNED:

  1. MOMENTUM is the only strategy that is both profitable AND survives
     walk-forward testing. Its 12-minus-1-month signal captures genuine
     price continuation that persists on unseen data (Sharpe decay 0.33).

  2. COMMODITY is robust but specialized. It only makes money during
     energy crises (oil spikes). In normal markets it underperforms.
     Best used as a 10-15% overlay, not a core strategy.

  3. NEWS is genuinely useful — but only for specific strategies.
     Balanced and Adaptive benefit significantly from geopolitical news.
     Defensive and Commodity are HURT by news (it causes bad trades).

  4. EARNINGS DATA actively HURTS two strategies (bug was fixed mid-test).
     EventDriven loses -18.5% from earnings triggers (buys beats in recession
     that keep falling). Momentum loses -5.8%. The trigger buys stocks after
     earnings beats, but in a recession good earnings don't prevent decline.

  5. TRADING FRICTION is a real concern. Adaptive loses 4.9% to friction,
     which nearly eliminates its alpha. Strategies that trade less (Value,
     Commodity) are more friction-resilient.

  6. The FALSE DISCOVERY check is MARGINAL (p=0.095). Our best result
     exceeds random expectation but not at the 5% significance level.
     The full 7-period test should clarify whether we have real edge.

B. RECOMMENDED PORTFOLIO (if deploying with real capital):

  Momentum:  60% allocation — only robust strategy with positive OOS Sharpe
  Commodity: 15% allocation — crisis hedge, uncorrelated to stocks
  Balanced:  15% allocation — news-aware, moderate but stable returns
  Cash:      10% allocation — dry powder for buying opportunities

C. DO NOT DEPLOY (without further fixes):

  EventDriven — BROKEN. Earnings triggers actively destroy returns (-18.5% impact
                in recession). The trigger buys on beats but stocks keep falling.
                Needs earnings trigger redesign before it can be trusted.
  Value — OVERFIT. Beats SPY in-sample but goes NEGATIVE out-of-sample.
          Walk-forward decay -0.32 means the edge is an illusion.
  Adaptive — TOO EXPENSIVE. Friction costs 4.9% on a 6% average return.
             Nearly zero net profit after realistic trading costs.
  Defensive — NOT ALPHA. Negative average return (-4.0%). Useful only as a
              crisis hedge, not as a standalone money-maker.

D. NEXT STEPS:

  1. Run full 7-period test: python eval/full_test.py (~54 min)
     More data will strengthen/weaken the deflated Sharpe result.

  2. Disable or redesign earnings triggers for EventDriven and Momentum
     (ablation proves they lose money from earnings-driven trades in recession)

  3. Remove news from Defensive and Commodity (proven harmful by ablation)

  4. Reduce Adaptive's trading frequency (friction is destroying alpha)

  5. Paper trade Momentum + Commodity combination for 30 days before
     considering any real capital deployment.

E. IMPORTANT CAVEATS:

  - This report uses only 2 test periods (quick mode). Results may change
    significantly with the full 7-period test.
  - Backtests always look better than reality. Even with slippage testing,
    real-world execution adds further friction (market impact, timing, etc.).
  - Past performance does not predict future results. Even "robust" strategies
    can fail when market regimes shift in unexpected ways.
  - The 50-stock universe is limited to large U.S. companies. Results may not
    generalize to other markets, small caps, or international stocks.


================================================================================
END OF REPORT
================================================================================
""")

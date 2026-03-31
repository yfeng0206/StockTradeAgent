# Data Sources

All data is free. No paid APIs, no subscriptions. Here's exactly what we pull, how we pull it, and where it's stored.

---

## yfinance (Price, Fundamentals, Earnings, News)

The backbone of the system. One library, no API key, covers most of what we need.

### Price Data (`tools/fetch_price_data.py`)

```python
fetch_price_data("AAPL", period="1y")
```

| What | How | Fields |
|:-----|:----|:-------|
| OHLCV history | `yf.Ticker.history()` | Open, High, Low, Close, Volume per day |
| Current quote | `yf.Ticker.info` | Price, previous close, daily change %, market cap |
| 52-week range | Computed from history | 52w high/low, % from each |
| Volatility | Computed: `std(returns) * sqrt(252)` | 30-day annualized volatility |

Used by: Every strategy (scoring), simulation engine (daily prices), trigger engine (stop-loss checks)

### Fundamentals (`tools/fetch_fundamentals.py`)

```python
fetch_fundamentals("AAPL")
```

| What | How | Fields |
|:-----|:----|:-------|
| Valuation ratios | `yf.Ticker.info` | P/E (trailing + forward), PEG, P/S, P/B, EV/EBITDA, EV/Revenue |
| Profitability | `yf.Ticker.info` | Profit margin, operating margin, gross margin, ROE, ROA |
| Balance sheet | `yf.Ticker.balance_sheet` | Debt-to-equity, current ratio, cash, total debt |
| Income statement | `yf.Ticker.income_stmt` | Revenue, net income, EPS (last 4 quarters) |
| Cash flow | `yf.Ticker.cashflow` | Free cash flow, operating cash flow (last 4 quarters) |
| Growth | Computed | Revenue YoY growth, earnings YoY growth |

Used by: Value strategy (quality scoring), Balanced (stability), valuation tool (DCF)

### Earnings (`tools/earnings.py`)

```python
fetch_earnings("AAPL")
```

| What | How | Fields |
|:-----|:----|:-------|
| Earnings history | `yf.Ticker.earnings_history` | Date, actual EPS, estimated EPS, surprise % (last 8 quarters) |
| Quarterly P&L | `yf.Ticker.quarterly_earnings` | Quarter, revenue, earnings |
| Next date | `yf.Ticker.calendar` | Upcoming earnings announcement date |
| Analyst targets | `yf.Ticker.info` | Price target (mean/low/high), number of analysts |

Used by: EventDriven strategy (hard event gate), trigger engine (earnings release detection), simulation events calendar

### Company News (`tools/fetch_news.py`)

```python
fetch_news("AAPL", limit=15)
```

| What | How | Fields |
|:-----|:----|:-------|
| Headlines | `yf.Ticker.news` | Title, publisher, link, date, type |
| Enrichment | `article_summarizer.py` fetches full URL, extracts 4-sentence summary | Summary text |

Used by: News collector (company category), portfolio watch skill

### Analyst Sentiment (`tools/sentiment.py`)

```python
fetch_sentiment("AAPL")
```

| What | How | Fields |
|:-----|:----|:-------|
| Recommendations | `yf.Ticker.recommendations` | Buy/hold/sell counts, mean score (1-5 scale) |
| Upgrades/downgrades | `yf.Ticker.upgrades_downgrades` | Firm, action, date |
| Short interest | `yf.Ticker.info` | Short ratio, short % of float |
| Price momentum | Computed from history | 1w, 1m, 3m returns, volume trend |

### Insider Activity (`tools/insider_activity.py`)

```python
fetch_insider_activity("AAPL")
```

| What | How | Fields |
|:-----|:----|:-------|
| Insider trades | `yf.Ticker.insider_transactions` | Name, position, buy/sell, date, shares, value (last 20) |
| Major holders | `yf.Ticker.major_holders` | % institutions, % insiders |
| Top institutions | `yf.Ticker.institutional_holders` | Name, shares, date, % outstanding |
| Buy/Sell signal | Computed | Strong buying / net buying / net selling / heavy selling |

### Macro & Sector Data (`tools/macro_data.py`)

```python
fetch_macro()
```

Pulls broad market data in one call:

| Category | Tickers | What |
|:---------|:--------|:-----|
| Indices | ^GSPC, ^DJI, ^IXIC, ^RUT | S&P 500, Dow, NASDAQ, Russell 2000 |
| Rates | ^TNX, ^TYX, ^FVX, ^IRX | 10y, 30y, 5y, 3-month Treasury yields |
| Commodities | GC=F, CL=F | Gold, crude oil futures |
| Volatility | ^VIX | CBOE Volatility Index (fear gauge) |
| Dollar | DX-Y.NYB | US Dollar Index |
| Sectors | XLK, XLF, XLV, XLE, XLI, XLP, XLY, XLU, XLRE, XLB, XLC | 11 sector ETFs: daily + monthly change |

### Technical Indicators (`tools/technical_indicators.py`)

```python
compute_indicators("AAPL")
```

Computed locally from yfinance price data using the `ta` library:

| Indicator | Parameters | Signal |
|:----------|:----------|:-------|
| Moving Averages | SMA 10/20/50/100/200, EMA 12/26 | Trend direction, golden/death cross |
| RSI | 14-period | <30 oversold, >70 overbought |
| MACD | 12/26/9 | Bullish/bearish cross |
| Bollinger Bands | 20-period, 2 std dev | Squeeze = breakout imminent |
| Stochastic | %K, %D | Oversold/overbought oscillator |
| ADX | 14-period | >25 strong trend, <25 weak |
| ATR | 14-period | Volatility in dollars (for stop-loss sizing) |
| Volume Ratio | Current / 20-day avg | >1.5 = spike, <0.5 = low activity |
| Support/Resistance | Pivot-based | S1, R1 levels |
| Technical Score | Composite 0-10 | Count of bullish vs bearish signals |

---

## SEC EDGAR (Filings)

**Tool:** `tools/fetch_filings.py`

```python
fetch_filings("AAPL", filing_types=["10-K", "10-Q", "8-K"], limit=10)
```

### How It Works

1. **Resolve ticker to CIK:** `https://www.sec.gov/files/company_tickers.json`
2. **Fetch filings list:** `https://data.sec.gov/submissions/CIK{cik}.json`
3. **Fetch structured data (XBRL):** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`

### What We Get

| Filing Type | What It Contains | How We Use It |
|:------------|:----------------|:-------------|
| **10-K** | Annual report: full financials, risk factors, strategy | Filing date used in events calendar |
| **10-Q** | Quarterly report: interim financials | Filing date used in events calendar |
| **8-K** | Material events: CEO changes, M&A, guidance updates | EventDriven strategy scores 8-K filings |

### XBRL Structured Data

For companies that file XBRL, we extract:
- Revenue, net income, EPS (basic + diluted)
- Total assets, liabilities, stockholders' equity
- Operating income, gross profit
- Cash, long-term debt
- Each with: period end date, value, form type, filing date

### Requirements

- **User-Agent header required:** SEC mandates identification. Set in `config.py`:
  ```python
  SEC_USER_AGENT = "ConsensusAITrader/1.0 (your-email@example.com)"
  ```
- No API key needed
- No rate limit (but be polite)

---

## GDELT (Geopolitical Events)

**Tool:** `tools/gdelt_backfill.py` + `tools/news_collector.py`

```python
# Real-time (today)
news_collector.collect_all(target_date, categories=["geopolitical"])

# Backfill historical
gdelt_backfill.backfill_period("2022-01-01", "2022-12-31", interval_days=7)
```

### How It Works

GDELT (Global Database of Events, Language, and Tone) monitors news worldwide. We query their API with 6 predefined searches:

| Query | What It Catches |
|:------|:---------------|
| `war OR conflict OR military` | Armed conflicts, military operations |
| `sanctions OR "trade war" OR tariff` | Trade disputes, economic sanctions |
| `OPEC OR "oil production" OR pipeline` | Energy supply disruptions |
| `pandemic OR outbreak OR WHO` | Health emergencies |
| `"interest rate" OR "central bank" OR inflation` | Monetary policy shifts |
| `geopolitical OR tensions OR crisis` | Broad geopolitical risk |

### API Details

- **Endpoint:** `https://api.gdeltproject.org/api/v2/doc/doc`
- **Format:** JSON article list
- **Fields:** Title, source, URL, published date, language, country
- **Rate limit:** 1 request per 6 seconds (429 triggers 10-second wait)
- **No API key required**

### Storage

```
data/news/{YYYY-MM-DD}/geopolitical/events.json
```

One file per date. Articles deduplicated by title. Backfill samples every 7 days to stay within rate limits (~30-50 min for 6 months).

### How It's Used

The signal engine computes a **geo_risk score** (0-1) from GDELT + Wikipedia events using exponential decay (half-life 2 days). This feeds into:
- Balanced strategy (shifts weights toward value/quality when risk is high)
- Adaptive strategy (triggers DEFENSIVE mode when geo_risk > 0.5 + vol > 0.22)
- MixLLM (included in the rich context sent to Opus)
- Trigger engine (NEWS_SPIKE trigger when risk jumps > 0.3 in one day)

---

## Wikipedia Current Events (Historical World Events)

**Tool:** `tools/wiki_news_backfill.py`

```python
# Backfill a date range
wiki_news_backfill.backfill_range("2022-01-01", "2022-12-31", interval=3)

# Load for simulation (with temporal gating)
data = wiki_news_backfill.load_wiki_for_sim("2022-06-15", lookback_days=7)
```

### How It Works

Wikipedia's [Portal:Current events](https://en.wikipedia.org/wiki/Portal:Current_events) has daily summaries of world events, categorized by type. We parse these for market-relevant events.

### API Details

- **Endpoint:** `https://en.wikipedia.org/w/api.php`
- **Action:** `parse` with `page=Portal:Current_events/{year}_{month}_{day}`
- **Format:** Wikitext (parsed locally)
- **Rate limit:** Generous (0.5s polite delay between requests)
- **No API key required**

### Categories Extracted

| Wikipedia Category | Our Market Category | Example |
|:-------------------|:-------------------|:--------|
| Armed conflicts | geopolitical | Russia-Ukraine escalation |
| Business and economy | business | Company earnings, trade deals |
| Disasters and accidents | disaster | Earthquakes, supply chain disruption |
| Health and environment | health | COVID updates, FDA approvals |
| International relations | politics | Sanctions, summits, elections |
| Law and crime | politics | Regulatory changes, antitrust |
| Science and technology | tech | AI breakthroughs, patent rulings |

### Storage

```
data/news/{YYYY-MM-DD}/geopolitical/wiki_events.json
```

One file per date. Sampled every 3 days by default (configurable). Covers 2019-2026 in the current backfill.

### Why Wikipedia?

- **Free** (no API key, no rate limits)
- **Curated** (editors filter noise, only notable events)
- **Historical** (available back to 2004)
- **Categorized** (saves us from building our own classifier)

---

## Google News RSS (Macro/Economic Headlines)

Used by `news_collector.py` for the **macro** category.

### How It Works

Fetches RSS feeds from Google News with specific topic searches:

| Topic | Search Query |
|:------|:------------|
| Fed/monetary policy | `Federal Reserve OR interest rate OR inflation` |
| Trade/tariffs | `tariff OR trade war OR sanctions` |
| Economic data | `GDP OR employment OR jobs report` |

### Details

- **Endpoint:** `https://news.google.com/rss/search?q={query}`
- **Format:** RSS/XML
- **Fields:** Title, link, published date, source
- **Rate limit:** Generally liberal
- **No API key required**

### Storage

```
data/news/{YYYY-MM-DD}/macro/macro.json
```

---

## FRED (Optional — Macro Economic Data)

**Tool:** `tools/macro_data.py`

Only used if `FRED_API_KEY` is set in environment. Not required for any core functionality.

### What It Provides

| Series | What |
|:-------|:-----|
| DGS10 | 10-year Treasury yield |
| DGS2 | 2-year Treasury yield |
| T10Y2Y | 10y-2y spread (yield curve) |
| FEDFUNDS | Federal funds rate |
| CPIAUCSL | CPI (inflation) |
| UNRATE | Unemployment rate |
| GDP | GDP |
| UMCSENT | Consumer sentiment |
| VIXCLS | VIX (alternative source) |

### How to Get a Key

1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Create a free account
3. Request an API key (instant)
4. Set `FRED_API_KEY` in your environment or `tools/config.py`

---

## Data Storage Structure

All collected data lives in `data/`:

```
data/
├── fundamentals/          # Pre-downloaded fundamental data
│   ├── AAPL.json             One file per ticker (93 stocks)
│   ├── MSFT.json
│   └── ...
│
└── news/                  # Daily news archive (380+ dates)
    └── {YYYY-MM-DD}/        One folder per date
        ├── company/            Per-ticker news (AAPL.json, MSFT.json, etc.)
        ├── geopolitical/       GDELT events.json + Wikipedia wiki_events.json
        ├── macro/              Google News RSS headlines
        ├── commodities/        Oil, gold, copper, nat gas prices + news
        ├── currencies/         USD index, EUR/USD, yields
        ├── sectors/            11 sector ETFs performance + rotation
        └── sentiment/          VIX, market breadth, fear/greed signals
```

### Caching Behavior

| Data Type | Cached? | How |
|:----------|:--------|:----|
| News (all categories) | Yes | Checks if `data/news/{date}/{category}/` exists, skips if present |
| Fundamentals | Yes | Pre-downloaded to `data/fundamentals/`, refreshed manually |
| Price data | No | Downloaded fresh each simulation run via yfinance |
| Technical indicators | No | Computed on-the-fly from price data |
| SEC filings | No | Fetched on demand |

### Daily Collection

Run `python tools/daily_collect.py` to:
1. Check last 14 business days for gaps
2. Backfill missing categories (geopolitical, macro, commodities, currencies, sectors, sentiment)
3. Collect all categories for today
4. Generate daily briefing

Company news cannot be backfilled (yfinance only returns current headlines).

---

## Rate Limits Summary

| Source | Limit | How We Handle It |
|:-------|:------|:----------------|
| yfinance | None official (Yahoo backend) | Bulk download with threading |
| SEC EDGAR | None (needs User-Agent) | Set in config.py |
| GDELT | 1 req / 6 seconds | Built-in delays, 429 retry |
| Wikipedia | Generous | 0.5s polite delay |
| Google News RSS | Liberal | No special handling |
| FRED | 120 req/min | Optional, rarely hits limit |

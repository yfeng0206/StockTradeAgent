"""Fetch fundamental financial data for a stock ticker via yfinance."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd


def df_to_dict(df: pd.DataFrame, periods: int = 4) -> list:
    """Convert a yfinance financial statement DataFrame to a list of dicts."""
    if df is None or df.empty:
        return []
    result = []
    for col in df.columns[:periods]:
        period_data = {"period": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)}
        for idx in df.index:
            val = df.loc[idx, col]
            if pd.notna(val):
                period_data[str(idx)] = float(val)
        result.append(period_data)
    return result


def fetch_fundamentals(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    # Key ratios from info
    ratios = {
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "pb_ratio": info.get("priceToBook"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "ev_to_revenue": info.get("enterpriseToRevenue"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "gross_margin": info.get("grossMargins"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "free_cash_flow": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "total_revenue": info.get("totalRevenue"),
        "ebitda": info.get("ebitda"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "float_shares": info.get("floatShares"),
        "dividend_yield": info.get("dividendYield"),
        "payout_ratio": info.get("payoutRatio"),
        "beta": info.get("beta"),
        "52w_change": info.get("52WeekChange"),
    }

    # Round float values
    for k, v in ratios.items():
        if isinstance(v, float):
            ratios[k] = round(v, 4)

    # Financial statements (last 4 periods)
    income_stmt = df_to_dict(stock.income_stmt)
    balance_sheet = df_to_dict(stock.balance_sheet)
    cash_flow = df_to_dict(stock.cashflow)

    # Revenue and earnings trend (compute YoY growth)
    revenue_trend = []
    if income_stmt:
        for i, period in enumerate(income_stmt):
            rev = period.get("Total Revenue")
            net = period.get("Net Income")
            entry = {"period": period["period"]}
            if rev:
                entry["revenue"] = rev
                if i + 1 < len(income_stmt) and income_stmt[i + 1].get("Total Revenue"):
                    prev_rev = income_stmt[i + 1]["Total Revenue"]
                    entry["revenue_yoy_growth"] = round((rev - prev_rev) / abs(prev_rev), 4) if prev_rev != 0 else None
            if net:
                entry["net_income"] = net
            revenue_trend.append(entry)

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company_name": info.get("longName", info.get("shortName", ticker)),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "description": info.get("longBusinessSummary", "")[:500],
        "key_ratios": ratios,
        "revenue_trend": revenue_trend,
        "income_statement": income_stmt,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch stock fundamentals")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()

    result = fetch_fundamentals(args.ticker.upper())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

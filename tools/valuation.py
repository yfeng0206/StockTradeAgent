"""Compute valuation estimates: simplified DCF, peer comparison, margin of safety."""

import argparse
import json
from datetime import datetime

import yfinance as yf
import pandas as pd


def compute_dcf(ticker: str, growth_rate: float = None, discount_rate: float = 0.10,
                terminal_growth: float = 0.03, projection_years: int = 5) -> dict:
    """Simplified DCF valuation based on free cash flow."""
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    fcf = info.get("freeCashflow")
    shares = info.get("sharesOutstanding")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    if not fcf or not shares or shares == 0:
        return {"error": "Insufficient data for DCF (need FCF and shares outstanding)"}

    # Estimate growth rate if not provided
    if growth_rate is None:
        rev_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")
        if rev_growth and earnings_growth:
            growth_rate = (rev_growth + earnings_growth) / 2
        elif rev_growth:
            growth_rate = rev_growth
        elif earnings_growth:
            growth_rate = earnings_growth
        else:
            growth_rate = 0.05  # default 5%

    # Cap growth rate at reasonable bounds
    growth_rate = max(min(growth_rate, 0.30), -0.10)

    # Project FCFs
    projected_fcfs = []
    for year in range(1, projection_years + 1):
        proj_fcf = fcf * (1 + growth_rate) ** year
        pv = proj_fcf / (1 + discount_rate) ** year
        projected_fcfs.append({
            "year": year,
            "projected_fcf": round(proj_fcf),
            "present_value": round(pv),
        })

    # Terminal value (Gordon Growth Model)
    terminal_fcf = fcf * (1 + growth_rate) ** projection_years * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / (1 + discount_rate) ** projection_years

    # Total enterprise value estimate
    total_pv_fcfs = sum(f["present_value"] for f in projected_fcfs)
    enterprise_value = total_pv_fcfs + pv_terminal

    # Per share intrinsic value
    cash = info.get("totalCash", 0) or 0
    debt = info.get("totalDebt", 0) or 0
    equity_value = enterprise_value + cash - debt
    intrinsic_per_share = equity_value / shares

    margin_of_safety = None
    if current_price and current_price > 0:
        margin_of_safety = round((intrinsic_per_share - current_price) / current_price * 100, 2)

    return {
        "method": "Discounted Cash Flow (simplified)",
        "current_fcf": round(fcf),
        "growth_rate_used": round(growth_rate, 4),
        "discount_rate": discount_rate,
        "terminal_growth": terminal_growth,
        "projection_years": projection_years,
        "projected_fcfs": projected_fcfs,
        "terminal_value": round(pv_terminal),
        "total_pv_fcfs": round(total_pv_fcfs),
        "enterprise_value_est": round(enterprise_value),
        "cash": round(cash),
        "debt": round(debt),
        "equity_value_est": round(equity_value),
        "intrinsic_value_per_share": round(intrinsic_per_share, 2),
        "current_price": current_price,
        "margin_of_safety_pct": margin_of_safety,
        "verdict": "Undervalued" if margin_of_safety and margin_of_safety > 15 else
                   "Fairly valued" if margin_of_safety and margin_of_safety > -10 else
                   "Overvalued" if margin_of_safety else "Unable to determine",
    }


def compute_peer_comparison(ticker: str) -> dict:
    """Compare valuation multiples against sector peers."""
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    sector = info.get("sector", "")
    industry = info.get("industry", "")

    # Key multiples for the target
    target_multiples = {
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "dividend_yield": info.get("dividendYield"),
        "profit_margin": info.get("profitMargins"),
        "roe": info.get("returnOnEquity"),
    }

    # Round values
    for k, v in target_multiples.items():
        if isinstance(v, float):
            target_multiples[k] = round(v, 4)

    return {
        "method": "Peer Comparison",
        "sector": sector,
        "industry": industry,
        "target_multiples": target_multiples,
        "note": "Compare these multiples against sector/industry averages. Lower P/E + higher ROE relative to peers suggests relative value.",
    }


def fetch_valuation(ticker: str) -> dict:
    dcf = compute_dcf(ticker)
    peers = compute_peer_comparison(ticker)

    result = {
        "ticker": ticker,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dcf_valuation": dcf,
        "peer_comparison": peers,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Compute stock valuation")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--growth", type=float, default=None, help="Override FCF growth rate (e.g., 0.10 for 10%%)")
    parser.add_argument("--discount", type=float, default=0.10, help="Discount rate (default 0.10)")
    args = parser.parse_args()

    result = fetch_valuation(args.ticker.upper())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

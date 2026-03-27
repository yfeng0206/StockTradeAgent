"""Fetch SEC EDGAR filings and XBRL financial facts for a U.S. company."""

import argparse
import json
import sys
from datetime import datetime

import requests

from config import SEC_USER_AGENT

HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}


def ticker_to_cik(ticker: str) -> str:
    """Resolve ticker to zero-padded CIK via SEC company tickers JSON."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return ""


def fetch_filings(ticker: str, filing_types: list = None, limit: int = 10) -> dict:
    if filing_types is None:
        filing_types = ["10-K", "10-Q", "8-K"]

    cik = ticker_to_cik(ticker)
    if not cik:
        return {"error": f"Could not find CIK for {ticker}", "ticker": ticker}

    # Fetch submission history
    sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(sub_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    sub_data = resp.json()

    company_name = sub_data.get("name", ticker)
    recent = sub_data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    filings = []
    for i in range(len(forms)):
        if forms[i] in filing_types:
            acc_clean = accessions[i].replace("-", "")
            filing = {
                "form": forms[i],
                "date": dates[i],
                "description": descriptions[i] if i < len(descriptions) else "",
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_clean}/{primary_docs[i]}",
            }
            filings.append(filing)
            if len(filings) >= limit:
                break

    # Fetch XBRL company facts (structured financial data)
    xbrl_facts = {}
    try:
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        facts_resp = requests.get(facts_url, headers=HEADERS, timeout=15)
        facts_resp.raise_for_status()
        facts_data = facts_resp.json()

        # Extract key financial facts from us-gaap
        us_gaap = facts_data.get("facts", {}).get("us-gaap", {})
        key_concepts = [
            "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "NetIncomeLoss", "EarningsPerShareBasic", "EarningsPerShareDiluted",
            "Assets", "Liabilities", "StockholdersEquity",
            "OperatingIncomeLoss", "GrossProfit",
            "CashAndCashEquivalentsAtCarryingValue",
            "LongTermDebt", "LongTermDebtNoncurrent",
        ]

        for concept in key_concepts:
            if concept in us_gaap:
                units = us_gaap[concept].get("units", {})
                # Get USD values or shares
                for unit_type in ["USD", "USD/shares"]:
                    if unit_type in units:
                        entries = units[unit_type]
                        # Get most recent entries
                        recent_entries = sorted(entries, key=lambda x: x.get("end", ""), reverse=True)[:4]
                        xbrl_facts[concept] = [
                            {
                                "period_end": e.get("end", ""),
                                "value": e.get("val"),
                                "form": e.get("form", ""),
                                "filed": e.get("filed", ""),
                            }
                            for e in recent_entries
                        ]
                        break
    except Exception:
        xbrl_facts = {"note": "XBRL data unavailable"}

    result = {
        "ticker": ticker,
        "cik": cik,
        "company_name": company_name,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "recent_filings": filings,
        "xbrl_financial_facts": xbrl_facts,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch SEC EDGAR filings")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--types", nargs="+", default=["10-K", "10-Q", "8-K"], help="Filing types")
    parser.add_argument("--limit", type=int, default=10, help="Max filings to return")
    args = parser.parse_args()

    result = fetch_filings(args.ticker.upper(), args.types, args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

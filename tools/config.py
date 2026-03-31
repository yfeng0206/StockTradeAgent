"""Shared configuration for stock research tools."""

import os

# SEC EDGAR requires a User-Agent header with your identity
# Set via environment variable or edit here
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "ConsensusAITrader/1.0 (garyfeng@example.com)"
)

# FRED API key (free from https://fred.stlouisfed.org/docs/api/api_key.html)
# Optional - macro_data.py falls back to yfinance proxies if not set
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# Default output format
OUTPUT_FORMAT = "json"

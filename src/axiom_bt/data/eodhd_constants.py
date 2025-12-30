"""EODHD API Constants and Limitations"""

# EODHD API Time Range Limitations
# Source: https://eodhd.com/financial-apis/intraday-historical-data-api

EODHD_MAX_DAYS = {
    "1m": 120,   # 1-minute bars: max 120 days per request
    "5m": 600,   # 5-minute bars: max 600 days per request
    "1h": 3650,  # 1-hour bars: max ~10 years
}

# Default: When no from/to specified, EODHD returns last N days
EODHD_DEFAULT_DAYS = {
    "1m": 120,  # Returns last 120 days
    "5m": 600,  # Returns last 600 days
}

# For chunked fetching when exceeding limits
EODHD_CHUNK_SIZE_DAYS = 120  # Fetch in 120-day chunks for 1m data

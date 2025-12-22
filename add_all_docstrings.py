#!/usr/bin/env python3
"""Add all function docstrings to eodhd_fetch.py - using line-based insertion"""

from pathlib import Path

source_file = Path("src/axiom_bt/data/eodhd_fetch.py")
with open(source_file) as f:
    lines = f.readlines()

# Docstrings to insert (line number -> docstring)
# Line numbers from current file (after module doc was added)
INSERTIONS = {
    203: '''    """
    Fetch 1-minute intraday OHLCV data from EODHD and save as parquet.
    
    Fetches ALL available intraday data (up to ~120 days) in a single API call.
    RTH (Regular Trading Hours) only.
    
    IMPORTANT: start_date/end_date parameters are kept for compatibility but
    currently IGNORED. The function fetches all available data from EODHD.
    
    Args:
        symbol: Stock ticker (e.g., 'TSLA', 'AAPL')
        exchange: Exchange code (e.g., 'US', 'NASDAQ')
        start_date: Start date 'YYYY-MM-DD' (currently ignored)
        end_date: End date 'YYYY-MM-DD' (currently ignored)
        out_dir: Output directory for parquet file
        tz: Target timezone (default: 'America/New_York')
        use_sample: If True, generate synthetic data instead of API call
    
    Returns:
        Path: Absolute path to saved parquet file
        
    Raises:
        SystemExit: If EODHD_API_TOKEN not found and use_sample=False
        SystemExit: If API returns no data
        requests.HTTPError: If API request fails (4xx/5xx)
    
    Data Format:
        Index: DatetimeIndex (timezone-aware, sorted)
        Columns: ['Open', 'High', 'Low', 'Close', 'Volume']
        Typical rows: ~40,000-50,000 bars for 60 days
    
    Example:
        >>> path = fetch_intraday_1m_to_parquet(
        ...     'TSLA', 'US', '2025-12-01', '2025-12-19',
        ...     Path('artifacts/data_m1')
        ... )
        >>> df = pd.read_parquet(path)
        >>> print(f"Rows: {len(df):,}")  # ~40,000+
    """
''',
    
    246: '''    """
    Resample 1-minute OHLCV data to higher timeframe (M5, M15).
    
    Args:
        m1_parquet: Path to M1 parquet file
        out_dir: Output directory for resampled data
        interval: Resample interval ('5min', '15min', '1h')
        tz: Target timezone (None = preserve M1 timezone)
        min_m1_rows: Minimum M1 rows required (default: 200)
    
    Returns:
        Path: Absolute path to resampled parquet file
        
    Raises:
        ValueError: If M1 file has < min_m1_rows
        ValueError: If resampling produces < 10 bars
    
    Resample Aggregation:
        Open: First value | High: Max | Low: Min | Close: Last | Volume: Sum
    
    Example:
        >>> m5 = resample_m1(Path('data_m1/TSLA.parquet'),
        ...                   Path('data_m5'), interval='5min')
    
    Note:
        Pandas 2.x compatible (uses lambda for first/last)
    """
''',

    73: '''    """
    Read EODHD API token from environment or config file.
    
    Search order:
        1. EODHD_API_TOKEN environment variable
        2. ~/.config/ib_project/credentials.toml
        3. ~/.config/axiom_bt/credentials.toml
        4. ./configs/credentials.toml
    
    Returns:
        str | None: API token if found, None otherwise
    """
''',

    197: '''    """
    Make HTTP GET request to EODHD API with 30s timeout.
    
    Args:
        url: API endpoint URL
        params: Query parameters (includes api_token)
    
    Returns:
        list: JSON response array
        
    Raises:
        requests.HTTPError: If status 4xx/5xx
        requests.Timeout: If exceeds 30s
    """
''',

    90: '''    """
    Standardize OHLCV DataFrame schema and timezone.
    
    Transformations:
        1. Rename columns to canonical (Open, High, Low, Close, Volume)
        2. Parse timestamp to DatetimeIndex
        3. Localize to UTC if naive
        4. Convert to target timezone
        5. Sort by timestamp
    
    Args:
        df: Raw DataFrame
        tz: Target timezone
    
    Returns:
        pd.DataFrame: Standardized with tz-aware index
    """
''',
}

# Sort by line number descending to avoid shifting line numbers
for line_num in sorted(INSERTIONS.keys(), reverse=True):
    docstring = INSERTIONS[line_num]
    # Insert after the function definition line
    lines.insert(line_num, docstring)
    print(f"✓ Inserted docstring at line {line_num}")

# Write back
with open(source_file, 'w') as f:
    f.writelines(lines)

print(f"\n✓ Updated {source_file}")
print(f"  Total lines: {len(lines)}")

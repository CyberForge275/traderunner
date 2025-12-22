#!/usr/bin/env python3
"""Add function docstrings to eodhd_fetch.py"""

from pathlib import Path
import re

source_file = Path("src/axiom_bt/data/eodhd_fetch.py")
with open(source_file) as f:
    content = f.read()

# Function docstrings to add
DOCSTRINGS = {
    'def fetch_intraday_1m_to_parquet(': '''    """
    Fetch 1-minute intraday OHLCV data from EODHD and save as parquet.
    
    This function fetches ALL available intraday data from the EODHD API
    (up to ~120 days historical data) and saves it to a parquet file.
    RTH (Regular Trading Hours) only.
    
    IMPORTANT: As of 2025-12-19, this function fetches ALL available data
    regardless of start_date/end_date parameters to avoid coverage issues.
    
    Args:
        symbol: Stock ticker (e.g., 'TSLA', 'AAPL')
        exchange: Exchange code (e.g., 'US', 'NASDAQ')
        start_date: Start date 'YYYY-MM-DD' (currently ignored - kept for compatibility)
        end_date: End date 'YYYY-MM-DD' (currently ignored - kept for compatibility)
        out_dir: Output directory for parquet file
        tz: Target timezone (default: 'America/New_York')
        use_sample: If True, generate synthetic data instead of API call
    
    Returns:
        Path: Absolute path to saved parquet file
        
    Raises:
        SystemExit: If EODHD_API_TOKEN not found and use_sample=False
        SystemExit: If API returns no data
        requests.HTTPError: If API request fails (4xx/5xx)
        requests.Timeout: If request times out (30s timeout)
    
    Data Format:
        - Index: DatetimeIndex (timezone-aware, sorted)
        - Columns: ['Open', 'High', 'Low', 'Close', 'Volume']
        - RTH only (no pre/after-market data)
        - Typical: ~40k-50k bars for 60+ days
    
    Example:
        >>> path = fetch_intraday_1m_to_parquet(
        ...     'TSLA', 'US', '2025-12-01', '2025-12-19',
        ...     Path('artifacts/data_m1')
        ... )
        >>> df = pd.read_parquet(path)
        >>> print(len(df))  # ~40,000+ bars
    """
''',

    'def resample_m1(': '''    """
    Resample 1-minute OHLCV data to higher timeframe (M5, M15).
    
    Reads M1 parquet, resamples using proper OHLCV aggregation, saves result.
    
    Args:
        m1_parquet: Path to M1 parquet file
        out_dir: Output directory for resampled data
        interval: Resample interval ('5min', '15min', '1h'). 
                  Must be pandas-compatible frequency string.
        tz: Target timezone (default: None = preserve M1 timezone)
        min_m1_rows: Minimum M1 rows required (default: 200)
    
    Returns:
        Path: Absolute path to resampled parquet file
        
    Raises:
        ValueError: If M1 file has < min_m1_rows
        ValueError: If resampling produces < 10 bars (data quality issue)
    
    Resample Logic:
        - Open: First value (lambda x: x.iloc[0])
        - High: Maximum value
        - Low: Minimum value  
        - Close: Last value (lambda x: x.iloc[-1])
        - Volume: Sum
        - NaN rows dropped after resampling
    
    Example:
        >>> m5_path = resample_m1(
        ...     Path('data_m1/TSLA.parquet'),
        ...     Path('data_m5'),
        ...     interval='5min'
        ... )
    
    Note:
        Pandas 2.x compatible (uses lambda for first/last aggregation)
    """
''',

    'def _read_token() -> Optional[str]:': '''    """
    Read EODHD API token from environment or config file.
    
    Search order:
        1. Environment variable: EODHD_API_TOKEN
        2. ~/.config/ib_project/credentials.toml
        3. ~/.config/axiom_bt/credentials.toml
        4. ./configs/credentials.toml
    
    Returns:
        str | None: API token if found, None otherwise
        
    Config File Format:
        [eodhd]
        api_token = "your-token-here"
    """
''',

    'def _request(url: str, params: dict) -> list:': '''    """
    Make HTTP GET request to EODHD API with timeout.
    
    Args:
        url: API endpoint URL
        params: Query parameters dict (includes api_token)
    
    Returns:
        list: JSON response (array of OHLCV dicts)
        
    Raises:
        requests.HTTPError: If response status is 4xx/5xx
        requests.Timeout: If request exceeds 30s timeout
    """
''',

    'def _standardize_ohlcv(df: pd.DataFrame, tz: str | None = None) -> pd.DataFrame:': '''    """
    Standardize OHLCV DataFrame schema and timezone.
    
    Transformations:
        1. Rename columns to canonical format (Open, High, Low, Close, Volume)
        2. Parse 'timestamp' column to DatetimeIndex
        3. Set timezone to UTC if naive
        4. Convert to target timezone
        5. Sort by timestamp
    
    Args:
        df: Raw DataFrame from API or file
        tz: Target timezone string
    
    Returns:
        pd.DataFrame: Standardized DataFrame with timezone-aware index
    """
''',
}

# Add docstrings
modified = content
for func_sig, docstring in DOCSTRINGS.items():
    # Find function definition
    pattern = re.escape(func_sig) + r'[^\n]*\):\n'
    matches = list(re.finditer(pattern, modified))
    
    if matches:
        match = matches[0]
        pos = match.end()
        
        # Check if docstring already exists
        next_line_start = pos
        next_line_end = modified.find('\n', next_line_start) + 1
        next_line = modified[next_line_start:next_line_end]
        
        if '"""' not in next_line:
            # Insert docstring
            modified = modified[:pos] + docstring + modified[pos:]
            print(f"✓ Added docstring for {func_sig[:40]}...")
        else:
            print(f"⊘ Skipped {func_sig[:40]}... (already has docstring)")
    else:
        print(f"✗ Could not find {func_sig[:40]}...")

# Write back
with open(source_file, 'w') as f:
    f.write(modified)

# Verify syntax
import py_compile
try:
    py_compile.compile(source_file, doraise=True)
    print(f"\n✓ Syntax check passed!")
except py_compile.PyCompileError as e:
    print(f"\n✗ Syntax error: {e}")

print(f"\n✓ Updated {source_file}")

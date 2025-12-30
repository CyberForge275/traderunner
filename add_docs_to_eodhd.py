#!/usr/bin/env python3
"""Add comprehensive inline documentation to eodhd_fetch.py"""

from pathlib import Path

# Read current file
source_file = Path("src/axiom_bt/data/eodhd_fetch.py")
with open(source_file) as f:
    lines = f.readlines()

# Module docstring to insert after imports
MODULE_DOC = '''"""
EODHD Data Fetching Service

This module provides functions to fetch intraday and daily OHLCV data from the
EODHD API and save it as parquet files for use in backtesting.

Key Features:
    - Fetches 1-minute intraday data (up to 120 days history)
    - Resamples M1 → M5, M15 for performance
    - Handles timezone conversion (UTC → target timezone)
    - Sample data generation for testing without API token
    - Simplified fetch: Gets ALL available data (no date range)

Architecture:
    EODHD API → fetch_intraday_1m_to_parquet() → M1 parquet
                                                  ↓
                                           resample_m1()
                                                  ↓
                                              M5/M15 parquet

API Documentation:
    https://eodhd.com/financial-apis/intraday-historical-data-api

Rate Limits:
    Varies by subscription (typically 100k requests/day)

Environment Variables:
    EODHD_API_TOKEN: Your EODHD API token (required unless use_sample=True)

Example Usage:
    >>> from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
    >>> from pathlib import Path
    >>>
    >>> # Fetch TSLA data (gets all available ~60 days)
    >>> path = fetch_intraday_1m_to_parquet(
    ...     symbol='TSLA',
    ...     exchange='US',
    ...     start_date='2025-12-01',  # Parameters kept for compatibility
    ...     end_date='2025-12-19',    # but currently ignored
    ...     out_dir=Path('artifacts/data_m1'),
    ...     tz='America/New_York'
    ... )
    >>> print(f"Data saved to: {path}")

Author: Droid Trading Team
Last Modified: 2025-12-19
Version: 2.0 (Simplified fetch - no date range)
"""

'''

# Find where to insert module doc (after __all__)
insert_pos = 0
for i, line in enumerate(lines):
    if '__all__' in line:
        # Find end of __all__ definition
        j = i
        while j < len(lines) and ']' not in lines[j]:
            j += 1
        insert_pos = j + 2  # After __all__ and blank line
        break

# Insert module doc
if insert_pos > 0:
    lines.insert(insert_pos, MODULE_DOC + '\n')
    print(f"✓ Inserted module docstring at line {insert_pos}")
else:
    print("✗ Could not find __all__ to insert module doc")

# Write back
with open(source_file, 'w') as f:
    f.writelines(lines)

print(f"✓ Updated {source_file}")
print(f"  Total lines: {len(lines)}")

"""
Architecture Tests: Data Source Segregation
===========================================

HARD FAIL tests enforcing strict separation between:
- Live pipeline (WebSocket/SQLite)
- Backtesting pipeline (Parquet/IntradayStore)

CRITICAL: Do NOT modify these tests to make them pass.
If they fail, fix the code, not the tests.

Enforcement Strategy:
1. AST-based import analysis (structural check)
2. String-based token detection (runtime check)
"""

import ast
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# ==============================================================================
# FORBIDDEN PATTERNS FOR LIVE CODE
# ==============================================================================

LIVE_FORBIDDEN_IMPORTS = {
    'axiom_bt.intraday',
    'axiom_bt.intraday.IntradayStore',
    'IntradayStore',
    'pandas.read_parquet',
    'pd.read_parquet',
}

LIVE_FORBIDDEN_TOKENS = [
    'read_parquet(',
    'IntradayStore(',
    'artifacts/data_m1',
    'artifacts/data_m5',
    'artifacts/data_m15',
    '/data_m1/',
    '/data_m5/',
    '/data_m15/',
    '.parquet',  # Live should never touch parquet files
]

# ==============================================================================
# FORBIDDEN PATTERNS FOR BACKTESTING CODE
# ==============================================================================

BACKTESTING_FORBIDDEN_IMPORTS = {
    'sqlite3',
    'trading_dashboard.repositories.live_candles',
    'repositories.live_candles',
    'LiveCandlesRepository',
}

BACKTESTING_FORBIDDEN_TOKENS = [
    'sqlite3.connect(',
    'LIVE_MARKETDATA_DB',
    'LiveCandlesRepository(',
    'market_data.db',  # Should not reference live database
]

# ==============================================================================
# TEST HELPERS
# ==============================================================================

def get_imports_from_file(file_path: Path) -> set:
    """Extract all imports from a Python file using AST."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        pytest.skip(f"Syntax error in {file_path}")
        return set()
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Also add full paths like "axiom_bt.intraday.IntradayStore"
                for alias in node.names:
                    full_import = f"{node.module}.{alias.name}"
                    imports.add(full_import)
    
    return imports


def check_forbidden_tokens(file_path: Path, forbidden_tokens: list) -> list:
    """Check for forbidden string tokens in file content."""
    try:
        with open(file_path) as f:
            content = f.read()
    except Exception as e:
        pytest.skip(f"Could not read {file_path}: {e}")
        return []
    
    found = []
    for token in forbidden_tokens:
        if token in content:
            found.append(token)
    
    return found


# ==============================================================================
# LIVE CODE TESTS (MUST NOT TOUCH PARQUET)
# ==============================================================================

def test_live_callbacks_no_parquet_imports():
    """Live chart callbacks MUST NOT import IntradayStore or parquet tools."""
    file_path = REPO_ROOT / 'trading_dashboard/callbacks/charts_live_callbacks.py'
    
    if not file_path.exists():
        pytest.skip("charts_live_callbacks.py not yet created")
    
    imports = get_imports_from_file(file_path)
    
    forbidden_found = [imp for imp in imports if any(fib in imp for fib in LIVE_FORBIDDEN_IMPORTS)]
    
    assert not forbidden_found, (
        f"❌ LIVE CALLBACKS VIOLATED DATA SEGREGATION!\n"
        f"File: {file_path}\n"
        f"Forbidden imports found: {forbidden_found}\n"
        f"\n"
        f"Live code MUST use SQLite only - NO Parquet/IntradayStore allowed.\n"
        f"This is enforced to prevent data source mixing."
    )


def test_live_callbacks_no_parquet_tokens():
    """Live callbacks MUST NOT contain parquet-related code strings."""
    file_path = REPO_ROOT / 'trading_dashboard/callbacks/charts_live_callbacks.py'
    
    if not file_path.exists():
        pytest.skip("charts_live_callbacks.py not yet created")
    
    forbidden_found = check_forbidden_tokens(file_path, LIVE_FORBIDDEN_TOKENS)
    
    assert not forbidden_found, (
        f"❌ LIVE CALLBACKS VIOLATED DATA SEGREGATION!\n"
        f"File: {file_path}\n"
        f"Forbidden tokens found: {forbidden_found}\n"
        f"\n"
        f"Live code MUST NOT reference Parquet paths or functions.\n"
        f"This is enforced to prevent data source mixing."
    )


def test_live_repository_no_parquet():
    """LiveCandlesRepository MUST use SQLite only."""
    file_path = REPO_ROOT / 'trading_dashboard/repositories/live_candles.py'
    
    assert file_path.exists(), "LiveCandlesRepository must exist"
    
    imports = get_imports_from_file(file_path)
    forbidden_imports = [imp for imp in imports if any(fib in imp for fib in LIVE_FORBIDDEN_IMPORTS)]
    
    assert not forbidden_imports, (
        f"❌ LiveCandlesRepository VIOLATED DATA SEGREGATION!\n"
        f"Forbidden imports: {forbidden_imports}\n"
        f"Live repository MUST use SQLite only."
    )
    
    forbidden_tokens = check_forbidden_tokens(file_path, LIVE_FORBIDDEN_TOKENS)
    
    assert not forbidden_tokens, (
        f"❌ LiveCandlesRepository VIOLATED DATA SEGREGATION!\n"
        f"Forbidden tokens: {forbidden_tokens}\n"
        f"Live repository MUST NOT touch Parquet files."
    )


# ==============================================================================
# BACKTESTING CODE TESTS (MUST NOT TOUCH SQLITE LIVE DB)
# ==============================================================================

def test_backtesting_callbacks_no_sqlite_imports():
    """Backtesting callbacks MUST NOT import sqlite3 or LiveCandlesRepository."""
    file_path = REPO_ROOT / 'trading_dashboard/callbacks/charts_backtesting_callbacks.py'
    
    if not file_path.exists():
        pytest.skip("charts_backtesting_callbacks.py not yet created")
    
    imports = get_imports_from_file(file_path)
    
    forbidden_found = [imp for imp in imports if any(fib in imp for fib in BACKTESTING_FORBIDDEN_IMPORTS)]
    
    assert not forbidden_found, (
        f"❌ BACKTESTING CALLBACKS VIOLATED DATA SEGREGATION!\n"
        f"File: {file_path}\n"
        f"Forbidden imports found: {forbidden_found}\n"
        f"\n"
        f"Backtesting code MUST use Parquet only - NO SQLite/Live DB allowed.\n"
        f"This is enforced to prevent data source mixing."
    )


def test_backtesting_callbacks_no_sqlite_tokens():
    """Backtesting callbacks MUST NOT contain sqlite-related code strings."""
    file_path = REPO_ROOT / 'trading_dashboard/callbacks/charts_backtesting_callbacks.py'
    
    if not file_path.exists():
        pytest.skip("charts_backtesting_callbacks.py not yet created")
    
    forbidden_found = check_forbidden_tokens(file_path, BACKTESTING_FORBIDDEN_TOKENS)
    
    assert not forbidden_found, (
        f"❌ BACKTESTING CALLBACKS VIOLATED DATA SEGREGATION!\n"
        f"File: {file_path}\n"
        f"Forbidden tokens found: {forbidden_found}\n"
        f"\n"
        f"Backtesting code MUST NOT reference Live SQLite DB.\n"
        f"This is enforced to prevent data source mixing."
    )


# ==============================================================================
# CROSS-CHECK: BOTH TABS EXIST AND ARE SEPARATE
# ==============================================================================

def test_separate_chart_tabs_exist():
    """Verify that separate tabs are implemented."""
    live_callbacks = REPO_ROOT / 'trading_dashboard/callbacks/charts_live_callbacks.py'
    backtest_callbacks = REPO_ROOT / 'trading_dashboard/callbacks/charts_backtesting_callbacks.py'
    
    assert live_callbacks.exists(), (
        "charts_live_callbacks.py must exist for Live tab"
    )
    assert backtest_callbacks.exists(), (
        "charts_backtesting_callbacks.py must exist for Backtesting tab"
    )
    
    # Verify they are different files
    assert live_callbacks != backtest_callbacks, (
        "Live and Backtesting must be separate callback files"
    )


def test_separate_repositories_exist():
    """Verify that separate repositories are implemented."""
    live_repo = REPO_ROOT / 'trading_dashboard/repositories/live_candles.py'
    
    assert live_repo.exists(), (
        "live_candles.py repository must exist for Live data"
    )
    
    # Backtesting uses existing IntradayStore (via axiom_bt)
    # Just verify Live repo is separate
    with open(live_repo) as f:
        content = f.read()
    
    assert 'LiveCandlesRepository' in content, (
        "live_candles.py must contain LiveCandlesRepository class"
    )


def test_helper_has_no_source_imports():
    """Chart preprocessing helper must not import data sources."""
    helper_path = REPO_ROOT / 'trading_dashboard/utils/chart_preprocess.py'
    
    assert helper_path.exists(), (
        "chart_preprocess.py helper must exist"
    )
    
    with open(helper_path) as f:
        content = f.read()
    
    # Forbidden tokens
    forbidden = ['sqlite3', 'read_parquet', 'IntradayStore', 'artifacts/data_m']
    found = [token for token in forbidden if token in content]
    
    assert not found, (
        f"❌ Chart preprocessing helper VIOLATED SOURCE NEUTRALITY!\n"
        f"File: {helper_path}\n"
        f"Forbidden tokens found: {found}\n"
        f"\n"
        f"Helper must be source-agnostic - NO direct data access.\n"
        f"It receives DataFrames and transforms them only."
    )

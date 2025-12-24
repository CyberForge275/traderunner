"""
Regression test: Ensure watchlist symbols are not hardcoded.

This test guards against drift between marketdata-stream subscriptions
and dashboard watchlist by ensuring no hardcoded symbol lists exist.
"""

import ast
import pytest
from pathlib import Path


def test_no_hardcoded_symbols_in_watchlist():
    """Verify get_watchlist_symbols does not contain hardcoded symbol lists."""
    
    # Read the repositories/__init__.py file
    repo_file = Path(__file__).parent.parent / "trading_dashboard" / "repositories" / "__init__.py"
    
    assert repo_file.exists(), f"Repository file not found: {repo_file}"
    
    with open(repo_file, 'r') as f:
        source_code = f.read()
    
    # Parse AST
    tree = ast.parse(source_code)
    
    # Find get_watchlist_symbols function
    watchlist_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_watchlist_symbols":
            watchlist_func = node
            break
    
    assert watchlist_func is not None, "get_watchlist_symbols function not found"
    
    # Check for hardcoded lists containing stock symbols
    suspicious_symbols = ["AAPL", "TSLA", "PLTR", "HOOD", "APP", "MSFT", "NVDA", "AMD"]
    
    func_source = ast.get_source_segment(source_code, watchlist_func)
    
    # Look for list literals with stock symbols
    for node in ast.walk(watchlist_func):
        if isinstance(node, ast.List):
            # Check if list contains string literals
            if all(isinstance(elt, ast.Constant) and isinstance(elt.value, str) for elt in node.elts):
                list_values = [elt.value for elt in node.elts]
                
                # Check if any suspicious symbols are in this list
                if any(sym in list_values for sym in suspicious_symbols):
                    pytest.fail(
                        f"Hardcoded symbol list found in get_watchlist_symbols: {list_values}\n"
                        "Symbols must come from EODHD_SYMBOLS environment variable only."
                    )
    
    # Additional check: function should reference EODHD_SYMBOLS
    if "EODHD_SYMBOLS" not in func_source:
        pytest.fail("get_watchlist_symbols does not reference EODHD_SYMBOLS environment variable")


def test_watchlist_requires_env_variable():
    """Verify that watchlist returns empty list when ENV not set."""
    import os
    from trading_dashboard.repositories import get_watchlist_symbols
    
    # Temporarily clear EODHD_SYMBOLS
    original_value = os.environ.get("EODHD_SYMBOLS")
    
    try:
        if "EODHD_SYMBOLS" in os.environ:
            del os.environ["EODHD_SYMBOLS"]
        
        symbols = get_watchlist_symbols()
        
        # Should return empty list, NOT a hardcoded default
        assert symbols == [], (
            f"Expected empty list when EODHD_SYMBOLS not set, got: {symbols}\n"
            "Hardcoded defaults are not allowed - use environment variable."
        )
    
    finally:
        # Restore original value
        if original_value is not None:
            os.environ["EODHD_SYMBOLS"] = original_value
        elif "EODHD_SYMBOLS" in os.environ:
            del os.environ["EODHD_SYMBOLS"]


def test_watchlist_parses_env_correctly():
    """Verify watchlist correctly parses EODHD_SYMBOLS."""
    import os
    from trading_dashboard.repositories import get_watchlist_symbols
    
    original_value = os.environ.get("EODHD_SYMBOLS")
    
    try:
        # Set test value
        os.environ["EODHD_SYMBOLS"] = "AAPL,MSFT,TSLA"
        
        symbols = get_watchlist_symbols()
        
        assert symbols == ["AAPL", "MSFT", "TSLA"], (
            f"Expected ['AAPL', 'MSFT', 'TSLA'], got: {symbols}"
        )
    
    finally:
        if original_value is not None:
            os.environ["EODHD_SYMBOLS"] = original_value
        elif "EODHD_SYMBOLS" in os.environ:
            del os.environ["EODHD_SYMBOLS"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pandas as pd
import pytest
from src.axiom_bt.compat.trades_contract import (
    normalize_trades_df_to_ui_contract,
    REQUIRED_UI_COLUMNS,
    OPTIONAL_UI_COLUMNS,
)

def test_normalization_success_title_case():
    """Test standard Title Case input from Compound Adapter."""
    data = {
        "Entry Time": ["2025-01-01"],
        "Exit Time": ["2025-01-02"],
        "Entry Price": [100.0],
        "Exit Price": [110.0],
        "PnL": [10.0],
        "Exit Reason": ["time_exit"],
        "Qty": [10],
        "Symbol": ["TEST"],
        "Side": ["BUY"],
        "Return %": [0.1]
    }
    df = pd.DataFrame(data)
    
    normalized = normalize_trades_df_to_ui_contract(df)
    
    # Check columns
    assert "entry_ts" in normalized.columns
    assert "entry_price" in normalized.columns
    assert "return_pct" in normalized.columns
    
    # Check ordering (required first)
    assert list(normalized.columns[:9]) == REQUIRED_UI_COLUMNS
    # optional columns follow
    opt_present = [c for c in OPTIONAL_UI_COLUMNS if c in normalized.columns]
    assert normalized.columns[9:9+len(opt_present)].tolist() == opt_present

def test_normalization_already_compliant():
    """Test input that is already snake_case."""
    data = {"symbol": ["S"], "side": ["B"], "qty": [1], 
            "entry_ts": ["t1"], "entry_price": [1], 
            "exit_ts": ["t2"], "exit_price": [2], 
            "pnl": [1], "reason": ["r"]}
    df = pd.DataFrame(data)
    
    normalized = normalize_trades_df_to_ui_contract(df)
    assert list(normalized.columns) == REQUIRED_UI_COLUMNS

def test_normalization_missing_cols():
    """Test missing required columns raises ValueError."""
    data = {
        "Entry Time": ["2025-01-01"],
        # Missing Exit Time
        "Entry Price": [100.0]
    }
    df = pd.DataFrame(data)
    
    with pytest.raises(ValueError, match="contract violation: missing columns"):
        normalize_trades_df_to_ui_contract(df)

def test_empty_df():
    """Test empty dataframe returns empty df with correct columns."""
    df = pd.DataFrame()
    normalized = normalize_trades_df_to_ui_contract(df)
    assert normalized.empty
    assert list(normalized.columns) == REQUIRED_UI_COLUMNS

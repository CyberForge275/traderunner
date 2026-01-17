import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Required columns in the final UI contract (snake_case)
REQUIRED_UI_COLUMNS = [
    "symbol",
    "side",
    "qty",
    "entry_ts",
    "entry_price",
    "exit_ts",
    "exit_price",
    "pnl",
    "reason",
]

# Optional but commonly present columns. These are ordered immediately after required.
OPTIONAL_UI_COLUMNS = [
    "return_pct",
]

# Mapping from Engine outputs (Title Case or alternate snake_case) to UI Contract (snake_case)
TITLE_TO_SNAKE_MAP = {
    # Compound Adapter (Title Case)
    "Entry Time": "entry_ts",
    "Exit Time": "exit_ts",
    "Entry Price": "entry_price",
    "Exit Price": "exit_price",
    "PnL": "pnl",
    "Exit Reason": "reason",
    "Qty": "qty",
    "Symbol": "symbol",
    "Side": "side",
    "Return %": "return_pct",
    
    # Legacy ReplayEngine (alternate snake_case)
    "exit_reason": "reason"
}

def normalize_trades_df_to_ui_contract(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert engine-native trades df into UI contract:
    required snake_case cols, stable types, stable ordering.
    Raises ValueError if required cols cannot be produced.
    """
    if df.empty:
        # Return empty DF with required columns
        return pd.DataFrame(columns=REQUIRED_UI_COLUMNS)

    # 1. Rename columns if they match the title case map
    df = df.rename(columns=TITLE_TO_SNAKE_MAP)

    # 2. Check for missing required columns
    missing = [c for c in REQUIRED_UI_COLUMNS if c not in df.columns]
    if missing:
        msg = f"trades.csv contract violation: missing columns: {missing}. Available: {list(df.columns)}"
        logger.error(f"actions: trades_contract_violation missing={missing}")
        raise ValueError(msg)

    # 3. Reorder keys to ensure stability (put required first, then others)
    optional_present = [c for c in OPTIONAL_UI_COLUMNS if c in df.columns]
    other_cols = [c for c in df.columns if c not in REQUIRED_UI_COLUMNS and c not in optional_present]
    final_order = REQUIRED_UI_COLUMNS + optional_present + other_cols
    
    return df[final_order]

def normalize_equity_curve_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure equity curve follows UI contract: 'ts', 'equity', 'drawdown_pct'.
    """
    if df.empty:
        return pd.DataFrame(columns=["ts", "equity", "drawdown_pct"])
    
    # Map common aliases
    mapping = {"timestamp": "ts", "cash": "equity"}
    df = df.rename(columns=mapping)
    
    if "ts" not in df.columns or "equity" not in df.columns:
        # Best effort: find anything timestamp-like or numeric? 
        # No, strict is better.
        logger.warning(f"actions: equity_contract_violation missing cols in {list(df.columns)}")
    
    # Ensure equity is numeric for drawdown calculation
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    
    # Calculate drawdown_pct if missing
    if "drawdown_pct" not in df.columns:
        running_max = df["equity"].cummax()
        df["drawdown_pct"] = (df["equity"] / running_max) - 1.0
        
    # Standard ordering
    cols = ["ts", "equity", "drawdown_pct"]
    others = [c for c in df.columns if c not in cols]
    return df[cols + others]

def normalize_filled_orders_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure filled orders follow UI contract. 
    In many cases, this is identical to trades.csv but with 'oco_group' etc.
    """
    # For now, we use the same required columns as trades, but maybe add others.
    # The UI typically expects the same as trades.csv for the Filled Orders tab.
    return normalize_trades_df_to_ui_contract(df)

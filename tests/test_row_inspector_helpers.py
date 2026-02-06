import pandas as pd

from trading_dashboard.components.row_inspector import (
    INSPECT_COL,
    add_inspect_column,
    derive_long_short_levels,
    row_to_kv_items,
    row_to_kv_sections_orders,
)


def test_add_inspect_column_dataframe():
    df = pd.DataFrame({"b": [1], "a": [2]})
    out = add_inspect_column(df)
    assert out.columns[0] == INSPECT_COL
    assert out.iloc[0][INSPECT_COL] == "🔍"


def test_add_inspect_column_rows():
    rows = [{"a": 1, "b": 2}]
    out = add_inspect_column(rows)
    assert list(out[0].keys())[0] == INSPECT_COL
    assert out[0][INSPECT_COL] == "🔍"


def test_row_to_kv_items_ordering_and_nulls():
    row = {
        "sig_x": 1,
        "dbg_a": None,
        "z": "val",
        "dbg_b": 2,
        "sig_a": 3,
        INSPECT_COL: "🔍",
    }
    items = row_to_kv_items(row)
    keys = [i["key"] for i in items]
    assert keys == ["dbg_a", "dbg_b", "sig_a", "sig_x", "z"]
    values = {i["key"]: i["value"] for i in items}
    assert values["dbg_a"] == ""


def test_row_to_kv_sections_orders_ordering():
    row = {
        "template_id": "t1",
        "oco_group_id": "g1",
        "symbol": "HOOD",
        "side": "BUY",
        "signal_ts": "2025-01-01 14:25:00+00:00",
        "qty": 1,
        "entry_price": 10.0,
        "stop_price": 9.0,
        "take_profit_price": 12.0,
        "dbg_mother_ts": "2025-01-01 14:30:00+00:00",
        "dbg_inside_ts": "2025-01-01 14:35:00+00:00",
        "dbg_valid_to_ts_utc": "2025-01-01 15:00:00+00:00",
        "order_valid_to_reason": "session_end",
        "order_expired": False,
    }
    sections = row_to_kv_sections_orders(row)
    flat = [item["key"] for section in sections for item in section["items"]]
    assert flat.index("template_id") < flat.index("dbg_mother_ts")
    assert "order_valid_to_ts (fallback)" in flat
    assert "LONG entry" in flat
    assert "entry_price" not in flat


def test_row_to_kv_sections_orders_dbg_last():
    row = {
        "symbol": "HOOD",
        "dbg_mother_ts": "2025-01-01 14:30:00+00:00",
        "entry_price": 10.0,
        "dbg_breakout_level": 11.0,
    }
    sections = row_to_kv_sections_orders(row)
    titles = [s["title"] for s in sections]
    assert titles[-1] == "Debug"


def test_derive_long_short_levels_from_buy_sell_rows():
    rows = [
        {"side": "BUY", "entry_price": 10.0, "stop_price": 9.0, "take_profit_price": 12.0},
        {"side": "SELL", "entry_price": 8.0, "stop_price": 9.0, "take_profit_price": 6.0},
    ]
    levels = derive_long_short_levels(rows)
    assert levels["long"]["entry"] == 10.0
    assert levels["short"]["entry"] == 8.0


def test_row_to_kv_sections_orders_always_shows_entries():
    row = {
        "template_id": "t2",
        "symbol": "HOOD",
        "side": "BUY",
        "signal_ts": "2025-01-01 14:25:00+00:00",
    }
    sections = row_to_kv_sections_orders(row)
    flat = [item["key"] for section in sections for item in section["items"]]
    assert "LONG entry" in flat
    assert "SHORT entry" in flat

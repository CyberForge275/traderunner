import pandas as pd

from trading_dashboard.components.row_inspector import (
    INSPECT_COL,
    add_inspect_column,
    row_to_kv_items,
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

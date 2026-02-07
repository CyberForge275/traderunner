"""Row Inspector helpers for Orders/Trades tables.

Provides a shared inspect column, row formatting, and a modal factory.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence
import logging

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)

INSPECT_COL = "__inspect__"
INSPECT_ICON = "🔍"


def add_inspect_column(rows_or_df: Any):
    """Prepend inspect column to rows or DataFrame.

    For list[dict], returns new list with INSPECT_COL first.
    For DataFrame, returns a new DataFrame with INSPECT_COL as first column.
    """
    if isinstance(rows_or_df, pd.DataFrame):
        df = rows_or_df.copy()
        df.insert(0, INSPECT_COL, INSPECT_ICON)
        return df

    rows = list(rows_or_df) if rows_or_df is not None else []
    out = []
    for row in rows:
        base = {INSPECT_COL: INSPECT_ICON}
        if isinstance(row, Mapping):
            base.update(row)
        out.append(base)
    return out


def _normalize_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _display_or_dash(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return str(value)


def resolve_oco_group(rows: Sequence[Mapping[str, Any]], selected_template_id: Any) -> list[dict[str, Any]]:
    """Resolve all rows belonging to the selected template's OCO group."""
    if not rows or selected_template_id is None:
        return []
    df = pd.DataFrame(rows)
    if df.empty or "template_id" not in df.columns:
        return []
    match = df[df["template_id"] == selected_template_id]
    if match.empty:
        return []
    oco_group_id = match.iloc[0].get("oco_group_id")
    if pd.notna(oco_group_id) and "oco_group_id" in df.columns:
        group = df[df["oco_group_id"] == oco_group_id]
    else:
        group = match
    return group.to_dict(orient="records")


def _first_non_null(values: Sequence[Any]) -> Any:
    for val in values:
        if val is None:
            continue
        if isinstance(val, float) and pd.isna(val):
            continue
        return val
    return None


def derive_long_short_levels(group_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Derive LONG/SHORT entry/stop/tp for OCO display."""
    if not group_rows:
        return {"long": {}, "short": {}}

    def _from_sig(keys: Sequence[str]) -> Any:
        return _first_non_null([row.get(k) for row in group_rows for k in keys])

    long_entry = _from_sig(["sig_LONG_entry_price", "sig_long_entry_price"])
    long_stop = _from_sig(["sig_LONG_stop_price", "sig_long_stop_price"])
    long_tp = _from_sig(["sig_LONG_take_profit_price", "sig_long_take_profit_price"])

    short_entry = _from_sig(["sig_SHORT_entry_price", "sig_short_entry_price"])
    short_stop = _from_sig(["sig_SHORT_stop_price", "sig_short_stop_price"])
    short_tp = _from_sig(["sig_SHORT_take_profit_price", "sig_short_take_profit_price"])

    if long_entry is None or long_stop is None or long_tp is None:
        buy_row = _first_non_null([row for row in group_rows if str(row.get("side", "")).upper() == "BUY"])
        if buy_row:
            long_entry = buy_row.get("entry_price") or buy_row.get("sig_entry_price")
            long_stop = buy_row.get("stop_price") or buy_row.get("stop_loss") or buy_row.get("sig_stop_price")
            long_tp = buy_row.get("take_profit_price") or buy_row.get("take_profit") or buy_row.get("sig_take_profit_price")

    if short_entry is None or short_stop is None or short_tp is None:
        sell_row = _first_non_null([row for row in group_rows if str(row.get("side", "")).upper() == "SELL"])
        if sell_row:
            short_entry = sell_row.get("entry_price") or sell_row.get("sig_entry_price")
            short_stop = sell_row.get("stop_price") or sell_row.get("stop_loss") or sell_row.get("sig_stop_price")
            short_tp = sell_row.get("take_profit_price") or sell_row.get("take_profit") or sell_row.get("sig_take_profit_price")

    return {
        "long": {"entry": long_entry, "stop": long_stop, "tp": long_tp},
        "short": {"entry": short_entry, "stop": short_stop, "tp": short_tp},
    }


def resolve_trade_oco_levels(
    trade_row: Mapping[str, Any],
    orders_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Resolve OCO signal levels and signal_ts for a trade row."""
    if not trade_row or not orders_rows:
        return {"signal_ts": None, "levels": {"long": {}, "short": {}}, "group_rows": [], "oco_group_id": None}

    template_id = trade_row.get("template_id")
    group_rows = resolve_oco_group(orders_rows, template_id)
    levels = derive_long_short_levels(group_rows)

    signal_ts = _first_non_null([row.get("signal_ts") for row in group_rows])
    signal_ts = pd.to_datetime(signal_ts, utc=True, errors="coerce") if signal_ts is not None else None
    if signal_ts is not None and pd.isna(signal_ts):
        signal_ts = None

    oco_group_id = _first_non_null([row.get("oco_group_id") for row in group_rows])

    return {
        "signal_ts": signal_ts,
        "levels": levels,
        "group_rows": group_rows,
        "oco_group_id": oco_group_id,
    }


def row_to_kv_items(row: Mapping[str, Any]) -> list[dict[str, str]]:
    """Convert row dict to sorted key/value items.

    Groups keys by prefix order: dbg_*, sig_*, then the rest (alphabetical within groups).
    """
    if not row:
        return []

    keys = [k for k in row.keys() if k != INSPECT_COL]
    dbg_keys = sorted([k for k in keys if k.startswith("dbg_")])
    sig_keys = sorted([k for k in keys if k.startswith("sig_")])
    other_keys = sorted([k for k in keys if k not in dbg_keys + sig_keys])
    ordered = dbg_keys + sig_keys + other_keys

    items = []
    for key in ordered:
        items.append({"key": key, "value": _normalize_value(row.get(key))})
    return items


def _take_keys(row: Mapping[str, Any], keys: Sequence[str], used: set[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key in keys:
        if key in row and key not in used:
            items.append({"key": key, "value": _normalize_value(row.get(key))})
            used.add(key)
    return items


def row_to_kv_sections_orders(
    row: Mapping[str, Any],
    *,
    group_rows: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build ordered sections for order inspector (core, time, levels, risk, flags, dbg)."""
    if not row:
        return []

    group = list(group_rows) if group_rows else [row]
    levels = derive_long_short_levels(group)

    used: set[str] = set()
    core_keys = [
        "template_id",
        "oco_group_id",
        "symbol",
        "side",
        "signal_ts",
        "qty",
        "order_valid_to_ts",
        "order_valid_to_reason",
        "dbg_mother_ts",
        "dbg_inside_ts",
        "dbg_mother_high",
        "dbg_mother_low",
        "dbg_mother_range",
    ]
    time_keys = [
        "entry_ts",
        "valid_from_ts",
        "dbg_valid_from_ts_utc",
        "dbg_signal_ts_ny",
        "dbg_signal_ts_berlin",
        "dbg_valid_to_ts_utc",
    ]
    risk_keys = [
        "atr",
        "risk_reward_ratio",
        "stop_distance_cap_ticks",
        "max_position_loss_pct_equity",
        "max_position_pct",
        "fees_bps",
        "slippage_bps",
    ]
    flag_keys = [
        "order_expired",
        "order_expire_reason",
        "dbg_order_expired",
        "dbg_order_expire_reason",
    ]

    sections: list[dict[str, Any]] = []
    core_items = _take_keys(row, core_keys, used)
    if "order_valid_to_ts" not in row and "dbg_valid_to_ts_utc" in row:
        core_items.append(
            {"key": "order_valid_to_ts (fallback)", "value": _normalize_value(row.get("dbg_valid_to_ts_utc"))}
        )
    if core_items:
        sections.append({"title": "Order", "items": core_items})

    long_items = []
    if levels["long"].get("entry") is not None:
        long_items.append({"key": "LONG entry", "value": _normalize_value(levels["long"].get("entry"))})
    if levels["long"].get("stop") is not None:
        long_items.append({"key": "LONG stop", "value": _normalize_value(levels["long"].get("stop"))})
    if levels["long"].get("tp") is not None:
        long_items.append({"key": "LONG tp", "value": _normalize_value(levels["long"].get("tp"))})

    short_items = []
    if levels["short"].get("entry") is not None:
        short_items.append({"key": "SHORT entry", "value": _normalize_value(levels["short"].get("entry"))})
    if levels["short"].get("stop") is not None:
        short_items.append({"key": "SHORT stop", "value": _normalize_value(levels["short"].get("stop"))})
    if levels["short"].get("tp") is not None:
        short_items.append({"key": "SHORT tp", "value": _normalize_value(levels["short"].get("tp"))})

    # Always show all 6 keys (use dash if missing)
    if not long_items:
        long_items = [
            {"key": "LONG entry", "value": _display_or_dash(levels["long"].get("entry"))},
            {"key": "LONG stop", "value": _display_or_dash(levels["long"].get("stop"))},
            {"key": "LONG tp", "value": _display_or_dash(levels["long"].get("tp"))},
        ]
    if not short_items:
        short_items = [
            {"key": "SHORT entry", "value": _display_or_dash(levels["short"].get("entry"))},
            {"key": "SHORT stop", "value": _display_or_dash(levels["short"].get("stop"))},
            {"key": "SHORT tp", "value": _display_or_dash(levels["short"].get("tp"))},
        ]
    sections.append({"title": "Levels (OCO)", "items": long_items + short_items})

    time_items = _take_keys(row, time_keys, used)
    if time_items:
        sections.append({"title": "Time", "items": time_items})

    risk_items = _take_keys(row, risk_keys, used)
    if risk_items:
        sections.append({"title": "Risk/Prices", "items": risk_items})

    bool_keys = sorted(
        k for k, v in row.items()
        if k not in used and not k.startswith("dbg_") and not k.startswith("sig_") and isinstance(v, bool)
    )
    flag_items = _take_keys(row, flag_keys, used)
    flag_items.extend(_take_keys(row, bool_keys, used))
    if flag_items:
        sections.append({"title": "Flags/Status", "items": flag_items})

    dbg_keys = sorted([k for k in row.keys() if k.startswith("dbg_") and k not in used])
    dbg_signal_order = [
        "dbg_breakout_level",
    ]
    dbg_validity_order = [
        "dbg_effective_valid_from_policy",
        "dbg_valid_from_ts_utc",
        "dbg_valid_from_ts_ny",
        "dbg_valid_to_ts_utc",
        "dbg_valid_to_ts_ny",
    ]
    dbg_items: list[dict[str, str]] = []
    dbg_items.extend(_take_keys(row, dbg_signal_order, used))
    dbg_items.extend(_take_keys(row, dbg_validity_order, used))
    for key in dbg_keys:
        if key not in used:
            dbg_items.append({"key": key, "value": _normalize_value(row.get(key))})
            used.add(key)
    if dbg_items:
        sections.append({"title": "Debug", "items": dbg_items})

    logger.info(
        "actions: inspector_kv_sort mode=orders core=%d dbg=%d total=%d",
        len(core_items),
        len(dbg_items),
        sum(len(s["items"]) for s in sections),
    )
    return sections


def render_kv_table(items: Iterable[Mapping[str, str]], *, scrollable: bool = True) -> html.Div:
    """Render a simple two-column key/value table for a row."""
    rows = []
    for item in items:
        rows.append(
            html.Div(
                className="inspector-row",
                children=[
                    html.Div(item.get("key", ""), className="inspector-key"),
                    html.Div(item.get("value", ""), className="inspector-value"),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "280px 1fr",
                    "gap": "12px",
                    "padding": "6px 0",
                    "borderBottom": "1px solid var(--border-color)",
                },
            )
        )

    style = {
        "fontFamily": "monospace",
        "wordBreak": "break-word",
        "overflowWrap": "anywhere",
    }
    if scrollable:
        style.update({"maxHeight": "65vh", "overflowY": "auto"})
    return html.Div(rows, style=style)


def render_kv_sections(sections: Sequence[Mapping[str, Any]]) -> html.Div:
    """Render key/value sections with headers and separators."""
    blocks = []
    for section in sections:
        title = section.get("title", "")
        items = section.get("items", [])
        if title:
            blocks.append(
                html.Div(
                    title,
                    style={"fontWeight": "600", "marginTop": "8px", "marginBottom": "4px"},
                )
            )
        blocks.append(render_kv_table(items, scrollable=False))
        blocks.append(html.Hr(style={"margin": "8px 0"}))
    return html.Div(
        blocks,
        style={
            "maxHeight": "65vh",
            "overflowY": "auto",
            "fontFamily": "monospace",
        },
    )


def build_inspector_modal(modal_id: str, title_id: str, body_id: str, chart_id: str | None = None) -> dbc.Modal:
    """Create a reusable Modal shell for row inspection."""
    close_id = f"{modal_id}__close"
    if chart_id:
        body = html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 2.25fr", "gap": "16px"},
            children=[
                html.Div(id=body_id, style={"minWidth": 0}),
                html.Div(
                    style={"minWidth": 0},
                    children=[dcc.Graph(id=chart_id, figure={})],
                ),
            ],
        )
    else:
        body = html.Div(id=body_id)
    return dbc.Modal(
        id=modal_id,
        is_open=False,
        size="xl",
        scrollable=True,
        className="trade-inspector-modal",
        style={"width": "95vw", "maxWidth": "1800px", "--bs-modal-width": "1800px"},
        children=[
            dbc.ModalHeader(dbc.ModalTitle(id=title_id)),
            dbc.ModalBody(body),
            dbc.ModalFooter(
                dbc.Button("Close", id=close_id, color="secondary")
            ),
        ],
    )


def log_open(table_name: str, template_id: Any = None, symbol: Any = None, ts: Any = None) -> None:
    """Structured logging for inspector open actions."""
    logger.info(
        "actions: inspector_open table=%s template_id=%s symbol=%s ts=%s",
        table_name,
        template_id,
        symbol,
        ts,
    )

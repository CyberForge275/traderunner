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


def row_to_kv_sections_orders(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build ordered sections for order inspector (core, time, risk, flags, dbg)."""
    if not row:
        return []

    used: set[str] = set()
    core_keys = [
        "template_id",
        "symbol",
        "side",
        "qty",
        "entry_price",
        "stop_loss",
        "stop_price",
        "take_profit",
        "take_profit_price",
        "exit_ts",
        "exit_reason",
    ]
    time_keys = [
        "signal_ts",
        "entry_ts",
        "valid_from_ts",
        "dbg_valid_from_ts_utc",
        "dbg_signal_ts_ny",
        "dbg_signal_ts_berlin",
        "dbg_exit_ts_ny",
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
    if "exit_ts" not in row and "dbg_valid_to_ts_utc" in row:
        core_items.append({"key": "exit_ts (fallback)", "value": _normalize_value(row.get("dbg_valid_to_ts_utc"))})
    if core_items:
        sections.append({"title": "Order", "items": core_items})

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
        "dbg_mother_ts",
        "dbg_inside_ts",
        "dbg_trigger_ts",
        "dbg_breakout_level",
        "dbg_mother_high",
        "dbg_mother_low",
        "dbg_mother_range",
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


def render_kv_table(items: Iterable[Mapping[str, str]]) -> html.Div:
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

    return html.Div(
        rows,
        style={
            "maxHeight": "65vh",
            "overflowY": "auto",
            "fontFamily": "monospace",
            "wordBreak": "break-word",
            "overflowWrap": "anywhere",
        },
    )


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
        blocks.append(render_kv_table(items))
        blocks.append(html.Hr(style={"margin": "8px 0"}))
    return html.Div(blocks)


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

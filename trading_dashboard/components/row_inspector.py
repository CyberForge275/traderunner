"""Row Inspector helpers for Orders/Trades tables.

Provides a shared inspect column, row formatting, and a modal factory.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping
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


def build_inspector_modal(modal_id: str, title_id: str, body_id: str, chart_id: str | None = None) -> dbc.Modal:
    """Create a reusable Modal shell for row inspection."""
    close_id = f"{modal_id}__close"
    if chart_id:
        body = html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1.5fr", "gap": "16px"},
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
        style={"width": "92vw", "maxWidth": "1600px"},
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

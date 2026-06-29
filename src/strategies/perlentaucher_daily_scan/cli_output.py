"""Formatting helpers for Perlentaucher scan CLI output."""

from __future__ import annotations

import pandas as pd


def _split_csv_values(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def build_signal_found_frame(summary_df: pd.DataFrame) -> pd.DataFrame:
    include_entry_fields = "entry_dates_csv" in summary_df.columns or "entry_prices_csv" in summary_df.columns
    columns = ["as_of_date", "symbol"]
    if include_entry_fields:
        columns.extend(["entry_date", "entry_price"])

    rows: list[dict[str, object]] = []
    for _, row in summary_df.iterrows():
        symbols = _split_csv_values(row.get("symbols_csv", ""))
        entry_dates = _split_csv_values(row.get("entry_dates_csv", "")) if include_entry_fields else []
        entry_prices = _split_csv_values(row.get("entry_prices_csv", "")) if include_entry_fields else []
        as_of_date = str(row.get("as_of_date", ""))
        for idx, symbol in enumerate(symbols):
            out_row: dict[str, object] = {
                "as_of_date": as_of_date,
                "symbol": symbol,
            }
            if include_entry_fields:
                out_row["entry_date"] = entry_dates[idx] if idx < len(entry_dates) else ""
                out_row["entry_price"] = entry_prices[idx] if idx < len(entry_prices) else ""
            rows.append(out_row)

    return pd.DataFrame(rows, columns=columns)


def build_closest_miss_frame(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
) -> pd.DataFrame | None:
    has_closest_miss_output = (
        "closest_miss_count" in summary_df.columns or "closest_miss_symbols_csv" in summary_df.columns
    )
    if not has_closest_miss_output:
        return None

    columns = [
        "as_of_date",
        "miss_rank",
        "symbol",
        "match_score",
        "closest_reference_symbol",
        "closest_reference_as_of_date",
    ]
    if detail_df.empty or "miss_rank" not in detail_df.columns:
        return pd.DataFrame(columns=columns)

    out = detail_df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out.loc[:, columns].copy()
    out["match_score"] = pd.to_numeric(out["match_score"], errors="coerce").map(
        lambda value: "" if pd.isna(value) else f"{float(value):.6f}"
    )
    return out


def _render_section(name: str, frame: pd.DataFrame) -> str:
    return f"[{name}]\n{frame.to_csv(index=False)}"


def render_scan_cli_output(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
) -> str:
    sections = [_render_section("signal_found", build_signal_found_frame(summary_df))]
    closest_miss_df = build_closest_miss_frame(summary_df, detail_df)
    if closest_miss_df is not None:
        sections.append(_render_section("closest_miss", closest_miss_df))
    return "\n\n".join(section.rstrip("\n") for section in sections) + "\n"


__all__ = [
    "build_closest_miss_frame",
    "build_signal_found_frame",
    "render_scan_cli_output",
]

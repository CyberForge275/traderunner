"""Inbound feature-frame contract for perlentaucher_daily_scan."""

from __future__ import annotations

import pandas as pd


IDENTIFIER_COLUMNS = ("symbol", "as_of_date")
FEATURE_COLUMNS = (
    "price_short",
    "price_mid",
    "price_l_long",
    "vol_short",
    "vol_mid",
    "vol_l_long",
)
REQUIRED_COLUMNS = (*IDENTIFIER_COLUMNS, *FEATURE_COLUMNS)


def normalize_feature_frame(frame: pd.DataFrame, *, frame_name: str) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(
            f"perlentaucher_daily_scan {frame_name} missing required columns: {', '.join(missing)}"
        )

    out = frame.loc[:, REQUIRED_COLUMNS].copy().reset_index(drop=True)
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    if (out["symbol"] == "").any():
        raise ValueError(f"perlentaucher_daily_scan {frame_name} has empty symbol values")

    dates = pd.to_datetime(out["as_of_date"], utc=True, errors="coerce", format="mixed")
    if dates.isna().any():
        raise ValueError(f"perlentaucher_daily_scan {frame_name} has invalid as_of_date values")
    out["as_of_date"] = dates.dt.date.astype(str)

    for column in FEATURE_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise ValueError(
                f"perlentaucher_daily_scan {frame_name} has invalid numeric values in {column}"
            )
        out[column] = out[column].astype(float)

    if out.duplicated(list(IDENTIFIER_COLUMNS)).any():
        raise ValueError(
            f"perlentaucher_daily_scan {frame_name} contains duplicate symbol/as_of_date rows"
        )

    return out.sort_values(list(IDENTIFIER_COLUMNS)).reset_index(drop=True)

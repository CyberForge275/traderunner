"""Pure sweet-spot reference-set helpers for perlentaucher_daily_scan."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


FEATURE_COLUMNS = (
    "price_short",
    "price_mid",
    "price_l_long",
    "vol_short",
    "vol_mid",
    "vol_l_long",
)


@dataclass(frozen=True)
class ReferenceSetArtifacts:
    reference_frame: pd.DataFrame
    native_ranges: dict[str, dict[str, float]]
    zscore_ranges: dict[str, dict[str, float]]


def build_reference_set(reference_features: pd.DataFrame) -> ReferenceSetArtifacts:
    required = {"symbol", *FEATURE_COLUMNS}
    missing = sorted(required - set(reference_features.columns))
    if missing:
        raise ValueError(
            "perlentaucher_daily_scan reference set missing required columns: "
            + ", ".join(missing)
        )

    df = reference_features.copy().reset_index(drop=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    if df.empty:
        raise ValueError("perlentaucher_daily_scan reference set cannot be empty")

    native_ranges: dict[str, dict[str, float]] = {}
    zscore_ranges: dict[str, dict[str, float]] = {}

    for column in FEATURE_COLUMNS:
        series = pd.to_numeric(df[column], errors="coerce")
        if series.isna().any():
            raise ValueError(f"perlentaucher_daily_scan reference set has invalid {column}")
        native_ranges[column] = {
            "lower": float(series.min()),
            "upper": float(series.max()),
        }
        std = float(series.std())
        mean = float(series.mean())
        zscore_ranges[column] = {
            "lower": mean - 3.5 * std,
            "upper": mean + 3.5 * std,
        }
        df[column] = series.astype(float)

    return ReferenceSetArtifacts(
        reference_frame=df,
        native_ranges=native_ranges,
        zscore_ranges=zscore_ranges,
    )

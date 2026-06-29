"""Helpers to precompute sweet-spot aggregation from in-memory slope features."""

from __future__ import annotations

import pandas as pd
from .feature_contract import normalize_feature_frame
from .reference_set import ReferenceSetArtifacts, build_reference_set


def _normalize_pairs(sweet_spot_pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    for symbol, as_of_date in sweet_spot_pairs:
        normalized.append((str(symbol).strip().upper(), pd.Timestamp(as_of_date).date().isoformat()))
    return normalized


def extract_sweet_spot_reference_features(
    feature_history_df: pd.DataFrame,
    *,
    sweet_spot_pairs: list[tuple[str, str]],
) -> pd.DataFrame:
    if not sweet_spot_pairs:
        raise ValueError("sweet_spot_pairs cannot be empty")

    history = normalize_feature_frame(feature_history_df, frame_name="feature_history")
    normalized_pairs = _normalize_pairs(sweet_spot_pairs)
    pair_df = pd.DataFrame(normalized_pairs, columns=["symbol", "as_of_date"]).drop_duplicates()

    out = history.merge(pair_df, on=["symbol", "as_of_date"], how="inner")
    if len(out) != len(pair_df):
        found_pairs = set(zip(out["symbol"], out["as_of_date"]))
        missing_pairs = [pair for pair in normalized_pairs if pair not in found_pairs]
        raise ValueError(
            "perlentaucher_daily_scan missing sweet spot rows: "
            + ", ".join(f"{symbol}@{as_of_date}" for symbol, as_of_date in missing_pairs)
        )

    return out.sort_values(["symbol", "as_of_date"]).reset_index(drop=True)


def precompute_sweet_spot_aggregation(
    feature_history_df: pd.DataFrame,
    *,
    sweet_spot_pairs: list[tuple[str, str]],
) -> ReferenceSetArtifacts:
    reference_features = extract_sweet_spot_reference_features(
        feature_history_df,
        sweet_spot_pairs=sweet_spot_pairs,
    )
    return build_reference_set(reference_features)


__all__ = [
    "extract_sweet_spot_reference_features",
    "precompute_sweet_spot_aggregation",
]

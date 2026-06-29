"""In-memory fetch/normalize/prefilter helpers for perlentaucher_daily_scan."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .debug_hooks import debug_stage_enabled
from .matcher import match_candidates
from .prefilter import build_volume_prefilter_metrics, select_volume_prefilter_candidates
from .reference_set import ReferenceSetArtifacts
from .slope_features import build_slope_feature_history_frame
from .sweet_spot_aggregation import (
    extract_sweet_spot_reference_features,
    precompute_sweet_spot_aggregation,
)


REQUIRED_FETCH_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class SweetSpotDailyPipelineArtifacts:
    daily_df: pd.DataFrame
    prefilter_metrics_df: pd.DataFrame
    candidate_symbols: list[str]
    candidate_daily_df: pd.DataFrame
    feature_history_df: pd.DataFrame
    candidate_feature_df: pd.DataFrame
    reference_feature_df: pd.DataFrame
    matched_df: pd.DataFrame


def normalize_daily_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    has_date = "date" in df.columns
    has_timestamp = "timestamp" in df.columns
    if not has_date and not has_timestamp:
        missing = sorted(set(REQUIRED_FETCH_COLUMNS) - set(df.columns))
        raise ValueError(
            "perlentaucher_daily_scan daily fetch missing required columns: "
            + ", ".join(missing)
        )

    required = {"symbol", "open", "high", "low", "close", "volume"}
    missing_core = sorted(required - set(df.columns))
    if missing_core:
        raise ValueError(
            "perlentaucher_daily_scan daily fetch missing required columns: "
            + ", ".join(missing_core)
        )

    time_col = "date" if has_date else "timestamp"
    out = df.loc[:, ["symbol", time_col, "open", "high", "low", "close", "volume"]].copy().reset_index(drop=True)
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["timestamp"] = pd.to_datetime(out.pop(time_col), utc=True, errors="coerce")
    if out["timestamp"].isna().any():
        raise ValueError("perlentaucher_daily_scan daily fetch contains invalid date/timestamp values")

    for column in ("open", "high", "low", "close", "volume"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise ValueError(
                f"perlentaucher_daily_scan daily fetch contains invalid numeric values in {column}"
            )

    out = out.loc[:, ["symbol", "timestamp", "open", "high", "low", "close", "volume"]]
    if debug_stage_enabled("normalize"):
        breakpoint()
    return out.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def select_prefilter_candidate_symbols(
    daily_df: pd.DataFrame,
    *,
    as_of_date: str,
) -> tuple[pd.DataFrame, list[str]]:
    metrics = build_volume_prefilter_metrics(daily_df, as_of_date=as_of_date)
    candidates = select_volume_prefilter_candidates(metrics)
    symbols = candidates["symbol"].astype(str).tolist() if not candidates.empty else []
    if debug_stage_enabled("candidate_select", as_of_date=as_of_date):
        breakpoint()
    return metrics, symbols


def filter_daily_frame_to_candidates(
    daily_df: pd.DataFrame,
    candidate_symbols: list[str],
) -> pd.DataFrame:
    normalized = [str(symbol).strip().upper() for symbol in candidate_symbols if str(symbol).strip()]
    if not normalized:
        return daily_df.iloc[0:0].copy()
    return (
        daily_df.loc[daily_df["symbol"].isin(normalized)]
        .sort_values(["symbol", "timestamp"])
        .reset_index(drop=True)
    )


def run_sweet_spot_daily_pipeline(
    raw_daily_df: pd.DataFrame,
    *,
    as_of_date: str,
    sweet_spot_pairs: list[tuple[str, str]],
    match_mode: str,
    max_candidates: int,
    reference_artifacts: ReferenceSetArtifacts | None = None,
    reference_feature_df: pd.DataFrame | None = None,
) -> SweetSpotDailyPipelineArtifacts:
    daily_df = normalize_daily_ohlcv_frame(raw_daily_df)
    prefilter_metrics_df, candidate_symbols = select_prefilter_candidate_symbols(
        daily_df,
        as_of_date=as_of_date,
    )
    candidate_daily_df = filter_daily_frame_to_candidates(daily_df, candidate_symbols)

    feature_history_df = build_slope_feature_history_frame(daily_df, as_of_date=as_of_date)
    candidate_feature_df = (
        feature_history_df.loc[feature_history_df["symbol"].isin(candidate_symbols)]
        .sort_values(["symbol", "as_of_date"])
        .drop_duplicates(subset=["symbol"], keep="last")
        .reset_index(drop=True)
    )
    if debug_stage_enabled("candidate_feature_filter", as_of_date=as_of_date):
        breakpoint()

    if reference_artifacts is None:
        reference_feature_df = extract_sweet_spot_reference_features(
            feature_history_df,
            sweet_spot_pairs=sweet_spot_pairs,
        )
        reference_set = precompute_sweet_spot_aggregation(
            feature_history_df,
            sweet_spot_pairs=sweet_spot_pairs,
        )
    else:
        reference_set = reference_artifacts
        if reference_feature_df is None:
            reference_feature_df = reference_artifacts.reference_frame.copy().reset_index(drop=True)
    if debug_stage_enabled("reference", as_of_date=as_of_date):
        breakpoint()

    if candidate_feature_df.empty:
        matched_df = candidate_feature_df.copy()
        matched_df["match_score"] = pd.Series(dtype=float)
        matched_df["eligibility_reason"] = pd.Series(dtype=object)
        matched_df["candidate_rank"] = pd.Series(dtype=float)
        matched_df["validity_class"] = pd.Series(dtype=object)
    else:
        matched_df = match_candidates(
            candidate_feature_df,
            reference_set,
            match_mode=match_mode,
            max_candidates=max_candidates,
        )

    return SweetSpotDailyPipelineArtifacts(
        daily_df=daily_df,
        prefilter_metrics_df=prefilter_metrics_df,
        candidate_symbols=candidate_symbols,
        candidate_daily_df=candidate_daily_df,
        feature_history_df=feature_history_df,
        candidate_feature_df=candidate_feature_df,
        reference_feature_df=reference_feature_df,
        matched_df=matched_df,
    )

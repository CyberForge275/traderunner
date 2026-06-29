"""Final SweetSpot match scans across a requested trading-date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .daily_pipeline import normalize_daily_ohlcv_frame, run_sweet_spot_daily_pipeline
from .matcher import feature_delta_map, find_closest_reference_row, resolve_match_ranges
from .reference_set import ReferenceSetArtifacts
from .scan_dates import coerce_scan_date, scan_session_dates
from .slope_features import build_slope_feature_history_frame
from .sweet_spot_aggregation import precompute_sweet_spot_aggregation

MAX_CLOSEST_MISSES = 3


@dataclass(frozen=True)
class MatchScanArtifacts:
    summary_df: pd.DataFrame
    detail_df: pd.DataFrame
    reference_frame_df: pd.DataFrame


def _normalize_pairs(sweet_spot_pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    for symbol, as_of_date in sweet_spot_pairs:
        normalized.append((str(symbol).strip().upper(), pd.Timestamp(as_of_date).date().isoformat()))
    if not normalized:
        raise ValueError("sweet_spot_pairs cannot be empty")
    return normalized


def _reference_target_date(valid_to: date, sweet_spot_pairs: list[tuple[str, str]]) -> str:
    target_dates = [valid_to]
    target_dates.extend(pd.Timestamp(as_of_date).date() for _, as_of_date in sweet_spot_pairs)
    return max(target_dates).isoformat()


def build_reference_artifacts_for_match_scan(
    daily_df: pd.DataFrame,
    *,
    valid_to: str | date,
    sweet_spot_pairs: list[tuple[str, str]],
) -> ReferenceSetArtifacts:
    normalized_pairs = _normalize_pairs(sweet_spot_pairs)
    feature_history_df = build_slope_feature_history_frame(
        daily_df,
        as_of_date=_reference_target_date(coerce_scan_date(valid_to), normalized_pairs),
    )
    return precompute_sweet_spot_aggregation(
        feature_history_df,
        sweet_spot_pairs=normalized_pairs,
    )


def _closest_miss_artifacts(
    matched_df: pd.DataFrame,
    *,
    as_of_date: str,
    reference_artifacts: ReferenceSetArtifacts,
    match_mode: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    miss_rows = (
        matched_df.loc[matched_df["eligibility_reason"] == "NO_MATCH"]
        .sort_values(["match_score", "symbol"])
        .head(MAX_CLOSEST_MISSES)
        .reset_index(drop=True)
    )
    if miss_rows.empty:
        return {
            "closest_miss_count": 0,
            "closest_miss_symbols": [],
            "closest_miss_symbols_csv": "",
            "closest_miss_scores_csv": "",
        }, []

    ranges = resolve_match_ranges(reference_artifacts, match_mode=match_mode)
    detail_rows: list[dict[str, object]] = []
    score_values: list[str] = []
    symbol_values: list[str] = []
    for miss_rank, (_, miss_row) in enumerate(miss_rows.iterrows(), start=1):
        ref_row, ref_score = find_closest_reference_row(
            miss_row,
            reference_artifacts.reference_frame,
            ranges=ranges,
        )
        symbol = str(miss_row["symbol"]).upper()
        symbol_values.append(symbol)
        score_values.append(f"{float(miss_row['match_score']):.6f}")
        detail_rows.append(
            {
                "as_of_date": as_of_date,
                "miss_rank": miss_rank,
                "symbol": symbol,
                "match_score": float(miss_row["match_score"]),
                "closest_reference_symbol": str(ref_row["symbol"]).upper(),
                "closest_reference_as_of_date": str(ref_row.get("as_of_date", "")),
                "closest_reference_score": ref_score,
                **feature_delta_map(miss_row, ref_row),
            }
        )

    return {
        "closest_miss_count": len(symbol_values),
        "closest_miss_symbols": symbol_values,
        "closest_miss_symbols_csv": ",".join(symbol_values),
        "closest_miss_scores_csv": ",".join(score_values),
    }, detail_rows


def scan_match_artifacts(
    raw_daily_df: pd.DataFrame,
    *,
    valid_from: str | date,
    valid_to: str | date,
    sweet_spot_pairs: list[tuple[str, str]],
    match_mode: str,
    max_candidates: int,
    session_timezone: str = "America/New_York",
    reference_artifacts: ReferenceSetArtifacts | None = None,
) -> MatchScanArtifacts:
    start_date = coerce_scan_date(valid_from)
    end_date = coerce_scan_date(valid_to)
    normalized_pairs = _normalize_pairs(sweet_spot_pairs)
    daily_df = normalize_daily_ohlcv_frame(raw_daily_df)
    scan_dates = scan_session_dates(
        daily_df["timestamp"],
        valid_from=start_date,
        valid_to=end_date,
        session_timezone=session_timezone,
        error_prefix="match scan bars",
    )
    if reference_artifacts is None:
        reference_artifacts = build_reference_artifacts_for_match_scan(
            daily_df,
            valid_to=end_date,
            sweet_spot_pairs=normalized_pairs,
        )

    summary_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    for as_of_date in scan_dates:
        artifacts = run_sweet_spot_daily_pipeline(
            daily_df,
            as_of_date=as_of_date.isoformat(),
            sweet_spot_pairs=normalized_pairs,
            match_mode=match_mode,
            max_candidates=max_candidates,
            reference_artifacts=reference_artifacts,
        )
        matched = artifacts.matched_df.loc[
            artifacts.matched_df["eligibility_reason"] == "MATCHED",
            ["symbol", "candidate_rank", "match_score"],
        ].sort_values(["candidate_rank", "match_score", "symbol"])
        matched_symbols = matched["symbol"].astype(str).tolist() if not matched.empty else []
        miss_summary, miss_detail_rows = _closest_miss_artifacts(
            artifacts.matched_df,
            as_of_date=as_of_date.isoformat(),
            reference_artifacts=reference_artifacts,
            match_mode=match_mode,
        )
        summary_rows.append(
            {
                "as_of_date": as_of_date.isoformat(),
                "symbol_count": len(matched_symbols),
                "symbols": matched_symbols,
                "symbols_csv": ",".join(matched_symbols),
                **miss_summary,
            }
        )
        detail_rows.extend(miss_detail_rows)

    summary_df = pd.DataFrame(summary_rows)
    if summary_df.empty:
        summary_df = pd.DataFrame(
            columns=[
                "as_of_date",
                "symbol_count",
                "symbols",
                "symbols_csv",
                "closest_miss_count",
                "closest_miss_symbols",
                "closest_miss_symbols_csv",
                "closest_miss_scores_csv",
            ]
        )
    summary_df = summary_df.loc[
        :,
        [
            "as_of_date",
            "symbol_count",
            "symbols",
            "symbols_csv",
            "closest_miss_count",
            "closest_miss_symbols",
            "closest_miss_symbols_csv",
            "closest_miss_scores_csv",
        ],
    ]
    detail_df = pd.DataFrame(
        detail_rows,
        columns=[
            "as_of_date",
            "miss_rank",
            "symbol",
            "match_score",
            "closest_reference_symbol",
            "closest_reference_as_of_date",
            "closest_reference_score",
            "delta_price_short",
            "delta_price_mid",
            "delta_price_l_long",
            "delta_vol_short",
            "delta_vol_mid",
            "delta_vol_l_long",
        ],
    )
    return MatchScanArtifacts(
        summary_df=summary_df,
        detail_df=detail_df,
        reference_frame_df=reference_artifacts.reference_frame.copy().reset_index(drop=True),
    )


def scan_match_dates(
    raw_daily_df: pd.DataFrame,
    *,
    valid_from: str | date,
    valid_to: str | date,
    sweet_spot_pairs: list[tuple[str, str]],
    match_mode: str,
    max_candidates: int,
    session_timezone: str = "America/New_York",
    reference_artifacts: ReferenceSetArtifacts | None = None,
) -> pd.DataFrame:
    return scan_match_artifacts(
        raw_daily_df,
        valid_from=valid_from,
        valid_to=valid_to,
        sweet_spot_pairs=sweet_spot_pairs,
        match_mode=match_mode,
        max_candidates=max_candidates,
        session_timezone=session_timezone,
        reference_artifacts=reference_artifacts,
    ).summary_df


__all__ = [
    "MatchScanArtifacts",
    "build_reference_artifacts_for_match_scan",
    "scan_match_artifacts",
    "scan_match_dates",
]

"""Pure candidate matcher for perlentaucher_daily_scan."""

from __future__ import annotations

import math

import pandas as pd

from .debug_hooks import debug_stage_enabled
from .reference_set import FEATURE_COLUMNS, ReferenceSetArtifacts

SINGLE_POINT_RELATIVE_EPSILON = 1e-9


def _expand_native_ranges(
    base_ranges: dict[str, dict[str, float]],
    *,
    multiplier: float,
) -> dict[str, dict[str, float]]:
    expanded: dict[str, dict[str, float]] = {}
    for key, value in base_ranges.items():
        width = value["upper"] - value["lower"]
        if width == 0.0:
            center = float(value["upper"])
            epsilon = max(abs(center) * SINGLE_POINT_RELATIVE_EPSILON, 1e-9)
            expanded[key] = {
                "lower": center - epsilon,
                "upper": center + epsilon,
            }
            continue
        expanded[key] = {
            "lower": float(value["lower"] - (multiplier - 2.0) * width),
            "upper": float(value["upper"] + (multiplier - 2.0) * width),
        }
    return expanded


def _score_row(
    row: pd.Series,
    reference_frame: pd.DataFrame,
    ranges: dict[str, dict[str, float]],
) -> float:
    scores: list[float] = []
    for _, ref_row in reference_frame.iterrows():
        scores.append(score_candidate_against_reference(row, ref_row, ranges))
    return min(scores) if scores else float("inf")


def _within_ranges(row: pd.Series, ranges: dict[str, dict[str, float]]) -> bool:
    for column in FEATURE_COLUMNS:
        value = float(row[column])
        if value < ranges[column]["lower"] or value > ranges[column]["upper"]:
            return False
    return True


def resolve_match_ranges(
    reference_set: ReferenceSetArtifacts,
    *,
    match_mode: str,
) -> dict[str, dict[str, float]]:
    if match_mode == "price_vol":
        return _expand_native_ranges(reference_set.native_ranges, multiplier=2.0)
    if match_mode == "zscore":
        return reference_set.zscore_ranges
    raise ValueError(f"unsupported match_mode: {match_mode!r}")


def score_candidate_against_reference(
    candidate_row: pd.Series,
    reference_row: pd.Series,
    ranges: dict[str, dict[str, float]],
) -> float:
    score = 0.0
    for column in FEATURE_COLUMNS:
        width = max(ranges[column]["upper"] - ranges[column]["lower"], 1e-9)
        score += abs(float(candidate_row[column]) - float(reference_row[column])) / width
    return score


def find_closest_reference_row(
    candidate_row: pd.Series,
    reference_frame: pd.DataFrame,
    *,
    ranges: dict[str, dict[str, float]],
) -> tuple[pd.Series, float]:
    best_row: pd.Series | None = None
    best_score = float("inf")
    for _, ref_row in reference_frame.iterrows():
        score = score_candidate_against_reference(candidate_row, ref_row, ranges)
        if score < best_score:
            best_row = ref_row
            best_score = score
    if best_row is None:
        raise ValueError("reference_frame cannot be empty")
    return best_row, float(best_score)


def feature_delta_map(
    candidate_row: pd.Series,
    reference_row: pd.Series,
) -> dict[str, float]:
    return {
        f"delta_{column}": float(candidate_row[column]) - float(reference_row[column])
        for column in FEATURE_COLUMNS
    }


def match_candidates(
    candidate_features: pd.DataFrame,
    reference_set: ReferenceSetArtifacts,
    *,
    match_mode: str,
    max_candidates: int,
) -> pd.DataFrame:
    required = {"symbol", *FEATURE_COLUMNS}
    missing = sorted(required - set(candidate_features.columns))
    if missing:
        raise ValueError(
            "perlentaucher_daily_scan matcher missing candidate columns: "
            + ", ".join(missing)
        )

    df = candidate_features.copy().reset_index(drop=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for column in FEATURE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if df[column].isna().any():
            raise ValueError(f"perlentaucher_daily_scan matcher has invalid {column}")

    ranges = resolve_match_ranges(reference_set, match_mode=match_mode)

    matched_mask = df.apply(lambda row: _within_ranges(row, ranges), axis=1)
    scores = df.apply(
        lambda row: _score_row(row, reference_set.reference_frame, ranges),
        axis=1,
    )

    df["match_score"] = scores.astype(float)
    df["eligibility_reason"] = matched_mask.map(lambda ok: "MATCHED" if bool(ok) else "NO_MATCH")
    df["candidate_rank"] = math.nan
    df["validity_class"] = matched_mask.map(lambda ok: "CANDIDATE" if bool(ok) else "INDICATIVE_ONLY")

    matched = df.loc[matched_mask].sort_values(["match_score", "symbol"]).head(max_candidates)
    for rank, index in enumerate(matched.index.tolist(), start=1):
        df.loc[index, "candidate_rank"] = float(rank)
    for _, row in df.iterrows():
        if debug_stage_enabled(
            "match",
            symbol=str(row["symbol"]),
            as_of_date=str(row["as_of_date"]) if "as_of_date" in row.index else None,
        ):
            breakpoint()
            break

    return df.sort_values(
        by=["candidate_rank", "match_score", "symbol"],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)

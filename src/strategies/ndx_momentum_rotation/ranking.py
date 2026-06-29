"""Cross-sectional ranking helpers with deterministic tie-break."""

from __future__ import annotations

import pandas as pd


RANK_COLUMNS = ["score", "symbol"]


def apply_deterministic_tie_break(scores: pd.DataFrame) -> pd.DataFrame:
    """Sort score desc, symbol asc for deterministic output."""

    required = {"symbol", "score"}
    missing = sorted(required - set(scores.columns))
    if missing:
        raise ValueError(f"scores missing required columns: {', '.join(missing)}")

    return (
        scores.copy()
        .sort_values(["score", "symbol"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def select_top_n(scores: pd.DataFrame, *, n: int, score_column: str = "score") -> pd.DataFrame:
    """Return deterministic Top-N with rank column."""

    if not isinstance(n, int) or n <= 0:
        raise ValueError("n must be int > 0")
    if score_column not in scores.columns:
        raise ValueError(f"scores missing score column: {score_column}")

    working = scores.copy()
    if score_column != "score":
        working["score"] = working[score_column]

    ranked = apply_deterministic_tie_break(working)
    out = ranked.head(n).copy().reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    return out

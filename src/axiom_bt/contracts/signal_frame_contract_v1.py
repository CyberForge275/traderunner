"""SignalFrame Contract V1 (generic framework, strategy-agnostic).

This module defines the generic schema primitives (ColumnSpec, SignalFrameSchemaV1)
and validation helpers. **No strategy-specific columns belong here.**
Concrete strategy schemas must live under ``src/strategies/<strategy>/...``.
"""

from __future__ import annotations

import json
import hashlib
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict

import pandas as pd

logger = logging.getLogger(__name__)


class SignalFrameContractError(ValueError):
    """Raised when a DataFrame violates SignalFrame Contract V1."""


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str
    nullable: bool
    kind: str  # e.g., base | indicator | signal | debug


@dataclass(frozen=True)
class SignalFrameSchemaV1:
    strategy_id: str
    strategy_tag: str
    version: str
    required_base: List[ColumnSpec]
    required_generic: List[ColumnSpec]
    required_strategy: List[ColumnSpec]

    def all_columns(self) -> List[ColumnSpec]:
        return [
            *self.required_base,
            *self.required_generic,
            *self.required_strategy,
        ]


def ensure_timestamp_utc(series: pd.Series, allow_nat: bool = False) -> pd.Series:
    """Return a tz-aware UTC timestamp series.

    Raises SignalFrameContractError if conversion fails or yields NaT (if not allowed).
    """
    try:
        ts_raw = pd.to_datetime(series, errors="coerce")
    except Exception as exc:  # pragma: no cover
        raise SignalFrameContractError(f"failed to parse timestamp column: {exc}") from exc

    if not allow_nat and ts_raw.isna().any():
        raise SignalFrameContractError("timestamp parsing produced NaT; ensure all timestamps are valid")

    # Reject naive timestamps (no tz info)
    if getattr(ts_raw.dt, "tz", None) is None:
        raise SignalFrameContractError("timestamp must be tz-aware; convert to UTC before use")

    ts = ts_raw.dt.tz_convert("UTC")
    return ts


def coerce_dtypes(df: pd.DataFrame, schema: SignalFrameSchemaV1) -> pd.DataFrame:
    """Coerce DataFrame columns to contract dtypes (best-effort).

    Supported dtype strings: datetime64[ns, UTC], float64, int64, bool, string.
    Raises SignalFrameContractError on failure.
    """
    df = df.copy()
    for col in schema.all_columns():
        if col.name not in df.columns:
            continue
        try:
            if col.dtype.startswith("datetime64"):
                df[col.name] = ensure_timestamp_utc(df[col.name], allow_nat=col.nullable)
            elif col.dtype == "bool":
                df[col.name] = df[col.name].astype(bool)
            elif col.dtype in {"float64", "float"}:
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce").astype(float)
            elif col.dtype in {"int64", "int"}:
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce").astype(int)
            elif col.dtype in {"string", "str", "object"}:
                df[col.name] = df[col.name].astype(str)
        except Exception as exc:  # pragma: no cover
            raise SignalFrameContractError(
                f"failed to coerce column '{col.name}' to dtype '{col.dtype}': {exc}"
            ) from exc
    return df


def _check_required_columns(df: pd.DataFrame, schema: SignalFrameSchemaV1) -> None:
    required = {c.name for c in schema.all_columns()}
    missing = required - set(df.columns)
    if missing:
        raise SignalFrameContractError(
            f"missing required columns: {sorted(missing)} for strategy_id={schema.strategy_id} version={schema.version}"
        )


def _check_nullability(df: pd.DataFrame, schema: SignalFrameSchemaV1) -> None:
    for col in schema.all_columns():
        if not col.nullable and df[col.name].isna().any():
            raise SignalFrameContractError(f"column '{col.name}' contains NaN but is non-nullable")


def _check_signal_invariants(df: pd.DataFrame) -> None:
    if {"sig_long", "sig_short"}.issubset(df.columns):
        both = (df["sig_long"] & df["sig_short"])
        if both.any():
            raise SignalFrameContractError("sig_long and sig_short cannot both be true")

    if "sig_side" in df.columns:
        allowed = {"LONG", "SHORT", "FLAT"}
        if not df["sig_side"].isin(allowed).all():
            bad = df.loc[~df["sig_side"].isin(allowed), "sig_side"].unique()
            raise SignalFrameContractError(f"sig_side contains invalid values: {bad}")

        if {"sig_long", "sig_short"}.issubset(df.columns):
            for _, row in df.iterrows():
                side = row["sig_side"]
                if side == "LONG" and not row["sig_long"]:
                    raise SignalFrameContractError("sig_side LONG requires sig_long=True")
                if side == "SHORT" and not row["sig_short"]:
                    raise SignalFrameContractError("sig_side SHORT requires sig_short=True")
                if side == "FLAT" and (row["sig_long"] or row["sig_short"]):
                    raise SignalFrameContractError("sig_side FLAT requires sig_long=False and sig_short=False")


def validate_signal_frame_v1(df: pd.DataFrame, schema: SignalFrameSchemaV1, *, strict: bool = True) -> None:
    """Validate DataFrame against SignalFrame Contract V1.

    Steps:
    1) Require all schema columns present.
    2) Coerce dtypes (datetime to UTC, numeric, bool, str).
    3) Enforce nullability and signal invariants.

    Args:
        df: Signal frame to validate.
        schema: Contract schema for the strategy/version.
        strict: If True, raises on failure; otherwise logs warning.

    Raises:
        SignalFrameContractError on violation when strict=True.
    """
    try:
        _check_required_columns(df, schema)
        df = coerce_dtypes(df, schema)
        _check_nullability(df, schema)
        _check_signal_invariants(df)
    except SignalFrameContractError:
        if strict:
            raise
        logger.warning("actions: signal_frame_contract_violation strategy_id=%s version=%s", schema.strategy_id, schema.version)
    else:
        logger.info(
            "actions: signal_frame_contract_valid strategy_id=%s version=%s rows=%d cols=%d",
            schema.strategy_id,
            schema.version,
            len(df),
            df.shape[1],
        )

def compute_schema_fingerprint(schema: SignalFrameSchemaV1) -> Dict:
    """Compute a stable, deterministic fingerprint of the SignalFrame schema.

    The fingerprint includes strategy metadata and a SHA256 hash of the
    column specifications ordered by name.
    """
    column_dicts = [asdict(c) for c in schema.all_columns()]
    # Stable sort by column name to ensure deterministic hash
    sorted_cols = sorted(column_dicts, key=lambda x: x["name"])

    payload = {
        "strategy_id": schema.strategy_id,
        "strategy_tag": schema.strategy_tag,
        "version": schema.version,
        "columns": sorted_cols,
    }

    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    schema_hash = hashlib.sha256(blob).hexdigest()

    return {
        "strategy_id": schema.strategy_id,
        "strategy_tag": schema.strategy_tag,
        "schema_version": schema.version,
        "schema_hash": schema_hash,
        "column_count": len(sorted_cols),
    }

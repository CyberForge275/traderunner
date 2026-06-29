"""Strategy plugin adapter for perlentaucher_daily_scan skeleton."""

from __future__ import annotations

import pandas as pd

from .config import build_perlentaucher_daily_scan_config
from .daily_pipeline import run_sweet_spot_daily_pipeline
from .intent_generation import generate_intent
from .matcher import match_candidates
from .reference_set import FEATURE_COLUMNS, build_reference_set
from .schema import get_signal_frame_schema
from .sweet_spot_cache import (
    load_sweet_spot_cache,
    load_sweet_spot_config,
    reference_artifacts_from_cache_payload,
    save_sweet_spot_cache,
)


def _load_reference_features(params: dict) -> pd.DataFrame | None:
    raw = params.get("reference_features")
    if raw is None:
        return None
    if isinstance(raw, pd.DataFrame):
        return raw.copy().reset_index(drop=True)
    if isinstance(raw, list):
        return pd.DataFrame(raw)
    raise ValueError("perlentaucher_daily_scan reference_features must be DataFrame or list[dict]")


def _load_sweet_spot_config(params: dict) -> dict | None:
    raw = params.get("sweet_spot_config")
    if raw is None:
        try:
            return load_sweet_spot_config()
        except FileNotFoundError:
            return None
    if isinstance(raw, dict):
        return raw
    raise ValueError("perlentaucher_daily_scan sweet_spot_config must be dict")


def _load_reference_artifacts_from_cache(params: dict, *, config: dict | None):
    raw = params.get("sweet_spot_cache_payload")
    if raw is not None:
        if not isinstance(raw, dict):
            raise ValueError("perlentaucher_daily_scan sweet_spot_cache_payload must be dict")
        return reference_artifacts_from_cache_payload(raw)
    if config is None:
        return None
    payload = load_sweet_spot_cache(config=config)
    if payload is None:
        return None
    return reference_artifacts_from_cache_payload(payload)


def _latest_rows_per_symbol(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return (
        df.sort_values(["symbol", "timestamp"])
        .drop_duplicates(subset=["symbol"], keep="last")
        .reset_index(drop=True)
    )


def _apply_long_signal_fields(df: pd.DataFrame, *, strategy_version: str) -> pd.DataFrame:
    out = df.copy().reset_index(drop=True)
    out["signal_side"] = pd.NA
    out["signal_reason"] = pd.NA
    out["entry_price"] = pd.NA
    out["stop_price"] = pd.NA
    out["take_profit_price"] = pd.NA
    out["template_id"] = pd.NA
    out["oco_group_id"] = pd.NA

    matched_mask = out["eligibility_reason"] == "MATCHED"
    if not matched_mask.any():
        return out

    out.loc[matched_mask, "signal_side"] = "BUY"
    out.loc[matched_mask, "signal_reason"] = "SWEET_SPOT_MATCH"
    out.loc[matched_mask, "entry_price"] = out.loc[matched_mask, "close"].astype(float)
    out.loc[matched_mask, "stop_price"] = out.loc[matched_mask, "entry_price"].astype(float) * 0.70
    out.loc[matched_mask, "take_profit_price"] = float("nan")

    for idx in out.index[matched_mask]:
        symbol = str(out.at[idx, "symbol"]).upper()
        signal_ts = pd.to_datetime(out.at[idx, "signal_ts"], utc=True)
        base_template_id = f"pts_{symbol}_{signal_ts.strftime('%Y%m%d_%H%M%S')}"
        out.at[idx, "template_id"] = f"{base_template_id}_BUY"
        out.at[idx, "oco_group_id"] = (
            f"{symbol}_{signal_ts.isoformat()}_perlentaucher_daily_scan_{strategy_version}"
        )

    return out


def extend_perlentaucher_signal_frame(bars: pd.DataFrame, params: dict) -> pd.DataFrame:
    cfg = build_perlentaucher_daily_scan_config(params)

    out = bars.copy().reset_index(drop=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    if out["timestamp"].isna().any():
        raise ValueError("perlentaucher_daily_scan bars contain invalid timestamps")
    if "symbol" not in out.columns:
        raise ValueError("perlentaucher_daily_scan requires bars with 'symbol' column")

    out["timeframe"] = "D1"
    out["strategy_id"] = "perlentaucher_daily_scan"
    out["strategy_version"] = str(params.get("strategy_version", "1.0.0"))
    out["strategy_tag"] = "pts"
    out["signal_ts"] = out["timestamp"]
    out["match_mode"] = cfg.match_mode.value
    out["use_volume_prefilter"] = cfg.use_volume_prefilter
    out["reference_set"] = cfg.reference_set.value
    out["candidate_rank"] = float("nan")
    out["eligibility_reason"] = "REFERENCE_SET_UNAVAILABLE"
    out["validity_class"] = "INDICATIVE_ONLY"
    out = _apply_long_signal_fields(
        out,
        strategy_version=str(params.get("strategy_version", "1.0.0")),
    )

    reference_features = _load_reference_features(params)
    if reference_features is None:
        sweet_spot_config = _load_sweet_spot_config(params)
        if sweet_spot_config is None:
            return out

        try:
            reference_artifacts = _load_reference_artifacts_from_cache(
                params,
                config=sweet_spot_config,
            )
            pipeline_artifacts = run_sweet_spot_daily_pipeline(
                out,
                as_of_date=str(out["timestamp"].max().date()),
                sweet_spot_pairs=[tuple(pair) for pair in sweet_spot_config["sweet_spot_pairs"]],
                match_mode=cfg.match_mode.value,
                max_candidates=cfg.max_candidates,
                reference_artifacts=reference_artifacts,
            )
            if reference_artifacts is None and bool(params.get("write_sweet_spot_cache", True)):
                save_sweet_spot_cache(
                    config=sweet_spot_config,
                    reference_artifacts=build_reference_set(pipeline_artifacts.reference_feature_df),
                )
            latest = _latest_rows_per_symbol(pipeline_artifacts.candidate_daily_df)
            merge_cols = ["symbol", "candidate_rank", "eligibility_reason", "validity_class"]
            if "match_score" in pipeline_artifacts.matched_df.columns:
                merge_cols.append("match_score")
            latest = latest.merge(
                pipeline_artifacts.matched_df[merge_cols],
                on="symbol",
                how="left",
            )
            latest["timeframe"] = "D1"
            latest["strategy_id"] = "perlentaucher_daily_scan"
            latest["strategy_version"] = str(params.get("strategy_version", "1.0.0"))
            latest["strategy_tag"] = "pts"
            latest["signal_ts"] = latest["timestamp"]
            latest["match_mode"] = cfg.match_mode.value
            latest["use_volume_prefilter"] = cfg.use_volume_prefilter
            latest["reference_set"] = cfg.reference_set.value
            if "candidate_rank" not in latest.columns:
                latest["candidate_rank"] = float("nan")
            if "eligibility_reason" not in latest.columns:
                latest["eligibility_reason"] = "NO_MATCH"
            if "validity_class" not in latest.columns:
                latest["validity_class"] = "INDICATIVE_ONLY"
            latest = latest.reset_index(drop=True)
            latest = _apply_long_signal_fields(
                latest,
                strategy_version=str(params.get("strategy_version", "1.0.0")),
            )
            return latest
        except ValueError:
            return out

    feature_missing = sorted(set(FEATURE_COLUMNS) - set(out.columns))
    if feature_missing:
        out["eligibility_reason"] = "FEATURES_MISSING"
        return out

    matched = match_candidates(
        out[["symbol", *FEATURE_COLUMNS]].copy(),
        build_reference_set(reference_features),
        match_mode=cfg.match_mode.value,
        max_candidates=cfg.max_candidates,
    )

    merge_cols = ["symbol", "candidate_rank", "eligibility_reason", "validity_class"]
    out = out.drop(columns=["candidate_rank", "eligibility_reason", "validity_class"]).merge(
        matched[merge_cols],
        on="symbol",
        how="left",
    )
    out = _apply_long_signal_fields(
        out,
        strategy_version=str(params.get("strategy_version", "1.0.0")),
    )
    return out


class PerlentaucherDailyScanPlugin:
    strategy_id = "perlentaucher_daily_scan"

    @staticmethod
    def get_schema(version: str):
        return get_signal_frame_schema(version)

    @staticmethod
    def extend_signal_frame(bars, params: dict):
        return extend_perlentaucher_signal_frame(bars, params)

    @staticmethod
    def generate_intent(signals_frame, strategy_id: str, strategy_version: str, params: dict):
        return generate_intent(signals_frame, strategy_id, strategy_version, params)

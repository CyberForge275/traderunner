"""Strategy-local scan orchestration for perlentaucher_daily_scan."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .candidate_scan import scan_candidate_dates
from .config import DEFAULT_MIN_HISTORY_DAYS
from .debug_hooks import debug_stage_enabled
from .impulse_backtest import (
    FIRST_TRIGGER_BACKTEST_MODE,
    build_first_trigger_backtest_artifacts,
)
from .impulse_scan import (
    FINAL_TRIGGER_MODE,
    FIRST_TRIGGER_MODE,
    build_impulse_scan_artifacts,
    extend_valid_to_for_confirmation,
    load_relaxed_impulse_scan_criteria,
)
from .match_scan import scan_match_artifacts
from .scan_marketdata import fetch_scan_marketdata
from .marketdata_request import build_stock_universe_request
from .reference_set import ReferenceSetArtifacts
from .sweet_spot_cache import (
    load_sweet_spot_cache,
    load_sweet_spot_config,
    reference_artifacts_from_cache_payload,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_MATCH_MODE = "price_vol"
DEFAULT_MAX_CANDIDATES = 25


@dataclass(frozen=True)
class PerlentaucherScanRequest:
    valid_from: str
    valid_to: str
    base_url: str
    mode: str
    non_empty_only: bool


@dataclass(frozen=True)
class PerlentaucherScanOutputs:
    summary_df: pd.DataFrame
    detail_df: pd.DataFrame
    reference_frame_df: pd.DataFrame


@dataclass(frozen=True)
class PerlentaucherScanArtifacts:
    summary_df: pd.DataFrame
    detail_df: pd.DataFrame
    reference_frame_df: pd.DataFrame
    raw_df: pd.DataFrame
    meta: dict
    request: PerlentaucherScanRequest
    sweet_spot_pairs: list[tuple[str, str]]


def load_active_sweet_spot_config() -> dict:
    return load_sweet_spot_config()


def load_active_sweet_spot_pairs(
    config: dict | None = None,
) -> list[tuple[str, str]]:
    resolved = config if config is not None else load_active_sweet_spot_config()
    return [tuple(pair) for pair in resolved["sweet_spot_pairs"]]


def load_cached_reference_artifacts(
    config: dict | None,
) -> ReferenceSetArtifacts | None:
    if config is None:
        return None
    payload = load_sweet_spot_cache(config=config)
    if payload is None:
        return None
    return reference_artifacts_from_cache_payload(payload)


def resolve_request_window(
    *,
    valid_from: str,
    valid_to: str,
    mode: str,
    sweet_spot_pairs: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    req = build_stock_universe_request(
        date_from=valid_from,
        date_to=valid_to,
        params={"min_history_days": DEFAULT_MIN_HISTORY_DAYS},
    )
    fetch_from = req.date_from
    if mode == "match":
        if not sweet_spot_pairs:
            raise ValueError("sweet_spot_pairs are required for mode=match")
        for _, as_of_date in sweet_spot_pairs:
            pair_req = build_stock_universe_request(
                date_from=as_of_date,
                date_to=as_of_date,
                params={"min_history_days": DEFAULT_MIN_HISTORY_DAYS},
            )
            fetch_from = min(fetch_from, pair_req.date_from)
    if debug_stage_enabled("request_window", as_of_date=valid_to):
        breakpoint()
    return fetch_from.isoformat(), req.date_to.isoformat()


def build_request_payload(
    *,
    valid_from: str,
    valid_to: str,
    mode: str,
    sweet_spot_pairs: list[tuple[str, str]] | None = None,
) -> dict:
    fetch_from, fetch_to = resolve_request_window(
        valid_from=valid_from,
        valid_to=valid_to,
        mode=mode,
        sweet_spot_pairs=sweet_spot_pairs,
    )
    return {
        "universe": "US",
        "asset_class": "stock",
        "symbol_mode": "ALL",
        "symbols": [],
        "valid_from": fetch_from,
        "valid_to": fetch_to,
    }


def fetch_daily_stock_data(
    *,
    base_url: str,
    valid_from: str,
    valid_to: str,
    mode: str,
    sweet_spot_pairs: list[tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, dict]:
    payload = build_request_payload(
        valid_from=valid_from,
        valid_to=valid_to,
        mode=mode,
        sweet_spot_pairs=sweet_spot_pairs,
    )
    if debug_stage_enabled("fetch_request", as_of_date=valid_to):
        breakpoint()
    return fetch_scan_marketdata(
        base_url=base_url,
        request_payload=payload,
        requested_valid_to=valid_to,
    )


def build_scan_outputs(
    *,
    raw_df: pd.DataFrame,
    request: PerlentaucherScanRequest,
    sweet_spot_pairs: list[tuple[str, str]],
    reference_artifacts: ReferenceSetArtifacts | None,
    impulse_criteria=None,
) -> PerlentaucherScanOutputs:
    if request.mode == "match":
        artifacts = scan_match_artifacts(
            raw_daily_df=raw_df,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            sweet_spot_pairs=sweet_spot_pairs,
            match_mode=DEFAULT_MATCH_MODE,
            max_candidates=DEFAULT_MAX_CANDIDATES,
            reference_artifacts=reference_artifacts,
        )
        return PerlentaucherScanOutputs(
            summary_df=artifacts.summary_df,
            detail_df=artifacts.detail_df,
            reference_frame_df=artifacts.reference_frame_df,
        )
    if request.mode in {FIRST_TRIGGER_MODE, FINAL_TRIGGER_MODE}:
        artifacts = build_impulse_scan_artifacts(
            raw_daily_df=raw_df,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            trigger_mode=request.mode,
            criteria=impulse_criteria,
        )
        return PerlentaucherScanOutputs(
            summary_df=artifacts.summary_df,
            detail_df=artifacts.detail_df,
            reference_frame_df=pd.DataFrame(),
        )
    return PerlentaucherScanOutputs(
        summary_df=scan_candidate_dates(
            raw_daily_df=raw_df,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
        ),
        detail_df=pd.DataFrame(),
        reference_frame_df=pd.DataFrame(),
    )


def _filter_non_empty(
    outputs: PerlentaucherScanOutputs,
) -> PerlentaucherScanOutputs:
    summary_df = outputs.summary_df.loc[outputs.summary_df["symbol_count"] > 0].reset_index(drop=True)
    detail_df = outputs.detail_df
    if not detail_df.empty:
        detail_df = detail_df.loc[detail_df["as_of_date"].isin(summary_df["as_of_date"])].reset_index(drop=True)
    return PerlentaucherScanOutputs(
        summary_df=summary_df,
        detail_df=detail_df,
        reference_frame_df=outputs.reference_frame_df,
    )


def run_perlentaucher_scan(
    request: PerlentaucherScanRequest,
) -> PerlentaucherScanArtifacts:
    config = load_active_sweet_spot_config() if request.mode == "match" else None
    sweet_spot_pairs = load_active_sweet_spot_pairs(config=config) if config is not None else []
    if debug_stage_enabled("sweet_spot_config", as_of_date=request.valid_to):
        breakpoint()
    reference_artifacts = load_cached_reference_artifacts(config)
    if debug_stage_enabled("sweet_spot_cache", as_of_date=request.valid_to):
        breakpoint()
    impulse_criteria = (
        load_relaxed_impulse_scan_criteria()
        if request.mode in {FIRST_TRIGGER_MODE, FINAL_TRIGGER_MODE, FIRST_TRIGGER_BACKTEST_MODE}
        else None
    )
    if request.mode == FIRST_TRIGGER_BACKTEST_MODE:
        if impulse_criteria is None or impulse_criteria.dataset_path is None:
            raise ValueError("first_trigger_backtest requires a frozen research dataset_path")
        raw_df = pd.read_parquet(impulse_criteria.dataset_path)
        meta = {
            "source": "frozen_research_dataset",
            "dataset_path": str(impulse_criteria.dataset_path),
        }
    else:
        fetch_valid_to = (
            extend_valid_to_for_confirmation(request.valid_to, confirm_offset=impulse_criteria.confirm_offset)
            if request.mode in {FIRST_TRIGGER_MODE, FINAL_TRIGGER_MODE} and impulse_criteria is not None
            else request.valid_to
        )
        raw_df, meta = fetch_daily_stock_data(
            base_url=request.base_url,
            valid_from=request.valid_from,
            valid_to=fetch_valid_to,
            mode=request.mode,
            sweet_spot_pairs=sweet_spot_pairs,
        )
    if request.mode == FIRST_TRIGGER_BACKTEST_MODE:
        artifacts = build_first_trigger_backtest_artifacts(
            raw_daily_df=raw_df,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            criteria=impulse_criteria,
        )
        outputs = PerlentaucherScanOutputs(
            summary_df=artifacts.summary_df,
            detail_df=artifacts.detail_df,
            reference_frame_df=pd.DataFrame(),
        )
        meta = {
            **dict(meta),
            "backtest_summary": dict(artifacts.backtest_summary),
        }
    else:
        outputs = build_scan_outputs(
            raw_df=raw_df,
            request=request,
            sweet_spot_pairs=sweet_spot_pairs,
            reference_artifacts=reference_artifacts,
            impulse_criteria=impulse_criteria,
        )

    if request.non_empty_only:
        outputs = _filter_non_empty(outputs)
    if debug_stage_enabled("summary", as_of_date=request.valid_to):
        breakpoint()

    return PerlentaucherScanArtifacts(
        summary_df=outputs.summary_df,
        detail_df=outputs.detail_df,
        reference_frame_df=outputs.reference_frame_df,
        raw_df=raw_df,
        meta=dict(meta),
        request=request,
        sweet_spot_pairs=sweet_spot_pairs,
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "PerlentaucherScanArtifacts",
    "PerlentaucherScanOutputs",
    "PerlentaucherScanRequest",
    "build_request_payload",
    "build_scan_outputs",
    "fetch_daily_stock_data",
    "load_active_sweet_spot_config",
    "load_active_sweet_spot_pairs",
    "resolve_request_window",
    "run_perlentaucher_scan",
]

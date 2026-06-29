"""Date-range impulse trigger scans for the isolated Perlentaucher research path."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from .daily_pipeline import normalize_daily_ohlcv_frame
from .impulse_features import build_impulse_features
from .impulse_trigger import evaluate_impulse_trigger
from .market_dates import market_date_series
from .scan_dates import coerce_scan_date, scan_session_dates


FIRST_TRIGGER_MODE = "first_trigger"
FINAL_TRIGGER_MODE = "final_trigger"
DEFAULT_IMPULSE_SCAN_META_PATH = (
    Path(__file__).resolve().parent
    / "docs"
    / "research"
    / "impulse_600_session_first_trigger_candidates_relaxed_baseline.meta.json"
)


@dataclass(frozen=True)
class ImpulseScanCriteria:
    dataset_path: Path | None
    pre_window: int
    confirm_offset: int
    trim_top_n: int
    trim_bottom_n: int
    cold_phase_price_min: float
    cold_phase_price_max: float
    cold_phase_mean_volume_min: float
    cold_phase_mean_volume_max: float
    cold_phase_median_volume_min: float
    cold_phase_median_volume_max: float
    min_price_lr_trimmed: float
    min_vol_lr_trimmed: float
    min_price_ratio_prev_to_breakout: float
    min_volume_ratio_prev_to_breakout: float
    min_price_ratio_prev_to_confirm: float
    min_volume_ratio_prev_to_confirm: float
    require_breakout_green: bool
    min_confirm_close_vs_breakout_close: float
    min_confirm_close_position_in_range: float
    min_pre_max_drawdown: float
    max_pre_gap_down_count: int
    invalid_symbols: frozenset[str]


@dataclass(frozen=True)
class ImpulseScanArtifacts:
    summary_df: pd.DataFrame
    detail_df: pd.DataFrame


def load_relaxed_impulse_scan_criteria(
    meta_path: Path = DEFAULT_IMPULSE_SCAN_META_PATH,
) -> ImpulseScanCriteria:
    with meta_path.open() as handle:
        payload = json.load(handle)
    criteria = payload["criteria"]
    invalid_symbols = frozenset(
        str(symbol).strip().upper()
        for symbol in payload.get("summary", {}).get("excluded_invalid_symbols", [])
    )
    return ImpulseScanCriteria(
        dataset_path=Path(criteria["dataset_path"]) if criteria.get("dataset_path") else None,
        pre_window=int(criteria["pre_window"]),
        confirm_offset=int(criteria["confirm_offset"]),
        trim_top_n=1,
        trim_bottom_n=1,
        cold_phase_price_min=float(criteria["cold_phase_price_min"]),
        cold_phase_price_max=float(criteria["cold_phase_price_max"]),
        cold_phase_mean_volume_min=float(criteria["cold_phase_mean_volume_min"]),
        cold_phase_mean_volume_max=float(criteria["cold_phase_mean_volume_max"]),
        cold_phase_median_volume_min=float(criteria["cold_phase_median_volume_min"]),
        cold_phase_median_volume_max=float(criteria["cold_phase_median_volume_max"]),
        min_price_lr_trimmed=float(criteria["min_price_lr_trimmed"]),
        min_vol_lr_trimmed=float(criteria["min_vol_lr_trimmed"]),
        min_price_ratio_prev_to_breakout=float(criteria["min_price_ratio_prev_to_breakout"]),
        min_volume_ratio_prev_to_breakout=float(criteria["min_volume_ratio_prev_to_breakout"]),
        min_price_ratio_prev_to_confirm=float(criteria["min_price_ratio_prev_to_confirm"]),
        min_volume_ratio_prev_to_confirm=float(criteria["min_volume_ratio_prev_to_confirm"]),
        require_breakout_green=bool(criteria["require_breakout_green"]),
        min_confirm_close_vs_breakout_close=float(criteria["min_confirm_close_vs_breakout_close"]),
        min_confirm_close_position_in_range=float(criteria["min_confirm_close_position_in_range"]),
        min_pre_max_drawdown=float(criteria["min_pre_max_drawdown"]),
        max_pre_gap_down_count=int(criteria["max_pre_gap_down_count"]),
        invalid_symbols=invalid_symbols,
    )


def extend_valid_to_for_confirmation(valid_to: str, *, confirm_offset: int) -> str:
    if confirm_offset < 1:
        raise ValueError("confirm_offset must be >= 1")
    business_days = pd.bdate_range(start=pd.Timestamp(valid_to), periods=confirm_offset + 1)
    return business_days[-1].date().isoformat()


def _cold_phase_metrics(pre_window_df: pd.DataFrame) -> dict[str, float]:
    closes = pd.to_numeric(pre_window_df["close"], errors="coerce")
    volumes = pd.to_numeric(pre_window_df["volume"], errors="coerce")
    return {
        "cold_phase_pre_min_close": float(closes.min()),
        "cold_phase_pre_max_close": float(closes.max()),
        "cold_phase_pre_mean_vol": float(volumes.mean()),
        "cold_phase_pre_median_vol": float(volumes.median()),
    }


def _cold_phase_passed(metrics: dict[str, float], criteria: ImpulseScanCriteria) -> bool:
    return bool(
        metrics["cold_phase_pre_min_close"] >= criteria.cold_phase_price_min
        and metrics["cold_phase_pre_max_close"] <= criteria.cold_phase_price_max
        and criteria.cold_phase_mean_volume_min <= metrics["cold_phase_pre_mean_vol"] <= criteria.cold_phase_mean_volume_max
        and criteria.cold_phase_median_volume_min
        <= metrics["cold_phase_pre_median_vol"]
        <= criteria.cold_phase_median_volume_max
    )


def _first_trigger_passed(decision: dict[str, object]) -> bool:
    return bool(
        decision["precondition_passed"]
        and decision["prewindow_path_passed"]
        and decision["breakout_passed"]
        and decision["breakout_bar_passed"]
    )


def _decision_for_symbol_date(
    sym_df: pd.DataFrame,
    *,
    breakout_idx: int,
    criteria: ImpulseScanCriteria,
) -> dict[str, object]:
    breakout_date = str(sym_df.iloc[breakout_idx]["session_date"])
    features = build_impulse_features(
        sym_df,
        symbol=str(sym_df.iloc[0]["symbol"]),
        breakout_date=breakout_date,
        pre_window=criteria.pre_window,
        confirm_offset=criteria.confirm_offset,
        trim_top_n=criteria.trim_top_n,
        trim_bottom_n=criteria.trim_bottom_n,
    )
    decision = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=criteria.min_price_lr_trimmed,
        min_vol_lr_trimmed=criteria.min_vol_lr_trimmed,
        min_price_ratio_prev_to_breakout=criteria.min_price_ratio_prev_to_breakout,
        min_volume_ratio_prev_to_breakout=criteria.min_volume_ratio_prev_to_breakout,
        min_price_ratio_prev_to_confirm=criteria.min_price_ratio_prev_to_confirm,
        min_volume_ratio_prev_to_confirm=criteria.min_volume_ratio_prev_to_confirm,
        require_breakout_green=criteria.require_breakout_green,
        min_confirm_close_vs_breakout_close=criteria.min_confirm_close_vs_breakout_close,
        min_confirm_close_position_in_range=criteria.min_confirm_close_position_in_range,
        min_pre_max_drawdown=criteria.min_pre_max_drawdown,
        max_pre_gap_down_count=criteria.max_pre_gap_down_count,
    )
    return {
        **features,
        **decision,
        "first_trigger_passed": _first_trigger_passed(decision),
        "final_trigger_passed": bool(decision["trigger_passed"]),
    }


def _entry_fields_for_breakout(
    sym_df: pd.DataFrame,
    *,
    breakout_idx: int,
) -> dict[str, object]:
    entry_idx = breakout_idx + 1
    if entry_idx >= len(sym_df):
        return {
            "entry_date": pd.NA,
            "entry_open": pd.NA,
            "entry_volume": pd.NA,
        }
    entry_row = sym_df.iloc[entry_idx]
    return {
        "entry_date": str(entry_row["session_date"]),
        "entry_open": float(entry_row["open"]),
        "entry_volume": float(entry_row["volume"]),
    }


def build_impulse_scan_artifacts(
    raw_daily_df: pd.DataFrame,
    *,
    valid_from: str,
    valid_to: str,
    trigger_mode: str,
    criteria: ImpulseScanCriteria | None = None,
    session_timezone: str = "America/New_York",
) -> ImpulseScanArtifacts:
    if trigger_mode not in {FIRST_TRIGGER_MODE, FINAL_TRIGGER_MODE}:
        raise ValueError(f"unsupported trigger_mode: {trigger_mode}")
    resolved_criteria = criteria if criteria is not None else load_relaxed_impulse_scan_criteria()

    start_date = coerce_scan_date(valid_from)
    end_date = coerce_scan_date(valid_to)
    daily_df = normalize_daily_ohlcv_frame(raw_daily_df)
    all_scan_dates = scan_session_dates(
        daily_df["timestamp"],
        valid_from=start_date,
        valid_to=end_date,
        session_timezone=session_timezone,
        error_prefix="impulse scan bars",
    )
    scan_date_set = {day.isoformat() for day in all_scan_dates}

    detail_rows: list[dict[str, object]] = []
    for symbol, sym_df in daily_df.groupby("symbol", sort=True):
        if symbol in resolved_criteria.invalid_symbols:
            continue
        symbol_df = sym_df.sort_values("timestamp").reset_index(drop=True).copy()
        symbol_df["session_date"] = market_date_series(
            symbol_df["timestamp"],
            session_timezone=session_timezone,
            error_prefix="impulse scan symbol bars",
        ).astype(str)
        breakout_indices = symbol_df.index[symbol_df["session_date"].isin(scan_date_set)]
        for idx in breakout_indices.tolist():
            if idx < resolved_criteria.pre_window:
                continue
            breakout_date = str(symbol_df.iloc[idx]["session_date"])
            pre_window_df = symbol_df.iloc[idx - resolved_criteria.pre_window : idx].reset_index(drop=True)
            cold_phase_metrics = _cold_phase_metrics(pre_window_df)
            if not _cold_phase_passed(cold_phase_metrics, resolved_criteria):
                continue

            decision = _decision_for_symbol_date(
                symbol_df,
                breakout_idx=idx,
                criteria=resolved_criteria,
            )
            if trigger_mode == FIRST_TRIGGER_MODE and not decision["first_trigger_passed"]:
                continue
            if trigger_mode == FINAL_TRIGGER_MODE and not decision["final_trigger_passed"]:
                continue

            detail_rows.append(
                {
                    "as_of_date": breakout_date,
                    **_entry_fields_for_breakout(symbol_df, breakout_idx=idx),
                    **cold_phase_metrics,
                    **decision,
                }
            )

    detail_df = pd.DataFrame(detail_rows).sort_values(["as_of_date", "symbol"]).reset_index(drop=True) if detail_rows else pd.DataFrame()
    summary_rows: list[dict[str, object]] = []
    for scan_day in all_scan_dates:
        as_of_date = scan_day.isoformat()
        if detail_df.empty:
            symbols: list[str] = []
            entry_dates: list[str] = []
            entry_prices: list[str] = []
        else:
            day_df = detail_df.loc[detail_df["as_of_date"] == as_of_date].reset_index(drop=True)
            symbols = day_df["symbol"].astype(str).tolist()
            entry_dates = day_df["entry_date"].fillna("").astype(str).tolist()
            entry_prices = [
                ""
                if pd.isna(value)
                else f"{float(value):.2f}"
                for value in day_df["entry_open"].tolist()
            ]
        summary_rows.append(
            {
                "as_of_date": as_of_date,
                "symbol_count": len(symbols),
                "symbols": symbols,
                "symbols_csv": ",".join(symbols),
                "entry_dates_csv": ",".join(entry_dates),
                "entry_prices_csv": ",".join(entry_prices),
            }
        )
    summary_df = pd.DataFrame(
        summary_rows,
        columns=[
            "as_of_date",
            "symbol_count",
            "symbols",
            "symbols_csv",
            "entry_dates_csv",
            "entry_prices_csv",
        ],
    )
    return ImpulseScanArtifacts(summary_df=summary_df, detail_df=detail_df)


__all__ = [
    "DEFAULT_IMPULSE_SCAN_META_PATH",
    "FINAL_TRIGGER_MODE",
    "FIRST_TRIGGER_MODE",
    "ImpulseScanArtifacts",
    "ImpulseScanCriteria",
    "build_impulse_scan_artifacts",
    "extend_valid_to_for_confirmation",
    "load_relaxed_impulse_scan_criteria",
]

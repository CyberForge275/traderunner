"""Strategy plugin adapter for ndx_momentum_rotation skeleton."""

from __future__ import annotations

import pandas as pd

from .artifacts import build_empty_debug_artifacts
from .config import build_ndx_momentum_rotation_config
from .intent_generation import generate_intent
from .regime import build_regime_filter
from .requirements import get_external_series_requirements
from .schema import get_signal_frame_schema
from .warnings import classify_validity


def _ensure_cross_sectional_bars(bars: pd.DataFrame) -> None:
    if "symbol" not in bars.columns:
        raise RuntimeError(
            "ndx_momentum_rotation requires multi-symbol bar frame with 'symbol' column. "
            "Pipeline currently appears to provide single-symbol bars. "
            "Implement a pre-aggregation bars-bundle mode before enabling this strategy."
        )
    symbols = bars["symbol"].astype(str)
    if symbols.nunique() < 2:
        raise RuntimeError(
            "ndx_momentum_rotation requires multi-symbol bars for cross-sectional ranking. "
            "Received <2 unique symbols."
        )


def extend_ndx_signal_frame(bars: pd.DataFrame, params: dict) -> pd.DataFrame:
    _ensure_cross_sectional_bars(bars)
    cfg = build_ndx_momentum_rotation_config(params)

    out = bars.copy().reset_index(drop=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    if out["timestamp"].isna().any():
        raise ValueError("ndx_momentum_rotation bars contain invalid timestamps")

    out["strategy_id"] = "ndx_momentum_rotation"
    out["strategy_version"] = str(params.get("strategy_version", "1.0.0"))
    out["strategy_tag"] = "nmr"
    out["timeframe"] = str(params.get("timeframe", "1D"))

    out["rebalance_month"] = out["timestamp"].dt.strftime("%Y-%m")
    out["signal_ts"] = out["timestamp"]
    # Skeleton placeholder for close->next open separation.
    out["exec_ts"] = out["timestamp"] + pd.Timedelta(days=1)
    if (out["signal_ts"] >= out["exec_ts"]).any():
        raise ValueError(
            "Potential lookahead / calendar bug: signal_ts must be strictly earlier than exec_ts"
        )

    regime_filter = build_regime_filter(cfg.regime_filter.value)
    regime_frame = regime_filter.evaluate(out)
    if len(regime_frame) != len(out):
        raise ValueError(
            "regime frame length mismatch in ndx_momentum_rotation skeleton"
        )
    out["regime_on"] = regime_frame["regime_on"].to_numpy()

    out["selection_rank"] = None
    out["score"] = None
    out["in_topk"] = None
    out["eligibility_reason"] = "SKELETON_NOT_IMPLEMENTED"

    validity = classify_validity(cfg.survivorship_mode.value)
    out["validity_class"] = validity.value

    _ = get_external_series_requirements(cfg.regime_filter.value)
    _ = build_empty_debug_artifacts(validity)

    return out


class NdxMomentumRotationPlugin:
    strategy_id = "ndx_momentum_rotation"

    @staticmethod
    def get_schema(version: str):
        return get_signal_frame_schema(version)

    @staticmethod
    def extend_signal_frame(bars, params: dict):
        return extend_ndx_signal_frame(bars, params)

    @staticmethod
    def generate_intent(signals_frame, strategy_id: str, strategy_version: str, params: dict):
        return generate_intent(signals_frame, strategy_id, strategy_version, params)

"""Signal frame schema for ndx_momentum_rotation skeleton."""

from __future__ import annotations

from axiom_bt.contracts.signal_frame_contract_v1 import ColumnSpec, SignalFrameSchemaV1


def get_signal_frame_schema(version: str) -> SignalFrameSchemaV1:
    if str(version) != "1.0.0":
        raise ValueError(
            f"Unknown ndx_momentum_rotation schema version {version!r}. Available: ['1.0.0']"
        )

    required_base = [
        ColumnSpec("timestamp", "datetime64[ns, UTC]", False, "base"),
        ColumnSpec("symbol", "string", False, "base"),
        ColumnSpec("open", "float64", False, "base"),
        ColumnSpec("high", "float64", False, "base"),
        ColumnSpec("low", "float64", False, "base"),
        ColumnSpec("close", "float64", False, "base"),
        ColumnSpec("volume", "float64", True, "base"),
    ]
    required_generic = [
        ColumnSpec("timeframe", "string", False, "generic"),
        ColumnSpec("strategy_id", "string", False, "generic"),
        ColumnSpec("strategy_version", "string", False, "generic"),
        ColumnSpec("strategy_tag", "string", False, "generic"),
    ]
    required_strategy = [
        ColumnSpec("rebalance_month", "string", True, "indicator"),
        ColumnSpec("signal_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("exec_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("regime_on", "bool", True, "indicator"),
        ColumnSpec("selection_rank", "float64", True, "indicator"),
        ColumnSpec("score", "float64", True, "indicator"),
        ColumnSpec("in_topk", "bool", True, "indicator"),
        ColumnSpec("eligibility_reason", "string", True, "indicator"),
        ColumnSpec("validity_class", "string", True, "indicator"),
    ]

    return SignalFrameSchemaV1(
        strategy_id="ndx_momentum_rotation",
        strategy_tag="nmr",
        version="1.0.0",
        required_base=required_base,
        required_generic=required_generic,
        required_strategy=required_strategy,
    )

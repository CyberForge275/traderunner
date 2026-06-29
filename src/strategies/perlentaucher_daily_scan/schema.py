"""Signal frame schema for perlentaucher_daily_scan skeleton."""

from __future__ import annotations

from axiom_bt.contracts.signal_frame_contract_v1 import ColumnSpec, SignalFrameSchemaV1


def get_signal_frame_schema(version: str) -> SignalFrameSchemaV1:
    if str(version) != "1.0.0":
        raise ValueError(
            "Unknown perlentaucher_daily_scan schema version "
            f"{version!r}. Available: ['1.0.0']"
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
        ColumnSpec("signal_ts", "datetime64[ns, UTC]", True, "indicator"),
        ColumnSpec("match_mode", "string", True, "indicator"),
        ColumnSpec("use_volume_prefilter", "bool", True, "indicator"),
        ColumnSpec("reference_set", "string", True, "indicator"),
        ColumnSpec("candidate_rank", "float64", True, "indicator"),
        ColumnSpec("eligibility_reason", "string", True, "indicator"),
        ColumnSpec("validity_class", "string", True, "indicator"),
        ColumnSpec("signal_side", "string", True, "signal"),
        ColumnSpec("signal_reason", "string", True, "signal"),
        ColumnSpec("entry_price", "float64", True, "signal"),
        ColumnSpec("stop_price", "float64", True, "signal"),
        ColumnSpec("take_profit_price", "float64", True, "signal"),
        ColumnSpec("template_id", "string", True, "signal"),
        ColumnSpec("oco_group_id", "string", True, "signal"),
    ]

    return SignalFrameSchemaV1(
        strategy_id="perlentaucher_daily_scan",
        strategy_tag="pts",
        version="1.0.0",
        required_base=required_base,
        required_generic=required_generic,
        required_strategy=required_strategy,
    )

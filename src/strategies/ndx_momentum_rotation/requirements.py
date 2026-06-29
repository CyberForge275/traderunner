"""External data requirements contract for ndx_momentum_rotation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalSeriesRequirement:
    name: str
    timeframe: str
    mandatory: bool
    note: str


def get_external_series_requirements(regime_filter: str) -> list[ExternalSeriesRequirement]:
    base = [
        ExternalSeriesRequirement(
            name="QQQ",
            timeframe="1D",
            mandatory=True,
            note="Required for qqq_sma200 regime filter",
        ),
        ExternalSeriesRequirement(
            name="SPY",
            timeframe="1D",
            mandatory=False,
            note="Needed when regime_filter=sp500_sma200",
        ),
    ]
    if regime_filter == "breadth_ema_cross":
        base.append(
            ExternalSeriesRequirement(
                name="BREADTH_CONSTITUENTS_200DMA",
                timeframe="1D",
                mandatory=True,
                note="TODO: breadth data pipeline is not implemented yet",
            )
        )
    return base

from __future__ import annotations


class MissingHistoricalDataError(Exception):
    """Raised when required historical bars are missing and backfill is required."""

    def __init__(
        self,
        *,
        symbol: str,
        requested_range: str,
        reason: str,
        hint: str,
    ) -> None:
        self.symbol = symbol
        self.requested_range = requested_range
        self.reason = reason
        self.hint = hint
        super().__init__(
            f"{reason} for symbol={symbol} range={requested_range}. {hint}"
        )


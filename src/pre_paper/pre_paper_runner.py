"""
Pre-Paper Runner (Orchestrator PoC)

Simple orchestrator demonstrating:
1. Load approved Backtest-Atom manifest (SSOT)
2. Calculate required history from manifest params
3. Check history status (ensure_history)
4. Execute strategy ONLY if SUFFICIENT

This is a PoC - production would add WebSocket integration,
signal handling, trade execution, etc.
"""

import logging
import json
from pathlib import Path
from typing import Optional
import pandas as pd

from pre_paper.runtime_history_loader import ensure_history
from pre_paper.history_status import HistoryStatus
from pre_paper.historical_provider import HistoricalProvider

logger = logging.getLogger(__name__)


class PrePaperRunner:
    """
    Pre-Paper runtime orchestrator (PoC).

    Demonstrates manifest SSOT contract + history gating.
    """

    def __init__(
        self,
        backtest_run_id: str,
        artifacts_root: Path = None,
        cache_db_path: Path = None,
        historical_provider: Optional[HistoricalProvider] = None
    ):
        """
        Args:
            backtest_run_id: Approved backtest run ID (e.g., "251215_144939_HOOD_15m_100d")
            artifacts_root: Artifacts root directory
            cache_db_path: Path to pre_paper_cache.db
            historical_provider: Provider for backfilling
        """
        if artifacts_root is None:
            artifacts_root = Path("artifacts")

        if cache_db_path is None:
            cache_db_path = artifacts_root / "pre_paper_cache" / "pre_paper_cache.db"

        self.backtest_run_id = backtest_run_id
        self.artifacts_root = Path(artifacts_root)
        self.cache_db_path = Path(cache_db_path)
        self.historical_provider = historical_provider

        # Load approved manifest (SSOT)
        self.manifest = self._load_manifest()

        # Extract config from manifest
        self.symbol = self.manifest["data"]["symbol"]
        self.base_tf = self.manifest["data"]["base_tf_used"]
        self.requested_tf = self.manifest["data"]["requested_tf"]
        self.params = self.manifest["params"]

        logger.info(f"Pre-Paper initialized: {self.symbol} {self.base_tf} (from run_id={backtest_run_id})")

    def _load_manifest(self) -> dict:
        """
        Load approved Backtest-Atom manifest (promotion contract).

        Returns:
            Manifest dict
        """
        manifest_path = (
            self.artifacts_root / "backtests" / self.backtest_run_id / "run_manifest.json"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found: {manifest_path}. "
                "Ensure backtest run completed successfully."
            )

        with open(manifest_path) as f:
            manifest = json.load(f)

        logger.info(f"Loaded manifest: {manifest_path}")

        return manifest

    def calculate_required_history(
        self,
        current_time: pd.Timestamp,
        safety_margin: int = 10
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        """
        Calculate required history window from manifest params.

        Args:
            current_time: Current time (market_tz)
            safety_margin: Extra bars for safety

        Returns:
            Tuple of (required_start_ts, required_end_ts)
        """
        # Extract lookback from params
        lookback_candles = self.params.get("lookback_candles", 50)
        max_pattern_age = self.params.get("max_pattern_age_candles", 5)

        # Total required bars
        required_bars = lookback_candles + max_pattern_age + safety_margin

        # Calculate bar duration
        tf_to_minutes = {
            "M1": 1,
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60
        }

        bar_minutes = tf_to_minutes.get(self.base_tf, 5)
        bar_duration = pd.Timedelta(minutes=bar_minutes)

        # Calculate required start
        required_start_ts = current_time - (required_bars * bar_duration)
        required_end_ts = current_time

        logger.info(
            f"Required history: {required_bars} bars ({lookback_candles} lookback + "
            f"{max_pattern_age} pattern age + {safety_margin} safety) = "
            f"{required_start_ts} → {required_end_ts}"
        )

        return (required_start_ts, required_end_ts)

    def check_history_status(
        self,
        current_time: pd.Timestamp,
        auto_backfill: bool = False
    ):
        """
        Check runtime history status.

        Args:
            current_time: Current time (market_tz)
            auto_backfill: Enable automatic backfill

        Returns:
            HistoryCheckResult
        """
        # Calculate required window
        required_start, required_end = self.calculate_required_history(current_time)

        # Check history
        result = ensure_history(
            symbol=self.symbol,
            tf=self.base_tf,
            base_tf_used=self.base_tf,
            required_start_ts=required_start,
            required_end_ts=required_end,
            cache_db_path=self.cache_db_path,
            historical_provider=self.historical_provider,
            auto_backfill=auto_backfill
        )

        return result

    def run_strategy_if_sufficient(
        self,
        current_time: pd.Timestamp,
        auto_backfill: bool = False
    ) -> dict:
        """
        Run strategy ONLY if history is SUFFICIENT.

        Otherwise: NO-SIGNALS with logged reason.

        Args:
            current_time: Current time
            auto_backfill: Enable backfill

        Returns:
            Dict with status and signals (or degradation reason)
        """
        # Check history
        history_result = self.check_history_status(current_time, auto_backfill)

        if history_result.status != HistoryStatus.SUFFICIENT:
            # NO-SIGNALS
            logger.warning(
                f"NO-SIGNALS: History {history_result.status.value} - {history_result.reason}"
            )

            return {
                "status": "no_signals",
                "reason": history_result.reason,
                "history_status": history_result.status.value,
                "signals": []
            }

        # History SUFFICIENT → run strategy
        logger.info(f"History SUFFICIENT - executing strategy for {self.symbol} {self.base_tf}")

        # TODO: Actual strategy execution
        # signals = self._execute_strategy(history_result)

        # PoC: Return placeholder
        return {
            "status": "executed",
            "reason": None,
            "history_status": "sufficient",
            "signals": []  # Would contain actual signals
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create runner from approved backtest atom
    runner = PrePaperRunner(
        backtest_run_id="251215_144939_HOOD_15m_100d",  # Example
        artifacts_root=Path("artifacts")
    )

    # Check history at current time
    current_time = pd.Timestamp.now(tz="America/New_York")

    result = runner.run_strategy_if_sufficient(
        current_time=current_time,
        auto_backfill=False
    )

    print(f"\nResult: {result['status']}")
    if result['reason']:
        print(f"Reason: {result['reason']}")

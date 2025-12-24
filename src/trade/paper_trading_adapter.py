"""
Paper Trading Adapter

Bridges traderunner signal generation with automatictrader-api for paper trading execution.
Transforms signals from CSV format → Order Intents via REST API with idempotency guarantees.
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("paper_trading_adapter")


class PaperTradingAdapter:
    """Adapter for sending traderunner signals to automatictrader-api"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        bearer_token: Optional[str] = None,
        timeout: int = 10
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        
        if bearer_token:
            self.headers["Authorization"] = f"Bearer {bearer_token}"
    
    def health_check(self) -> bool:
        """Check if automatictrader-api is reachable"""
        try:
            resp = requests.get(
                f"{self.api_url}/healthz",
                timeout=self.timeout
            )
            return resp.status_code == 200 and resp.json().get("ok") is True
        except Exception as e:
            log.error("Health check failed: %s", e)
            return False
    
    def send_signal_as_intent(self, signal_row: dict) -> dict:
        """
        Transform traderunner signal → automatictrader order intent
        
        Args:
            signal_row: Dictionary with keys: symbol, side, qty, order_type, price, etc.
        
        Returns:
            Response dict with status and details
        """
        # Generate deterministic idempotency key
        idem_key = self._generate_idempotency_key(signal_row)
        
        # Transform to automatictrader-api format
        intent = {
            "symbol": str(signal_row["symbol"]).upper(),
            "side": str(signal_row["side"]).upper(),  # BUY/SELL
            "quantity": int(signal_row["qty"]),
            "order_type": str(signal_row.get("order_type", "LMT")).upper(),
            "price": float(signal_row["price"]) if signal_row.get("price") else None,
            "client_tag": signal_row.get("source", "traderunner")
        }
        
        # Validate required fields
        if intent["order_type"] == "LMT" and intent["price"] is None:
            log.warning("LMT order without price for %s, skipping", intent["symbol"])
            return {"status": "skipped", "reason": "LMT without price"}
        
        headers = {**self.headers, "Idempotency-Key": idem_key}
        
        try:
            resp = requests.post(
                f"{self.api_url}/api/v1/orderintents",
                json=intent,
                headers=headers,
                timeout=self.timeout
            )
            
            if resp.status_code == 409:
                # Duplicate idempotency key - this is OK!
                log.info("Intent already exists (idempotent): %s", idem_key)
                return {"status": "duplicate", "idempotency_key": idem_key, "code": 409}
            
            resp.raise_for_status()
            result = resp.json()
            log.info(
                "Intent created: id=%s symbol=%s side=%s qty=%s",
                result.get("id"),
                intent["symbol"],
                intent["side"],
                intent["quantity"],
            )

            # Preserve a stable high-level status flag for callers while
            # still exposing the API's own status field separately.
            payload = {
                "status": "created",
                "intent_status": result.get("status"),
            }
            for key, value in result.items():
                if key == "status":
                    continue
                payload[key] = value
            return payload
        
        except requests.RequestException as e:
            log.error("Failed to send intent for %s: %s", intent["symbol"], e)
            return {"status": "error", "error": str(e)}
    
    def send_signals_from_csv(self, csv_path: Path) -> dict:
        """
        Read signals CSV and send all as order intents
        
        Returns:
            Summary dict with counts
        """
        if not csv_path.exists():
            log.error("Signals file not found: %s", csv_path)
            return {"error": "file_not_found"}
        
        df = pd.read_csv(csv_path)
        
        if df.empty:
            log.info("No signals in %s", csv_path)
            return {"total": 0, "created": 0, "duplicates": 0, "errors": 0, "skipped": 0}
        
        # Ensure required columns exist
        required = ["symbol", "side", "qty"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            log.error("Missing required columns: %s", missing)
            return {"error": f"missing_columns: {missing}"}
        
        results = {
            "total": len(df),
            "created": 0,
            "duplicates": 0,
            "errors": 0,
            "skipped": 0
        }
        
        for idx, row in df.iterrows():
            signal = row.to_dict()
            result = self.send_signal_as_intent(signal)
            
            status = result.get("status")
            if status == "created":
                results["created"] += 1
            elif status == "duplicate":
                results["duplicates"] += 1
            elif status == "skipped":
                results["skipped"] += 1
            else:
                results["errors"] += 1
        
        return results
    
    def _generate_idempotency_key(self, signal: dict) -> str:
        """
        Generate deterministic UUID from signal attributes
        
        Key components:
        - symbol
        - side (BUY/SELL)
        - timestamp (if available)
        - source tag
        
        This ensures the same signal generates the same key for idempotency.
        """
        components = [
            str(signal.get("symbol", "")).upper(),
            str(signal.get("side", "")).upper(),
            str(signal.get("timestamp", "")),
            str(signal.get("source", "traderunner")),
            str(signal.get("order_type", "LMT"))
        ]
        
        key_str = "|".join(components)
        # Use UUID5 (deterministic based on string)
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, key_str))


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser"""
    parser = argparse.ArgumentParser(
        description="Send traderunner signals to automatictrader-api as order intents"
    )
    
    parser.add_argument(
        "--signals",
        type=Path,
        required=True,
        help="Path to signals CSV file"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8080",
        help="automatictrader-api URL (default: http://localhost:8080)"
    )
    
    parser.add_argument(
        "--bearer-token",
        help="Optional bearer token for API authentication"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)"
    )
    
    parser.add_argument(
        "--health-check-only",
        action="store_true",
        help="Only check API health, don't send signals"
    )
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point"""
    parser = build_parser()
    args = parser.parse_args(argv)
    
    adapter = PaperTradingAdapter(
        api_url=args.api_url,
        bearer_token=args.bearer_token,
        timeout=args.timeout
    )
    
    # Health check
    if not adapter.health_check():
        log.error("automatictrader-api is not reachable at %s", args.api_url)
        log.error("Ensure the service is running: cd automatictrader-api && bash scripts/run_dev.sh")
        return 1
    
    log.info("✓ API health check passed")
    
    if args.health_check_only:
        return 0
    
    # Send signals
    log.info("Reading signals from %s", args.signals)
    results = adapter.send_signals_from_csv(args.signals)
    
    if "error" in results:
        log.error("Failed to process signals: %s", results["error"])
        return 1
    
    log.info("=" * 60)
    log.info("SUMMARY:")
    log.info("  Total signals:     %d", results["total"])
    log.info("  Created intents:   %d", results["created"])
    log.info("  Duplicates:        %d", results["duplicates"])
    log.info("  Skipped:           %d", results["skipped"])
    log.info("  Errors:            %d", results["errors"])
    log.info("=" * 60)
    
    if results["errors"] > 0:
        log.warning("Some signals failed to send, check logs above")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

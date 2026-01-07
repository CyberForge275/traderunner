"""
PrePaper Plan Writer

Writes deterministic plan.json with:
- Stable sorting (ts, symbol, side, idempotency_key)
- Canonical JSON (sort_keys, stable separators)
- Schema versioning
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class PlanWriter:
    """
    Deterministic plan.json writer for PrePaper.
    
    Guarantees:
    - Same inputs → same bytes (for fixed run_id)
    - Stable sort order
    - Canonical JSON serialization
    """
    
    SCHEMA_VERSION = "1.0.0"
    
    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: Directory to write plan.json (artifacts/prepaper/<run_id>/)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plan_path = self.output_dir / "plan.json"
    
    def write_plan(self, orders: List[Dict[str, Any]]) -> str:
        """
        Write plan.json with deterministic ordering.
        
        Args:
            orders: List of order dicts (must have ts, symbol, side, idempotency_key)
        
        Returns:
            SHA256 hash of written plan (for plan_hash in manifest)
        """
        # Stable sort: (ts, symbol, side, idempotency_key)
        sorted_orders = sorted(
            orders,
            key=lambda o: (
                o.get("ts", ""),
                o.get("symbol", ""),
                o.get("side", ""),
                o.get("idempotency_key", "")
            )
        )
        
        # Canonical structure
        plan = {
            "schema_version": self.SCHEMA_VERSION,
            "orders": sorted_orders
        }
        
        # Canonical JSON: sort_keys, stable separators
        plan_json = json.dumps(
            plan,
            indent=2,
            sort_keys=True,
            separators=(",", ": ")  # Stable separators
        )
        
        # Write to file
        self.plan_path.write_text(plan_json, encoding="utf-8")
        
        # Compute hash over bytes (for determinism proof)
        plan_hash = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
        
        return plan_hash
    
    def read_plan(self) -> Dict[str, Any]:
        """
        Read plan.json.
        
        Returns:
            Plan dict with schema_version + orders
        """
        if not self.plan_path.exists():
            raise FileNotFoundError(f"Plan not found: {self.plan_path}")
        
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

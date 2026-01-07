"""
PrePaper Manifest Writer

Writes run_manifest.json with:
- backtest_manifest_hash
- marketdata_data_hash (from DataProvenance)
- plan_hash
- signals_count (from run-scoped query)
- lab, run_id, mode, source_backtest_run_id
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class ManifestWriter:
    """
    Writes run_manifest.json for PrePaper runs.
    
    Adapts backtest ManifestWriter pattern for PrePaper.
    """
    
    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: Directory to write run_manifest.json (artifacts/prepaper/<run_id>/)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "run_manifest.json"
    
    def write_manifest(
        self,
        run_id: str,
        lab: str,
        mode: str,
        source_backtest_run_id: str,
        backtest_manifest: Dict[str, Any],
        marketdata_data_hash: str,
        plan_hash: str,
        signals_count: int,
        strategy: Dict[str, Any],
        params: Dict[str, Any],
        data: Dict[str, Any],
        git_commit: Optional[str] = None
    ):
        """
        Write run_manifest.json with all hashes and metadata.
        
        Args:
            run_id: PrePaper run ID
            lab: "PREPAPER"
            mode: "replay" or "live"
            source_backtest_run_id: Backtest run this PrePaper run is based on
            backtest_manifest: Full backtest manifest dict
            marketdata_data_hash: DataProvenance.data_hash from marketdata_service
            plan_hash: SHA256 hash of plan.json bytes
            signals_count: Number of signals written (from query)
            strategy: Strategy metadata from backtest
            params: Strategy params from backtest
            data: Data metadata (symbol, tf, etc.)
            git_commit: Optional git commit hash
        """
        # Compute backtest_manifest_hash
        backtest_manifest_json = json.dumps(backtest_manifest, sort_keys=True)
        backtest_manifest_hash = hashlib.sha256(
            backtest_manifest_json.encode("utf-8")
        ).hexdigest()
        
        # Build manifest
        manifest = {
            "identity": {
                "run_id": run_id,
                "lab": lab,
                "mode": mode,
                "source_backtest_run_id": source_backtest_run_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "git_commit": git_commit or "unknown"
            },
            "strategy": strategy,  # Immutable from backtest
            "params": params,      # Immutable from backtest
            "data": data,
            "inputs": {
                "backtest_manifest_hash": backtest_manifest_hash,
                "marketdata_data_hash": marketdata_data_hash,
                "git_commit": git_commit or "unknown"
            },
            "outputs": {
                "plan_hash": plan_hash,
                "signals_count": signals_count
            },
            "result": {
                "status": "SUCCESS",  # Can be DEGRADED, FAILED, etc.
                "errors": []
            }
        }
        
        # Write (diff-friendly: sort_keys, indent)
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True, separators=(",", ": "))
        
        return manifest
    
    def read_manifest(self) -> Dict[str, Any]:
        """
        Read run_manifest.json.
        
        Returns:
            Manifest dict
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

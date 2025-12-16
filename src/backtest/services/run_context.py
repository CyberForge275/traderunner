"""
RunContext DTO - Single Source of Truth for Run Identity

This module provides a frozen dataclass that encapsulates run identity.
After create_run_dir(), all code must use RunContext.run_dir as SSOT
(no manager.run_dir or current_run_dir access allowed).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunContext:
    """
    Immutable context for a backtest run.
    
    This is the SSOT for run identity after directory creation.
    All filesystem operations must use ctx.run_dir, never derive paths
    from run_id or run_name.
    
    Attributes:
        run_id: Unique identifier (e.g., "251216_231420_TEST1_bug1")
        run_name: Human-readable name (same as run_id in current impl)
        run_dir: Absolute path to artifacts directory (SSOT)
    """
    run_id: str
    run_name: str
    run_dir: Path
    
    def __post_init__(self):
        """Validate that run_dir is absolute and exists."""
        if not isinstance(self.run_dir, Path):
            object.__setattr__(self, 'run_dir', Path(self.run_dir))
        
        if not self.run_dir.is_absolute():
            raise ValueError(f"run_dir must be absolute path, got: {self.run_dir}")
        
        if not self.run_dir.exists():
            raise ValueError(f"run_dir must exist, got: {self.run_dir}")

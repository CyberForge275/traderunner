"""
Strategy Lifecycle Metadata Repository
========================================

Manages strategy_version and strategy_run tables for tracking strategy
lifecycle through Factory Labs (Explore → Backtest → Pre-Papertrade → Paper → Live).

This implements the metadata layer defined in FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md:
- Immutable Strategy Versions after Backtest Lab
- Traceability across all Labs
- No anonymous strategies in higher Labs
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import IntEnum


# =====  Enums matching FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md =====

class LifecycleStage(IntEnum):
    """Strategy version lifecycle stages."""
    DRAFT_EXPLORE = 0          # Explore Lab - mutable
    BACKTEST_APPROVED = 1      # Approved in Backtest Lab - IMMUTABLE from here
    PRE_PAPERTRADE_DONE = 2    # Passed Pre-PaperTrade Lab
    PAPER_DONE = 3             # Passed Paper Trading Lab
    LIVE = 4                   # Running in Live Trading
    RETIRED = 5                # No longer used


class LabStage(IntEnum):
    """Lab stages where strategies execute."""
    BACKTEST = 0
    PRE_PAPERTRADE = 1
    PAPER = 2
    LIVE = 3


# ===== Dataclasses =====

@dataclass
class StrategyVersion:
    """
    Represents an immutable Strategy Version.
    
    Uniquely identified by: (strategy_key, impl_version, profile_key, profile_version)
    """
    id: Optional[int]
    strategy_key: str
    impl_version: int
    profile_key: str
    profile_version: int
    label: str
    lifecycle_stage: LifecycleStage
    code_ref_type: str
    code_ref_value: str
    config_hash: str
    config_json: str
    universe_key: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class StrategyRun:
    """Represents a single execution of a Strategy Version in a specific Lab."""
    id: Optional[int]
    strategy_version_id: int
    lab_stage: LabStage
    environment: str
    run_type: str
    external_run_id: Optional[str]
    started_at: str
    ended_at: Optional[str]
    status: str  # 'running', 'completed', 'failed', 'aborted'
    error_message: Optional[str]
    metrics_json: Optional[str]
    tags: Optional[str]


# ===== SQL DDL =====

STRATEGY_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS strategy_version (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_key      TEXT    NOT NULL,
    impl_version      INTEGER NOT NULL,
    profile_key       TEXT    NOT NULL DEFAULT 'default',
    profile_version   INTEGER NOT NULL DEFAULT 1,
    label             TEXT    NOT NULL,
    lifecycle_stage   INTEGER NOT NULL DEFAULT 0,
    code_ref_type     TEXT    NOT NULL DEFAULT 'git',
    code_ref_value    TEXT    NOT NULL,
    config_hash       TEXT    NOT NULL,
    config_json       TEXT    NOT NULL,
    universe_key      TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(strategy_key, impl_version, profile_key, profile_version)
)
"""

STRATEGY_VERSION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_strategy_key ON strategy_version(strategy_key)",
    "CREATE INDEX IF NOT EXISTS idx_lifecycle_stage ON strategy_version(lifecycle_stage)",
]

STRATEGY_RUN_DDL = """
CREATE TABLE IF NOT EXISTS strategy_run (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_version_id INTEGER NOT NULL,
    lab_stage           INTEGER NOT NULL,
    environment         TEXT    NOT NULL DEFAULT 'prod',
    run_type            TEXT    NOT NULL,
    external_run_id     TEXT,
    started_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    ended_at            TEXT,
    status              TEXT    NOT NULL DEFAULT 'running',
    error_message       TEXT,
    metrics_json        TEXT,
    tags                TEXT,
    
    FOREIGN KEY(strategy_version_id) REFERENCES strategy_version(id)
)
"""

STRATEGY_RUN_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sv_id ON strategy_run(strategy_version_id)",
    "CREATE INDEX IF NOT EXISTS idx_lab_stage ON strategy_run(lab_stage)",
    "CREATE INDEX IF NOT EXISTS idx_status ON strategy_run(status)",
    "CREATE INDEX IF NOT EXISTS idx_environment ON strategy_run(environment)",
]


# ===== Repository =====

class StrategyMetadataRepository:
    """
    Repository for Strategy Lifecycle metadata.
    
    Provides CRUD operations for strategy_version and strategy_run tables.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database (typically signals.db)
        """
        self.db_path = Path(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def initialize_schema(self):
        """
        Create tables and indexes if they don't exist.
        
        This is idempotent and safe to call multiple times.
        """
        conn = self._get_connection()
        try:
            # Create tables
            conn.execute(STRATEGY_VERSION_DDL)
            conn.execute(STRATEGY_RUN_DDL)
            
            # Create indexes
            for index_ddl in STRATEGY_VERSION_INDEXES:
                conn.execute(index_ddl)
            for index_ddl in STRATEGY_RUN_INDEXES:
                conn.execute(index_ddl)
            
            conn.commit()
        finally:
            conn.close()
    
    # ===== StrategyVersion CRUD =====
    
    def create_strategy_version(
        self,
        strategy_key: str,
        impl_version: int,
        label: str,
        code_ref_value: str,
        config_json: dict,
        profile_key: str = "default",
        profile_version: int = 1,
        lifecycle_stage: LifecycleStage = LifecycleStage.DRAFT_EXPLORE,
        code_ref_type: str = "git",
        universe_key: Optional[str] = None,
    ) -> int:
        """
        Create a new Strategy Version.
        
        Args:
            strategy_key: Strategy identifier (e.g., 'insidebar_intraday')
            impl_version: Implementation version number
            label: Human-readable label
            code_ref_value: Git commit hash or version tag
            config_json: Strategy configuration as dictionary
            profile_key: Configuration profile name
            profile_version: Configuration profile version
            lifecycle_stage: Current lifecycle stage
            code_ref_type: Type of code reference ('git', 'tag', etc.)
            universe_key: Optional universe identifier
            
        Returns:
            strategy_version_id (primary key)
            
        Raises:
            sqlite3.IntegrityError: If (strategy_key, impl_version, profile_key, profile_version) already exists
        """
        config_json_str = json.dumps(config_json, sort_keys=True)
        config_hash = self._calculate_config_hash(config_json_str)
        
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO strategy_version (
                    strategy_key, impl_version, profile_key, profile_version,
                    label, lifecycle_stage, code_ref_type, code_ref_value,
                    config_hash, config_json, universe_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_key, impl_version, profile_key, profile_version,
                label, lifecycle_stage.value, code_ref_type, code_ref_value,
                config_hash, config_json_str, universe_key
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_strategy_version_by_id(self, version_id: int) -> Optional[StrategyVersion]:
        """
        Get Strategy Version by primary key.
        
        Args:
            version_id: Primary key
            
        Returns:
            StrategyVersion or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM strategy_version WHERE id = ?",
                (version_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_strategy_version(row)
            return None
        finally:
            conn.close()
    
    def find_strategy_version(
        self,
        strategy_key: str,
        impl_version: int,
        profile_key: str = "default",
        profile_version: int = 1,
    ) -> Optional[StrategyVersion]:
        """
        Find Strategy Version by unique identifier.
        
        Args:
            strategy_key: Strategy identifier
            impl_version: Implementation version
            profile_key: Configuration profile name
            profile_version: Configuration profile version
            
        Returns:
            StrategyVersion or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM strategy_version 
                WHERE strategy_key = ? 
                  AND impl_version = ?
                  AND profile_key = ?
                  AND profile_version = ?
            """, (strategy_key, impl_version, profile_key, profile_version))
            row = cursor.fetchone()
            if row:
                return self._row_to_strategy_version(row)
            return None
        finally:
            conn.close()
    
    def update_lifecycle_stage(
        self,
        version_id: int,
        new_stage: LifecycleStage
    ):
        """
        Update lifecycle stage of a Strategy Version.
        
        Args:
            version_id: Strategy version primary key
            new_stage: New lifecycle stage
            
        Note: This should only progress forward (Explore → Backtest → ... → Live)
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE strategy_version 
                SET lifecycle_stage = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (new_stage.value, version_id))
            conn.commit()
        finally:
            conn.close()
    
    # ===== StrategyRun CRUD =====
    
    def create_strategy_run(
        self,
        strategy_version_id: int,
        lab_stage: LabStage,
        run_type: str,
        environment: str = "prod",
        external_run_id: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> int:
        """
        Create a new Strategy Run.
        
        Args:
            strategy_version_id: Foreign key to strategy_version
            lab_stage: Lab where this run executes
            run_type: Type of run ('batch_backtest', 'replay', 'paper_session', etc.)
            environment: Environment name ('prod', 'dev', 'test')
            external_run_id: Optional external identifier (e.g., backtest run ID)
            tags: Optional JSON string with run tags
            
        Returns:
            strategy_run_id (primary key)
            
        Raises:
            sqlite3.IntegrityError: If strategy_version_id doesn't exist (FK constraint)
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO strategy_run (
                    strategy_version_id, lab_stage, environment, run_type,
                    external_run_id, tags
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                strategy_version_id, lab_stage.value, environment, run_type,
                external_run_id, tags
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def update_strategy_run_status(
        self,
        run_id: int,
        status: str,
        ended_at: Optional[str] = None,
        error_message: Optional[str] = None,
        metrics_json: Optional[dict] = None,
    ):
        """
        Update Strategy Run status and completion information.
        
        Args:
            run_id: Strategy run primary key
            status: New status ('running', 'completed', 'failed', 'aborted')
            ended_at: Optional completion timestamp (defaults to now if status is terminal)
            error_message: Optional error message if failed
            metrics_json: Optional metrics dictionary
        """
        if ended_at is None and status in ('completed', 'failed', 'aborted'):
            ended_at = datetime.now().isoformat()
        
        metrics_str = json.dumps(metrics_json) if metrics_json else None
        
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE strategy_run 
                SET status = ?, ended_at = ?, error_message = ?, metrics_json = ?
                WHERE id = ?
            """, (status, ended_at, error_message, metrics_str, run_id))
            conn.commit()
        finally:
            conn.close()
    
    def get_runs_for_strategy_version(
        self,
        version_id: int,
        lab_stage: Optional[LabStage] = None
    ) -> List[StrategyRun]:
        """
        Get all runs for a Strategy Version, optionally filtered by lab stage.
        
        Args:
            version_id: Strategy version primary key
            lab_stage: Optional filter by lab stage
            
        Returns:
            List of StrategyRun objects
        """
        conn = self._get_connection()
        try:
            if lab_stage is not None:
                cursor = conn.execute("""
                    SELECT * FROM strategy_run 
                    WHERE strategy_version_id = ? AND lab_stage = ?
                    ORDER BY started_at DESC
                """, (version_id, lab_stage.value))
            else:
                cursor = conn.execute("""
                    SELECT * FROM strategy_run 
                    WHERE strategy_version_id = ?
                    ORDER BY started_at DESC
                """, (version_id,))
            
            rows = cursor.fetchall()
            return [self._row_to_strategy_run(row) for row in rows]
        finally:
            conn.close()
    
    # ===== Helper Methods =====
    
    def _calculate_config_hash(self, config_json_str: str) -> str:
        """Calculate SHA256 hash of configuration JSON (first 16 chars)."""
        import hashlib
        return hashlib.sha256(config_json_str.encode()).hexdigest()[:16]
    
    def _row_to_strategy_version(self, row: tuple) -> StrategyVersion:
        """Convert database row to StrategyVersion dataclass."""
        return StrategyVersion(
            id=row[0],
            strategy_key=row[1],
            impl_version=row[2],
            profile_key=row[3],
            profile_version=row[4],
            label=row[5],
            lifecycle_stage=LifecycleStage(row[6]),
            code_ref_type=row[7],
            code_ref_value=row[8],
            config_hash=row[9],
            config_json=row[10],
            universe_key=row[11],
            created_at=row[12],
            updated_at=row[13],
        )
    
    def _row_to_strategy_run(self, row: tuple) -> StrategyRun:
        """Convert database row to StrategyRun dataclass."""
        return StrategyRun(
            id=row[0],
            strategy_version_id=row[1],
            lab_stage=LabStage(row[2]),
            environment=row[3],
            run_type=row[4],
            external_run_id=row[5],
            started_at=row[6],
            ended_at=row[7],
            status=row[8],
            error_message=row[9],
            metrics_json=row[10],
            tags=row[11],
        )


# ===== Convenience Functions =====

def get_repository(db_path: Optional[Path] = None) -> StrategyMetadataRepository:
    """
    Get repository instance using default database path from Settings.
    
    Args:
        db_path: Optional explicit database path (defaults to signals.db from Settings)
        
    Returns:
        StrategyMetadataRepository instance
    """
    if db_path is None:
        from src.core.settings import get_settings
        settings = get_settings()
        db_path = settings.signals_db_path
    
    repo = StrategyMetadataRepository(db_path)
    repo.initialize_schema()  # Ensure tables exist
    return repo

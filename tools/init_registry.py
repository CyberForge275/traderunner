#!/usr/bin/env python3
"""
Strategy Version Registry Database Initializer

Creates and manages the SQLite registry for versioned strategy configurations.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib
import yaml


def create_registry(strategy_dir: Path) -> Path:
    """Create registry database with schema."""
    db_path = strategy_dir / "registry.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Versions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS versions (
            version TEXT PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            config_hash TEXT NOT NULL,
            config_path TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            lab_stage TEXT,
            notes TEXT,
            created_by TEXT
        )
    """)
    
    # Backtest runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            run_id TEXT PRIMARY KEY,
            version TEXT REFERENCES versions(version),
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            config_snapshot TEXT NOT NULL,
            data_start_date TEXT,
            data_end_date TEXT,
            symbols TEXT,
            total_trades INTEGER,
            win_rate REAL,
            profit_factor REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            total_return_pct REAL,
            run_metadata TEXT,
            result_path TEXT
        )
    """)
    
    # Version history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_version TEXT,
            to_version TEXT NOT NULL REFERENCES versions(version),
            change_type TEXT NOT NULL,
            changed_params TEXT NOT NULL,
            change_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        )
    """)
    
    # Deployments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT REFERENCES versions(version),
            lab_stage TEXT NOT NULL,
            deployed_at TIMESTAMP NOT NULL,
            deployed_by TEXT,
            config_hash TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            notes TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    return db_path


def calculate_config_hash(config_path: Path) -> str:
    """Calculate SHA256 hash of config file."""
    with open(config_path, 'r') as f:
        content = f.read()
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def register_version(
    db_path: Path,
    version: str,
    config_path: Path,
    status: str = "production",
    lab_stage: str = None,
    notes: str = None,
    created_by: str = "system"
):
    """Register a version in the database."""
    config_hash = calculate_config_hash(config_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO versions 
        (version, created_at, config_hash, config_path, status, lab_stage, notes, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        version,
        datetime.now().isoformat(),
        config_hash,
        str(config_path),
        status,
        lab_stage,
        notes,
        created_by
    ))
    
    conn.commit()
    conn.close()
    
    return config_hash


if __name__ == "__main__":
    # Initialize for InsideBar strategy
    strategy_dir = Path(__file__).parent.parent / "src" / "strategies" / "inside_bar"
    
    print(f"Creating registry for: {strategy_dir}")
    db_path = create_registry(strategy_dir)
    print(f"✅ Registry created: {db_path}")
    
    # Register v1.00
    v100_path = strategy_dir / "versions" / "v1.00.yaml"
    if v100_path.exists():
        config_hash = register_version(
            db_path,
            version="1.00",
            config_path=v100_path,
            status="production",
            lab_stage="pre-papertrading",
            notes="Initial version from production config",
            created_by="mirko"
        )
        print(f"✅ Registered v1.00 (hash: {config_hash})")
    else:
        print(f"⚠️  v1.00.yaml not found at {v100_path}")

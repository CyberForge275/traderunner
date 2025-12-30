#!/usr/bin/env python3
"""
Initialize Strategy Lifecycle Metadata Tables
==============================================

This script creates the strategy_version and strategy_run tables
in the signals database if they don't already exist.

Run this once to set up the schema:
    python scripts/init_strategy_metadata.py

The script is idempotent - safe to run multiple times.
"""

import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from src.core.settings import get_settings
from trading_dashboard.repositories.strategy_metadata import get_repository


def main():
    """Initialize strategy metadata schema in signals database."""
    print("=" * 60)
    print("Strategy Lifecycle Metadata Tables - Schema Initialization")
    print("=" * 60)

    # Get database path from Settings
    settings = get_settings()
    db_path = settings.signals_db_path

    print(f"\nDatabase: {db_path}")

    if not db_path.exists():
        print(f"\n⚠️  Database does not exist yet: {db_path}")
        print("   It will be created when first accessed.")

    # Initialize schema
    print("\n📋 Creating tables and indexes...")
    repo = get_repository(db_path)

    print("   ✅ strategy_version table")
    print("   ✅ strategy_run table")
    print("   ✅ Indexes created")
    print("   ✅ Foreign key constraints enabled")

    print("\n" + "=" * 60)
    print("✅ Schema initialization complete!")
    print("=" * 60)
    print("\nYou can now use the Strategy Metadata Repository:")
    print("\n  from trading_dashboard.repositories.strategy_metadata import get_repository")
    print("  repo = get_repository()")
    print("  version_id = repo.create_strategy_version(...)")
    print("\nSee tests/test_strategy_metadata.py for usage examples.")
    print("")


if __name__ == "__main__":
    main()

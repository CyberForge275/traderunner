#!/usr/bin/env python3
"""
Bootstrap Script: InsideBar Intraday Strategy Version
======================================================

Creates the initial stable strategy version for InsideBar Intraday strategy.

This script implements manual gating: the user runs it explicitly on each
environment (dev, int, prod) to create the InsideBar v1.00 strategy version
with BACKTEST_APPROVED lifecycle stage.

Per FACTORY_LABS_AND_STRATEGY_LIFECYCLE_v2.md:
- impl_version = 1 (stable, not beta)
- lifecycle_stage = BACKTEST_APPROVED
- profile_key = "insidebar_intraday"
- profile_version = 1

Usage:
    # On any host (dev, int, prod):
    cd /path/to/traderunner
    source .venv/bin/activate
    PYTHONPATH=src python scripts/bootstrap_insidebar_strategy_version.py
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add src to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SRC = ROOT / "src"
DASHBOARD = ROOT / "trading_dashboard"

# Add both src and parent directory to path
for path_dir in [str(SRC), str(ROOT)]:
    if path_dir not in sys.path:
        sys.path.insert(0, path_dir)

# Now we can import from src and trading_dashboard
from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    get_repository,
)
from strategies.profiles.inside_bar import INSIDE_BAR_V1_PROFILE


def get_git_commit() -> str:
    """Get current Git commit hash (short form)."""
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=ROOT,
            stderr=subprocess.STDOUT
        ).decode().strip()
        return commit
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Could not determine Git commit: {e}")
        print(f"   Using fallback: 'unknown'")
        return "unknown"


def get_config_from_profile() -> dict:
    """
    Extract configuration from INSIDE_BAR_V1_PROFILE.
    
    Returns:
        Dictionary with strategy configuration parameters
    """
    # Use default_parameters from the profile
    config = INSIDE_BAR_V1_PROFILE.default_parameters.copy()
    
    # Add any additional metadata
    config['_profile_source'] = 'INSIDE_BAR_V1_PROFILE'
    config['_strategy_id'] = INSIDE_BAR_V1_PROFILE.strategy_id
    config['_version'] = INSIDE_BAR_V1_PROFILE.version
    
    return config


def main():
    """Bootstrap InsideBar Intraday strategy version."""
    
    print("=" * 70)
    print("InsideBar Intraday Strategy Version Bootstrap")
    print("=" * 70)
    print()
    
    # Step 1: Get Git commit
    print("📋 Step 1: Getting Git commit reference...")
    git_commit = get_git_commit()
    print(f"   Git commit: {git_commit}")
    print()
    
    # Step 2: Load configuration
    print("📋 Step 2: Loading InsideBar V1 configuration...")
    config_dict = get_config_from_profile()
    print(f"   Config parameters: {len(config_dict)} keys")
    print(f"   Sample: atr_period={config_dict.get('atr_period')}, "
          f"risk_reward_ratio={config_dict.get('risk_reward_ratio')}")
    print()
    
    # Step 3: Get repository (uses Settings for DB path)
    print("📋 Step 3: Connecting to strategy metadata repository...")
    repo = get_repository()  # Uses Settings.signals_db_path
    print(f"   Database: {repo.db_path}")
    print()
    
    # Step 4: Define strategy version parameters
    print("📋 Step 4: Strategy version parameters...")
    strategy_key = "insidebar_intraday"
    impl_version = 1
    profile_key = "insidebar_intraday"  # CRITICAL: NOT "default"!
    profile_version = 1
    label = "InsideBar v1.00 – Initial Stable"
    lifecycle_stage = LifecycleStage.BACKTEST_APPROVED
    
    print(f"   strategy_key:     {strategy_key}")
    print(f"   impl_version:     {impl_version}")
    print(f"   profile_key:      {profile_key}")
    print(f"   profile_version:  {profile_version}")
    print(f"   label:            {label}")
    print(f"   lifecycle_stage:  {lifecycle_stage.name}")
    print()
    
    # Step 5: Check if version already exists
    print("📋 Step 5: Checking for existing strategy version...")
    existing_version = repo.find_strategy_version(
        strategy_key=strategy_key,
        impl_version=impl_version,
        profile_key=profile_key,
        profile_version=profile_version
    )
    
    if existing_version:
        print(f"✅ Strategy version ALREADY EXISTS:")
        print(f"   ID:                {existing_version.id}")
        print(f"   Label:             {existing_version.label}")
        print(f"   Lifecycle Stage:   {existing_version.lifecycle_stage.name}")
        print(f"   Code Ref:          {existing_version.code_ref_value}")
        print(f"   Config Hash:       {existing_version.config_hash}")
        print(f"   Created:           {existing_version.created_at}")
        print()
        print("ℹ️  No action needed - using existing version.")
        print("=" * 70)
        return 0
    
    # Step 6: Create new strategy version
    print("🆕 Strategy version does NOT exist - creating new version...")
    print()
    
    try:
        version_id = repo.create_strategy_version(
            strategy_key=strategy_key,
            impl_version=impl_version,
            label=label,
            code_ref_value=git_commit,
            config_json=config_dict,
            profile_key=profile_key,
            profile_version=profile_version,
            lifecycle_stage=lifecycle_stage,
            code_ref_type="git",
            universe_key=None  # InsideBar doesn't use universe
        )
        
        print(f"✅ SUCCESS! Strategy version created:")
        print(f"   ID:                {version_id}")
        print(f"   strategy_key:      {strategy_key}")
        print(f"   impl_version:      {impl_version}")
        print(f"   profile_key:       {profile_key}")
        print(f"   profile_version:   {profile_version}")
        print(f"   label:             {label}")
        print(f"   lifecycle_stage:   {lifecycle_stage.name}")
        print(f"   code_ref_value:    {git_commit}")
        print()
        
        # Verify by reading it back
        created_version = repo.get_strategy_version_by_id(version_id)
        if created_version:
            print("✅ Verification: Version successfully persisted to database")
            print(f"   Config Hash:       {created_version.config_hash}")
            print(f"   Created At:        {created_version.created_at}")
        
        print()
        print("=" * 70)
        print("🎉 Bootstrap complete!")
        print()
        print("Next steps:")
        print("  1. This version can now be used in Pre-PaperTrading")
        print("  2. Run tests: PYTHONPATH=src pytest tests/test_lifecycle_integration.py")
        print("  3. Deploy to other environments (int, prod) and run this script there")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"❌ ERROR creating strategy version:")
        print(f"   {type(e).__name__}: {e}")
        print()
        print("Please check:")
        print("  - Database permissions")
        print("  - UNIQUE constraint not violated")
        print("  - Repository schema is initialized")
        import traceback
        print()
        print("Full traceback:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
Strategy Version Resolution Helpers
====================================

Helper functions to resolve strategy versions for lifecycle-tracked labs.

Per FACTORY_LABS_AND_STRATEGY_LIFECYCLE_v2.md:
- Pre-PaperTrading requires impl_version >= 1
- Pre-PaperTrading requires lifecycle_stage >= BACKTEST_APPROVED
"""

from typing import Optional
from trading_dashboard.repositories.strategy_metadata import (
    get_repository,
    LifecycleStage,
    StrategyVersion,
)


def resolve_pre_paper_version(strategy_key: str) -> StrategyVersion:
    """
    Resolve a valid strategy version for Pre-PaperTrading Lab.

    Selection Criteria:
    - impl_version >= 1 (no beta versions)
    - lifecycle_stage >= BACKTEST_APPROVED
    - Prefers highest impl_version

    Args:
        strategy_key: Strategy identifier (e.g., "insidebar_intraday")

    Returns:
        StrategyVersion object

    Raises:
        ValueError: If no valid version exists, with actionable error message
    """
    repo = get_repository()

    # Query all versions for this strategy
    conn = repo._get_connection()
    cursor = conn.execute("""
        SELECT id
        FROM strategy_version
        WHERE strategy_key = ?
        ORDER BY impl_version DESC, id DESC
    """, (strategy_key,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError(
            f"❌ No strategy versions found for '{strategy_key}'.\n"
            f"\n"
            f"Please run bootstrap script first:\n"
            f"  PYTHONPATH=src:. python scripts/bootstrap_insidebar_strategy_version.py"
        )

    # Check each version using public API
    valid_versions = []
    all_versions_info = []

    for row in rows:
        version_id = row[0]
        version = repo.get_strategy_version_by_id(version_id)

        if not version:
            continue

        # Track for error message
        all_versions_info.append(
            f"  - ID={version.id}: impl_version={version.impl_version}, "
            f"lifecycle_stage={version.lifecycle_stage.name}"
        )

        # Check gating rules
        if version.impl_version < 1:
            continue  # Skip beta versions

        if version.lifecycle_stage < LifecycleStage.BACKTEST_APPROVED:
            continue  # Skip unapproved versions

        valid_versions.append(version)

    if not valid_versions:
        # Provide helpful error message
        versions_summary = "\n".join(all_versions_info[:5])  # Show first 5

        raise ValueError(
            f"❌ No valid strategy version for '{strategy_key}' in Pre-PaperTrading.\n"
            f"\n"
            f"Existing versions:\n{versions_summary}\n"
            f"\n"
            f"Pre-PaperTrading requires:\n"
            f"  - impl_version >= 1 (stable, not beta)\n"
            f"  - lifecycle_stage >= BACKTEST_APPROVED\n"
            f"\n"
            f"Please promote a version to BACKTEST_APPROVED or run bootstrap script."
        )

    # Return first valid version (already sorted by impl_version DESC)
    return valid_versions[0]


def format_version_for_ui(version: StrategyVersion) -> dict:
    """
    Format strategy version for UI display.

    Args:
        version: StrategyVersion object

    Returns:
        Dictionary with UI-friendly fields
    """
    return {
        "id": version.id,
        "strategy_key": version.strategy_key,
        "impl_version": version.impl_version,
        "profile_key": version.profile_key,
        "profile_version": version.profile_version,
        "label": version.label,
        "lifecycle_stage": version.lifecycle_stage.name,
        "code_ref": version.code_ref_value,
        "config_hash": version.config_hash,
    }

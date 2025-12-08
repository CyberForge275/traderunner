"""
Version Loader Utility

Loads available strategy versions from registry database for dashboard dropdown.
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional


def get_strategy_versions(strategy_name: str) -> List[Dict[str, str]]:
    """
    Load available versions from registry database.
    
    Args:
        strategy_name: Strategy identifier from dashboard (e.g., 'insidebar_intraday')
        
    Returns:
        List of dicts with 'label' and 'value' for dropdown options
    """
    # Map dashboard strategy names to folder names
    strategy_map = {
        "insidebar_intraday": "inside_bar",
        "insidebar_intraday_v2": "inside_bar",
    }
    
    folder_name = strategy_map.get(strategy_name)
    if not folder_name:
        return []
    
    # Path to registry database
    db_path = Path(__file__).parent.parent.parent / "src" / "strategies" / folder_name / "registry.db"
    
    if not db_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT version, status, lab_stage, created_at
            FROM versions
            ORDER BY created_at DESC
        """)
        
        versions = []
        for row in cursor.fetchall():
            version, status, lab_stage, created_at = row
            label = f"v{version}"
            if status:
                label += f" ({status})"
            if lab_stage:
                label += f" - {lab_stage}"
            
            versions.append({
                "label": label,
                "value": version
            })
        
        conn.close()
        return versions
        
    except Exception as e:
        print(f"Error loading versions for {strategy_name}: {e}")
        return []


def has_version_support(strategy_name: str) -> bool:
    """Check if strategy has version registry."""
    strategy_map = {
        "insidebar_intraday": "inside_bar",
        "insidebar_intraday_v2": "inside_bar",
    }
    
    folder_name = strategy_map.get(strategy_name)
    if not folder_name:
        return False
    
    db_path = Path(__file__).parent.parent.parent / "src" / "strategies" / folder_name / "registry.db"
    return db_path.exists()

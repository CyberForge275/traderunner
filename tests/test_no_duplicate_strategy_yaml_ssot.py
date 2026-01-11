"""Architecture test to ensure Strategy Config SSOT compliance."""

import os
import subprocess
from pathlib import Path
import yaml
import pytest


def get_tracked_yaml_files():
    """Get list of all YAML files tracked by git."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.splitlines()
        return [f for f in files if f.endswith('.yaml') or f.endswith('.yml')]
    except subprocess.CalledProcessError:
        # Fallback for non-git environments (though this should be a git repo)
        return []


def is_strategy_config(file_path):
    """Check if a YAML file is a strategy configuration file."""
    try:
        with open(file_path, 'r') as f:
            content = yaml.safe_load(f)
            if not isinstance(content, dict):
                return False
            # Strategy configs must have strategy_id or versions
            return 'strategy_id' in content or 'versions' in content
    except Exception:
        return False


def test_strategy_yaml_location_guardrail():
    """
    Guardrail: All strategy YAML files must be in configs/strategies/.
    Fail if any tracked strategy YAML is found elsewhere.
    """
    tracked_yamls = get_tracked_yaml_files()
    strategy_yamls = []
    
    for f in tracked_yamls:
        if is_strategy_config(f):
            strategy_yamls.append(f)
            
    # Check location
    illegal_locations = []
    for f in strategy_yamls:
        path = Path(f)
        if 'configs/strategies' not in str(path.parent):
            illegal_locations.append(f)
            
    assert not illegal_locations, f"Strategy YAMLs found in illegal locations: {illegal_locations}"


def test_no_duplicate_strategy_ids():
    """
    Guardrail: strategy_id must be unique across all strategy configurations.
    """
    tracked_yamls = get_tracked_yaml_files()
    strategy_ids = {} # strategy_id -> [files]
    
    for f in tracked_yamls:
        try:
            with open(f, 'r') as fileobj:
                content = yaml.safe_load(fileobj)
                if isinstance(content, dict) and 'strategy_id' in content:
                    sid = content['strategy_id']
                    if sid not in strategy_ids:
                        strategy_ids[sid] = []
                    strategy_ids[sid].append(f)
        except Exception:
            continue
            
    duplicates = {sid: files for sid, files in strategy_ids.items() if len(files) > 1}
    assert not duplicates, f"Duplicate strategy_ids found: {duplicates}"

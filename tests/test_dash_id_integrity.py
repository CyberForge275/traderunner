"""AST-based ID Integrity Guard for Dash UI.

Ensures:
1) No raw strings or inline dicts are used as IDs in Dash components.
2) No raw strings are used in Input/Output/State callback arguments.
3) ui_ids.py is clean (no duplicates, matches convention).
"""

import ast
import os
import re
from pathlib import Path
import pytest

from trading_dashboard import ui_ids

# ENFORCEMENT ALLOWLIST
# Start empty to ensure green state during Phase 0.
# Add files here once they are migrated to ui_ids.py.
ENFORCED_FILES = {
    # "trading_dashboard/layouts/backtests.py",
}

ID_REGEX = re.compile(r"^[a-z0-9]+([:-][a-z0-9]+)*$")

class DashIDVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.errors = []

    def visit_Call(self, node):
        # 1. Check Dash Component ID keyword argument
        # Example: html.Div(id="raw") -> ERROR
        for keyword in node.keywords:
            if keyword.arg == "id":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    self.errors.append(f"Raw string ID found: id='{keyword.value.value}' at {node.lineno}")
                elif isinstance(keyword.value, ast.Dict):
                    self.errors.append(f"Inline dict Pattern ID found at {node.lineno} (use ui_ids.py builders)")

        # 2. Check Callback Input/Output/State first argument
        # Example: Output("raw", "prop") -> ERROR
        if isinstance(node.func, ast.Name) and node.func.id in ("Input", "Output", "State"):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.errors.append(f"Raw string used in {node.func.id}: '{node.args[0].value}' at {node.lineno}")
        
        # Handle attribute access for Output/Input (e.g., dash.Output)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in ("Input", "Output", "State"):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.errors.append(f"Raw string used in {node.func.attr}: '{node.args[0].value}' at {node.lineno}")

        self.generic_visit(node)


def test_ssot_structure():
    """Verify ui_ids.py for duplicates and naming conventions."""
    seen_ids = {}
    namespaces = [ui_ids.Nav, ui_ids.BT, ui_ids.SSOT, ui_ids.RUN, ui_ids.Common]
    
    for ns in namespaces:
        for attr_name in dir(ns):
            if attr_name.startswith("_") or attr_name.islower():
                continue
            
            val = getattr(ns, attr_name)
            if isinstance(val, str):
                # Convention Check
                assert ID_REGEX.match(val), f"ID '{val}' in {ns.__name__}.{attr_name} violates naming convention"
                
                # Duplicate Check
                if val in seen_ids:
                    pytest.fail(f"Duplicate ID value detected: '{val}' in {seen_ids[val]} and {ns.__name__}.{attr_name}")
                seen_ids[val] = f"{ns.__name__}.{attr_name}"


def test_id_enforcement():
    """Run AST check on all files in the enforcement allowlist."""
    root_dir = Path(__file__).parents[1]
    all_errors = []

    for rel_path in ENFORCED_FILES:
        abs_path = root_dir / rel_path
        if not abs_path.exists():
            pytest.fail(f"Allowlisted file missing: {rel_path}")

        tree = ast.parse(abs_path.read_text())
        visitor = DashIDVisitor(rel_path)
        visitor.visit(tree)
        
        if visitor.errors:
            all_errors.append(f"--- {rel_path} ---\n" + "\n".join(visitor.errors))

    if all_errors:
        pytest.fail("AST Guard found raw string IDs in enforced files:\n\n" + "\n\n".join(all_errors))


def test_guard_smoke_check():
    """Verify that the visitor correctly identifies errors in a dummy snippet."""
    code = """
from dash import html, Output
html.Div(id="bad-string")
Output("bad-output", "data")
html.Div(id={"type": "bad-dict"})
"""
    tree = ast.parse(code)
    visitor = DashIDVisitor("smoke_test.py")
    visitor.visit(tree)
    
    assert len(visitor.errors) == 3
    assert "Raw string ID found" in visitor.errors[0]
    assert "Raw string used in Output" in visitor.errors[1]
    assert "Inline dict Pattern ID found" in visitor.errors[2]

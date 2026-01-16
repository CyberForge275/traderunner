from pathlib import Path
import ast


def test_signal_frame_factory_has_no_direct_insidebar_imports():
    p = Path("src/axiom_bt/pipeline/signal_frame_factory.py")
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("strategies.inside_bar"), (
                "Forbidden import: axiom_bt must not import strategies.inside_bar.* "
                f"but found: from {node.module} import ..."
            )

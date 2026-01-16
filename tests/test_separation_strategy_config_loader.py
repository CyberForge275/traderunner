from pathlib import Path
import ast


def test_strategy_config_loader_has_no_static_strategies_config_imports():
    p = Path("src/axiom_bt/pipeline/strategy_config_loader.py")
    tree = ast.parse(p.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("strategies.config"), (
                "Forbidden static import in framework: "
                f"from {node.module} import ..."
            )

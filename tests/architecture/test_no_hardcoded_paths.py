# tests/architecture/test_no_hardcoded_paths.py

from pathlib import Path
import re

# Verzeichnisse, in denen wir harte Pfade NICHT akzeptieren
# (auf das Repo-Root bezogen: traderunner/)
CORE_DIRS = [
    Path("src"),
    Path("trading_dashboard/services"),
    Path("trading_dashboard/repositories"),
    Path("monitoring"),
]

# Strings/Patterns, die in Core/Service-Code nicht hart vorkommen dürfen
FORBIDDEN_PATTERNS = [
    r"/home/",
    r"/opt/",
    r"signals\.db",
]


def test_no_hardcoded_paths_in_core_and_services():
    """
    Ensure there are no obvious hard-coded paths or DB file names
    in core/service modules.

    Pfade und DBs müssen über Settings/Config gesteuert werden
    (vgl. AI_CONTRIBUTION_GUIDE & ENGINEERING_MANIFEST).
    """
    offending = []

    for base_dir in CORE_DIRS:
        if not base_dir.exists():
            # Falls ein Verzeichnis in einer bestimmten Variante nicht existiert,
            # einfach überspringen (z. B. in Teilprojekten)
            continue

        for py_file in base_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")

            # Kommentare/Strings werden absichtlich nicht ausgefiltert:
            # selbst Beispiele sollten keine harten Pfade propagieren.
            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, text):
                    offending.append((str(py_file), pattern))

    assert not offending, (
        "Hard-coded paths or DB names found in core/service modules. "
        "Move these into settings/config:\n"
        + "\n".join(f"- {file}: {pattern}" for file, pattern in offending)
    )

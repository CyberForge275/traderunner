#!/usr/bin/env python3
"""Fix docstring placement - insert AFTER function signature, not inside it"""

from pathlib import Path
import re

source_file = Path("src/axiom_bt/data/eodhd_fetch.py")

# Read the file and remove the badly placed docstrings
with open(source_file) as f:
    content = f.read()

# Remove all function docstrings that were inserted in wrong places
# Keep only the module docstring
lines = content.split('\n')
cleaned_lines = []
in_bad_docstring = False
docstring_indent = None

for i, line in enumerate(lines):
    # Detect start of misplaced docstring (has """ but is indented and appears after "symbol:" or similar)
    if '    """' in line and i > 0 and any(x in lines[i-1] for x in ['symbol:', 'exchange:', 'm1_parquet:', 'df:', 'url:']):
        in_bad_docstring = True
        docstring_indent = len(line) - len(line.lstrip())
        continue

    # Detect end of misplaced docstring
    if in_bad_docstring and '"""' in line:
        in_bad_docstring = False
        docstring_indent = None
        continue

    # Skip lines inside bad docstring
    if in_bad_docstring:
        continue

    cleaned_lines.append(line)

# Write cleaned version
with open(source_file, 'w') as f:
    f.write('\n'.join(cleaned_lines))

print(f"✓ Removed misplaced docstrings")
print(f"  Lines before: {len(lines)}")
print(f"  Lines after: {len(cleaned_lines)}")

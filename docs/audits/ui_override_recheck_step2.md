# Step 2 — Repro conversion behavior (read-only)

Command:
```
PYTHONPATH=src:. python docs/audits/repro_ui_override_comma03.py | tee docs/audits/repro_ui_override_comma03.out
```

Output (excerpt):
```
$(sed -n '1,200p' docs/audits/repro_ui_override_comma03.out)
```

Table (input → result):
- value="0,03" → ValueError (float parsing)
- value="0.03" → override set to 0.03
- value="" or None → override set to 0.0
- value=["0,03"] → TypeError (float on list)

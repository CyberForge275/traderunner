# Merge to main notes

- Command sequence:
  - `git checkout main`
  - `git reset --hard origin/main`
  - `git merge --no-ff chore/remove-legacy-guards`
  - `PYTHONPATH=src:. pytest tests/test_no_duplicate_strategy_yaml_ssot.py -q`
- Merge result: clean, no conflicts.
- Smoke test: PASS (2 tests).
- Full suite not executed here (previously failing in repo).

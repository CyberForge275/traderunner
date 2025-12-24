# Contributing to Trading Platform

## Repository Hygiene Rules

### 🚫 What NEVER Belongs in Git

1. **Artifacts**: Never track `artifacts/**` directory
   - Backtests results, parquet files, generated reports
   - These are outputs, not source code
   
2. **Binary files**: Never track `*.db`, `*.sqlite`, `*.pdf`
   - SQLite databases are generated/stateful
   - PDFs should be built artifacts, not source
   
3. **Large files**: Nothing > 5MB without Git LFS
   - Slows down clones, increases repo size
   - Use external storage (S3, artifact repos)

4. **Generated code**: Build outputs, compiled files
   - `__pycache__/`, `.pyc` files
   - Already in `.gitignore`

5. **Secrets**: API keys, tokens, credentials
   - Use environment variables
   - `credentials.toml` is gitignored

---

## 🔧 How to Fix Accidentally Tracked Files

### Remove artifacts from tracking:
```bash
git rm -r --cached artifacts/
git commit -m "chore: remove artifacts from tracking"
```

### Remove specific binary file:
```bash
git rm --cached path/to/file.db
git commit -m "chore: remove binary from tracking"
```

### Check what's tracked:
```bash
git ls-files artifacts/          # Should be empty
git ls-files | grep '\.db$'      # Should be empty
```

### If file is already committed and pushed:
```bash
# Remove from index (keeps local file)
git rm --cached path/to/file

# Update .gitignore if needed
echo "*.db" >> .gitignore

# Commit the removal
git add .gitignore
git commit -m "chore: remove binary and update gitignore"
```

---

## ✅ Quality Gates (Enforced in CI)

### Automatic Checks (`.github/workflows/guardrails.yml`)

Every PR and push to `main`/`develop` runs:

1. **Artifact Gate**: Fails if `git ls-files artifacts/` is not empty
2. **Binary Gate**: Fails if `*.db`, `*.sqlite`, `*.pdf` files are tracked
3. **Size Gate**: Fails if new files > 5MB in PR

**If CI fails**, check the error output - it shows exactly which files to remove.

### Pre-commit Hooks (Optional but Recommended)

Install locally to catch issues before committing:

```bash
pip install pre-commit
pre-commit install
```

Now hooks run automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

To bypass (NOT recommended):
```bash
git commit --no-verify
```

---

## 📋 Developer Workflow

### Before committing:

```bash
# 1. Check status
git status

# 2. Verify no artifacts tracked
git ls-files artifacts/ | wc -l  # Should be 0

# 3. Run pre-commit checks (if installed)
pre-commit run --all-files

# 4. Commit
git commit -m "feat: your changes"
```

### If pre-commit fails:

Read the error message - it tells you the fix command.

Example output:
```
❌ Binary files tracked:
  src/strategies/inside_bar/registry.db

Run: git rm --cached src/strategies/inside_bar/registry.db
```

Just copy-paste the command, then commit again.

---

## 🚨 Common Pitfalls

### Pitfall 1: `.gitignore` doesn't untrack files
- **Problem**: Added `artifacts/` to `.gitignore` but files still show in `git status`
- **Cause**: Files were already tracked before `.gitignore` was updated
- **Fix**: `git rm -r --cached artifacts/`

### Pitfall 2: Large file in commit history
- **Problem**: Removed large file but repo still slow to clone
- **Cause**: File is in git history, not current commit
- **Fix**: Contact maintainer - requires history rewrite (BFG/filter-repo)

### Pitfall 3: Binary file keeps being re-tracked
- **Problem**: Removed `.db` file but it comes back
- **Cause**: Not in `.gitignore`, IDE/tool re-adds it
- **Fix 1**: Add `*.db` to `.gitignore` (already done)
- **Fix 2**: Check IDE settings, disable auto-add for generated files

### Pitfall 4: Pre-commit blocking legitimate file
- **Problem**: Need to commit a doc PDF intentionally
- **Cause**: Pre-commit blocks all PDFs
- **Fix**: Update `.pre-commit-config.yaml` exclude pattern, or use `--no-verify` (last resort)

### Pitfall 5: CI passes locally but fails remotely
- **Problem**: Pre-commit passes, CI fails
- **Cause**: Pre-commit only checks staged files, CI checks entire index
- **Fix**: Run `git ls-files artifacts/` before pushing

---

## 📚 References

- `.gitignore`: Line 84 (`artifacts/`), Line 116+ (`*.db`, `*.pdf`)
- Quality Gates: `.github/workflows/guardrails.yml`
- Pre-commit: `.pre-commit-config.yaml`
- Issue tracker: Tag issues with `repo-hygiene` label

---

**Questions?** Check existing issues or create new one with `repo-hygiene` label.

Run comprehensive security and quality checks on the Empathy Framework codebase.

## Execution Steps

### 1. Run Test Suite
```bash
pytest tests/ -v --tb=short -q
```
Report: total tests, passed/failed, time taken.

### 2. Run Linters
```bash
# Code formatting check
black --check src/ tests/

# Linting with ruff
ruff check src/ tests/

# Type checking (if mypy configured)
mypy src/ --ignore-missing-imports 2>/dev/null || echo "MyPy not configured"
```
Report any formatting or linting issues found.

### 3. Run Security Scans
```bash
# Bandit security linter
bandit -r src/ --severity-level medium -q

# Check for secrets
pre-commit run detect-secrets --all-files 2>/dev/null || echo "detect-secrets hook not available"
```
Report any security vulnerabilities or exposed secrets.

### 4. Pre-commit Hooks (if available)
```bash
pre-commit run --all-files
```

## Output Format

Provide a summary table:

| Check | Status | Issues |
|-------|--------|--------|
| Tests | PASS/FAIL | count |
| Black | PASS/FAIL | count |
| Ruff | PASS/FAIL | count |
| Bandit | PASS/FAIL | count |
| Secrets | PASS/FAIL | count |

If any checks fail:
1. List the specific issues found
2. Prioritize by severity (security issues first)
3. Suggest fixes for common problems

Keep output concise but actionable.

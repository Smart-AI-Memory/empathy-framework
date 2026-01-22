Automated Code Review - Enforce coding standards and best practices.

## Overview

This skill performs automated code review against the project's coding standards, checking for security issues, exception handling, type hints, and code quality.

## Execution Steps

### 1. Security Checks (CRITICAL)

#### Check for eval()/exec() Usage
```bash
# Find dangerous eval/exec (Bandit S307, S102)
ruff check src/ --select=S307,S102 --output-format=text
bandit -r src/ --severity-level medium -f txt | grep -E "eval|exec"
```

Any `eval()` or `exec()` usage is a **CRITICAL** finding.

#### Check for Path Traversal Vulnerabilities
```bash
# Find file operations without validation
grep -rn "open(" src/ --include="*.py" | grep -v "_validate_file_path" | grep -v "# validated"
grep -rn "\.write_text\|\.write_bytes" src/ --include="*.py" | grep -v "_validate_file_path"
```

All file writes must use `_validate_file_path()` from `empathy_os.config`.

#### Check for Hardcoded Secrets
```bash
# Run detect-secrets
pre-commit run detect-secrets --all-files 2>/dev/null || echo "detect-secrets not configured"

# Manual check for common patterns
grep -rn "api_key\s*=\s*['\"]" src/ --include="*.py" | grep -v "os.getenv"
grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "os.getenv"
```

### 2. Exception Handling (HIGH)

#### Check for Bare except:
```bash
# Ruff BLE001 check
ruff check src/ --select=BLE --output-format=text
```

Bare `except:` or unjustified `except Exception:` must be fixed or have `# noqa: BLE001` with `# INTENTIONAL:` comment.

#### Verify Exception Logging
```bash
# Find except blocks without logging
grep -rn "except.*:" src/ --include="*.py" -A 2 | grep -v "logger\." | grep -v "logging\."
```

All exceptions should be logged with `logger.exception()` or `logger.error()`.

### 3. Code Quality (MEDIUM)

#### Check Type Hints
```bash
# MyPy check (if configured)
mypy src/ --ignore-missing-imports --disallow-untyped-defs 2>/dev/null | head -50

# Find functions without type hints
grep -rn "def .*):$" src/ --include="*.py" | head -20
```

All public functions must have type hints.

#### Check Docstrings
```bash
# Find public functions without docstrings
ruff check src/ --select=D100,D101,D102,D103 --output-format=text | head -30
```

All public APIs must have Google-style docstrings.

#### Run Linters
```bash
# Ruff (comprehensive)
ruff check src/ --output-format=grouped

# Black (formatting)
black --check --diff src/

# Combined pre-commit
pre-commit run --all-files
```

### 4. Performance Patterns (MEDIUM)

#### Check for Antipatterns
```bash
# sorted()[:N] antipattern
grep -rn "sorted(.*)\[:" src/ --include="*.py"

# list(set()) without order preservation
grep -rn "list(set(" src/ --include="*.py"

# Unnecessary list(range())
grep -rn "list(range(" src/ --include="*.py"
```

Reference `.claude/rules/empathy/list-copy-guidelines.md` for fixes.

### 5. Test Coverage

```bash
# Check coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80 -q

# Security test coverage
pytest tests/unit/test_*security*.py -v --tb=short
```

Minimum 80% coverage required. Security tests mandatory for file operations.

## Output Format

```
============================================================
CODE REVIEW REPORT
============================================================

Files Reviewed: XX
Total Issues: XX

------------------------------------------------------------
CRITICAL (Must fix immediately)
------------------------------------------------------------
🔴 [file:line] eval() usage detected
   Code: result = eval(user_input)
   Fix: Use ast.literal_eval() or json.loads()

🔴 [file:line] Path traversal vulnerability
   Code: open(user_path, 'w')
   Fix: Use _validate_file_path(user_path) first

------------------------------------------------------------
HIGH (Must fix before merge)
------------------------------------------------------------
🟠 [file:line] Bare except clause
   Code: except:
   Fix: Catch specific exceptions or add # noqa: BLE001 with justification

🟠 [file:line] Missing exception logging
   Code: except ValueError: pass
   Fix: Add logger.error() or logger.exception()

------------------------------------------------------------
MEDIUM (Should fix)
------------------------------------------------------------
🟡 [file:line] Missing type hints
   Code: def process(data):
   Fix: def process(data: dict) -> Result:

🟡 [file:line] Performance antipattern
   Code: sorted(items)[:10]
   Fix: heapq.nlargest(10, items)

------------------------------------------------------------
LOW (Nice to have)
------------------------------------------------------------
⚪ [file:line] Missing docstring
⚪ [file:line] Line too long (105 > 100)

------------------------------------------------------------
SUMMARY
------------------------------------------------------------
| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0     | ✅     |
| High     | 2     | ❌     |
| Medium   | 5     | ⚠️     |
| Low      | 3     | ⚠️     |

Overall: ❌ CHANGES REQUESTED
[or]
Overall: ✅ APPROVED (with minor suggestions)

============================================================
```

## Severity Definitions

| Level | Description | Action | Timeline |
|-------|-------------|--------|----------|
| CRITICAL | Security vulnerability | Block merge | Fix immediately |
| HIGH | Standards violation | Block merge | Fix in same PR |
| MEDIUM | Quality issue | Request changes | Fix before release |
| LOW | Style/minor | Suggest | Fix when convenient |

## Automated Fixes

Some issues can be auto-fixed:

```bash
# Auto-fix formatting
black src/

# Auto-fix import sorting
ruff check src/ --select=I --fix

# Auto-fix simple issues
ruff check src/ --fix
```

## Related Commands

- `/security-scan` - Deeper security analysis
- `/refactor` - Apply fixes systematically
- `/test` - Verify fixes don't break tests

## Reference Files

- `.claude/rules/empathy/coding-standards-index.md` - Full coding standards
- `.claude/rules/empathy/list-copy-guidelines.md` - Performance patterns
- `.pre-commit-config.yaml` - Pre-commit hook configuration

## Auto-Learn Patterns

After completing the review, automatically save learned patterns:

```bash
# Run pattern learning in background (non-blocking)
python -m empathy_os.cli learn --quiet &
```

This captures the review session insights for future reference.

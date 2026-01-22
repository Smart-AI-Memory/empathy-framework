Safe Refactoring Assistant - Apply code improvements while maintaining correctness.

## Overview

This skill identifies refactoring opportunities and applies them safely, ensuring tests pass and coding standards are maintained. It focuses on patterns from the project's coding guidelines.

## Execution Steps

### 1. Pre-Refactor Safety Check

Before any refactoring, establish a baseline:

```bash
# Run tests to ensure they pass before refactoring
pytest tests/ -x --no-cov -q

# Check current linting status
ruff check src/ --statistics

# Note current test count
pytest tests/ --collect-only -q | tail -1
```

### 2. Identify Refactoring Opportunities

#### Performance Antipatterns (from list-copy-guidelines.md)

Search for `sorted()[:N]` patterns:
```bash
grep -rn "sorted(.*)\[:" src/ --include="*.py"
```

Search for `list(set())` patterns:
```bash
grep -rn "list(set(" src/ --include="*.py"
```

Search for `list(range())` patterns:
```bash
grep -rn "list(range(" src/ --include="*.py"
```

#### Security Antipatterns (from coding-standards-index.md)

Search for `eval()` usage:
```bash
grep -rn "eval(" src/ --include="*.py" | grep -v "# noqa"
```

Search for bare `except:`:
```bash
ruff check src/ --select=BLE --output-format=text
```

Search for unvalidated file paths:
```bash
grep -rn "open(" src/ --include="*.py" | grep -v "_validate_file_path"
```

### 3. Apply Refactorings

#### Pattern: sorted()[:N] → heapq.nlargest()

Before:
```python
top_items = sorted(items, key=lambda x: x.score, reverse=True)[:10]
```

After:
```python
import heapq
top_items = heapq.nlargest(10, items, key=lambda x: x.score)
```

#### Pattern: list(set()) → dict.fromkeys()

Before:
```python
unique_items = list(set(items))  # Order not preserved
```

After:
```python
unique_items = list(dict.fromkeys(items))  # Order preserved
```

#### Pattern: Add Path Validation

Before:
```python
def save_data(filepath: str, data: dict):
    with open(filepath, 'w') as f:
        json.dump(data, f)
```

After:
```python
from empathy_os.config import _validate_file_path

def save_data(filepath: str, data: dict):
    validated_path = _validate_file_path(filepath)
    with validated_path.open('w') as f:
        json.dump(data, f)
```

#### Pattern: Bare except → Specific exceptions

Before:
```python
try:
    risky_operation()
except:
    pass
```

After:
```python
try:
    risky_operation()
except (ValueError, IOError) as e:
    logger.error(f"Operation failed: {e}")
    raise
```

### 4. Post-Refactor Verification

After each refactoring:

```bash
# Run tests
pytest tests/ -x --no-cov -q

# Run linters
ruff check src/ --fix
black src/

# Run type checker (if configured)
mypy src/ --ignore-missing-imports 2>/dev/null || echo "MyPy check skipped"
```

### 5. Incremental Approach

For large refactorings:

1. **Identify** all instances of the pattern
2. **Fix one** instance
3. **Test** to ensure no regressions
4. **Repeat** for remaining instances
5. **Commit** with descriptive message

## Output Format

```
============================================================
REFACTORING REPORT
============================================================

Files Analyzed: XX
Patterns Found: XX
Refactorings Applied: XX

------------------------------------------------------------
CHANGES MADE
------------------------------------------------------------
File: src/empathy_os/module.py
  Line 45: sorted()[:N] → heapq.nlargest()
  Line 89: list(set()) → dict.fromkeys()

File: src/empathy_os/other.py
  Line 23: Added _validate_file_path()

------------------------------------------------------------
VERIFICATION
------------------------------------------------------------
Tests: PASS (127 passed)
Linting: PASS (0 errors)
Type Check: PASS

------------------------------------------------------------
REMAINING OPPORTUNITIES
------------------------------------------------------------
[Patterns that weren't auto-fixed - need manual review]

============================================================
```

## Safety Rules

1. **Never refactor without passing tests first**
2. **Make one type of change at a time**
3. **Run tests after each change**
4. **Don't change behavior, only implementation**
5. **Preserve all public APIs**

## Related Commands

- `/profile` - Identify what to optimize
- `/review` - Verify refactoring meets standards
- `/test` - Run test suite

## Coding Standards Reference

- `.claude/rules/empathy/coding-standards-index.md`
- `.claude/rules/empathy/list-copy-guidelines.md`

## Auto-Learn Patterns

After completing refactoring, automatically save learned patterns:

```bash
# Run pattern learning in background (non-blocking)
python -m empathy_os.cli learn --quiet &
```

This captures the refactoring session insights for future reference.

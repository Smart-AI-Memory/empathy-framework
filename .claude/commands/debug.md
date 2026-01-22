Bug Investigation Workflow - Analyze errors and find root causes.

## Overview

This skill helps investigate bugs by analyzing stack traces, cross-referencing with historical patterns, and suggesting fixes based on similar past issues.

## Execution Steps

### 1. Gather Error Information

If user provides a stack trace, parse it to identify:
- Exception type
- Error message
- File and line number
- Call stack

If no stack trace provided, ask user for:
- What operation was being performed?
- What was the expected behavior?
- What actually happened?
- Can they reproduce it?

### 2. Reproduce the Issue

```bash
# Run the failing test if identified
pytest tests/path/to/test.py::test_name -v --tb=long

# Or run the specific command that failed
python -c "from module import func; func(args)"
```

### 3. Analyze the Error

#### Common Error Categories

**ImportError / ModuleNotFoundError**
```bash
# Check if module exists
python -c "import module_name"

# Check installed packages
pip show package_name

# Check for circular imports
python -c "import sys; import module; print([m for m in sys.modules if 'empathy' in m])"
```

**TypeError / AttributeError**
- Check type hints match actual types
- Look for None values where objects expected
- Verify API compatibility

**FileNotFoundError / PermissionError**
```bash
# Check file exists
ls -la path/to/file

# Check permissions
stat path/to/file
```

**ValueError**
- Check input validation
- Look for edge cases (empty lists, None, etc.)

### 4. Cross-Reference Historical Patterns

Check the debugging patterns file for similar issues:

```bash
# Search for similar error types
grep -i "error_type" .claude/rules/empathy/debugging.md

# Search patterns database
grep -r "similar_keyword" patterns/debugging.json
```

Reference: `.claude/rules/empathy/debugging.md` contains 84 historical patterns.

### 5. Common Bug Patterns in This Codebase

#### Pattern: Path Traversal (Security)
```python
# Bug: Unvalidated file path
with open(user_input, 'w') as f:  # VULNERABLE!

# Fix: Always validate paths
from empathy_os.config import _validate_file_path
validated = _validate_file_path(user_input)
```

#### Pattern: Bare Exception Masking Real Error
```python
# Bug: Exception hidden
try:
    operation()
except:
    pass  # What went wrong? We'll never know!

# Fix: Log and handle specifically
try:
    operation()
except SpecificError as e:
    logger.exception(f"Operation failed: {e}")
    raise
```

#### Pattern: Type Mismatch
```python
# Bug: Optional not handled
def process(data: dict | None):
    return data["key"]  # TypeError if data is None!

# Fix: Handle None case
def process(data: dict | None):
    if data is None:
        return default_value
    return data["key"]
```

#### Pattern: Async/Await Missing
```python
# Bug: Coroutine not awaited
result = async_function()  # Returns coroutine, not result!

# Fix: Await the coroutine
result = await async_function()
```

### 6. Generate Fix

Once root cause identified:

1. **Explain** the bug clearly
2. **Show** the problematic code
3. **Provide** the fix with explanation
4. **Add** a test to prevent regression

## Output Format

```
============================================================
BUG INVESTIGATION REPORT
============================================================

Error Type: [ExceptionType]
Location: [file:line]

------------------------------------------------------------
ROOT CAUSE ANALYSIS
------------------------------------------------------------
[Explanation of what went wrong and why]

------------------------------------------------------------
PROBLEMATIC CODE
------------------------------------------------------------
```python
# file.py:123
[code snippet]
```

------------------------------------------------------------
SUGGESTED FIX
------------------------------------------------------------
```python
# file.py:123
[fixed code]
```

Explanation: [Why this fix works]

------------------------------------------------------------
REGRESSION TEST
------------------------------------------------------------
```python
def test_bug_fix_issue_xxx():
    """Regression test for [bug description]."""
    # Given
    [setup]

    # When
    [action]

    # Then
    [assertion]
```

------------------------------------------------------------
SIMILAR HISTORICAL ISSUES
------------------------------------------------------------
[List of similar past bugs and their fixes from debugging.md]

============================================================
```

## Interactive Debugging

For complex issues, suggest using pdb:

```python
import pdb; pdb.set_trace()  # Add breakpoint

# Or use breakpoint() in Python 3.7+
breakpoint()
```

Or pytest with debugging:
```bash
pytest tests/test_file.py::test_name -v --pdb
```

## Related Commands

- `/test` - Run tests to verify fix
- `/review` - Ensure fix meets coding standards
- `/profile` - Check if fix impacts performance

## Reference Files

- `.claude/rules/empathy/debugging.md` - Historical bug patterns
- `.claude/rules/empathy/coding-standards-index.md` - Coding standards
- `patterns/debugging.json` - Machine-readable patterns

## Auto-Learn Patterns

After completing the investigation, automatically save learned patterns:

```bash
# Run pattern learning in background (non-blocking)
python -m empathy_os.cli learn --quiet &
```

This captures the debugging session insights for future reference.

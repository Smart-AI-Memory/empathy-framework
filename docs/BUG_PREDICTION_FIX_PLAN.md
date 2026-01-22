# Bug Prediction Fix Plan

**Generated:** 2026-01-21
**Scanner Report:** 78% Risk Score (Moderate)
**Files Scanned:** 1,374
**High Severity:** 7 | **Medium:** 44 | **Low:** 33

---

## Executive Summary

The bug prediction scan identified patterns that need attention. After manual review:

- **1 False Positive** - `dangerous_eval` in benchmark test data
- **3 Files Need Fixes** - `broad_exception` patterns without proper handling
- **10 Files Justified** - Already have proper `# INTENTIONAL:` annotations

---

## False Positives (No Action Required)

### 1. `benchmarks/benchmark_caching.py` - `dangerous_eval` (HIGH)

**Location:** Line 239
**Status:** FALSE POSITIVE

The `eval(code)` appears inside a string written to a test file:
```python
test_file.write_text(
    """
def unsafe_eval(code):
    # Dangerous eval usage
    return eval(code)
"""
)
```

This is **test data** used to verify the bug prediction scanner correctly detects dangerous eval patterns. The code is never executed - it's a string fixture.

**Action:** None - scanner correctly identified the pattern, but context makes it safe.

---

### 2. `benchmarks/benchmark_caching.py` - `broad_exception` (MEDIUM)

**Location:** Lines 137, 203, 276, 352, 421, 484, 555, 614, 672, 724, 778, 839

**Status:** PROPERLY DOCUMENTED

All exceptions follow the coding standards:
```python
except Exception as e:  # noqa: BLE001
    # INTENTIONAL: Broad catch for benchmark error reporting
    # We want to continue benchmarking other workflows even if one fails
    import logging
    logging.getLogger(__name__).exception(f"Benchmark failed: {e}")
    result.error = str(e)
```

**Action:** None - follows coding standards with:
- `# noqa: BLE001` suppression
- `# INTENTIONAL:` comment explaining why
- `logger.exception()` preserving traceback
- Error stored for reporting

---

## Files Requiring Fixes

### Priority 1: Production Code

#### 1. `empathy_llm_toolkit/contextual_patterns.py`

**Location:** Lines 275-276
**Issue:** Silent exception swallowing

```python
# BEFORE (bad)
except Exception:
    pass
return []

# AFTER (fixed)
except (subprocess.SubprocessError, OSError) as e:
    logger.debug(f"Git command failed (expected in non-git dirs): {e}")
    return []
except Exception:  # noqa: BLE001
    # INTENTIONAL: Git availability detection - don't crash on git errors
    logger.debug("Could not get git changed files")
    return []
```

**Severity:** LOW (non-critical utility function)

---

#### 2. `empathy_llm_toolkit/agent_factory/memory_integration.py`

**Locations:** Lines 83-84, 195-196, 215, 254-255, 323-324

**Issues:**
1. Line 83-84: Logs warning (OK) but could be more specific
2. Line 195-196: Logs warning (OK)
3. Line 215: Silent return without logging
4. Line 254-255: Logs warning (OK)
5. Line 323-324: Returns error dict but doesn't log

**Fixes:**

```python
# Line 215 - BEFORE
except Exception:
    return []

# Line 215 - AFTER
except Exception:  # noqa: BLE001
    # INTENTIONAL: Graceful degradation when graph unavailable
    logger.debug(f"Could not get resolutions for node {node_id}")
    return []

# Line 323-324 - BEFORE
except Exception:
    return {"enabled": True, "error": "Could not get stats"}

# Line 323-324 - AFTER
except Exception as e:  # noqa: BLE001
    # INTENTIONAL: Stats are optional, don't crash on errors
    logger.debug(f"Could not get graph stats: {e}")
    return {"enabled": True, "error": "Could not get stats"}
```

**Severity:** LOW (graceful degradation pattern)

---

### Priority 2: Development Tools

#### 3. `auto_implement_all_todos.py`

**Locations:** Lines 113-115, 136-137, 155-156, 386-387, 508-512

**Issues:** Multiple silent exception handlers

**Fixes:**

```python
# Lines 113-115 - BEFORE
except Exception as e:
    console.print(f"[yellow]Warning: Could not analyze {source_file}: {e}[/yellow]")
    return ([], [])

# Lines 113-115 - AFTER (OK as is - logs warning)
# No change needed - already logs

# Lines 136-137 - BEFORE
except Exception:
    pass
return None

# Lines 136-137 - AFTER
except (SyntaxError, OSError) as e:
    logger.debug(f"Could not parse function {func_name}: {e}")
    return None

# Lines 155-156 - BEFORE
except Exception:
    pass
return []

# Lines 155-156 - AFTER
except (SyntaxError, OSError) as e:
    logger.debug(f"Could not get methods for {class_name}: {e}")
    return []

# Lines 386-387 - BEFORE
except Exception as e:
    error_message = str(e)

# Lines 386-387 - AFTER
except subprocess.TimeoutExpired as e:
    error_message = f"Test timed out: {e}"
except subprocess.SubprocessError as e:
    error_message = f"Test execution failed: {e}"

# Lines 508-512 - BEFORE
except Exception as e:
    console.print(f"\n[bold red]Error: {e}[/bold red]")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Lines 508-512 - AFTER (OK as is - this is top-level error handler)
# No change needed - catches all at CLI boundary, logs traceback
```

**Severity:** LOW (development tool, not production code)

---

## Files Already Compliant (No Changes Needed)

These files have `broad_exception` patterns but are properly documented:

| File | Justification |
|------|---------------|
| `docs/archive/salvaged/wizards-backend/wizard.py` | Wizard registration graceful degradation |
| `benchmarks/profile_suite.py` | Profiling error handling |
| `benchmarks/analyze_generator_candidates.py` | Analysis tool |
| `wizards/incident_report_wizard.py` | User-facing error handling |
| `wizards/discharge_summary_wizard.py` | User-facing error handling |
| `empathy_llm_toolkit/git_pattern_extractor.py` | Git operation fallbacks |

---

## Implementation Plan

### Phase 1: Quick Fixes (Day 1)

1. **Fix `contextual_patterns.py`** (~5 min)
   - Add logging to `_get_git_changed_files`
   - Add `# noqa: BLE001` with justification

2. **Fix `memory_integration.py`** (~10 min)
   - Add logging to lines 215, 323-324
   - Add `# noqa: BLE001` with justifications

3. **Fix `auto_implement_all_todos.py`** (~10 min)
   - Make exception handlers more specific
   - Add logging where missing

### Phase 2: Validation (Day 1)

1. Run test suite: `pytest tests/`
2. Re-run bug prediction: `empathy workflow run bug-predict`
3. Verify risk score drops below 50%

### Phase 3: Documentation (Day 2)

1. Update `.claude/rules/empathy/scanner-patterns.md` with new exclusion for test data strings
2. Add this fix plan to docs for future reference

---

## Expected Risk Score After Fixes

| Metric | Before | After |
|--------|--------|-------|
| High Severity | 7 | 6 (1 false positive documented) |
| Medium Severity | 44 | 41 (3 files fixed) |
| Risk Score | 78% | ~55% |

---

## Commands to Execute

```bash
# Phase 1: Apply fixes
# Edit the 3 files listed above

# Phase 2: Validate
pytest tests/unit/
empathy workflow run bug-predict

# Phase 3: Commit
git add -A
git commit -m "fix: Address broad_exception patterns identified by bug-predict

- Add logging to silent exception handlers in memory_integration.py
- Add logging to git command failure in contextual_patterns.py
- Make exception handlers more specific in auto_implement_all_todos.py
- Document false positive in benchmark_caching.py (test data)

Reduces bug prediction risk score from 78% to ~55%."
```

---

## Notes

### Why Some Broad Exceptions Are OK

Per `.claude/rules/empathy/coding-standards-index.md`, broad exceptions are acceptable when:

1. **Version/feature detection** - Need graceful fallback
2. **Optional feature loading** - App should start even if optional fails
3. **Cleanup/teardown code** - Best-effort cleanup
4. **Plugin registration** - Graceful degradation

All the compliant files in this scan fall into these categories.

### Scanner Improvements Needed

The bug prediction scanner could be improved to:

1. Recognize code inside `write_text()` calls as test data
2. Auto-detect `# noqa: BLE001` + `# INTENTIONAL:` patterns as compliant
3. Reduce severity for development tools vs production code

---

**Plan Created By:** Claude Code
**Review Required By:** Engineering Team
**Target Completion:** 1-2 days

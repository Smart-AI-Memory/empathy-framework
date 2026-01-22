Performance Regression Tracker - Track and compare performance over time.

## Overview

This skill runs benchmarks, compares against baselines, and detects performance regressions before they reach production.

## Execution Steps

### 1. Check for Existing Benchmarks

```bash
# Look for benchmark files
ls -la benchmarks/ 2>/dev/null || echo "No benchmarks/ directory"

# Check for pytest-benchmark
python -c "import pytest_benchmark; print('pytest-benchmark available')" 2>/dev/null || echo "pytest-benchmark not installed"
```

If pytest-benchmark not installed:
```bash
pip install pytest-benchmark
```

### 2. Run Benchmarks

```bash
# Run all benchmarks
pytest benchmarks/ --benchmark-only --benchmark-json=benchmark_results.json

# Run specific benchmark
pytest benchmarks/benchmark_caching.py --benchmark-only -v

# Compare against saved baseline
pytest benchmarks/ --benchmark-compare=baseline.json
```

### 3. Create Baseline

First run to establish baseline:

```bash
# Save current performance as baseline
pytest benchmarks/ --benchmark-only --benchmark-save=baseline

# Baseline saved to .benchmarks/
```

### 4. Compare Against Baseline

After changes:

```bash
# Compare current vs baseline
pytest benchmarks/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:10%

# Fail if >10% slower than baseline
```

### 5. Key Metrics to Track

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| mean | Average execution time | >10% regression |
| median | Middle value (less affected by outliers) | >10% regression |
| stddev | Variance in measurements | >50% increase |
| ops/sec | Operations per second | >10% decrease |
| memory | Peak memory usage | >20% increase |

### 6. Sample Benchmark Tests

```python
# benchmarks/benchmark_core.py
import pytest
from empathy_os.core import EmpathyCore

def test_benchmark_initialization(benchmark):
    """Benchmark core initialization."""
    result = benchmark(EmpathyCore)
    assert result is not None

def test_benchmark_pattern_matching(benchmark):
    """Benchmark pattern matching performance."""
    from empathy_os.pattern_library import PatternLibrary
    library = PatternLibrary()
    context = {"query": "test query", "history": ["item1", "item2"]}

    result = benchmark(library.match, context)
    assert result is not None

def test_benchmark_memory_recall(benchmark):
    """Benchmark memory recall operations."""
    from empathy_os.memory import MemoryGraph
    graph = MemoryGraph()

    # Setup
    for i in range(100):
        graph.store(f"key_{i}", f"value_{i}")

    result = benchmark(graph.recall, "key_50")
    assert result is not None
```

### 7. CI Integration

Add to GitHub Actions:

```yaml
# .github/workflows/benchmark.yml
name: Performance Benchmarks

on:
  pull_request:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install pytest-benchmark

      - name: Download baseline
        uses: actions/download-artifact@v4
        with:
          name: benchmark-baseline
          path: .benchmarks/
        continue-on-error: true  # First run won't have baseline

      - name: Run benchmarks
        run: |
          pytest benchmarks/ --benchmark-only \
            --benchmark-json=benchmark_results.json \
            --benchmark-compare-fail=mean:15%

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmark_results.json
```

### 8. Manual Quick Benchmark

For ad-hoc timing:

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    start = time.perf_counter()
    yield
    duration = time.perf_counter() - start
    print(f"{name}: {duration:.4f}s")

# Usage
with timer("Pattern matching"):
    for _ in range(1000):
        library.match(context)
```

## Output Format

```
============================================================
PERFORMANCE BENCHMARK REPORT
============================================================

Run Date: [timestamp]
Git Commit: [hash]
Python Version: [version]

------------------------------------------------------------
BENCHMARK RESULTS
------------------------------------------------------------
Name                          Mean        Median      Ops/sec
----------------------------  ----------  ----------  --------
test_initialization           0.0234s     0.0221s     42.7
test_pattern_matching         0.0012s     0.0011s     833.3
test_memory_recall            0.0003s     0.0003s     3333.3

------------------------------------------------------------
COMPARISON VS BASELINE
------------------------------------------------------------
Name                          Current     Baseline    Change
----------------------------  ----------  ----------  --------
test_initialization           0.0234s     0.0215s     +8.8%  ⚠️
test_pattern_matching         0.0012s     0.0013s     -7.7%  ✅
test_memory_recall            0.0003s     0.0003s     +0.0%  ✅

------------------------------------------------------------
REGRESSIONS DETECTED
------------------------------------------------------------
⚠️  test_initialization: +8.8% slower (approaching 10% threshold)

------------------------------------------------------------
RECOMMENDATIONS
------------------------------------------------------------
- Investigate initialization regression
- Consider profiling with /profile skill

============================================================
```

## Alert Thresholds

| Change | Status | Action |
|--------|--------|--------|
| < -10% | Improvement | Celebrate! Update baseline |
| -10% to +10% | Normal | No action needed |
| +10% to +20% | Warning | Investigate before merge |
| > +20% | Critical | Block merge, fix required |

## Related Commands

- `/profile` - Deep dive into performance issues
- `/refactor` - Apply optimizations
- `/test` - Ensure benchmarks don't break functionality

## Reference

- `benchmarks/` - Existing benchmark tests
- `.benchmarks/` - Saved baseline data
- `.claude/rules/empathy/advanced-optimization-plan.md` - Optimization targets

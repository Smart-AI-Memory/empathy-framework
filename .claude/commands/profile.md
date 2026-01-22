Performance Profiling Workflow - Identify bottlenecks and optimize hot paths.

## Overview

This skill profiles Python code to identify performance bottlenecks using cProfile, memory_profiler, and line_profiler. It generates actionable optimization recommendations.

## Execution Steps

### 1. Check Available Profiling Tools

```bash
python -c "import cProfile; print('cProfile: available')" 2>/dev/null || echo "cProfile: not available"
python -c "import memory_profiler; print('memory_profiler: available')" 2>/dev/null || echo "memory_profiler: not installed (pip install memory_profiler)"
python -c "import line_profiler; print('line_profiler: available')" 2>/dev/null || echo "line_profiler: not installed (pip install line_profiler)"
python -c "import snakeviz; print('snakeviz: available')" 2>/dev/null || echo "snakeviz: not installed (pip install snakeviz)"
```

### 2. CPU Profiling with cProfile

Profile a specific module or script:

```bash
# Profile entire test suite
python -m cProfile -o profiles/test_suite.prof -m pytest tests/ -x --no-cov -q 2>/dev/null

# Profile specific module
python -m cProfile -o profiles/module.prof -c "from empathy_os.core import EmpathyCore; e = EmpathyCore(); e.process('test')"
```

Analyze the profile:

```python
import pstats
from pstats import SortKey

# Load and analyze profile
stats = pstats.Stats('profiles/test_suite.prof')
stats.sort_stats(SortKey.CUMULATIVE)
stats.print_stats(20)  # Top 20 functions by cumulative time
```

### 3. Memory Profiling

For memory-intensive operations:

```bash
# Profile memory usage
python -m memory_profiler script.py

# Or use mprof for timeline
mprof run script.py
mprof plot  # Generates memory usage graph
```

### 4. Line-by-Line Profiling

For detailed function analysis:

```python
# Add @profile decorator to functions of interest
# Then run with kernprof
kernprof -l -v script.py
```

### 5. Identify Hot Paths

Look for functions that:
- Consume >10% of total runtime
- Are called >1000 times
- Have high per-call time (>1ms for simple operations)

### 6. Common Optimization Patterns

Based on project standards, check for:

#### List Copy Antipatterns
```python
# Bad: sorted()[:N] - O(n log n)
top_10 = sorted(items, key=lambda x: x.score, reverse=True)[:10]

# Good: heapq.nlargest - O(n log k)
import heapq
top_10 = heapq.nlargest(10, items, key=lambda x: x.score)
```

#### Generator vs List
```python
# Bad: Creates full list in memory
results = [process(x) for x in large_dataset]
for r in results:
    use(r)

# Good: Generator for single iteration
results = (process(x) for x in large_dataset)
for r in results:
    use(r)
```

#### O(n) Lookups
```python
# Bad: Linear search
if item in large_list:  # O(n)

# Good: Set lookup
large_set = set(large_list)
if item in large_set:  # O(1)
```

## Output Format

```
============================================================
PERFORMANCE PROFILING REPORT
============================================================

Target: [file/module profiled]
Total Runtime: X.XX seconds
Memory Peak: XXX MB

------------------------------------------------------------
TOP 10 HOTSPOTS (by cumulative time)
------------------------------------------------------------
Rank  Function                          Calls    Total    Per Call
----  --------------------------------  -------  -------  --------
1     module.function_name              1,234    2.34s    1.90ms
2     ...

------------------------------------------------------------
MEMORY HOTSPOTS
------------------------------------------------------------
[Functions with high memory allocation]

------------------------------------------------------------
OPTIMIZATION RECOMMENDATIONS
------------------------------------------------------------
Priority 1 (HIGH IMPACT):
  - [Specific recommendation with code example]

Priority 2 (MEDIUM IMPACT):
  - [Specific recommendation]

------------------------------------------------------------
QUICK WINS
------------------------------------------------------------
[Low-effort, high-impact optimizations]

============================================================
```

## Visualization

Generate visual profile with snakeviz:

```bash
snakeviz profiles/test_suite.prof
```

This opens an interactive browser visualization.

## Related Commands

- `/benchmark` - Track performance over time
- `/refactor` - Apply optimizations safely
- `/test` - Verify optimizations don't break functionality

## Project-Specific Patterns

Reference the optimization guidelines:
- `.claude/rules/empathy/list-copy-guidelines.md`
- `.claude/rules/empathy/advanced-optimization-plan.md`

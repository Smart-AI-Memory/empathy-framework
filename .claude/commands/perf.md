Analyze project performance and suggest optimizations.

## Commands

### 1. Run Performance Audit Workflow
```bash
empathy workflow run perf-audit --input '{"path": "./src"}'
```

### 2. Profile Hot Paths (if pytest-benchmark installed)
```bash
pytest benchmarks/ --benchmark-only --benchmark-json=benchmark.json
```

### 3. Check for Common Antipatterns
The framework detects:
- Unnecessary list copies (`sorted()[:N]` → use `heapq.nlargest`)
- O(n²) lookups (list membership → use set)
- Missing caching opportunities
- Blocking I/O in async code
- N+1 query patterns

## Analysis Areas

### 1. Algorithmic Complexity
- Identify O(n²) or worse operations
- Suggest data structure improvements
- Find unnecessary iterations

### 2. Memory Usage
- Large list comprehensions → generators
- Unnecessary copies → views/iterators
- Memory leaks in long-running processes

### 3. I/O Patterns
- Synchronous I/O blocking async code
- Missing connection pooling
- Unbatched database queries

### 4. Caching Opportunities
- Repeated expensive computations
- Cacheable API responses
- File content that could be memoized

## Pattern Detection

The framework's bug-predict workflow includes performance patterns:

```bash
empathy workflow run bug-predict --input '{"path": "./src", "focus": "performance"}'
```

Detects:
- `sorted(items)[:10]` → `heapq.nlargest(10, items)`
- `list(set(items))` → `list(dict.fromkeys(items))` (preserves order)
- `for x in list(dict.keys())` → `for x in dict`
- Nested loops with O(n²) complexity

## Profiling Guide

### CPU Profiling
```bash
python -m cProfile -o profile.prof your_script.py
snakeviz profile.prof  # Visualize
```

### Memory Profiling
```bash
python -m memory_profiler your_script.py
```

### Line-by-line Profiling
```python
# Add @profile decorator to functions
kernprof -l -v your_script.py
```

## Output

Provide performance report:

| Category | Issues | Impact |
|----------|--------|--------|
| Algorithmic | X | High |
| Memory | X | Medium |
| I/O | X | High |
| Caching | X | Medium |

For each issue:
1. Location (file:line)
2. Current pattern
3. Recommended fix
4. Expected improvement

Prioritize by impact (High → Low).

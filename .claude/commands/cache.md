Manage the hybrid caching system for LLM cost savings.

## Cache Architecture

The Empathy Framework uses a hybrid cache:
- **Hash Cache**: Exact match on prompt hash (fast, precise)
- **Semantic Cache**: Similarity-based matching (handles variations)
- **Dependency-aware**: Invalidates when source files change

## Commands

### 1. View Cache Statistics
```bash
empathy cache stats
```

Shows:
- Total entries
- Hit rate (target: 70%+)
- Size on disk
- Oldest/newest entry

### 2. Analyze Cache Effectiveness
```bash
empathy cache analyze
```

Shows:
- Hit rate by workflow type
- Most frequently cached queries
- Cache miss patterns
- Estimated cost savings

### 3. Clear Cache
```bash
# Clear all
empathy cache clear

# Clear specific workflow
empathy cache clear --workflow code-review

# Clear entries older than N days
empathy cache clear --older-than 7d
```

### 4. Warm Cache
```bash
# Pre-populate cache for common queries
empathy cache warm --workflows code-review,bug-predict
```

### 5. Configure Cache
In `empathy.config.yml`:
```yaml
cache:
  enabled: true
  type: "hybrid"          # hash, semantic, or hybrid
  max_size_mb: 100        # Maximum cache size
  ttl_hours: 24           # Time-to-live for entries
  similarity_threshold: 0.85  # For semantic matching
```

## Cache Performance Targets

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Hit Rate | >70% | Increase TTL, check query patterns |
| Avg Latency | <50ms | Check disk I/O, reduce cache size |
| Size | <100MB | Prune old entries |

## Monitoring

```bash
# Real-time cache monitoring
empathy cache monitor

# Export cache metrics
empathy cache export-metrics --format json
```

## Output

Provide cache health summary:
- Hit Rate: XX% (target: 70%+)
- Entries: X
- Size: X MB / 100 MB limit
- Estimated savings: $X.XX
- Recommendation: [OK / Needs attention]

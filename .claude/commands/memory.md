Manage the Empathy Framework memory system.

## Memory Architecture

The framework uses a unified memory system:
- **Short-term**: Redis-backed, fast access, TTL-based expiry
- **Long-term**: SQLite-backed, persistent, semantic search
- **Pattern Library**: Learned patterns from interactions

## Commands

### 1. Check Memory Status
```bash
empathy memory status
```
Shows: Redis connection, memory stats, pattern count

### 2. View Memory Statistics
```bash
empathy memory stats
```
Shows: Entry counts, storage size, hit rates

### 3. List Stored Patterns
```bash
empathy memory patterns
```
Shows: Learned patterns with metadata

### 4. Search Memory
```bash
empathy memory search "authentication error handling"
```
Semantic search across stored memories

### 5. Start/Stop Redis (Short-term Memory)
```bash
# Start Redis server
empathy memory start

# Stop Redis server
empathy memory stop
```

### 6. Export Memory
```bash
empathy memory export --output memory_backup.json
```

### 7. Prune Old Entries
```bash
empathy memory prune --older-than 30d
```

## Memory Graph Visualization

The memory system stores relationships as a graph:
- **Nodes**: Code patterns, decisions, context
- **Edges**: Relationships (similar_to, caused_by, resolved_by)

To explore:
```bash
empathy memory graph --output memory_graph.html
```

## Health Checks

Verify memory system health:
```bash
empathy health --component memory
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Redis not running | `empathy memory start` |
| Memory full | `empathy memory prune --older-than 7d` |
| Slow searches | Check index: `empathy memory reindex` |
| Connection refused | Check REDIS_URL in .env |

## Output

Provide current memory status:
- Redis: Connected/Disconnected
- Short-term entries: X
- Long-term entries: X
- Patterns learned: X
- Storage size: X MB

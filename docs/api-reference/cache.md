# Cache API Reference

The cache module provides intelligent caching for LLM responses with multiple storage backends.

## Overview

Empathy Framework includes a sophisticated caching system that can achieve up to 85% cache hit rates, significantly reducing API costs.

## BaseCache

Abstract base class for all cache implementations.

```python
from empathy_os.cache import BaseCache

class BaseCache(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve cached value."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete cached value."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        ...
```

## Cache Factory

Create cache instances with `create_cache()`.

```python
from empathy_os.cache import create_cache

# Memory cache (default)
cache = create_cache("memory", max_size=1000)

# SQLite cache
cache = create_cache("sqlite", db_path=".empathy/cache.db")

# Redis cache (requires redis extra)
cache = create_cache("redis", host="localhost", port=6379)
```

**Supported backends:**

| Backend | Description | Best For |
|---------|-------------|----------|
| `memory` | In-memory LRU cache | Development, single-process |
| `sqlite` | SQLite-based persistent cache | Local persistence |
| `redis` | Redis-based distributed cache | Production, multi-process |
| `hybrid` | Memory + persistent fallback | Best performance |

## Auto Setup

Automatically configure optimal cache based on environment.

```python
from empathy_os.cache import auto_setup_cache

# Detects available backends and configures optimal cache
cache = auto_setup_cache()
```

## HybridCache

Combines fast in-memory cache with persistent storage.

```python
from empathy_os.cache import HybridCache

cache = HybridCache(
    memory_size=500,           # In-memory LRU size
    persistent_backend="sqlite",
    db_path=".empathy/cache.db",
)

# Use like any cache
cache.set("key", {"response": "data"}, ttl=3600)
result = cache.get("key")
```

## Cache Keys

Generate consistent cache keys for LLM requests.

```python
from empathy_os.cache import generate_cache_key

key = generate_cache_key(
    model="claude-3-sonnet",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
)
```

## Semantic Cache

Optional semantic similarity-based caching.

```python
from empathy_os.cache import SemanticCache

# Requires sentence-transformers
cache = SemanticCache(
    similarity_threshold=0.95,
    embedding_model="all-MiniLM-L6-v2",
)

# Similar queries return cached results
cache.set("What is Python?", "Python is a programming language...")
result = cache.get("Tell me about Python")  # Returns cached result
```

## Cache Statistics

Monitor cache performance.

```python
from empathy_os.cache_stats import CacheStats

stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Hits: {stats.hits}")
print(f"Misses: {stats.misses}")
print(f"Size: {stats.size}")
```

## Configuration

Configure caching via `empathy.config.yml`:

```yaml
cache:
  backend: hybrid
  memory_size: 1000
  ttl: 3600  # 1 hour default TTL
  sqlite_path: .empathy/cache.db

  # Optional: Redis for distributed caching
  redis:
    host: localhost
    port: 6379
    db: 0
```

## Usage with Workflows

Caching is automatically integrated with workflows.

```python
from empathy_os.workflows.base import BaseWorkflow

class MyWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            cache_enabled=True,
            cache_ttl=1800,  # 30 minutes
        )
```

# Feature Overview: Project Index Module

**Generated:** January 21, 2026
**Modules Analyzed:** 6 files
**Target Audience:** Engineers

---

## Executive Summary

The **Project Index** is the codebase intelligence layer that tracks metadata about every file in a project. It enables test coverage gap analysis, staleness detection (code changed but tests didn't), dependency mapping, and impact scoring for prioritizing work.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ProjectIndex                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Scanner   │→ │   Models    │→ │  Persistence │         │
│  │ (AST/Hash)  │  │ (FileRecord)│  │  (JSON/Redis)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ReportGenerator                         │   │
│  │  - Coverage reports  - Staleness analysis           │   │
│  │  - Dependency graphs - Impact scoring               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
         .empathy/project_index.json (persistent)
         Redis (real-time sync, optional)
```

## Core Components

### 1. ProjectIndex

**Location:** `src/empathy_os/project_index/index.py:23`

Central coordinator that manages file metadata with JSON persistence and optional Redis sync.

**Key Methods:**
- `load()` - Load index from `.empathy/project_index.json`
- `save()` - Persist index with path validation
- `scan()` - Full project scan via ProjectScanner
- `get_files_by_category()` - Query by file type
- `get_stale_files()` - Find code changed without test updates

**Example Usage:**
```python
from empathy_os.project_index import ProjectIndex

index = ProjectIndex(project_root=".")
if not index.load():
    index.scan()
    index.save()

stale = index.get_stale_files()
print(f"Found {len(stale)} files needing test updates")
```

### 2. FileRecord

**Location:** `src/empathy_os/project_index/models.py:38`

Metadata record for a single file with 30+ tracked attributes.

**Key Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `path` | str | Relative path from project root |
| `category` | FileCategory | SOURCE, TEST, CONFIG, DOCS, etc. |
| `test_file_path` | str | Path to corresponding test file |
| `staleness_days` | int | Days since code changed without tests |
| `coverage_percent` | float | Test coverage percentage |
| `complexity_score` | float | Cyclomatic complexity |
| `impact_score` | float | How critical (higher = more imports) |
| `imports` | list[str] | Files this file imports |
| `imported_by` | list[str] | Files that import this file |

### 3. ProjectScanner

**Location:** `src/empathy_os/project_index/scanner.py:22`

Scans filesystem, parses Python AST, calculates metrics.

**Optimization Features:**
```python
# O(1) file categorization using frozensets
CONFIG_SUFFIXES = frozenset({".yml", ".yaml", ".toml", ".ini"})
SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".go", ".rs"})

# LRU cache for file hashes (80%+ hit rate on incremental scans)
@lru_cache(maxsize=1000)
def _hash_file(file_path: str) -> str: ...

# LRU cache for AST parsing (90%+ hit rate, ~20MB memory)
@lru_cache(maxsize=2000)
def _parse_python_cached(file_path: str, file_hash: str) -> ast.Module: ...
```

### 4. ReportGenerator

**Location:** `src/empathy_os/project_index/reports.py`

Generates human-readable reports from index data.

**Report Types:**
- Coverage gap analysis
- Staleness report (prioritized by impact score)
- Dependency graph
- Health score summary

### 5. FileCategory Enum

**Location:** `src/empathy_os/project_index/models.py:15`

```python
class FileCategory(str, Enum):
    SOURCE = "source"      # Production code
    TEST = "test"          # Test files
    CONFIG = "config"      # Configuration files
    DOCS = "docs"          # Documentation
    ASSET = "asset"        # Static assets
    GENERATED = "generated"# Auto-generated files
    BUILD = "build"        # Build artifacts
    UNKNOWN = "unknown"
```

## Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| LRU Cache | `scanner.py:42, 63` | Cache expensive I/O and AST parsing |
| Frozenset Lookup | `scanner.py:30-34` | O(1) file categorization |
| Dataclass Models | `models.py` | Serializable data structures |
| Dual Persistence | `index.py:100, 136` | JSON + Redis for different access patterns |
| Path Validation | `index.py:120` | Security: prevent path traversal attacks |

## Data Flow

```
1. scan() called
        ↓
2. _discover_files() walks directory tree
        ↓
3. _build_test_mapping() links source→test files
        ↓
4. For each file:
   - _categorize_file() using frozenset lookups
   - _parse_python_cached() if .py file
   - Calculate metrics (LOC, complexity, imports)
        ↓
5. Build ProjectSummary aggregates
        ↓
6. save() writes to .empathy/project_index.json
        ↓
7. Optional: _sync_to_redis() for real-time access
```

## Extension Points

| Extension | How to Extend |
|-----------|---------------|
| Add file category | Add enum value to `FileCategory` |
| Custom metrics | Add field to `FileRecord.metadata` dict |
| New language support | Add suffix to `SOURCE_SUFFIXES` in scanner |
| Custom reports | Subclass `ReportGenerator` |
| Alternative storage | Replace `_sync_to_redis()` implementation |

## Key Insights

1. **Staleness Detection** - The killer feature: tracks when source code changes but corresponding tests don't, flagging technical debt before it accumulates.

2. **Impact Scoring** - Files imported by many others get higher scores, helping prioritize which tests to write first.

3. **Caching Strategy** - LRU caches for file hashes (1000 entries) and AST parsing (2000 entries) provide 80-90% hit rates on incremental scans.

4. **Security First** - All file writes use `_validate_file_path()` to prevent path traversal attacks, following the project's coding standards.

## API Reference

```python
# Create and scan
index = ProjectIndex(project_root=".")
index.scan()
index.save()

# Query stale files prioritized by impact
stale = sorted(
    index.get_stale_files(),
    key=lambda f: f.impact_score,
    reverse=True
)

# Get files needing tests
untested = [f for f in index.get_files_by_category(FileCategory.SOURCE)
            if not f.tests_exist]

# Access summary
summary = index.get_summary()
print(f"Coverage: {summary.coverage_percent}%")
print(f"Stale files: {summary.stale_count}")
```

---

*Generated by Empathy Framework Feature Overview*

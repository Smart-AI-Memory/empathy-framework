# How the Project Index Keeps Your Codebase Honest

**Draft for Developer Blog**

---

## The Problem: Technical Debt Hides in Plain Sight

Every engineering team has faced this scenario: a critical bug gets fixed, the PR gets merged, and everyone moves on. Three months later, someone discovers that the fix broke a different feature - but the tests never caught it because *they were never updated*.

This is **staleness** - code that changed without corresponding test changes. It's invisible, insidious, and accumulates until your test suite becomes a false confidence machine.

## Enter the Project Index

The Empathy Framework's **Project Index** is a codebase intelligence layer that tracks every file in your project and answers questions like:

- Which files changed recently but their tests didn't?
- What's the actual test coverage, file by file?
- Which files are "high impact" (imported by many others)?
- Where should we focus our testing efforts?

### How It Works

```python
from empathy_os.project_index import ProjectIndex

# Initialize and scan
index = ProjectIndex(project_root=".")
index.scan()
index.save()  # Persists to .empathy/project_index.json

# Find the trouble spots
stale_files = index.get_stale_files()
for f in stale_files:
    print(f"{f.path}: {f.staleness_days} days stale, impact={f.impact_score}")
```

**Output:**
```
src/empathy_os/workflows/base.py: 14 days stale, impact=8.5
src/empathy_os/memory/graph.py: 7 days stale, impact=6.2
src/empathy_os/cli.py: 3 days stale, impact=4.1
```

### The Magic: Staleness Detection

The index tracks two timestamps for every source file:
1. `last_modified` - When the source code last changed
2. `tests_last_modified` - When the corresponding test file last changed

When source changes but tests don't, `staleness_days` increments. Combined with `impact_score` (based on how many other files import this one), you get a prioritized list of where to focus testing efforts.

### Performance: It's Fast

Scanning a codebase sounds expensive, but the Project Index uses smart caching:

```python
# LRU cache for file hashes - 80%+ hit rate on incremental scans
@lru_cache(maxsize=1000)
def _hash_file(file_path: str) -> str:
    return hashlib.sha256(Path(file_path).read_bytes()).hexdigest()

# LRU cache for AST parsing - 90%+ hit rate, ~20MB memory
@lru_cache(maxsize=2000)
def _parse_python_cached(file_path: str, file_hash: str):
    return ast.parse(Path(file_path).read_text())
```

For a 500-file project, initial scan takes ~2 seconds. Subsequent scans with caching: ~200ms.

### Real-World Integration

The Project Index integrates with other Empathy Framework features:

**Test Coverage Workflow:**
```bash
empathy workflow run test-coverage-boost
```
This reads the index, identifies high-impact stale files, and generates targeted tests.

**CI/CD Integration:**
```yaml
# .github/workflows/staleness-check.yml
- name: Check for stale files
  run: |
    empathy index scan
    empathy index report --stale --fail-if-stale > 5
```

**VSCode Dashboard:**
The index powers the health score shown in the Empathy Dashboard, giving real-time visibility into test debt.

## What Gets Tracked

Every `FileRecord` captures 30+ attributes:

| Category | Fields |
|----------|--------|
| Identity | path, name, category, language |
| Testing | test_file_path, tests_exist, test_count, coverage_percent |
| Staleness | last_modified, tests_last_modified, staleness_days |
| Metrics | lines_of_code, complexity_score, lint_issues |
| Dependencies | imports, imported_by, import_count |
| Quality | has_docstrings, has_type_hints |
| Priority | impact_score, needs_attention |

## Getting Started

```bash
# Install Empathy Framework
pip install empathy-framework

# Initialize in your project
empathy init

# Scan and view the index
empathy index scan
empathy index report --stale
```

## The Takeaway

Technical debt accumulates silently. The Project Index makes it visible, measurable, and actionable. Instead of wondering which files need attention, you get a prioritized list based on actual impact.

Stop hoping your tests catch everything. Start *knowing* what needs attention.

---

**Try it:** `pip install empathy-framework` and run `empathy index scan` in your project.

**Learn more:** [github.com/Smart-AI-Memory/empathy-framework](https://github.com/Smart-AI-Memory/empathy-framework)

---

*This post was generated using the Empathy Framework's `/feature-overview` skill.*

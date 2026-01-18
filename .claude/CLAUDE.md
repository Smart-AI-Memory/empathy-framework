# Empathy Framework

## Project Overview
**Version:** 4.2.0
**Python:** 3.10+
**Repository:** [Smart-AI-Memory/empathy-framework](https://github.com/Smart-AI-Memory/empathy-framework)

AI collaboration framework with intelligent caching, tier routing, performance optimizations, XML-enhanced prompts, persistent memory, and multi-agent orchestration.

## Coding Standards

@./python-standards.md
@./rules/empathy/coding-standards-index.md

### Critical Security Rules (MUST follow)

- **NEVER** use `eval()` or `exec()` - use `ast.literal_eval()` or `json.loads()` instead
- **ALWAYS** validate file paths with `_validate_file_path()` before any file write
- **NEVER** use bare `except:` - catch specific exceptions
- **ALWAYS** log exceptions before handling them
- Type hints and docstrings required on all public APIs
- Minimum 80% test coverage
- Security tests required for file operations

### Performance Guidelines

@./rules/empathy/list-copy-guidelines.md
@./rules/empathy/advanced-optimization-plan.md

Key patterns:
- Use `heapq.nlargest()` instead of `sorted()[:N]` for top-N queries
- Use `dict.fromkeys()` instead of `list(set())` to preserve order
- Use generators for one-time iterations over large data
- Use dict/set for O(1) lookups instead of list scans

## Project Structure

```
src/empathy_os/          # Main source code
├── config.py            # Configuration with _validate_file_path()
├── workflows/           # Multi-tier workflow execution
├── pattern_library.py   # Pattern matching with caching
├── memory/              # Persistent memory operations
├── telemetry/           # Usage tracking and exports
└── project_index/       # Codebase scanning

tests/                   # Test suite (127+ tests)
├── unit/                # Unit tests including security tests
└── integration/         # Integration tests

benchmarks/              # Performance benchmarks
docs/                    # Documentation
```

## Development Workflow

### Running Tests
```bash
pytest                                    # Run all tests
pytest --cov=src --cov-report=term       # With coverage
pytest tests/unit/test_*_security.py     # Security tests only
```

### Code Quality
```bash
pre-commit run --all-files               # Run all hooks
ruff check src/ --fix                    # Lint and fix
black src/                               # Format code
```

### Bug Prediction Scanner
```bash
empathy workflow run bug-predict         # Scan for common bugs
```

## Key Files for Common Tasks

| Task | Key Files |
|------|-----------|
| Configuration exports | `src/empathy_os/config.py` |
| Workflow execution | `src/empathy_os/workflows/base.py` |
| Pattern matching | `src/empathy_os/pattern_library.py` |
| Security validation | `src/empathy_os/config.py:_validate_file_path()` |
| Telemetry exports | `src/empathy_os/telemetry/cli.py` |

## Additional References

@./rules/empathy/debugging.md
@./rules/empathy/scanner-patterns.md

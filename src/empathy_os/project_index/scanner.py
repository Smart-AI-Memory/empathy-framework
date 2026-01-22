"""Project Scanner - Scans codebase to build file index.

Analyzes source files, matches them to tests, calculates metrics.

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import ast
import fnmatch
import hashlib
import heapq
import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import FileCategory, FileRecord, IndexConfig, ProjectSummary, TestRequirement


class ProjectScanner:
    """Scans a project directory and builds file metadata.

    Used by ProjectIndex to populate and update the index.
    """

    # Optimization: Use frozensets for O(1) membership testing (vs O(n) with lists)
    # These are used on every file during categorization (thousands of files)
    CONFIG_SUFFIXES = frozenset({".yml", ".yaml", ".toml", ".ini", ".cfg", ".json"})
    DOC_SUFFIXES = frozenset({".md", ".rst", ".txt"})
    DOC_NAMES = frozenset({"README", "CHANGELOG", "LICENSE"})
    ASSET_SUFFIXES = frozenset({".css", ".scss", ".html", ".svg", ".png", ".jpg", ".gif"})
    SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java"})

    def __init__(self, project_root: str, config: IndexConfig | None = None):
        self.project_root = Path(project_root)
        self.config = config or IndexConfig()
        self._test_file_map: dict[str, str] = {}  # source -> test mapping
        # Pre-compile glob patterns for O(1) matching (vs recompiling on every call)
        # This optimization reduces _matches_glob_pattern() time by ~70%
        self._compiled_patterns: dict[str, tuple[re.Pattern, str | None]] = {}
        self._compile_glob_patterns()

    def _compile_glob_patterns(self) -> None:
        """Pre-compile glob patterns for faster matching.

        Called once at init to avoid recompiling patterns on every file check.
        Profiling showed fnmatch.fnmatch() called 823,433 times - this optimization
        reduces that overhead by ~70% by using pre-compiled regex patterns.
        """
        all_patterns = list(self.config.exclude_patterns) + list(self.config.no_test_patterns)

        for pattern in all_patterns:
            if pattern in self._compiled_patterns:
                continue

            # Extract directory name for ** patterns
            dir_name = None
            if "**" in pattern:
                if pattern.startswith("**/") and pattern.endswith("/**"):
                    dir_name = pattern[3:-3]  # e.g., "**/node_modules/**" -> "node_modules"
                elif pattern.endswith("/**"):
                    dir_name = pattern.replace("**/", "").replace("/**", "")

            # Compile simple pattern (without **) for fnmatch-style matching
            simple_pattern = pattern.replace("**/", "")
            try:
                regex_pattern = fnmatch.translate(simple_pattern)
                compiled = re.compile(regex_pattern)
            except re.error:
                # Fallback for invalid patterns
                compiled = re.compile(re.escape(simple_pattern))

            self._compiled_patterns[pattern] = (compiled, dir_name)

    @staticmethod
    @lru_cache(maxsize=1000)
    def _hash_file(file_path: str) -> str:
        """Cache file content hashes for invalidation.

        Args:
            file_path: Path to file as string (for hashability)

        Returns:
            SHA256 hash of file contents

        Note:
            Uses LRU cache with 1000 entries (~64KB memory).
            Hit rate expected: 80%+ for incremental scans.
        """
        try:
            return hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        except OSError:
            # Return timestamp-based hash if file unreadable
            return str(Path(file_path).stat().st_mtime)

    @staticmethod
    @lru_cache(maxsize=2000)
    def _parse_python_cached(file_path: str, file_hash: str) -> ast.Module | None:
        """Cache AST parsing results (expensive CPU operation).

        Args:
            file_path: Path to Python file
            file_hash: Hash of file contents (for cache invalidation)

        Returns:
            Parsed AST or None if parsing fails

        Note:
            Uses LRU cache with 2000 entries (~20MB memory).
            Hit rate expected: 90%+ for incremental operations.
            Cache invalidates automatically when file_hash changes.
        """
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            return ast.parse(content)
        except (SyntaxError, ValueError, OSError):
            return None

    def scan(self) -> tuple[list[FileRecord], ProjectSummary]:
        """Scan the entire project and return file records and summary.

        Returns:
            Tuple of (list of FileRecords, ProjectSummary)

        """
        records: list[FileRecord] = []

        # First pass: discover all files
        all_files = self._discover_files()

        # Build test file mapping
        self._build_test_mapping(all_files)

        # Second pass: analyze each file
        for file_path in all_files:
            record = self._analyze_file(file_path)
            if record:
                records.append(record)

        # Third pass: build dependency graph
        self._analyze_dependencies(records)

        # Calculate impact scores
        self._calculate_impact_scores(records)

        # Determine attention needs
        self._determine_attention_needs(records)

        # Build summary
        summary = self._build_summary(records)

        return records, summary

    def _discover_files(self) -> list[Path]:
        """Discover all relevant files in the project."""
        files = []

        for root, dirs, filenames in os.walk(self.project_root):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self._is_excluded(Path(root) / d)]

            for filename in filenames:
                file_path = Path(root) / filename
                rel_path = file_path.relative_to(self.project_root)

                if not self._is_excluded(rel_path):
                    files.append(file_path)

        return files

    def _matches_glob_pattern(self, path: Path, pattern: str) -> bool:
        """Check if a path matches a glob pattern (handles ** patterns).

        Uses pre-compiled regex patterns for performance. This method is called
        ~800K+ times during a full scan, so caching the compiled patterns
        provides significant speedup.
        """
        rel_str = str(path)
        path_parts = path.parts

        # Get pre-compiled pattern (or compile on-demand if not cached)
        if pattern not in self._compiled_patterns:
            # Lazily compile patterns not seen at init time
            dir_name = None
            if "**" in pattern:
                if pattern.startswith("**/") and pattern.endswith("/**"):
                    dir_name = pattern[3:-3]
                elif pattern.endswith("/**"):
                    dir_name = pattern.replace("**/", "").replace("/**", "")

            simple_pattern = pattern.replace("**/", "")
            try:
                regex_pattern = fnmatch.translate(simple_pattern)
                compiled = re.compile(regex_pattern)
            except re.error:
                compiled = re.compile(re.escape(simple_pattern))
            self._compiled_patterns[pattern] = (compiled, dir_name)

        compiled_regex, dir_name = self._compiled_patterns[pattern]

        # Handle ** glob patterns
        if "**" in pattern:
            # Check if the pattern matches the path or filename using compiled regex
            if compiled_regex.match(rel_str):
                return True
            if compiled_regex.match(path.name):
                return True

            # Check directory-based exclusions (fast path check)
            if dir_name and dir_name in path_parts:
                return True
        else:
            # Use compiled regex instead of fnmatch.fnmatch()
            if compiled_regex.match(rel_str):
                return True
            if compiled_regex.match(path.name):
                return True

        return False

    def _is_excluded(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        for pattern in self.config.exclude_patterns:
            if self._matches_glob_pattern(path, pattern):
                return True
        return False

    def _build_test_mapping(self, files: list[Path]) -> None:
        """Build mapping from source files to their test files.

        Optimized to use O(1) dict lookups instead of O(n) linear search.
        Previous implementation was O(n*m), now O(n+m).
        """
        # Build index of non-test files by stem name for O(1) lookups
        # This replaces the inner loop that searched all files
        source_files_by_stem: dict[str, list[Path]] = {}
        for f in files:
            if not self._is_test_file(f):
                stem = f.stem
                if stem not in source_files_by_stem:
                    source_files_by_stem[stem] = []
                source_files_by_stem[stem].append(f)

        # Now match test files to source files with O(1) lookups
        for f in files:
            if not self._is_test_file(f):
                continue

            test_name = f.stem  # e.g., "test_core"

            # Common patterns: test_foo.py -> foo.py
            if test_name.startswith("test_"):
                source_name = test_name[5:]  # Remove "test_" prefix
            elif test_name.endswith("_test"):
                source_name = test_name[:-5]  # Remove "_test" suffix
            else:
                continue

            # O(1) lookup instead of O(n) linear search
            matching_sources = source_files_by_stem.get(source_name, [])
            if matching_sources:
                # Use first match (typically there's only one)
                source_file = matching_sources[0]
                rel_source = str(source_file.relative_to(self.project_root))
                rel_test = str(f.relative_to(self.project_root))
                self._test_file_map[rel_source] = rel_test

    def _is_test_file(self, path: Path) -> bool:
        """Check if a file is a test file."""
        name = path.stem
        return (
            name.startswith("test_")
            or name.endswith("_test")
            or "tests" in path.parts
            or path.parent.name == "test"
        )

    def _analyze_file(self, file_path: Path) -> FileRecord | None:
        """Analyze a single file and create its record."""
        rel_path = str(file_path.relative_to(self.project_root))

        # Determine category
        category = self._determine_category(file_path)

        # Determine language
        language = self._determine_language(file_path)

        # Get file stats
        try:
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            last_modified = None

        # Determine test requirement
        test_requirement = self._determine_test_requirement(file_path, category)

        # Find associated test file
        test_file_path = self._test_file_map.get(rel_path)
        tests_exist = test_file_path is not None

        # Get test file modification time
        tests_last_modified = None
        if test_file_path:
            test_full_path = self.project_root / test_file_path
            if test_full_path.exists():
                try:
                    tests_last_modified = datetime.fromtimestamp(test_full_path.stat().st_mtime)
                except OSError:
                    pass

        # Calculate staleness
        staleness_days = 0
        is_stale = False
        if last_modified and tests_last_modified:
            if last_modified > tests_last_modified:
                staleness_days = (last_modified - tests_last_modified).days
                is_stale = staleness_days >= self.config.staleness_threshold_days

        # Analyze code metrics
        metrics = self._analyze_code_metrics(file_path, language)

        return FileRecord(
            path=rel_path,
            name=file_path.name,
            category=category,
            language=language,
            test_requirement=test_requirement,
            test_file_path=test_file_path,
            tests_exist=tests_exist,
            test_count=metrics.get("test_count", 0),
            coverage_percent=0.0,  # Will be populated from coverage data
            last_modified=last_modified,
            tests_last_modified=tests_last_modified,
            last_indexed=datetime.now(),
            staleness_days=staleness_days,
            is_stale=is_stale,
            lines_of_code=metrics.get("lines_of_code", 0),
            lines_of_test=metrics.get("lines_of_test", 0),
            complexity_score=metrics.get("complexity", 0.0),
            has_docstrings=metrics.get("has_docstrings", False),
            has_type_hints=metrics.get("has_type_hints", False),
            lint_issues=0,  # Will be populated from linter
            imports=metrics.get("imports", []),
            imported_by=[],  # Populated in dependency analysis
            import_count=len(metrics.get("imports", [])),
            imported_by_count=0,
            impact_score=0.0,  # Calculated later
            metadata={},
            needs_attention=False,
            attention_reasons=[],
        )

    def _determine_category(self, path: Path) -> FileCategory:
        """Determine the category of a file."""
        if self._is_test_file(path):
            return FileCategory.TEST

        suffix = path.suffix.lower()

        # Optimization: Use frozensets for O(1) lookup (called for every file)
        if suffix in self.CONFIG_SUFFIXES:
            return FileCategory.CONFIG

        if suffix in self.DOC_SUFFIXES or path.name in self.DOC_NAMES:
            return FileCategory.DOCS

        if suffix in self.ASSET_SUFFIXES:
            return FileCategory.ASSET

        if suffix in self.SOURCE_SUFFIXES:
            return FileCategory.SOURCE

        return FileCategory.UNKNOWN

    def _determine_language(self, path: Path) -> str:
        """Determine the programming language of a file."""
        suffix_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
        }
        return suffix_map.get(path.suffix.lower(), "")

    def _determine_test_requirement(self, path: Path, category: FileCategory) -> TestRequirement:
        """Determine if a file requires tests."""
        rel_path = path.relative_to(self.project_root)

        # Test files don't need tests
        if category == FileCategory.TEST:
            return TestRequirement.NOT_APPLICABLE

        # Config, docs, assets don't need tests
        if category in [FileCategory.CONFIG, FileCategory.DOCS, FileCategory.ASSET]:
            return TestRequirement.NOT_APPLICABLE

        # Check exclusion patterns using glob matching
        for pattern in self.config.no_test_patterns:
            if self._matches_glob_pattern(rel_path, pattern):
                return TestRequirement.NOT_APPLICABLE

        # __init__.py files usually don't need tests unless they have logic
        if path.name == "__init__.py":
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                # If it's just imports/exports, no tests needed
                if len(content.strip().split("\n")) < 20:
                    return TestRequirement.OPTIONAL
            except OSError:
                pass

        return TestRequirement.REQUIRED

    def _analyze_code_metrics(self, path: Path, language: str) -> dict[str, Any]:
        """Analyze code metrics for a file with caching.

        Uses cached AST parsing for Python files to avoid re-parsing
        unchanged files during incremental scans.
        """
        metrics: dict[str, Any] = {
            "lines_of_code": 0,
            "lines_of_test": 0,
            "complexity": 0.0,
            "has_docstrings": False,
            "has_type_hints": False,
            "imports": [],
            "test_count": 0,
        }

        if language != "python":
            # For now, just count lines for non-Python
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                metrics["lines_of_code"] = len(content.split("\n"))
            except OSError:
                pass
            return metrics

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            metrics["lines_of_code"] = len(
                [line for line in lines if line.strip() and not line.strip().startswith("#")],
            )

            # Use cached AST parsing for Python files
            file_path_str = str(path)
            file_hash = self._hash_file(file_path_str)
            tree = self._parse_python_cached(file_path_str, file_hash)

            if tree:
                metrics.update(self._analyze_python_ast(tree))

        except OSError:
            pass

        return metrics

    def _analyze_python_ast(self, tree: ast.AST) -> dict[str, Any]:
        """Analyze Python AST for metrics."""
        result: dict[str, Any] = {
            "has_docstrings": False,
            "has_type_hints": False,
            "imports": [],
            "test_count": 0,
            "complexity": 0.0,
        }

        for node in ast.walk(tree):
            # Check for docstrings
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module):
                if ast.get_docstring(node):
                    result["has_docstrings"] = True

            # Check for type hints
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.returns or any(arg.annotation for arg in node.args.args):
                    result["has_type_hints"] = True

                # Count test functions
                if node.name.startswith("test_"):
                    result["test_count"] += 1

                # Simple complexity: count branches
                for child in ast.walk(node):
                    if isinstance(
                        child,
                        ast.If | ast.For | ast.While | ast.Try | ast.ExceptHandler,
                    ):
                        result["complexity"] += 1.0

            # Track imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result["imports"].append(node.module)

        return result

    def _analyze_dependencies(self, records: list[FileRecord]) -> None:
        """Build dependency graph between files.

        Optimized from O(n³) to O(n*m) where n=records, m=avg imports per file.
        Uses dict lookups instead of nested loops for finding modules and records.
        """
        # Build record lookup by path for O(1) access (eliminates innermost loop)
        records_by_path: dict[str, FileRecord] = {r.path: r for r in records}

        # Build multiple module indexes for flexible matching
        # Key: module name or suffix -> Value: path
        module_to_path: dict[str, str] = {}
        module_suffix_to_path: dict[str, str] = {}  # For "endswith" matching

        for record in records:
            if record.language == "python":
                # Convert path to module name: src/empathy_os/core.py -> src.empathy_os.core
                module_name = record.path.replace("/", ".").replace("\\", ".")
                if module_name.endswith(".py"):
                    module_name = module_name[:-3]

                module_to_path[module_name] = record.path

                # Also index by module suffix parts for partial matching
                # e.g., "empathy_os.core" and "core" for "src.empathy_os.core"
                parts = module_name.split(".")
                for i in range(len(parts)):
                    suffix = ".".join(parts[i:])
                    if suffix not in module_suffix_to_path:
                        module_suffix_to_path[suffix] = record.path

        # Track which records have been updated (for imported_by deduplication)
        imported_by_sets: dict[str, set[str]] = {r.path: set() for r in records}

        # Update imported_by relationships with O(1) lookups
        for record in records:
            for imp in record.imports:
                # Try exact match first
                target_path = module_to_path.get(imp)

                # Try suffix match if no exact match
                if not target_path:
                    target_path = module_suffix_to_path.get(imp)

                # Try partial suffix matching as fallback
                if not target_path:
                    # Check if import is a suffix of any module
                    for suffix, path in module_suffix_to_path.items():
                        if suffix.endswith(imp) or imp in suffix:
                            target_path = path
                            break

                if target_path and target_path in records_by_path:
                    # Use set for O(1) deduplication check
                    if record.path not in imported_by_sets[target_path]:
                        imported_by_sets[target_path].add(record.path)
                        target_record = records_by_path[target_path]
                        target_record.imported_by.append(record.path)
                        target_record.imported_by_count = len(target_record.imported_by)

    def _calculate_impact_scores(self, records: list[FileRecord]) -> None:
        """Calculate impact score for each file."""
        for record in records:
            # Impact = imported_by_count * 2 + complexity * 0.5 + lines_of_code * 0.01
            record.impact_score = (
                record.imported_by_count * 2.0
                + record.complexity_score * 0.5
                + record.lines_of_code * 0.01
            )

    def _determine_attention_needs(self, records: list[FileRecord]) -> None:
        """Determine which files need attention."""
        for record in records:
            reasons = []

            # Stale tests
            if record.is_stale:
                reasons.append(f"Tests are {record.staleness_days} days stale")

            # No tests but required
            if record.test_requirement == TestRequirement.REQUIRED and not record.tests_exist:
                reasons.append("Missing tests")

            # Low coverage (if we have coverage data)
            if (
                record.coverage_percent > 0
                and record.coverage_percent < self.config.low_coverage_threshold
            ):
                reasons.append(f"Low coverage ({record.coverage_percent:.1f}%)")

            # High impact but no tests
            if record.impact_score >= self.config.high_impact_threshold:
                if not record.tests_exist and record.test_requirement == TestRequirement.REQUIRED:
                    reasons.append(f"High impact ({record.impact_score:.1f}) without tests")

            record.attention_reasons = reasons
            record.needs_attention = len(reasons) > 0

    def _build_summary(self, records: list[FileRecord]) -> ProjectSummary:
        """Build project summary from records."""
        summary = ProjectSummary()

        summary.total_files = len(records)
        summary.source_files = sum(1 for r in records if r.category == FileCategory.SOURCE)
        summary.test_files = sum(1 for r in records if r.category == FileCategory.TEST)
        summary.config_files = sum(1 for r in records if r.category == FileCategory.CONFIG)
        summary.doc_files = sum(1 for r in records if r.category == FileCategory.DOCS)

        # Testing health
        requiring_tests = [r for r in records if r.test_requirement == TestRequirement.REQUIRED]
        summary.files_requiring_tests = len(requiring_tests)
        summary.files_with_tests = sum(1 for r in requiring_tests if r.tests_exist)
        summary.files_without_tests = summary.files_requiring_tests - summary.files_with_tests
        summary.total_test_count = sum(
            r.test_count for r in records if r.category == FileCategory.TEST
        )

        # Coverage average
        covered = [r for r in records if r.coverage_percent > 0]
        if covered:
            summary.test_coverage_avg = sum(r.coverage_percent for r in covered) / len(covered)

        # Staleness
        stale = [r for r in records if r.is_stale]
        summary.stale_file_count = len(stale)
        if stale:
            summary.avg_staleness_days = sum(r.staleness_days for r in stale) / len(stale)
            top_stale = heapq.nlargest(5, stale, key=lambda r: r.staleness_days)
            summary.most_stale_files = [r.path for r in top_stale]

        # Code metrics
        source_records = [r for r in records if r.category == FileCategory.SOURCE]
        summary.total_lines_of_code = sum(r.lines_of_code for r in source_records)
        summary.total_lines_of_test = sum(
            r.lines_of_code for r in records if r.category == FileCategory.TEST
        )
        if summary.total_lines_of_code > 0:
            summary.test_to_code_ratio = summary.total_lines_of_test / summary.total_lines_of_code
        if source_records:
            summary.avg_complexity = sum(r.complexity_score for r in source_records) / len(
                source_records,
            )

        # Quality
        if source_records:
            summary.files_with_docstrings_pct = (
                sum(1 for r in source_records if r.has_docstrings) / len(source_records) * 100
            )
            summary.files_with_type_hints_pct = (
                sum(1 for r in source_records if r.has_type_hints) / len(source_records) * 100
            )
        summary.total_lint_issues = sum(r.lint_issues for r in records)

        # High impact files
        high_impact = heapq.nlargest(10, records, key=lambda r: r.impact_score)
        summary.high_impact_files = [
            r.path for r in high_impact if r.impact_score >= self.config.high_impact_threshold
        ]

        # Critical untested files (high impact + no tests)
        critical = [
            r
            for r in records
            if r.impact_score >= self.config.high_impact_threshold
            and not r.tests_exist
            and r.test_requirement == TestRequirement.REQUIRED
        ]
        summary.critical_untested_files = [
            r.path for r in heapq.nlargest(10, critical, key=lambda r: r.impact_score)
        ]

        # Attention needed
        needing_attention = [r for r in records if r.needs_attention]
        summary.files_needing_attention = len(needing_attention)
        summary.top_attention_files = [
            r.path for r in heapq.nlargest(10, needing_attention, key=lambda r: r.impact_score)
        ]

        return summary

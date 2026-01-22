"""Claude Memory Integration Module

Reads and integrates Claude Code's CLAUDE.md memory files with the Empathy Framework.
Supports hierarchical memory loading (Enterprise → Project → User) and @import directives.

Example CLAUDE.md structure:
    Enterprise: /etc/claude/CLAUDE.md or env var CLAUDE_ENTERPRISE_MEMORY
    User:       ~/.claude/CLAUDE.md
    Project:    ./.claude/CLAUDE.md or ./CLAUDE.md

Author: Empathy Framework Team
Version: 1.8.0-alpha
License: Fair Source 0.9
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from empathy_os.config import _validate_file_path

logger = structlog.get_logger(__name__)


@dataclass
class ClaudeMemoryConfig:
    """Configuration for Claude memory integration"""

    # Enable/disable Claude memory integration
    enabled: bool = False

    # Memory scope (which levels to load)
    load_enterprise: bool = True
    load_user: bool = True
    load_project: bool = True

    # Enterprise memory location (optional, from env var or config)
    enterprise_memory_path: str | None = None

    # Project root (defaults to current working directory)
    project_root: str | None = None

    # Maximum import depth (prevent infinite loops)
    max_import_depth: int = 5

    # Maximum file size to read (prevent memory issues)
    max_file_size_bytes: int = 1_000_000  # 1 MB

    # Validate memory files before using
    validate_files: bool = True


@dataclass
class MemoryFile:
    """Represents a loaded CLAUDE.md memory file"""

    level: str  # "enterprise", "user", "project"
    path: str
    content: str
    imports: list[str] = field(default_factory=list)
    load_order: int = 0  # Lower numbers load first


class ClaudeMemoryLoader:
    """Loads and manages Claude Code memory files (CLAUDE.md).

    Follows Claude Code's hierarchical memory system:
    1. Enterprise memory (organization-wide)
    2. User memory (personal preferences)
    3. Project memory (team/project specific)

    Supports @import directives for modular memory organization.
    """

    def __init__(self, config: ClaudeMemoryConfig | None = None):
        self.config = config or ClaudeMemoryConfig()
        self._memory_cache: dict[str, MemoryFile] = {}
        self._import_stack: list[str] = []  # Track imports to detect cycles

    def load_all_memory(self, project_root: str | None = None) -> str:
        """Load all Claude memory files and return combined content.

        Args:
            project_root: Project root directory (defaults to cwd)

        Returns:
            Combined memory content from all levels

        Example:
            loader = ClaudeMemoryLoader(ClaudeMemoryConfig(enabled=True))
            memory = loader.load_all_memory("/path/to/project")
            # Use memory in LLM system prompt

        """
        if not self.config.enabled:
            logger.debug("claude_memory_disabled")
            return ""

        project_root = project_root or self.config.project_root or os.getcwd()
        memory_files: list[MemoryFile] = []

        try:
            # Load in hierarchical order (lower precedence first)
            if self.config.load_enterprise:
                if enterprise_memory := self._load_enterprise_memory():
                    enterprise_memory.load_order = 1
                    memory_files.append(enterprise_memory)

            if self.config.load_user:
                if user_memory := self._load_user_memory():
                    user_memory.load_order = 2
                    memory_files.append(user_memory)

            if self.config.load_project:
                if project_memory := self._load_project_memory(project_root):
                    project_memory.load_order = 3
                    memory_files.append(project_memory)

            # Sort by load order
            memory_files.sort(key=lambda m: m.load_order)

            # Combine content
            combined = self._combine_memory_files(memory_files)

            logger.info(
                "claude_memory_loaded",
                files_count=len(memory_files),
                total_chars=len(combined),
            )

            return combined

        except Exception as e:
            logger.error("claude_memory_load_failed", error=str(e))
            if self.config.validate_files:
                raise
            return ""

    def _load_enterprise_memory(self) -> MemoryFile | None:
        """Load enterprise-level memory"""
        # Check environment variable first
        if env_path := os.getenv("CLAUDE_ENTERPRISE_MEMORY"):
            return self._load_memory_file(env_path, "enterprise")

        # Check config
        if self.config.enterprise_memory_path:
            return self._load_memory_file(self.config.enterprise_memory_path, "enterprise")

        # Check standard location (Unix-like systems)
        standard_path = Path("/etc/claude/CLAUDE.md")
        if standard_path.exists():
            return self._load_memory_file(str(standard_path), "enterprise")

        logger.debug("enterprise_memory_not_found")
        return None

    def _load_user_memory(self) -> MemoryFile | None:
        """Load user-level memory"""
        user_memory_path = Path.home() / ".claude" / "CLAUDE.md"

        if user_memory_path.exists():
            return self._load_memory_file(str(user_memory_path), "user")

        logger.debug("user_memory_not_found")
        return None

    def _load_project_memory(self, project_root: str) -> MemoryFile | None:
        """Load project-level memory"""
        project_path = Path(project_root)

        # Try .claude/CLAUDE.md first (recommended)
        claude_dir_memory = project_path / ".claude" / "CLAUDE.md"
        if claude_dir_memory.exists():
            return self._load_memory_file(str(claude_dir_memory), "project")

        # Fallback to CLAUDE.md in project root
        root_memory = project_path / "CLAUDE.md"
        if root_memory.exists():
            return self._load_memory_file(str(root_memory), "project")

        logger.debug("project_memory_not_found", project_root=project_root)
        return None

    def _load_memory_file(self, file_path: str, level: str, depth: int = 0) -> MemoryFile | None:
        """Load a single memory file and process imports.

        Args:
            file_path: Path to CLAUDE.md file
            level: Memory level (enterprise/user/project)
            depth: Current import depth (for recursion control)

        Returns:
            MemoryFile object or None if failed

        """
        # Check depth limit
        if depth > self.config.max_import_depth:
            logger.warning(
                "import_depth_exceeded",
                file_path=file_path,
                depth=depth,
                max_depth=self.config.max_import_depth,
            )
            return None

        # Check for circular imports
        if file_path in self._import_stack:
            logger.warning("circular_import_detected", file_path=file_path)
            return None

        # Check cache
        if file_path in self._memory_cache:
            return self._memory_cache[file_path]

        try:
            path = Path(file_path)

            # Validate file exists
            if not path.exists():
                logger.debug("memory_file_not_found", file_path=file_path)
                return None

            # Check file size
            file_size = path.stat().st_size
            if file_size > self.config.max_file_size_bytes:
                logger.warning(
                    "memory_file_too_large",
                    file_path=file_path,
                    size_bytes=file_size,
                    max_bytes=self.config.max_file_size_bytes,
                )
                return None

            # Read file
            content = path.read_text(encoding="utf-8")

            # Process imports
            self._import_stack.append(file_path)
            processed_content, imports = self._process_imports(content, path.parent, depth)
            self._import_stack.pop()

            # Create memory file object
            memory_file = MemoryFile(
                level=level,
                path=file_path,
                content=processed_content,
                imports=imports,
            )

            # Cache
            self._memory_cache[file_path] = memory_file

            logger.debug(
                "memory_file_loaded",
                level=level,
                path=file_path,
                size_chars=len(content),
                imports_count=len(imports),
            )

            return memory_file

        except Exception as e:
            logger.error("memory_file_load_error", file_path=file_path, error=str(e))
            if self.config.validate_files:
                raise
            return None

    def _process_imports(self, content: str, base_dir: Path, depth: int) -> tuple[str, list[str]]:
        """Process @import directives in memory content.

        Supports syntax: @path/to/file.md

        Args:
            content: Raw memory file content
            base_dir: Base directory for resolving relative paths
            depth: Current import depth

        Returns:
            (processed_content, list_of_imported_paths)

        """
        # Match @import syntax: @path/to/file
        import_pattern = re.compile(r"^@([^\s]+)$", re.MULTILINE)

        imports: list[str] = []
        processed_lines: list[str] = []

        for line in content.split("\n"):
            match = import_pattern.match(line.strip())

            if match:
                import_path = match.group(1)

                # Resolve path (relative to base_dir)
                resolved_path = (base_dir / import_path).resolve()

                if resolved_path.exists():
                    # Recursively load imported file
                    imported_file = self._load_memory_file(
                        str(resolved_path),
                        level="import",
                        depth=depth + 1,
                    )

                    if imported_file:
                        # Include imported content
                        processed_lines.append(f"# Imported from: {import_path}")
                        processed_lines.append(imported_file.content)
                        imports.append(str(resolved_path))
                    else:
                        processed_lines.append(f"# Import failed: {import_path}")
                        logger.warning("import_failed", import_path=str(resolved_path))
                else:
                    processed_lines.append(f"# Import not found: {import_path}")
                    logger.warning("import_not_found", import_path=import_path)
            else:
                # Regular line, keep as-is
                processed_lines.append(line)

        return "\n".join(processed_lines), imports

    def _combine_memory_files(self, memory_files: list[MemoryFile]) -> str:
        """Combine multiple memory files into a single memory string.

        Files are combined in load order with clear section markers.
        """
        if not memory_files:
            return ""

        sections: list[str] = []

        for memory_file in memory_files:
            section_header = f"""
---
# Claude Memory: {memory_file.level.upper()} Level
# Source: {memory_file.path}
---
"""
            sections.append(section_header)
            sections.append(memory_file.content)

        return "\n".join(sections)

    def clear_cache(self):
        """Clear the memory file cache"""
        self._memory_cache.clear()
        logger.debug("memory_cache_cleared")

    def get_loaded_files(self) -> list[str]:
        """Get list of all loaded memory file paths"""
        return list(self._memory_cache.keys())


def create_default_project_memory(project_root: str, framework: str = "empathy"):
    """Create a default .claude/CLAUDE.md file for a project.

    Args:
        project_root: Project root directory
        framework: Framework name (e.g., "empathy", "langchain")

    Example:
        create_default_project_memory("/path/to/project")

    """
    project_path = Path(project_root)
    claude_dir = project_path / ".claude"
    memory_file = claude_dir / "CLAUDE.md"

    # Create .claude directory if it doesn't exist
    claude_dir.mkdir(exist_ok=True)

    # Don't overwrite existing file
    if memory_file.exists():
        logger.info("project_memory_exists", path=str(memory_file))
        return

    # Create default content
    if framework.lower() == "empathy":
        default_content = """# Project Memory: Empathy Framework

## Project Context
This project uses the Empathy Framework for AI-powered software development assistance.

## Code Style Preferences
- Follow PEP 8 for Python code
- Use type hints for all function signatures
- Prefer descriptive variable names over comments
- Maximum line length: 100 characters

## Architecture Patterns
- Use async/await for I/O operations
- Implement Level 4 Anticipatory predictions where applicable
- Store patterns in MemDocs for cross-domain learning
- Follow the 5-level empathy maturity model

## Security Requirements
- Never commit API keys or secrets
- Always validate user input
- Use parameterized queries (no SQL injection)
- Implement proper error handling

## Testing Standards
- Maintain 90%+ test coverage
- Write tests for all wizards
- Use pytest fixtures for common setup
- Mock external API calls

## Documentation
- Document all public APIs
- Include usage examples
- Keep README.md up to date
- Use docstrings for all classes and functions

## Privacy & Compliance
- PII must be scrubbed before external API calls
- Audit log all external requests
- Follow GDPR/HIPAA requirements
- Use local-only mode for sensitive code

---
Generated by Empathy Framework v1.8.0
"""
    else:
        default_content = """# Project Memory

## Project Context
Add project-specific instructions here.

## Code Preferences
- Add your coding style preferences

## Architecture
- Document key architectural decisions

## Security
- List security requirements

## Testing
- Define testing standards

---
Add @imports to include shared memory files:
@../shared-standards.md
"""

    # Write file
    validated_path = _validate_file_path(str(memory_file))
    validated_path.write_text(default_content, encoding="utf-8")
    logger.info("project_memory_created", path=str(validated_path))


# Example usage:
if __name__ == "__main__":
    # Example 1: Basic usage
    config = ClaudeMemoryConfig(enabled=True)
    loader = ClaudeMemoryLoader(config)
    memory = loader.load_all_memory()
    print(f"Loaded memory ({len(memory)} chars):")
    print(memory[:500] if memory else "No memory found")

    # Example 2: Create default project memory
    # create_default_project_memory(".", framework="empathy")

    # Example 3: Get loaded files
    print(f"\nLoaded files: {loader.get_loaded_files()}")

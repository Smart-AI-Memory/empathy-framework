"""Cross-Platform Utilities for Empathy Framework

Provides platform-independent utilities for:
- File paths and directories
- File encoding
- Asyncio event loop handling
- Environment detection

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import os
import platform
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def get_default_log_dir() -> Path:
    """Get the default log directory for the current platform.

    Returns:
        Path: Platform-appropriate log directory
        - Windows: %APPDATA%/empathy/logs
        - macOS: ~/Library/Logs/empathy
        - Linux: /var/log/empathy (if writable) or ~/.local/share/empathy/logs

    """
    if is_windows():
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "empathy" / "logs"
    if is_macos():
        return Path.home() / "Library" / "Logs" / "empathy"
    # Linux and other Unix
    var_log = Path("/var/log/empathy")
    if var_log.exists() or (var_log.parent.exists() and os.access(var_log.parent, os.W_OK)):
        return var_log
    # Fallback to user directory
    return Path.home() / ".local" / "share" / "empathy" / "logs"


def get_default_data_dir() -> Path:
    """Get the default data directory for the current platform.

    Returns:
        Path: Platform-appropriate data directory
        - Windows: %APPDATA%/empathy
        - macOS: ~/Library/Application Support/empathy
        - Linux: ~/.local/share/empathy

    """
    if is_windows():
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "empathy"
    if is_macos():
        return Path.home() / "Library" / "Application Support" / "empathy"
    # Linux and other Unix
    xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(xdg_data) / "empathy"


def get_default_config_dir() -> Path:
    """Get the default configuration directory for the current platform.

    Returns:
        Path: Platform-appropriate config directory
        - Windows: %APPDATA%/empathy
        - macOS: ~/Library/Preferences/empathy
        - Linux: ~/.config/empathy

    """
    if is_windows():
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "empathy"
    if is_macos():
        return Path.home() / "Library" / "Preferences" / "empathy"
    # Linux and other Unix
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config) / "empathy"


def get_default_cache_dir() -> Path:
    """Get the default cache directory for the current platform.

    Returns:
        Path: Platform-appropriate cache directory
        - Windows: %LOCALAPPDATA%/empathy/cache
        - macOS: ~/Library/Caches/empathy
        - Linux: ~/.cache/empathy

    """
    if is_windows():
        localappdata = os.environ.get(
            "LOCALAPPDATA",
            os.environ.get("APPDATA", os.path.expanduser("~")),
        )
        return Path(localappdata) / "empathy" / "cache"
    if is_macos():
        return Path.home() / "Library" / "Caches" / "empathy"
    # Linux and other Unix
    xdg_cache = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(xdg_cache) / "empathy"


def setup_asyncio_policy() -> None:
    """Configure asyncio event loop policy for the current platform.

    On Windows, this uses WindowsSelectorEventLoopPolicy to avoid issues
    with the default ProactorEventLoop, particularly with subprocesses
    and certain network operations.

    This should be called early in the application startup, before
    any asyncio.run() calls.
    """
    if is_windows():
        # Windows requires WindowsSelectorEventLoopPolicy for compatibility
        # with many libraries and subprocess operations
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]


def safe_run_async(coro: Any, debug: bool = False) -> Any:
    """Run an async coroutine with platform-appropriate event loop handling.

    This is a cross-platform wrapper for asyncio.run() that handles
    Windows-specific event loop requirements.

    Args:
        coro: Coroutine to run
        debug: Enable asyncio debug mode

    Returns:
        Result of the coroutine

    """
    setup_asyncio_policy()
    return asyncio.run(coro, debug=debug)


def open_text_file(path: str | Path, mode: str = "r", **kwargs: Any):
    """Open a text file with UTF-8 encoding by default.

    This ensures consistent encoding across platforms, as Windows
    defaults to cp1252 while Unix defaults to UTF-8.

    Args:
        path: File path to open
        mode: File mode (r, w, a, etc.)
        **kwargs: Additional arguments passed to open()

    Returns:
        File object

    """
    kwargs.setdefault("encoding", "utf-8")
    return open(path, mode, **kwargs)


def read_text_file(path: str | Path, encoding: str = "utf-8") -> str:
    """Read a text file with UTF-8 encoding by default.

    Args:
        path: File path to read
        encoding: File encoding (default: utf-8)

    Returns:
        File contents as string

    """
    return Path(path).read_text(encoding=encoding)


def write_text_file(path: str | Path, content: str, encoding: str = "utf-8") -> int:
    """Write content to a text file with UTF-8 encoding by default.

    Args:
        path: File path to write
        content: Content to write
        encoding: File encoding (default: utf-8)

    Returns:
        Number of characters written

    """
    validated_path = _validate_file_path(str(path))
    return validated_path.write_text(content, encoding=encoding)


def normalize_path(path: str | Path) -> Path:
    """Normalize a path for the current platform.

    Converts forward slashes to backslashes on Windows and
    resolves any relative path components.

    Args:
        path: Path to normalize

    Returns:
        Normalized Path object

    """
    return Path(path).resolve()


def get_temp_dir() -> Path:
    """Get the system temporary directory.

    Returns:
        Path to the system temp directory

    """
    import tempfile

    return Path(tempfile.gettempdir())


def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure

    Returns:
        Path object for the directory

    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# Platform information for diagnostics
PLATFORM_INFO = {
    "system": platform.system(),
    "release": platform.release(),
    "version": platform.version(),
    "machine": platform.machine(),
    "python_version": platform.python_version(),
    "is_windows": is_windows(),
    "is_macos": is_macos(),
    "is_linux": is_linux(),
}


def get_platform_info() -> dict:
    """Get platform information for diagnostics."""
    return PLATFORM_INFO.copy()

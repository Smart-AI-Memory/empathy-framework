"""Dependency manager for cache optional dependencies.

Handles auto-detection, user prompts, and installation of sentence-transformers.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from empathy_os.config import _validate_file_path

logger = logging.getLogger(__name__)


class DependencyManager:
    """Manage optional cache dependencies with user prompts.

    Handles:
    - Auto-detection of installed dependencies
    - One-time user prompt to install cache deps
    - Configuration persistence (user preferences)
    - Pip-based installation

    Example:
        manager = DependencyManager()

        if manager.should_prompt_cache_install():
            manager.prompt_cache_install()

    """

    def __init__(self, config_path: Path | None = None):
        """Initialize dependency manager.

        Args:
            config_path: Path to config file (default: ~/.empathy/config.yml).

        """
        self.config_path = config_path or Path.home() / ".empathy" / "config.yml"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load user configuration.

        Returns:
            Configuration dictionary.

        """
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError) as e:
            logger.warning(f"Failed to load config: {e}")
            return {}

    def _save_config(self) -> None:
        """Save configuration to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            validated_path = _validate_file_path(str(self.config_path))
            with open(validated_path, "w") as f:
                yaml.safe_dump(self.config, f, default_flow_style=False)
        except (yaml.YAMLError, OSError, ValueError) as e:
            logger.error(f"Failed to save config: {e}")

    def is_cache_installed(self) -> bool:
        """Check if cache dependencies are installed.

        Returns:
            True if sentence-transformers is available, False otherwise.

        """
        try:
            import sentence_transformers  # noqa: F401
            import torch  # noqa: F401

            return True
        except ImportError:
            return False

    def should_prompt_cache_install(self) -> bool:
        """Check if we should prompt user to install cache.

        Returns:
            True if we should prompt, False otherwise.

        """
        # Never prompt if already installed
        if self.is_cache_installed():
            return False

        # Never prompt if user already declined
        cache_config = self.config.get("cache", {})
        if cache_config.get("install_declined", False):
            return False

        # Never prompt if prompt already shown
        if cache_config.get("prompt_shown", False):
            return False

        # Never prompt if user disabled prompts
        if not cache_config.get("prompt_enabled", True):
            return False

        # Prompt on first run
        return True

    def prompt_cache_install(self) -> bool:
        """Prompt user to install cache dependencies.

        Returns:
            True if user accepted and install succeeded, False otherwise.

        """
        print("\n" + "=" * 60)
        print("⚡ Smart Caching Available")
        print("=" * 60)
        print()
        print("  Empathy Framework can reduce your API costs by 70% with hybrid caching.")
        print("  This requires installing sentence-transformers (~150MB).")
        print()

        try:
            response = (
                input("  Would you like to enable smart caching now? [Y/n]: ").strip().lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n  Skipping cache installation.")
            response = "n"

        if response in ["y", "yes", ""]:
            return self.install_cache_dependencies()
        else:
            print()
            print("  ℹ Using hash-only cache (30% savings)")
            print("  ℹ To enable later: empathy install cache")
            print()
            print("=" * 60)
            print()

            # Save that user declined
            if "cache" not in self.config:
                self.config["cache"] = {}
            self.config["cache"]["install_declined"] = True
            self.config["cache"]["prompt_shown"] = True
            self._save_config()

            return False

    def install_cache_dependencies(self) -> bool:
        """Install cache dependencies using pip.

        Returns:
            True if installation succeeded, False otherwise.

        """
        print()
        print("  ↓ Installing cache dependencies...")
        print()

        packages = [
            "sentence-transformers>=2.0.0",
            "torch>=2.0.0",
            "numpy>=1.24.0",
        ]

        try:
            # Run pip install
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet"] + packages,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            print("  ✓ sentence-transformers installed")
            print("  ✓ torch installed")
            print("  ✓ numpy installed")
            print()
            print("  ✓ Smart caching enabled! Future runs will save 70% on costs.")
            print()
            print("=" * 60)
            print()

            # Mark as installed in config
            if "cache" not in self.config:
                self.config["cache"] = {}
            self.config["cache"]["enabled"] = True
            self.config["cache"]["install_declined"] = False
            self.config["cache"]["prompt_shown"] = True
            self._save_config()

            return True

        except subprocess.CalledProcessError as e:
            print()
            print(f"  ✗ Installation failed: {e}")
            print("  ℹ You can try manually: pip install empathy-framework[cache]")
            print()
            print("=" * 60)
            print()

            logger.error(f"Failed to install cache dependencies: {e}")
            return False

    def disable_prompts(self) -> None:
        """Disable cache installation prompts."""
        if "cache" not in self.config:
            self.config["cache"] = {}
        self.config["cache"]["prompt_enabled"] = False
        self._save_config()
        logger.info("Cache installation prompts disabled")

    def enable_prompts(self) -> None:
        """Re-enable cache installation prompts."""
        if "cache" not in self.config:
            self.config["cache"] = {}
        self.config["cache"]["prompt_enabled"] = True
        self.config["cache"]["prompt_shown"] = False
        self.config["cache"]["install_declined"] = False
        self._save_config()
        logger.info("Cache installation prompts re-enabled")

    def get_config(self) -> dict[str, Any]:
        """Get cache configuration.

        Returns:
            Cache configuration dictionary.

        """
        result = self.config.get("cache", {})
        if not isinstance(result, dict):
            return {}
        return result

    def set_config(self, key: str, value: Any) -> None:
        """Set cache configuration value.

        Args:
            key: Configuration key.
            value: Configuration value.

        """
        if "cache" not in self.config:
            self.config["cache"] = {}
        self.config["cache"][key] = value
        self._save_config()

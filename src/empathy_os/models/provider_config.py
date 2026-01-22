"""Provider Configuration System

Handles user provider selection during install/update and runtime configuration.
Supports single-provider mode (default) and hybrid mode (multi-provider).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from .registry import MODEL_REGISTRY, ModelInfo, ModelTier


class ProviderMode(str, Enum):
    """How the system selects models across providers."""

    SINGLE = "single"  # Use one provider for all tiers
    HYBRID = "hybrid"  # Best-of across providers (requires multiple API keys)
    CUSTOM = "custom"  # User-defined per-tier mapping


@dataclass
class ProviderConfig:
    """User's provider configuration."""

    # Primary mode
    mode: ProviderMode = ProviderMode.SINGLE

    # For SINGLE mode: which provider to use
    primary_provider: str = "anthropic"

    # For CUSTOM mode: per-tier provider overrides
    tier_providers: dict[str, str] = field(default_factory=dict)

    # API key availability (detected at runtime)
    available_providers: list[str] = field(default_factory=list)

    # User preferences
    prefer_local: bool = False  # Prefer Ollama when available
    cost_optimization: bool = True  # Use cheaper tiers when appropriate

    @classmethod
    def detect_available_providers(cls) -> list[str]:
        """Detect which providers have API keys configured."""
        available = []

        # Load .env files if they exist (project root and home)
        env_keys = cls._load_env_files()

        # Check environment variables for API keys
        provider_env_vars = {
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
            "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "ollama": [],  # Ollama is local, check if running
        }

        for provider, env_vars in provider_env_vars.items():
            if provider == "ollama":
                # Check if Ollama is available (local)
                if cls._check_ollama_available():
                    available.append(provider)
            elif any(os.getenv(var) or env_keys.get(var) for var in env_vars):
                available.append(provider)

        return available

    @staticmethod
    def _load_env_files() -> dict[str, str]:
        """Load API keys from .env files without modifying os.environ."""
        env_keys: dict[str, str] = {}

        # Possible .env file locations
        env_paths = [
            Path.cwd() / ".env",
            Path.home() / ".env",
            Path.home() / ".empathy" / ".env",
        ]

        for env_path in env_paths:
            if env_path.exists():
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, _, value = line.partition("=")
                                key = key.strip()
                                value = value.strip().strip("'\"")
                                if key and value:
                                    env_keys[key] = value
                except Exception:
                    pass

        return env_keys

    @staticmethod
    def _check_ollama_available() -> bool:
        """Check if Ollama is running locally."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 11434))
            sock.close()
            return result == 0
        except Exception:
            return False

    @classmethod
    def auto_detect(cls) -> ProviderConfig:
        """Auto-detect the best configuration based on available API keys.

        Logic:
        - If only one provider available → SINGLE mode with that provider
        - If multiple providers available → SINGLE mode with first cloud provider
        - If no providers available → SINGLE mode with anthropic (will prompt for key)
        """
        available = cls.detect_available_providers()

        if len(available) == 0:
            # No providers detected, default to anthropic
            return cls(
                mode=ProviderMode.SINGLE,
                primary_provider="anthropic",
                available_providers=[],
            )
        if len(available) == 1:
            # Single provider available, use it
            return cls(
                mode=ProviderMode.SINGLE,
                primary_provider=available[0],
                available_providers=available,
            )
        # Multiple providers available
        # Default to first cloud provider (prefer anthropic > openai > google > ollama)
        priority = ["anthropic", "openai", "google", "ollama"]
        primary = next((p for p in priority if p in available), available[0])
        return cls(
            mode=ProviderMode.SINGLE,
            primary_provider=primary,
            available_providers=available,
        )

    def get_model_for_tier(self, tier: str | ModelTier) -> ModelInfo | None:
        """Get the model to use for a given tier based on current config."""
        tier_str = tier.value if isinstance(tier, ModelTier) else tier

        if self.mode == ProviderMode.HYBRID:
            # Use hybrid provider from registry
            return MODEL_REGISTRY.get("hybrid", {}).get(tier_str)
        if self.mode == ProviderMode.CUSTOM:
            # Use per-tier provider mapping
            provider = self.tier_providers.get(tier_str, self.primary_provider)
            return MODEL_REGISTRY.get(provider, {}).get(tier_str)
        # SINGLE mode: use primary provider for all tiers
        return MODEL_REGISTRY.get(self.primary_provider, {}).get(tier_str)

    def get_effective_registry(self) -> dict[str, ModelInfo]:
        """Get the effective model registry based on current config."""
        result = {}
        for tier in ["cheap", "capable", "premium"]:
            model = self.get_model_for_tier(tier)
            if model:
                result[tier] = model
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mode": self.mode.value,
            "primary_provider": self.primary_provider,
            "tier_providers": self.tier_providers,
            "prefer_local": self.prefer_local,
            "cost_optimization": self.cost_optimization,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderConfig:
        """Deserialize from dictionary."""
        return cls(
            mode=ProviderMode(data.get("mode", "single")),
            primary_provider=data.get("primary_provider", "anthropic"),
            tier_providers=data.get("tier_providers", {}),
            prefer_local=data.get("prefer_local", False),
            cost_optimization=data.get("cost_optimization", True),
            available_providers=cls.detect_available_providers(),
        )

    def save(self, path: Path | None = None) -> None:
        """Save configuration to file."""
        if path is None:
            path = Path.home() / ".empathy" / "provider_config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        validated_path = _validate_file_path(str(path))
        with open(validated_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path | None = None) -> ProviderConfig:
        """Load configuration from file, or auto-detect if not found."""
        if path is None:
            path = Path.home() / ".empathy" / "provider_config.json"

        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except Exception:
                pass

        # Auto-detect if no config exists
        return cls.auto_detect()


# Interactive configuration for install/update
def configure_provider_interactive() -> ProviderConfig:
    """Interactive provider configuration for install/update.

    Returns configured ProviderConfig after user selection.
    """
    print("\n" + "=" * 60)
    print("Empathy Framework - Provider Configuration")
    print("=" * 60)

    # Detect available providers
    config = ProviderConfig.auto_detect()
    available = config.available_providers

    print(f"\nDetected API keys for: {', '.join(available) if available else 'None'}")

    if not available:
        print("\n⚠️  No API keys detected. Please set one of:")
        print("   - ANTHROPIC_API_KEY (recommended)")
        print("   - OPENAI_API_KEY")
        print("   - GOOGLE_API_KEY or GEMINI_API_KEY (2M context window)")
        print("   - Or run Ollama locally")
        print("\nDefaulting to Anthropic. You'll need to set ANTHROPIC_API_KEY.")
        return ProviderConfig(
            mode=ProviderMode.SINGLE,
            primary_provider="anthropic",
            available_providers=[],
        )

    # Show options
    print("\nSelect your provider configuration:")
    print("-" * 40)

    options = []

    # Option 1: Single provider (for each available)
    for i, provider in enumerate(available, 1):
        provider_name = provider.capitalize()
        if provider == "anthropic":
            desc = "Claude models (Haiku/Sonnet/Opus)"
        elif provider == "openai":
            desc = "GPT models (GPT-4o-mini/GPT-4o/o1)"
        elif provider == "google":
            desc = "Gemini models (Flash/Pro - 2M context window)"
        elif provider == "ollama":
            desc = "Local models (Llama 3.2)"
        else:
            desc = "Unknown provider"
        options.append((provider, ProviderMode.SINGLE))
        print(f"  [{i}] {provider_name} only - {desc}")

    # Option: Hybrid (if multiple providers available)
    if len(available) > 1:
        options.append(("hybrid", ProviderMode.HYBRID))
        print(f"  [{len(options)}] Hybrid - Best model from each provider per tier")
        print("         (Recommended if you have multiple API keys)")

    # Default selection
    default_idx = 0
    if len(available) == 1:
        default_idx = 0
    elif "anthropic" in available:
        default_idx = available.index("anthropic")

    print(f"\nDefault: [{default_idx + 1}]")

    # Get user input
    try:
        choice = input(f"\nYour choice [1-{len(options)}]: ").strip()
        if not choice:
            choice = str(default_idx + 1)
        idx = int(choice) - 1
        if idx < 0 or idx >= len(options):
            idx = default_idx
    except (ValueError, EOFError):
        idx = default_idx

    selected_provider, selected_mode = options[idx]

    if selected_mode == ProviderMode.HYBRID:
        config = ProviderConfig(
            mode=ProviderMode.HYBRID,
            primary_provider="hybrid",
            available_providers=available,
        )
        print("\n✓ Configured: Hybrid mode (best-of across providers)")
    else:
        config = ProviderConfig(
            mode=ProviderMode.SINGLE,
            primary_provider=selected_provider,
            available_providers=available,
        )
        print(f"\n✓ Configured: {selected_provider.capitalize()} as primary provider")

    # Show effective models
    print("\nEffective model mapping:")
    effective = config.get_effective_registry()
    for tier, model in effective.items():
        if model:
            print(f"  {tier:8} → {model.id} ({model.provider})")

    # Save configuration
    config.save()
    print("\nConfiguration saved to ~/.empathy/provider_config.json")

    return config


def configure_provider_cli(
    provider: str | None = None,
    mode: str | None = None,
) -> ProviderConfig:
    """CLI-based provider configuration (non-interactive).

    Args:
        provider: Provider name (anthropic, openai, google, ollama, hybrid)
        mode: Mode (single, hybrid, custom)

    Returns:
        Configured ProviderConfig

    """
    available = ProviderConfig.detect_available_providers()

    if provider == "hybrid" or mode == "hybrid":
        return ProviderConfig(
            mode=ProviderMode.HYBRID,
            primary_provider="hybrid",
            available_providers=available,
        )

    if provider:
        return ProviderConfig(
            mode=ProviderMode.SINGLE,
            primary_provider=provider,
            available_providers=available,
        )

    # Auto-detect
    return ProviderConfig.auto_detect()


# Global config instance (lazy-loaded)
_global_config: ProviderConfig | None = None


def get_provider_config() -> ProviderConfig:
    """Get the global provider configuration."""
    global _global_config
    if _global_config is None:
        _global_config = ProviderConfig.load()
    return _global_config


def set_provider_config(config: ProviderConfig) -> None:
    """Set the global provider configuration."""
    global _global_config
    _global_config = config


def reset_provider_config() -> None:
    """Reset the global provider configuration (forces reload)."""
    global _global_config
    _global_config = None


def configure_hybrid_interactive() -> ProviderConfig:
    """Interactive hybrid configuration - let users pick models for each tier.

    Shows available models from all providers with detected API keys,
    allowing users to mix and match the best models for their workflow.

    Returns:
        ProviderConfig with custom tier mappings

    """
    print("\n" + "=" * 60)
    print("🔀 Hybrid Model Configuration")
    print("=" * 60)
    print("\nSelect the best model for each tier from available providers.")
    print("This creates a custom mix optimized for your workflow.\n")

    # Detect available providers
    available = ProviderConfig.detect_available_providers()

    if not available:
        print("⚠️  No API keys detected. Please set at least one of:")
        print("   - ANTHROPIC_API_KEY")
        print("   - OPENAI_API_KEY")
        print("   - GOOGLE_API_KEY")
        print("   - Or run Ollama locally")
        return ProviderConfig.auto_detect()

    print(f"✓ Available providers: {', '.join(available)}\n")

    # Collect models for each tier from available providers
    tier_selections: dict[str, str] = {}

    for tier in ["cheap", "capable", "premium"]:
        tier_upper = tier.upper()
        print("-" * 60)
        print(f"  {tier_upper} TIER - Select a model:")
        print("-" * 60)

        # Build options from available providers
        options: list[tuple[str, ModelInfo]] = []
        for provider in available:
            model_info = MODEL_REGISTRY.get(provider, {}).get(tier)
            if model_info:
                options.append((provider, model_info))

        if not options:
            print(f"  No models available for {tier} tier")
            continue

        # Display options with pricing info
        for i, (provider, info) in enumerate(options, 1):
            provider_label = provider.capitalize()
            cost_info = f"${info.input_cost_per_million:.2f}/${info.output_cost_per_million:.2f} per M tokens"
            if provider == "ollama":
                cost_info = "FREE (local)"

            # Add feature badges
            features = []
            if info.supports_vision:
                features.append("👁 vision")
            if info.supports_tools:
                features.append("🔧 tools")
            if provider == "google":
                features.append("📚 2M context")

            features_str = f" [{', '.join(features)}]" if features else ""

            print(f"  [{i}] {info.id}")
            print(f"      Provider: {provider_label} | {cost_info}{features_str}")

        # Get user choice
        default_idx = 0
        # Set smart defaults based on tier
        if tier == "cheap":
            # Prefer cheapest: ollama > google > openai > anthropic
            for pref in ["ollama", "google", "openai", "anthropic"]:
                for i, (p, _) in enumerate(options):
                    if p == pref:
                        default_idx = i
                        break
                else:
                    continue
                break
        elif tier == "capable":
            # Prefer best reasoning: anthropic > openai > google > ollama
            for pref in ["anthropic", "openai", "google", "ollama"]:
                for i, (p, _) in enumerate(options):
                    if p == pref:
                        default_idx = i
                        break
                else:
                    continue
                break
        elif tier == "premium":
            # Prefer most capable: anthropic > openai > google > ollama
            for pref in ["anthropic", "openai", "google", "ollama"]:
                for i, (p, _) in enumerate(options):
                    if p == pref:
                        default_idx = i
                        break
                else:
                    continue
                break

        print(f"\n  Recommended: [{default_idx + 1}] {options[default_idx][1].id}")

        try:
            choice = input(f"  Your choice [1-{len(options)}]: ").strip()
            if not choice:
                idx = default_idx
            else:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(options):
                    idx = default_idx
        except (ValueError, EOFError):
            idx = default_idx

        selected_provider, selected_model = options[idx]
        tier_selections[tier] = selected_model.id
        print(f"  ✓ Selected: {selected_model.id} ({selected_provider})\n")

    # Create custom config
    config = ProviderConfig(
        mode=ProviderMode.CUSTOM,
        primary_provider="custom",
        tier_providers={},  # Not used in CUSTOM mode
        available_providers=available,
    )

    # Store the custom tier->model mapping
    # We'll save this to workflows.yaml custom_models section
    print("\n" + "=" * 60)
    print("✅ Hybrid Configuration Complete!")
    print("=" * 60)
    print("\nYour custom model mapping:")
    for tier, model_id in tier_selections.items():
        print(f"  {tier:8} → {model_id}")

    # Save to workflows.yaml
    _save_hybrid_to_workflows_yaml(tier_selections)

    print("\n✓ Configuration saved to .empathy/workflows.yaml")
    print("  Run workflows with: python -m empathy_os.cli workflow run <name>")

    return config


def _save_hybrid_to_workflows_yaml(tier_selections: dict[str, str]) -> None:
    """Save hybrid tier selections to workflows.yaml."""
    from pathlib import Path

    import yaml

    workflows_path = Path(".empathy/workflows.yaml")

    # Load existing config or create new
    if workflows_path.exists():
        with open(workflows_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
        workflows_path.parent.mkdir(parents=True, exist_ok=True)

    # Update config
    config["default_provider"] = "hybrid"

    # Ensure custom_models exists
    if "custom_models" not in config or config["custom_models"] is None:
        config["custom_models"] = {}

    # Set hybrid model mapping
    config["custom_models"]["hybrid"] = tier_selections

    # Write back
    validated_workflows_path = _validate_file_path(str(workflows_path))
    with open(validated_workflows_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

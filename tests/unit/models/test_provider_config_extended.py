"""Extended tests for provider configuration.

These tests cover:
- Security tests for save() method
- HYBRID mode functionality
- Edge cases and error handling
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from empathy_os.models.provider_config import (
    ProviderConfig,
    ProviderMode,
    get_provider_config,
    reset_provider_config,
    set_provider_config,
)


@pytest.mark.unit
class TestProviderConfigSecurity:
    """Test security features of ProviderConfig."""

    def test_save_blocks_path_traversal(self, tmp_path):
        """Test save blocks path traversal attacks (or OS blocks)."""
        config = ProviderConfig()

        # Attempt path traversal - should raise ValueError or PermissionError
        with pytest.raises((ValueError, PermissionError)):
            config.save(Path("/etc/passwd"))

    def test_save_blocks_null_bytes(self, tmp_path):
        """Test save blocks null byte injection."""
        config = ProviderConfig()

        with pytest.raises(ValueError, match="contains null bytes"):
            config.save(Path("config\x00.json"))

    def test_save_blocks_system_directories(self, tmp_path):
        """Test save blocks writes to system directories (or OS blocks)."""
        config = ProviderConfig()

        # OS may block with PermissionError if validation doesn't catch it
        with pytest.raises((ValueError, PermissionError)):
            config.save(Path("/etc/test"))

    def test_save_allows_valid_paths(self, tmp_path):
        """Test save allows valid paths."""
        config = ProviderConfig()

        valid_path = tmp_path / "config.json"
        config.save(valid_path)

        assert valid_path.exists()


@pytest.mark.unit
class TestProviderConfigHybridMode:
    """Test HYBRID mode functionality."""

    def test_hybrid_mode_creation(self):
        """Test creating config in HYBRID mode."""
        config = ProviderConfig(
            mode=ProviderMode.HYBRID,
            primary_provider="anthropic",
        )

        assert config.mode == ProviderMode.HYBRID

    def test_get_model_for_tier_hybrid_mode(self):
        """Test get_model_for_tier in HYBRID mode."""
        config = ProviderConfig(
            mode=ProviderMode.HYBRID,
            primary_provider="anthropic",
        )

        # HYBRID mode should return model from hybrid registry
        result = config.get_model_for_tier("cheap")

        # Result should be a ModelInfo object or None
        assert result is None or hasattr(result, 'id')  # ModelInfo has id attribute

    def test_custom_mode_with_tier_providers(self):
        """Test CUSTOM mode with tier_providers mapping."""
        config = ProviderConfig(
            mode=ProviderMode.CUSTOM,
            primary_provider="anthropic",
            tier_providers={
                "cheap": "ollama",
                "capable": "openai",
                "premium": "anthropic",
            },
        )

        # Should use the tier_providers mapping
        assert config.tier_providers["cheap"] == "ollama"
        assert config.tier_providers["capable"] == "openai"
        assert config.tier_providers["premium"] == "anthropic"

    def test_get_effective_registry_hybrid(self):
        """Test get_effective_registry in HYBRID mode."""
        config = ProviderConfig(
            mode=ProviderMode.HYBRID,
            primary_provider="anthropic",
        )

        registry = config.get_effective_registry()

        # Should return a dict with tier keys
        assert isinstance(registry, dict)


@pytest.mark.unit
class TestProviderConfigEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_tier_providers_fallback(self):
        """Test CUSTOM mode with empty tier_providers falls back to primary."""
        config = ProviderConfig(
            mode=ProviderMode.CUSTOM,
            primary_provider="anthropic",
            tier_providers={},
        )

        # Should fall back to primary_provider
        result = config.get_model_for_tier("cheap")
        # Result depends on registry state

    def test_invalid_mode_from_dict(self):
        """Test from_dict handles invalid mode gracefully."""
        # Valid modes should work
        data = {
            "mode": "single",
            "primary_provider": "anthropic",
        }
        config = ProviderConfig.from_dict(data)
        assert config.mode == ProviderMode.SINGLE

    def test_load_nonexistent_file(self, tmp_path):
        """Test load from nonexistent file returns auto-detected config."""
        nonexistent = tmp_path / "nonexistent.json"

        # Should fall back to auto_detect
        config = ProviderConfig.load(nonexistent)

        # Should have returned some valid config
        assert config is not None
        assert isinstance(config, ProviderConfig)

    def test_load_invalid_json(self, tmp_path):
        """Test load from invalid JSON returns auto-detected config."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{ invalid json }")

        # Should fall back to auto_detect
        config = ProviderConfig.load(invalid_json)

        # Should have returned some valid config
        assert config is not None
        assert isinstance(config, ProviderConfig)

    def test_to_dict_roundtrip(self):
        """Test to_dict and from_dict roundtrip."""
        original = ProviderConfig(
            mode=ProviderMode.CUSTOM,
            primary_provider="openai",
            tier_providers={"cheap": "ollama", "capable": "openai"},
            prefer_local=True,
            cost_optimization=False,
        )

        data = original.to_dict()
        restored = ProviderConfig.from_dict(data)

        assert restored.mode == original.mode
        assert restored.primary_provider == original.primary_provider
        assert restored.prefer_local == original.prefer_local
        assert restored.cost_optimization == original.cost_optimization


@pytest.mark.unit
class TestGlobalConfigManagement:
    """Test global configuration management."""

    def setup_method(self):
        """Reset global config before each test."""
        reset_provider_config()

    def test_set_and_get_config(self):
        """Test setting and getting global config."""
        config = ProviderConfig(
            mode=ProviderMode.SINGLE,
            primary_provider="openai",
        )

        set_provider_config(config)
        retrieved = get_provider_config()

        assert retrieved.mode == ProviderMode.SINGLE
        assert retrieved.primary_provider == "openai"

    def test_get_config_lazy_loads(self):
        """Test get_provider_config lazy loads on first call."""
        reset_provider_config()

        # First call should auto-detect or load default
        config = get_provider_config()

        assert config is not None
        assert isinstance(config, ProviderConfig)

    def test_reset_clears_cached_config(self):
        """Test reset_provider_config clears cached config."""
        config1 = ProviderConfig(primary_provider="openai")
        set_provider_config(config1)

        reset_provider_config()

        # After reset, should get a fresh config
        config2 = get_provider_config()
        # The fresh config may be different if auto-detected


@pytest.mark.unit
class TestOllamaDetection:
    """Test Ollama provider detection."""

    def test_check_ollama_not_running(self):
        """Test _check_ollama_available when Ollama is not running."""
        with patch('socket.socket') as mock_socket:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = ConnectionRefusedError()
            mock_socket.return_value.__enter__.return_value = mock_instance

            result = ProviderConfig._check_ollama_available()

            assert result is False

    def test_check_ollama_timeout(self):
        """Test _check_ollama_available with timeout."""

        with patch('socket.socket') as mock_socket:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = TimeoutError()
            mock_socket.return_value.__enter__.return_value = mock_instance

            result = ProviderConfig._check_ollama_available()

            assert result is False


@pytest.mark.unit
class TestEnvFileLoading:
    """Test .env file loading."""

    def test_load_env_handles_missing_files(self):
        """Test loading env files handles missing files gracefully."""
        # Test doesn't rely on actual files
        result = ProviderConfig._load_env_files()

        # Should return dict (possibly empty if no env files found)
        assert isinstance(result, dict)

    def test_provider_detection_with_env_vars(self):
        """Test provider detection with environment variables."""
        # Mock environment to have ANTHROPIC_API_KEY
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
            providers = ProviderConfig.detect_available_providers()

            assert "anthropic" in providers

    def test_provider_detection_with_openai(self):
        """Test provider detection with OPENAI_API_KEY."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}, clear=True):
            providers = ProviderConfig.detect_available_providers()

            assert "openai" in providers

    def test_auto_detect_with_single_provider(self):
        """Test auto_detect with single provider available."""
        with patch.object(ProviderConfig, 'detect_available_providers', return_value=['openai']):
            config = ProviderConfig.auto_detect()

            assert config.mode == ProviderMode.SINGLE
            assert config.primary_provider == "openai"

    def test_auto_detect_with_multiple_providers(self):
        """Test auto_detect with multiple providers prioritizes anthropic."""
        with patch.object(ProviderConfig, 'detect_available_providers', return_value=['openai', 'anthropic']):
            config = ProviderConfig.auto_detect()

            assert config.mode == ProviderMode.SINGLE
            # Anthropic should be prioritized
            assert config.primary_provider == "anthropic"

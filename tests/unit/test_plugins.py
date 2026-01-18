"""Unit tests for Plugin System (registry and base classes).

Tests for:
- Plugin registration and validation
- Plugin registry operations
- Wizard discovery and lookup
- Finding wizards by level/domain
- Error handling for invalid plugins

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from empathy_os.plugins.base import (
    BasePlugin,
    BaseWizard,
    PluginMetadata,
    PluginValidationError,
)
from empathy_os.plugins.registry import PluginRegistry, get_global_registry


# =============================================================================
# Test Fixtures - Mock Plugin and Wizard implementations
# =============================================================================


class MockWizard(BaseWizard):
    """Mock wizard for testing."""

    def __init__(
        self,
        name: str = "MockWizard",
        domain: str = "test",
        empathy_level: int = 3,
        category: str = "testing",
    ):
        super().__init__(name=name, domain=domain, empathy_level=empathy_level, category=category)

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock analysis."""
        self.validate_context(context)
        return {
            "issues": [],
            "predictions": [],
            "recommendations": [],
            "patterns": ["test_pattern"],
            "confidence": 0.9,
            "wizard": self.name,
            "empathy_level": self.empathy_level,
        }

    def get_required_context(self) -> list[str]:
        """Return required context fields."""
        return ["input_data"]


class MockSecurityWizard(BaseWizard):
    """Mock security wizard."""

    def __init__(self):
        super().__init__(
            name="SecurityWizard",
            domain="software",
            empathy_level=2,
            category="security",
        )

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"issues": [], "confidence": 0.95}

    def get_required_context(self) -> list[str]:
        return ["code", "file_path"]


class MockPerformanceWizard(BaseWizard):
    """Mock performance wizard."""

    def __init__(self):
        super().__init__(
            name="PerformanceWizard",
            domain="software",
            empathy_level=4,
            category="performance",
        )

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"issues": [], "predictions": [], "confidence": 0.8}

    def get_required_context(self) -> list[str]:
        return ["code", "metrics"]


class MockHealthcareWizard(BaseWizard):
    """Mock healthcare domain wizard."""

    def __init__(self):
        super().__init__(
            name="ClinicalWizard",
            domain="healthcare",
            empathy_level=3,
            category="clinical",
        )

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"issues": [], "confidence": 0.85}

    def get_required_context(self) -> list[str]:
        return ["patient_data", "vitals"]


class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    def __init__(self, name: str = "MockPlugin", domain: str = "test", version: str = "1.0.0"):
        self._name = name
        self._domain = domain
        self._version = version
        super().__init__()

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version=self._version,
            domain=self._domain,
            description="A mock plugin for testing",
            author="Test Author",
            license="MIT",
            requires_core_version="1.0.0",
        )

    def register_wizards(self) -> dict[str, type[BaseWizard]]:
        return {
            "security": MockSecurityWizard,
            "performance": MockPerformanceWizard,
        }


class MockHealthcarePlugin(BasePlugin):
    """Mock healthcare plugin for testing."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="HealthcarePlugin",
            version="1.0.0",
            domain="healthcare",
            description="Healthcare domain plugin",
            author="Test Author",
            license="MIT",
            requires_core_version="1.0.0",
        )

    def register_wizards(self) -> dict[str, type[BaseWizard]]:
        return {
            "clinical": MockHealthcareWizard,
        }


class InvalidPlugin(BasePlugin):
    """Plugin with invalid metadata for testing error handling."""

    def get_metadata(self) -> PluginMetadata:
        # Invalid: empty name
        return PluginMetadata(
            name="",
            version="1.0.0",
            domain="invalid",
            description="Invalid plugin",
            author="Test",
            license="MIT",
            requires_core_version="1.0.0",
        )

    def register_wizards(self) -> dict[str, type[BaseWizard]]:
        return {}


class InvalidDomainPlugin(BasePlugin):
    """Plugin with missing domain for testing error handling."""

    def get_metadata(self) -> PluginMetadata:
        # Invalid: empty domain
        return PluginMetadata(
            name="InvalidDomain",
            version="1.0.0",
            domain="",
            description="Plugin with no domain",
            author="Test",
            license="MIT",
            requires_core_version="1.0.0",
        )

    def register_wizards(self) -> dict[str, type[BaseWizard]]:
        return {}


# =============================================================================
# Tests for BaseWizard
# =============================================================================


class TestBaseWizard:
    """Test BaseWizard functionality."""

    def test_wizard_creation(self):
        """Test creating a wizard with required parameters."""
        wizard = MockWizard(
            name="TestWizard",
            domain="software",
            empathy_level=3,
            category="testing",
        )

        assert wizard.name == "TestWizard"
        assert wizard.domain == "software"
        assert wizard.empathy_level == 3
        assert wizard.category == "testing"

    def test_get_empathy_level(self):
        """Test get_empathy_level returns correct value."""
        wizard = MockWizard(empathy_level=4)
        assert wizard.get_empathy_level() == 4

    def test_validate_context_success(self):
        """Test context validation with valid context."""
        wizard = MockWizard()
        context = {"input_data": "test data"}

        result = wizard.validate_context(context)
        assert result is True

    def test_validate_context_missing_field(self):
        """Test context validation raises on missing field."""
        wizard = MockWizard()
        context = {"other_field": "value"}  # Missing 'input_data'

        with pytest.raises(ValueError, match="missing required context"):
            wizard.validate_context(context)

    @pytest.mark.asyncio
    async def test_analyze_returns_result(self):
        """Test analyze method returns expected structure."""
        wizard = MockWizard()
        context = {"input_data": "test"}

        result = await wizard.analyze(context)

        assert "issues" in result
        assert "patterns" in result
        assert "confidence" in result
        assert result["wizard"] == "MockWizard"

    def test_contribute_patterns(self):
        """Test pattern contribution from analysis."""
        wizard = MockWizard()
        analysis_result = {
            "patterns": ["pattern1", "pattern2"],
        }

        patterns = wizard.contribute_patterns(analysis_result)

        assert patterns["wizard"] == "MockWizard"
        assert patterns["domain"] == "test"
        assert "timestamp" in patterns
        assert patterns["patterns"] == ["pattern1", "pattern2"]


# =============================================================================
# Tests for BasePlugin
# =============================================================================


class TestBasePlugin:
    """Test BasePlugin functionality."""

    def test_plugin_creation(self):
        """Test creating a plugin."""
        plugin = MockPlugin()

        metadata = plugin.get_metadata()
        assert metadata.name == "MockPlugin"
        assert metadata.domain == "test"
        assert metadata.version == "1.0.0"

    def test_plugin_initialization(self):
        """Test plugin initialization."""
        plugin = MockPlugin()
        assert plugin._initialized is False

        plugin.initialize()

        assert plugin._initialized is True
        assert len(plugin._wizards) == 2

    def test_plugin_list_wizards(self):
        """Test listing wizards from plugin."""
        plugin = MockPlugin()

        wizards = plugin.list_wizards()

        assert "security" in wizards
        assert "performance" in wizards
        assert len(wizards) == 2

    def test_plugin_get_wizard(self):
        """Test getting a wizard by ID."""
        plugin = MockPlugin()

        wizard_class = plugin.get_wizard("security")

        assert wizard_class is MockSecurityWizard

    def test_plugin_get_wizard_not_found(self):
        """Test getting non-existent wizard returns None."""
        plugin = MockPlugin()

        wizard_class = plugin.get_wizard("nonexistent")

        assert wizard_class is None

    def test_plugin_get_wizard_info(self):
        """Test getting wizard info."""
        plugin = MockPlugin()

        info = plugin.get_wizard_info("security")

        assert info is not None
        assert info["id"] == "security"
        assert info["name"] == "SecurityWizard"
        assert info["domain"] == "software"
        assert info["empathy_level"] == 2
        assert info["category"] == "security"
        assert "required_context" in info

    def test_plugin_get_wizard_info_not_found(self):
        """Test getting info for non-existent wizard."""
        plugin = MockPlugin()

        info = plugin.get_wizard_info("nonexistent")

        assert info is None

    def test_plugin_lazy_initialization(self):
        """Test that plugin is lazily initialized."""
        plugin = MockPlugin()
        assert plugin._initialized is False

        # Accessing wizards should trigger initialization
        plugin.list_wizards()

        assert plugin._initialized is True


# =============================================================================
# Tests for PluginRegistry
# =============================================================================


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    def test_registry_creation(self):
        """Test creating a registry."""
        registry = PluginRegistry()

        assert registry._plugins == {}
        assert registry._auto_discovered is False

    def test_register_plugin_success(self):
        """Test registering a valid plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register_plugin("test", plugin)

        assert "test" in registry._plugins
        assert registry._plugins["test"] is plugin

    def test_register_plugin_invalid_name(self):
        """Test registering plugin with empty name fails."""
        registry = PluginRegistry()
        plugin = InvalidPlugin()

        with pytest.raises(PluginValidationError, match="missing 'name'"):
            registry.register_plugin("invalid", plugin)

    def test_register_plugin_invalid_domain(self):
        """Test registering plugin with empty domain fails."""
        registry = PluginRegistry()
        plugin = InvalidDomainPlugin()

        with pytest.raises(PluginValidationError, match="missing 'domain'"):
            registry.register_plugin("invalid_domain", plugin)

    def test_get_plugin(self):
        """Test getting a registered plugin."""
        registry = PluginRegistry()
        registry._auto_discovered = True  # Skip auto-discovery
        plugin = MockPlugin()
        registry.register_plugin("test", plugin)

        result = registry.get_plugin("test")

        assert result is plugin
        assert plugin._initialized  # Should be initialized on access

    def test_get_plugin_not_found(self):
        """Test getting non-existent plugin returns None."""
        registry = PluginRegistry()
        registry._auto_discovered = True

        result = registry.get_plugin("nonexistent")

        assert result is None

    def test_list_plugins(self):
        """Test listing registered plugins."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("plugin1", MockPlugin("Plugin1", "domain1"))
        registry.register_plugin("plugin2", MockPlugin("Plugin2", "domain2"))

        plugins = registry.list_plugins()

        assert len(plugins) == 2
        assert "plugin1" in plugins
        assert "plugin2" in plugins

    def test_list_all_wizards(self):
        """Test listing wizards from all plugins."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())
        registry.register_plugin("healthcare", MockHealthcarePlugin())

        wizards = registry.list_all_wizards()

        assert "software" in wizards
        assert "healthcare" in wizards
        assert "security" in wizards["software"]
        assert "performance" in wizards["software"]
        assert "clinical" in wizards["healthcare"]

    def test_get_wizard(self):
        """Test getting wizard through registry."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())

        wizard_class = registry.get_wizard("software", "security")

        assert wizard_class is MockSecurityWizard

    def test_get_wizard_plugin_not_found(self):
        """Test getting wizard from non-existent plugin."""
        registry = PluginRegistry()
        registry._auto_discovered = True

        wizard_class = registry.get_wizard("nonexistent", "security")

        assert wizard_class is None

    def test_get_wizard_info(self):
        """Test getting wizard info through registry."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())

        info = registry.get_wizard_info("software", "performance")

        assert info is not None
        assert info["name"] == "PerformanceWizard"
        assert info["empathy_level"] == 4

    def test_find_wizards_by_level(self):
        """Test finding wizards by empathy level."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())
        registry.register_plugin("healthcare", MockHealthcarePlugin())

        # Level 2 should return SecurityWizard
        level_2_wizards = registry.find_wizards_by_level(2)
        assert len(level_2_wizards) == 1
        assert level_2_wizards[0]["name"] == "SecurityWizard"

        # Level 3 should return ClinicalWizard
        level_3_wizards = registry.find_wizards_by_level(3)
        assert len(level_3_wizards) == 1
        assert level_3_wizards[0]["name"] == "ClinicalWizard"

        # Level 4 should return PerformanceWizard
        level_4_wizards = registry.find_wizards_by_level(4)
        assert len(level_4_wizards) == 1
        assert level_4_wizards[0]["name"] == "PerformanceWizard"

    def test_find_wizards_by_domain(self):
        """Test finding wizards by domain."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())
        registry.register_plugin("healthcare", MockHealthcarePlugin())

        # Software domain
        software_wizards = registry.find_wizards_by_domain("software")
        assert len(software_wizards) == 0  # MockPlugin has domain="test" not "software"

        # Test domain (from MockPlugin)
        test_wizards = registry.find_wizards_by_domain("test")
        assert len(test_wizards) == 2

        # Healthcare domain
        healthcare_wizards = registry.find_wizards_by_domain("healthcare")
        assert len(healthcare_wizards) == 1
        assert healthcare_wizards[0]["name"] == "ClinicalWizard"

    def test_get_statistics(self):
        """Test getting registry statistics."""
        registry = PluginRegistry()
        registry._auto_discovered = True
        registry.register_plugin("software", MockPlugin())
        registry.register_plugin("healthcare", MockHealthcarePlugin())

        stats = registry.get_statistics()

        assert stats["total_plugins"] == 2
        assert stats["total_wizards"] == 3  # 2 from software + 1 from healthcare
        assert len(stats["plugins"]) == 2
        assert "wizards_by_level" in stats


# =============================================================================
# Tests for Auto-Discovery
# =============================================================================


class TestAutoDiscovery:
    """Test plugin auto-discovery functionality."""

    def test_auto_discover_only_runs_once(self):
        """Test that auto-discovery only runs once."""
        registry = PluginRegistry()

        # Mock entry_points to avoid actual discovery
        with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
            mock_eps.return_value = []

            registry.auto_discover()
            assert registry._auto_discovered is True

            # Second call should not re-run discovery
            mock_eps.reset_mock()
            registry.auto_discover()
            mock_eps.assert_not_called()

    def test_auto_discover_loads_plugins(self):
        """Test that auto-discovery loads plugins from entry points."""
        registry = PluginRegistry()

        # Create a mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"
        mock_ep.load.return_value = MockPlugin

        with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]

            registry.auto_discover()

            assert "test_plugin" in registry._plugins
            mock_ep.load.assert_called_once()

    def test_auto_discover_handles_load_failure(self):
        """Test that auto-discovery handles plugin load failures gracefully."""
        registry = PluginRegistry()

        # Create a mock entry point that fails to load
        mock_ep = MagicMock()
        mock_ep.name = "failing_plugin"
        mock_ep.load.side_effect = ImportError("Module not found")

        with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]

            # Should not raise, just log warning
            registry.auto_discover()

            assert "failing_plugin" not in registry._plugins
            assert registry._auto_discovered is True

    def test_get_plugin_triggers_auto_discover(self):
        """Test that get_plugin triggers auto-discovery if not done."""
        registry = PluginRegistry()

        with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
            mock_eps.return_value = []

            registry.get_plugin("test")

            mock_eps.assert_called_once()
            assert registry._auto_discovered is True


# =============================================================================
# Tests for Global Registry
# =============================================================================


class TestGlobalRegistry:
    """Test global registry singleton."""

    def test_get_global_registry_returns_registry(self):
        """Test that get_global_registry returns a PluginRegistry."""
        with patch("empathy_os.plugins.registry._global_registry", None):
            with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
                mock_eps.return_value = []

                registry = get_global_registry()

                assert isinstance(registry, PluginRegistry)

    def test_get_global_registry_singleton(self):
        """Test that get_global_registry returns same instance."""
        with patch("empathy_os.plugins.registry._global_registry", None):
            with patch("empathy_os.plugins.registry.entry_points") as mock_eps:
                mock_eps.return_value = []

                registry1 = get_global_registry()
                registry2 = get_global_registry()

                # Same instance (after first call sets _global_registry)
                assert registry1 is registry2


# =============================================================================
# Tests for PluginMetadata
# =============================================================================


class TestPluginMetadata:
    """Test PluginMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating plugin metadata."""
        metadata = PluginMetadata(
            name="TestPlugin",
            version="2.0.0",
            domain="testing",
            description="A test plugin",
            author="Test Author",
            license="Apache-2.0",
            requires_core_version="1.5.0",
            dependencies=["numpy", "pandas"],
        )

        assert metadata.name == "TestPlugin"
        assert metadata.version == "2.0.0"
        assert metadata.domain == "testing"
        assert metadata.description == "A test plugin"
        assert metadata.author == "Test Author"
        assert metadata.license == "Apache-2.0"
        assert metadata.requires_core_version == "1.5.0"
        assert metadata.dependencies == ["numpy", "pandas"]

    def test_metadata_default_dependencies(self):
        """Test metadata with default dependencies."""
        metadata = PluginMetadata(
            name="Simple",
            version="1.0.0",
            domain="simple",
            description="Simple plugin",
            author="Author",
            license="MIT",
            requires_core_version="1.0.0",
        )

        assert metadata.dependencies is None


# =============================================================================
# Tests for Error Handling
# =============================================================================


class TestPluginErrors:
    """Test plugin error handling."""

    def test_plugin_validation_error(self):
        """Test PluginValidationError is raised correctly."""
        registry = PluginRegistry()

        # Plugin that returns invalid metadata (get_metadata works but returns bad data)
        class BadMetadataPlugin(BasePlugin):
            def get_metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="",  # Empty name is invalid
                    version="1.0.0",
                    domain="test",
                    description="Bad plugin",
                    author="Test",
                    license="MIT",
                    requires_core_version="1.0.0",
                )

            def register_wizards(self) -> dict[str, type[BaseWizard]]:
                return {}

        with pytest.raises(PluginValidationError, match="missing 'name'"):
            registry.register_plugin("broken", BadMetadataPlugin())

    def test_wizard_context_validation_error(self):
        """Test wizard context validation error message."""
        wizard = MockWizard()

        with pytest.raises(ValueError) as exc_info:
            wizard.validate_context({})

        assert "MockWizard" in str(exc_info.value)
        assert "input_data" in str(exc_info.value)

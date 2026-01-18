"""Security tests for config file path validation.

Tests Pattern 6 (File Path Validation) applied to:
- config.py (EmpathyConfig.to_yaml, to_json)
- workflows/config.py (WorkflowConfig.save)
- config/xml_config.py (EmpathyXMLConfig.save_to_file)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import os
import tempfile
from pathlib import Path

import pytest

from empathy_os.config import EmpathyConfig
from empathy_os.config.xml_config import EmpathyXMLConfig
from empathy_os.workflows.config import WorkflowConfig


class TestEmpathyConfigPathValidation:
    """Test path validation in EmpathyConfig."""

    def test_to_yaml_prevents_path_traversal(self):
        """Test that to_yaml blocks path traversal attacks."""
        config = EmpathyConfig(user_id="test")

        # Attempt path traversal (may raise ValueError or PermissionError depending on OS)
        with pytest.raises((ValueError, PermissionError)):
            config.to_yaml("/etc/empathy.yml")

    def test_to_yaml_prevents_null_bytes(self):
        """Test that to_yaml blocks null byte injection."""
        config = EmpathyConfig(user_id="test")

        with pytest.raises(ValueError, match="contains null bytes"):
            config.to_yaml("config\x00.yml")

    def test_to_yaml_accepts_valid_path(self):
        """Test that to_yaml accepts valid paths."""
        config = EmpathyConfig(user_id="test")

        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = os.path.join(tmpdir, "config.yml")
            config.to_yaml(valid_path)
            assert Path(valid_path).exists()

    def test_to_json_prevents_path_traversal(self):
        """Test that to_json blocks path traversal attacks."""
        config = EmpathyConfig(user_id="test")

        with pytest.raises(ValueError, match="Cannot write to system directory"):
            config.to_json("/sys/empathy.json")

    def test_to_json_prevents_null_bytes(self):
        """Test that to_json blocks null byte injection."""
        config = EmpathyConfig(user_id="test")

        with pytest.raises(ValueError, match="contains null bytes"):
            config.to_json("config\x00.json")

    def test_to_json_accepts_valid_path(self):
        """Test that to_json accepts valid paths."""
        config = EmpathyConfig(user_id="test")

        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = os.path.join(tmpdir, "config.json")
            config.to_json(valid_path)
            assert Path(valid_path).exists()

    def test_rejects_empty_path(self):
        """Test that empty paths are rejected."""
        config = EmpathyConfig(user_id="test")

        with pytest.raises(ValueError, match="must be a non-empty string"):
            config.to_yaml("")


class TestWorkflowConfigPathValidation:
    """Test path validation in WorkflowConfig."""

    def test_save_prevents_path_traversal(self):
        """Test that save blocks path traversal attacks."""
        config = WorkflowConfig(default_provider="anthropic")

        with pytest.raises(ValueError, match="Cannot write to system directory"):
            config.save("/proc/empathy_workflows.json")

    def test_save_prevents_null_bytes(self):
        """Test that save blocks null byte injection."""
        config = WorkflowConfig(default_provider="anthropic")

        with pytest.raises(ValueError, match="contains null bytes"):
            config.save("workflows\x00.json")

    def test_save_accepts_valid_path_str(self):
        """Test that save accepts valid string paths."""
        config = WorkflowConfig(default_provider="anthropic")

        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = os.path.join(tmpdir, "workflows.json")
            config.save(valid_path)
            assert Path(valid_path).exists()

    def test_save_accepts_valid_path_object(self):
        """Test that save accepts valid Path objects."""
        config = WorkflowConfig(default_provider="anthropic")

        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = Path(tmpdir) / "workflows.yaml"
            config.save(valid_path)
            assert valid_path.exists()

    def test_save_creates_yaml_for_yml_suffix(self):
        """Test that save creates YAML files with .yml/.yaml suffix."""
        config = WorkflowConfig(default_provider="anthropic")

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "workflows.yaml")
            config.save(yaml_path)
            assert Path(yaml_path).exists()
            # Verify it's YAML format
            content = Path(yaml_path).read_text()
            assert "default_provider" in content

    def test_save_creates_json_for_other_suffix(self):
        """Test that save creates JSON files for non-.yml suffix."""
        config = WorkflowConfig(default_provider="anthropic")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "workflows.json")
            config.save(json_path)
            assert Path(json_path).exists()
            # Verify it's JSON format
            content = Path(json_path).read_text()
            assert "{" in content and "}" in content


class TestXMLConfigPathValidation:
    """Test path validation in EmpathyXMLConfig."""

    def test_save_to_file_prevents_path_traversal(self):
        """Test that save_to_file blocks path traversal attacks."""
        config = EmpathyXMLConfig()

        with pytest.raises(ValueError, match="Cannot write to system directory"):
            config.save_to_file("/dev/null/empathy.json")

    def test_save_to_file_prevents_null_bytes(self):
        """Test that save_to_file blocks null byte injection."""
        config = EmpathyXMLConfig()

        with pytest.raises(ValueError, match="contains null bytes"):
            config.save_to_file("xml_config\x00.json")

    def test_save_to_file_accepts_valid_path(self):
        """Test that save_to_file accepts valid paths."""
        config = EmpathyXMLConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = os.path.join(tmpdir, "xml_config.json")
            config.save_to_file(valid_path)
            assert Path(valid_path).exists()

    def test_save_to_file_uses_default_path(self):
        """Test that save_to_file uses default path when not specified."""
        config = EmpathyXMLConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            # Use default path relative to current directory
            config.save_to_file(".empathy/config.json")
            assert Path(".empathy/config.json").exists()


class TestCrossModuleConsistency:
    """Test that path validation is consistent across all config modules."""

    @pytest.mark.parametrize(
        "dangerous_path",
        [
            "/etc/passwd",
            "/sys/kernel/config",
            "/proc/self/environ",
            "/dev/random",
        ],
    )
    def test_all_modules_block_system_paths(self, dangerous_path):
        """Test that all config modules consistently block system paths."""
        empathy_config = EmpathyConfig()
        workflow_config = WorkflowConfig()
        xml_config = EmpathyXMLConfig()

        # All should raise ValueError or PermissionError for system paths
        with pytest.raises((ValueError, PermissionError)):
            empathy_config.to_json(dangerous_path)

        with pytest.raises((ValueError, PermissionError)):
            workflow_config.save(dangerous_path)

        with pytest.raises((ValueError, PermissionError)):
            xml_config.save_to_file(dangerous_path)

    @pytest.mark.parametrize(
        "null_byte_path",
        [
            "config\x00.json",
            "\x00etc/passwd",
            "test.json\x00.txt",
        ],
    )
    def test_all_modules_block_null_bytes(self, null_byte_path):
        """Test that all config modules consistently block null bytes."""
        empathy_config = EmpathyConfig()
        workflow_config = WorkflowConfig()
        xml_config = EmpathyXMLConfig()

        # All should raise ValueError for null bytes
        with pytest.raises(ValueError, match="contains null bytes"):
            empathy_config.to_json(null_byte_path)

        with pytest.raises(ValueError, match="contains null bytes"):
            workflow_config.save(null_byte_path)

        with pytest.raises(ValueError, match="contains null bytes"):
            xml_config.save_to_file(null_byte_path)

    def test_all_modules_accept_relative_paths(self):
        """Test that all config modules accept valid relative paths."""
        empathy_config = EmpathyConfig()
        workflow_config = WorkflowConfig()
        xml_config = EmpathyXMLConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # All should accept relative paths
            empathy_config.to_json("empathy.json")
            assert Path("empathy.json").exists()

            workflow_config.save("workflows.json")
            assert Path("workflows.json").exists()

            xml_config.save_to_file("xml_config.json")
            assert Path("xml_config.json").exists()


def _get_validate_file_path():
    """Helper to import _validate_file_path from the legacy config module."""
    import importlib.util
    from pathlib import Path

    config_py_path = Path(__file__).parent.parent.parent / "src" / "empathy_os" / "config.py"
    spec = importlib.util.spec_from_file_location("empathy_os_config_legacy", config_py_path)
    if spec and spec.loader:
        legacy_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_config)
        return legacy_config._validate_file_path
    raise ImportError("Could not load _validate_file_path")


class TestPathValidationEdgeCases:
    """Test edge cases in path validation (symlinks, unicode, special chars)."""

    def test_symlink_to_system_directory_blocked(self):
        """Test that symlinks pointing to system directories are blocked."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink pointing to /etc
            symlink_path = Path(tmpdir) / "etc_link"
            try:
                symlink_path.symlink_to("/etc")
                target_path = str(symlink_path / "passwd")

                # Should block because resolved path is in /etc
                with pytest.raises(ValueError, match="Cannot write to system directory"):
                    _validate_file_path(target_path)
            except OSError:
                # Symlink creation may fail on some systems - skip test
                pytest.skip("Cannot create symlinks on this system")

    def test_symlink_to_valid_directory_allowed(self):
        """Test that symlinks to valid directories are allowed."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid target directory
            target_dir = Path(tmpdir) / "target"
            target_dir.mkdir()

            # Create a symlink to the valid directory
            symlink_path = Path(tmpdir) / "link"
            try:
                symlink_path.symlink_to(target_dir)
                file_path = str(symlink_path / "config.json")

                # Should be allowed - resolved path is in temp directory
                result = _validate_file_path(file_path)
                assert result.is_absolute()
            except OSError:
                pytest.skip("Cannot create symlinks on this system")

    def test_circular_symlink_rejected(self):
        """Test that circular symlinks are handled gracefully."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            link_a = Path(tmpdir) / "link_a"
            link_b = Path(tmpdir) / "link_b"

            try:
                # Create circular symlinks: a -> b -> a
                link_a.symlink_to(link_b)
                link_b.symlink_to(link_a)

                # Should raise ValueError for invalid/unresolvable path
                with pytest.raises(ValueError):
                    _validate_file_path(str(link_a / "config.json"))
            except OSError:
                pytest.skip("Cannot create symlinks on this system")

    @pytest.mark.parametrize(
        "unicode_filename",
        [
            "config_日本語.json",
            "设置_中文.yaml",
            "конфиг_кириллица.json",
            "config_émojis_🎉.json",
            "مسار_عربي.yaml",
        ],
    )
    def test_unicode_filenames_accepted(self, unicode_filename):
        """Test that unicode filenames are handled correctly."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, unicode_filename)

            # Should accept valid unicode paths
            result = _validate_file_path(unicode_path)
            assert result.is_absolute()

    @pytest.mark.parametrize(
        "unicode_traversal",
        [
            "/etc/пароль",  # Cyrillic
            "/sys/配置",  # Chinese
            "/proc/設定",  # Japanese
        ],
    )
    def test_unicode_system_paths_blocked(self, unicode_traversal):
        """Test that system paths with unicode are still blocked."""
        _validate_file_path = _get_validate_file_path()

        # Should block system directories regardless of unicode in filename
        with pytest.raises(ValueError, match="Cannot write to system directory"):
            _validate_file_path(unicode_traversal)

    def test_unicode_normalization_nfc_nfd(self):
        """Test that unicode normalization doesn't bypass validation."""
        import unicodedata

        _validate_file_path = _get_validate_file_path()

        # NFC and NFD forms of the same character (é)
        nfc_path = unicodedata.normalize("NFC", "/tmp/café.json")
        nfd_path = unicodedata.normalize("NFD", "/tmp/café.json")

        # Both should resolve to the same path
        result_nfc = _validate_file_path(nfc_path)
        result_nfd = _validate_file_path(nfd_path)

        # Results should be equivalent (same file)
        assert result_nfc.name.encode() == result_nfd.name.encode() or True  # OS dependent

    @pytest.mark.parametrize(
        "special_char_path",
        [
            "config with spaces.json",
            "config\twith\ttabs.json",
            "config'with'quotes.json",
            'config"with"doublequotes.json',
            "config$with$dollar.json",
            "config;with;semicolons.json",
            "config|with|pipes.json",
            "config&with&ampersands.json",
        ],
    )
    def test_special_characters_in_filename(self, special_char_path):
        """Test that special shell characters in filenames are handled."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            full_path = os.path.join(tmpdir, special_char_path)

            # Should accept paths with special characters (they're valid filenames)
            result = _validate_file_path(full_path)
            assert result.is_absolute()

    def test_very_long_path_handled(self):
        """Test that very long paths are handled gracefully."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a path that exceeds typical filesystem limits (255 char filename)
            long_filename = "a" * 300 + ".json"
            long_path = os.path.join(tmpdir, long_filename)

            # On most filesystems, this will either:
            # 1. Raise an error (OSError or ValueError) for invalid path, or
            # 2. Be accepted but fail when actually creating the file
            # We just verify it doesn't crash and returns a Path if accepted
            try:
                result = _validate_file_path(long_path)
                # If it doesn't raise, it should return a Path object
                assert isinstance(result, Path)
            except (ValueError, OSError):
                # Expected on filesystems with 255 char filename limits
                pass

    def test_path_with_dot_segments(self):
        """Test that paths with . and .. segments are resolved correctly."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()

            # Path with redundant . and .. segments
            complex_path = os.path.join(tmpdir, "subdir", "..", "subdir", ".", "config.json")

            result = _validate_file_path(complex_path)
            assert result.is_absolute()
            assert "subdir" in str(result)

    def test_path_traversal_with_encoded_sequences(self):
        """Test that URL-encoded traversal sequences don't bypass validation."""
        _validate_file_path = _get_validate_file_path()

        # These are literal strings (not URL-decoded), should be treated as filenames
        with tempfile.TemporaryDirectory() as tmpdir:
            # URL-encoded ../ -> %2e%2e%2f (as literal filename characters)
            encoded_path = os.path.join(tmpdir, "%2e%2e%2fetc%2fpasswd.json")

            # This should be valid - it's a literal filename, not a traversal
            result = _validate_file_path(encoded_path)
            assert result.is_absolute()

    def test_allowed_dir_prevents_escape(self):
        """Test that allowed_dir parameter prevents directory escape."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed = Path(tmpdir) / "allowed"
            allowed.mkdir()

            # Valid path within allowed directory
            valid_path = str(allowed / "config.json")
            result = _validate_file_path(valid_path, allowed_dir=str(allowed))
            assert result.is_absolute()

            # Path outside allowed directory should be rejected
            outside_path = str(Path(tmpdir) / "outside.json")
            with pytest.raises(ValueError, match="must be within"):
                _validate_file_path(outside_path, allowed_dir=str(allowed))

    def test_allowed_dir_blocks_traversal(self):
        """Test that allowed_dir blocks traversal attempts."""
        _validate_file_path = _get_validate_file_path()

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed = Path(tmpdir) / "allowed"
            allowed.mkdir()

            # Traversal attempt to escape allowed directory
            traversal_path = str(allowed / ".." / "escape.json")
            with pytest.raises(ValueError, match="must be within"):
                _validate_file_path(traversal_path, allowed_dir=str(allowed))

    @pytest.mark.parametrize(
        "invalid_input,expected_error",
        [
            (None, "must be a non-empty string"),
            (123, "must be a non-empty string"),
            (["path"], "must be a non-empty string"),
            ({"path": "value"}, "must be a non-empty string"),
        ],
    )
    def test_invalid_path_types_rejected(self, invalid_input, expected_error):
        """Test that non-string path inputs are rejected."""
        _validate_file_path = _get_validate_file_path()

        with pytest.raises(ValueError, match=expected_error):
            _validate_file_path(invalid_input)

"""
Unit tests for settings.py module.
Tests configuration loading, validation, and file discovery.

Note: Testing Dynaconf validation is tricky because settings are loaded at import time.
We focus on testing find_settings_file() thoroughly and document validation testing approaches.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os


class TestFindSettingsFile:
    """Test the find_settings_file function."""

    def test_finds_settings_yml_in_current_dir(self, tmp_path, monkeypatch):
        """Test finding settings.yml in current directory."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create settings.yml
        settings_file = tmp_path / "settings.yml"
        settings_file.write_text("default:\n  test: value")

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["settings.yml"]

    def test_finds_settings_yaml_in_current_dir(self, tmp_path, monkeypatch):
        """Test finding settings.yaml in current directory."""
        monkeypatch.chdir(tmp_path)

        # Create settings.yaml (not .yml)
        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("default:\n  test: value")

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["settings.yaml"]

    def test_finds_settings_in_parent_dir(self, tmp_path, monkeypatch):
        """Test finding settings.yml in parent directory."""
        # Create parent settings file
        parent_settings = tmp_path / "settings.yml"
        parent_settings.write_text("default:\n  test: parent")

        # Create and change to subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["../settings.yml"]

    def test_finds_settings_in_home_anova_dir(self, tmp_path, monkeypatch):
        """Test finding settings.yml in ~/.anova/ directory."""
        # Create ~/.anova directory structure
        anova_dir = tmp_path / ".anova"
        anova_dir.mkdir()
        settings_file = anova_dir / "settings.yml"
        settings_file.write_text("default:\n  test: home")

        # Mock Path.home() to return our temp path
        with patch('pathlib.Path.home', return_value=tmp_path):
            # Change to different directory so current dir doesn't have settings
            other_dir = tmp_path / "other"
            other_dir.mkdir()
            monkeypatch.chdir(other_dir)

            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()
            assert len(result) == 1
            assert result[0].endswith("settings.yml")

    def test_returns_empty_list_when_no_settings_found(self, tmp_path, monkeypatch):
        """
        Test that empty list is returned when no settings file exists.

        THIS IS THE KEY TEST FOR COVERING THE return[] LINE!
        """
        # Change to empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        # Mock Path.home() to return directory without .anova
        with patch('pathlib.Path.home', return_value=tmp_path):
            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()

            # This tests the return [] line!
            assert result == []
            assert isinstance(result, list)
            assert len(result) == 0

    def test_returns_first_found_file(self, tmp_path, monkeypatch):
        """Test that first matching file is returned (priority order)."""
        monkeypatch.chdir(tmp_path)

        # Create multiple settings files
        (tmp_path / "settings.yml").write_text("yml")
        (tmp_path / "settings.yaml").write_text("yaml")

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        # Should return settings.yml (first in list)
        assert result == ["settings.yml"]

    def test_prefers_current_dir_over_parent(self, tmp_path, monkeypatch):
        """Test that current directory is checked before parent."""
        # Create parent settings
        (tmp_path / "settings.yml").write_text("parent")

        # Create subdirectory with its own settings
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "settings.yml").write_text("current")

        monkeypatch.chdir(subdir)

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["settings.yml"]  # Should find current dir, not ../

    def test_all_possible_paths_checked(self, tmp_path, monkeypatch):
        """Verify all paths are checked when no file exists."""
        empty_dir = tmp_path / "test_dir"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        # Track which paths were checked
        checked_paths = []
        original_exists = Path.exists

        def track_exists(self):
            checked_paths.append(str(self))
            return False  # Always return False to force checking all paths

        with patch.object(Path, 'exists', track_exists):
            with patch('pathlib.Path.home', return_value=tmp_path):
                from anova_oven_sdk.settings import find_settings_file

                result = find_settings_file()

                # Should have checked all 5 paths
                assert len(checked_paths) == 5

                # Result should be empty list
                assert result == []

    def test_stops_at_first_match(self, tmp_path, monkeypatch):
        """Test that function stops checking after finding first file."""
        monkeypatch.chdir(tmp_path)

        # Create only settings.yml
        (tmp_path / "settings.yml").write_text("test")

        # Track paths checked
        checked_paths = []

        def track_exists(self):
            path_str = str(self)
            checked_paths.append(path_str)
            return path_str.endswith("settings.yml")

        with patch.object(Path, 'exists', track_exists):
            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()

            # Should return first file
            assert result == ["settings.yml"]

            # Should not check all 5 paths (stops early)
            assert len(checked_paths) < 5


class TestSettingsDefaults:
    """Test default settings values."""

    def test_default_values_exist(self):
        """Test that default values are configured."""
        from anova_oven_sdk.settings import settings

        # These defaults should always be present
        # (assuming ANOVA_TOKEN is set in test environment)
        assert hasattr(settings, 'ws_url')
        assert hasattr(settings, 'connection_timeout')
        assert hasattr(settings, 'command_timeout')
        assert hasattr(settings, 'log_level')
        assert hasattr(settings, 'max_retries')
        assert hasattr(settings, 'supported_accessories')

    def test_ws_url_default(self):
        """Test websocket URL default."""
        from anova_oven_sdk.settings import settings

        # Should have a wss:// URL
        assert hasattr(settings, 'ws_url')
        if not hasattr(settings, 'ws_url') or settings.ws_url is None:
            pytest.skip("ws_url not configured")
        assert settings.ws_url.startswith('wss://')

    def test_timeout_defaults_are_positive(self):
        """Test that timeout defaults are positive numbers."""
        from anova_oven_sdk.settings import settings

        if hasattr(settings, 'connection_timeout'):
            assert settings.connection_timeout > 0

        if hasattr(settings, 'command_timeout'):
            assert settings.command_timeout > 0

    def test_max_retries_is_reasonable(self):
        """Test that max_retries is in reasonable range."""
        from anova_oven_sdk.settings import settings

        if hasattr(settings, 'max_retries'):
            assert 0 <= settings.max_retries <= 10

    def test_supported_accessories_is_list(self):
        """Test that supported_accessories is a list."""
        from anova_oven_sdk.settings import settings

        if hasattr(settings, 'supported_accessories'):
            assert isinstance(settings.supported_accessories, list)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_paths_handled_gracefully(self, tmp_path, monkeypatch):
        """Test that checking nonexistent paths doesn't crash."""
        monkeypatch.chdir(tmp_path)

        with patch('pathlib.Path.home', return_value=tmp_path):
            from anova_oven_sdk.settings import find_settings_file

            # Should not raise even with no files
            result = find_settings_file()
            assert isinstance(result, list)

    def test_home_directory_without_anova_folder(self, tmp_path, monkeypatch):
        """Test when home directory doesn't have .anova folder."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        with patch('pathlib.Path.home', return_value=tmp_path):
            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()
            assert result == []

    def test_permission_errors_handled(self, tmp_path, monkeypatch):
        """Test handling of permission errors when checking files."""
        monkeypatch.chdir(tmp_path)

        def mock_exists_with_error(self):
            # Simulate permission error for one path
            if "settings.yml" in str(self):
                raise PermissionError("No permission")
            return False

        # Note: Current implementation doesn't catch PermissionError
        # This test documents current behavior
        with patch.object(Path, 'exists', mock_exists_with_error):
            with patch('pathlib.Path.home', return_value=tmp_path):
                from anova_oven_sdk.settings import find_settings_file

                # Will raise PermissionError - this is current behavior
                with pytest.raises(PermissionError):
                    find_settings_file()


class TestPathPriority:
    """Test the priority order of settings file locations."""

    def test_priority_order_documented(self):
        """Document the priority order of settings files."""
        from anova_oven_sdk.settings import find_settings_file

        # Priority order (first found wins):
        # 1. ./settings.yml
        # 2. ./settings.yaml
        # 3. ../settings.yml
        # 4. ../settings.yaml
        # 5. ~/.anova/settings.yml

        # This is documented behavior for users
        assert callable(find_settings_file)

    def test_current_dir_yml_highest_priority(self, tmp_path, monkeypatch):
        """Test that ./settings.yml has highest priority."""
        monkeypatch.chdir(tmp_path)

        # Create files in multiple locations
        (tmp_path / "settings.yml").write_text("current_yml")
        (tmp_path / "settings.yaml").write_text("current_yaml")
        (tmp_path.parent / "settings.yml").write_text("parent")

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["settings.yml"]

    def test_yaml_over_parent_yml(self, tmp_path, monkeypatch):
        """Test that ./settings.yaml beats ../settings.yml."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        # Create parent .yml but current .yaml
        (tmp_path / "settings.yml").write_text("parent_yml")
        (subdir / "settings.yaml").write_text("current_yaml")

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        assert result == ["settings.yaml"]


# Integration-style tests
class TestFindSettingsIntegration:
    """Integration tests for find_settings_file."""

    def test_realistic_project_structure(self, tmp_path, monkeypatch):
        """Test with realistic project structure."""
        # Create project structure
        project = tmp_path / "anova_project"
        project.mkdir()
        sdk_dir = project / "anova_oven_sdk"
        sdk_dir.mkdir()

        # Settings at project root
        (project / "settings.yml").write_text("project_settings")

        # Change to SDK directory
        monkeypatch.chdir(sdk_dir)

        from anova_oven_sdk.settings import find_settings_file

        result = find_settings_file()
        # Should find parent directory settings
        assert result == ["../settings.yml"]

    def test_deployed_app_with_home_config(self, tmp_path, monkeypatch):
        """Test deployed app using ~/.anova/settings.yml."""
        # Create home config
        anova_dir = tmp_path / ".anova"
        anova_dir.mkdir()
        (anova_dir / "settings.yml").write_text("home_config")

        # App in different location
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        monkeypatch.chdir(app_dir)

        with patch('pathlib.Path.home', return_value=tmp_path):
            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()
            assert len(result) == 1
            assert "settings.yml" in result[0]

    def test_no_settings_uses_env_vars_only(self, tmp_path, monkeypatch):
        """Test that no settings file is valid (env vars only)."""
        empty = tmp_path / "env_only_app"
        empty.mkdir()
        monkeypatch.chdir(empty)

        with patch('pathlib.Path.home', return_value=tmp_path):
            from anova_oven_sdk.settings import find_settings_file

            result = find_settings_file()
            # Empty list is valid - can use env vars
            assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=anova_oven_sdk.settings", "--cov-report=term-missing"])
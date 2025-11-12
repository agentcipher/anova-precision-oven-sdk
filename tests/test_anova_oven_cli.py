"""
Unit tests for anova_oven_cli.py

This module provides comprehensive test coverage for the Anova Oven CLI,
including all commands, error conditions, and edge cases.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import the module under test
from anova_oven_cli import (
    AnovaOvenCLI,
    create_parser,
    async_main,
    main,
)
from anova_oven_sdk.models import (
    RecipeLibrary,
    Recipe,
    RecipeStageConfig,
    Device,
    OvenVersion,
    DeviceState,
)
from anova_oven_sdk.exceptions import AnovaError


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_recipe_library() -> RecipeLibrary:
    """Create a mock recipe library with test recipes."""
    library = RecipeLibrary()

    # Create a test recipe stage
    stage = RecipeStageConfig(
        name="Test Stage",
        temperature={"value": 200, "temperature_unit": "C", "mode": "DRY"},
        heating_elements={"top": True, "bottom": True, "rear": False},
        fan_speed=100,
        timer={"seconds": 1800},
        steam={"relative_humidity": 50, "steam_percentage": 30}
    )

    recipe = Recipe(
        recipe_id="test_recipe",
        name="Test Recipe",
        description="A test recipe",
        stages=[stage],
        oven_version=OvenVersion.V2
    )

    library.recipes = {"test_recipe": recipe}
    return library


@pytest.fixture
def mock_oven_device() -> Device:
    """Create a mock oven device."""
    return Device(
        cookerId="device123",
        name="Test Oven",
        pairedAt="2024-01-01T00:00:00Z",
        type=OvenVersion.V2,
        state=DeviceState.IDLE,
        current_temperature=25.0
    )


@pytest.fixture
def mock_oven_device_no_temp() -> Device:
    """Create a mock oven device without temperature."""
    return Device(
        cookerId="device456",
        name="Test Oven 2",
        pairedAt="2024-01-01T00:00:00Z",
        type=OvenVersion.V2,
        state=DeviceState.IDLE,
        current_temperature=None
    )


@pytest.fixture
def temp_recipe_file(tmp_path: Path) -> Path:
    """Create a temporary recipe file."""
    recipe_file = tmp_path / "recipes.yml"
    recipe_file.write_text("""
recipes:
  - test_recipe:
      name: Test Recipe
      description: A test recipe
      oven_version: v2
      stages:
        - name: Test Stage
          temperature:
            value: 200
            temperature_unit: C
            mode: DRY
          heating_elements:
            top: true
            bottom: true
            rear: false
          fan_speed: 100
          timer:
            seconds: 1800
""")
    return recipe_file


# ============================================================================
# AnovaOvenCLI Class Tests
# ============================================================================


class TestAnovaOvenCLI:
    """Tests for AnovaOvenCLI class."""

    def test_init_with_recipe_file(self) -> None:
        """Test CLI initialization with recipe file."""
        cli = AnovaOvenCLI(recipe_file="test.yml", environment="dev")
        assert cli.recipe_file == "test.yml"
        assert cli.environment == "dev"
        assert cli.library is None

    def test_init_without_recipe_file(self) -> None:
        """Test CLI initialization without recipe file."""
        with patch.object(AnovaOvenCLI, '_find_recipe_file', return_value='found.yml'):
            cli = AnovaOvenCLI()
            assert cli.recipe_file == 'found.yml'
            assert cli.environment is None

    def test_find_recipe_file_in_current_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test finding recipe file in current directory."""
        monkeypatch.chdir(tmp_path)
        recipe_file = tmp_path / "recipes.yml"
        recipe_file.touch()

        cli = AnovaOvenCLI()
        assert cli.recipe_file == "recipes.yml"

    def test_find_recipe_file_yaml_extension(self, tmp_path: Path, monkeypatch) -> None:
        """Test finding recipe file with .yaml extension."""
        monkeypatch.chdir(tmp_path)
        recipe_file = tmp_path / "recipes.yaml"
        recipe_file.touch()

        cli = AnovaOvenCLI()
        assert cli.recipe_file == "recipes.yaml"

    def test_find_recipe_file_in_home_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test finding recipe file in home directory."""
        # Create the .anova directory with recipes file
        anova_dir = tmp_path / ".anova"
        anova_dir.mkdir()
        recipe_file = anova_dir / "recipes.yml"
        recipe_file.touch()

        # Change to a different directory so current dir doesn't have recipes.yml
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        # Mock Path.home to return tmp_path
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)

        cli = AnovaOvenCLI()
        # Should find the file in home directory
        assert Path(cli.recipe_file).resolve() == recipe_file.resolve()

    def test_find_recipe_file_not_found(self) -> None:
        """Test finding recipe file when none exists."""
        with patch('pathlib.Path.exists', return_value=False):
            cli = AnovaOvenCLI()
            assert cli.recipe_file == "recipes.yml"

    def test_load_recipes_success(self, temp_recipe_file: Path) -> None:
        """Test loading recipes successfully."""
        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
        library = cli._load_recipes()

        assert library is not None
        assert "test_recipe" in library.recipes
        assert cli.library is library  # Cached

    def test_load_recipes_caching(self, temp_recipe_file: Path) -> None:
        """Test that recipes are cached after first load."""
        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))

        library1 = cli._load_recipes()
        library2 = cli._load_recipes()

        assert library1 is library2

    def test_load_recipes_file_not_found(self, capsys) -> None:
        """Test loading recipes when file doesn't exist."""
        cli = AnovaOvenCLI(recipe_file="nonexistent.yml")
        library = cli._load_recipes()

        assert library is not None
        assert len(library.recipes) == 0

        captured = capsys.readouterr()
        assert "Warning: Recipe file not found" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_discover_success(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test discover command with successful device discovery."""
        args = argparse.Namespace(timeout=5.0, json=False)

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_discover(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Found 1 device(s)" in captured.out
            assert "device123" in captured.out
            assert "Test Oven" in captured.out
            assert "25.0°C" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_discover_no_devices(self, capsys) -> None:
        """Test discover command when no devices are found."""
        args = argparse.Namespace(timeout=5.0, json=False)

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_discover(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "No devices found" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_discover_json_output(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test discover command with JSON output."""
        args = argparse.Namespace(timeout=5.0, json=True)

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_discover(args)

            assert exit_code == 0
            captured = capsys.readouterr()

            # With the fixed CLI, --json should output ONLY valid JSON
            # (no human-readable text mixed in)
            output = json.loads(captured.out.strip())

            assert isinstance(output, list)
            assert len(output) == 1
            assert output[0]['id'] == 'device123'
            assert output[0]['name'] == 'Test Oven'
            assert output[0]['type'] == 'oven_v2'
            assert output[0]['state'] == 'idle'

    @pytest.mark.asyncio
    async def test_cmd_discover_no_temperature(
        self,
        mock_oven_device_no_temp: Device,
        capsys
    ) -> None:
        """Test discover command with device that has no temperature."""
        args = argparse.Namespace(timeout=5.0, json=False)

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device_no_temp])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_discover(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Should not display temperature line
            assert "Temp:" not in captured.out

    @pytest.mark.asyncio
    async def test_cmd_discover_error(self, capsys) -> None:
        """Test discover command with error."""
        args = argparse.Namespace(timeout=5.0, json=False)

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(side_effect=AnovaError("Connection failed"))
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_discover(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error: Connection failed" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_recipes_list_success(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes list command."""
        args = argparse.Namespace(json=False)

        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
        exit_code = await cli.cmd_recipes_list(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "test_recipe" in captured.out
        assert "Test Recipe" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_list_no_recipes(self, capsys) -> None:
        """Test recipes list command with no recipes."""
        args = argparse.Namespace(json=False)

        with patch.object(AnovaOvenCLI, '_load_recipes') as mock_load:
            mock_load.return_value = RecipeLibrary()

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_list(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "No recipes found" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_list_json_output(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes list command with JSON output."""
        args = argparse.Namespace(json=True)

        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
        exit_code = await cli.cmd_recipes_list(args)

        assert exit_code == 0
        captured = capsys.readouterr()

        output = json.loads(captured.out)
        assert len(output) > 0
        assert output[0]['id'] == 'test_recipe'

    @pytest.mark.asyncio
    async def test_cmd_recipes_list_error(self, capsys) -> None:
        """Test recipes list command with error."""
        args = argparse.Namespace(json=False)

        with patch.object(AnovaOvenCLI, '_load_recipes') as mock_load:
            mock_load.side_effect = Exception("File error")

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_list(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error: File error" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_success(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes show command."""
        args = argparse.Namespace(recipe_id='test_recipe', json=False)

        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
        exit_code = await cli.cmd_recipes_show(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Test Recipe" in captured.out
        assert "Test Stage" in captured.out
        assert "200°C" in captured.out
        assert "30m 0s" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_json_output(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes show command with JSON output."""
        args = argparse.Namespace(recipe_id='test_recipe', json=True)

        cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
        exit_code = await cli.cmd_recipes_show(args)

        assert exit_code == 0
        captured = capsys.readouterr()

        output = json.loads(captured.out)
        assert output['recipe_id'] == 'test_recipe'
        assert output['name'] == 'Test Recipe'

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_with_steam_settings(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes show command displays recipe correctly."""
        # Create a recipe with steam in a temp file
        recipe_file = temp_recipe_file.parent / "steam_recipe.yml"
        recipe_file.write_text("""
recipes:
  - steam_recipe:
      name: Steam Test Recipe
      description: A test recipe with steam
      oven_version: v2
      stages:
        - name: Steam Stage
          temperature:
            value: 200
            temperature_unit: C
            mode: DRY
          heating_elements:
            top: true
            bottom: true
            rear: false
          fan_speed: 100
          timer:
            seconds: 1800
          steam:
            relative_humidity: 50
            steam_percentage: 30
""")

        args = argparse.Namespace(recipe_id='steam_recipe', json=False)

        cli = AnovaOvenCLI(recipe_file=str(recipe_file))
        exit_code = await cli.cmd_recipes_show(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Check that steam settings are shown
        assert "50% relative humidity" in captured.out or "steam_percentage" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_no_steam(
        self,
        capsys
    ) -> None:
        """Test recipes show command with recipe that has no steam."""
        stage = RecipeStageConfig(
            name="No Steam Stage",
            temperature={"value": 200, "temperature_unit": "C"},
            heating_elements={"top": True, "bottom": True, "rear": False},
            fan_speed=100,
            steam=None  # No steam
        )

        recipe = Recipe(
            recipe_id="no_steam_test",
            name="No Steam Test",
            description="Test",
            stages=[stage]
        )

        library = RecipeLibrary()
        library.recipes = {"no_steam_test": recipe}

        args = argparse.Namespace(recipe_id='no_steam_test', json=False)

        with patch.object(AnovaOvenCLI, '_load_recipes', return_value=library):
            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_show(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Should not show steam section
            assert "Steam:" not in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_no_timer(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes show command with recipe that has no timer."""
        stage = RecipeStageConfig(
            name="No Timer Stage",
            temperature={"value": 180, "temperature_unit": "C"},
            heating_elements={"top": True, "bottom": True},
            fan_speed=50,
            timer=None
        )

        recipe = Recipe(
            recipe_id="no_timer",
            name="No Timer",
            description="Test",
            stages=[stage]
        )

        library = RecipeLibrary()
        library.recipes = {"no_timer": recipe}

        args = argparse.Namespace(recipe_id='no_timer', json=False)

        with patch.object(AnovaOvenCLI, '_load_recipes', return_value=library):
            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_show(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Timer:" not in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_heating_elements(
        self,
        temp_recipe_file: Path,
        capsys
    ) -> None:
        """Test recipes show command displays heating elements correctly."""
        # Create recipe with specific heating elements
        stage = RecipeStageConfig(
            name="Test",
            temperature={"value": 200},
            heating_elements={"top": True, "bottom": False, "rear": True},
            fan_speed=100
        )

        recipe = Recipe(
            recipe_id="heating_test",
            name="Heating Test",
            description="Test",
            stages=[stage]
        )

        library = RecipeLibrary()
        library.recipes = {"heating_test": recipe}

        args = argparse.Namespace(recipe_id='heating_test', json=False)

        with patch.object(AnovaOvenCLI, '_load_recipes', return_value=library):
            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_show(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "top, rear" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_recipes_show_not_found(self, capsys) -> None:
        """Test recipes show command with invalid recipe ID."""
        args = argparse.Namespace(recipe_id='nonexistent', json=False)

        library = RecipeLibrary()

        with patch.object(AnovaOvenCLI, '_load_recipes', return_value=library):
            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_recipes_show(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error:" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_cook_with_recipe(
        self,
        temp_recipe_file: Path,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test cook command with recipe."""
        args = argparse.Namespace(
            device='device123',
            recipe='test_recipe',
            temp=None,
            unit='C',
            duration=None,
            fan_speed=100
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.get_device = Mock(return_value=mock_oven_device)
            mock_oven.start_cook = AsyncMock()
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI(recipe_file=str(temp_recipe_file))
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Cook started successfully" in captured.out
            mock_oven.start_cook.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_cook_simple_with_duration(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test simple cook command with duration."""
        args = argparse.Namespace(
            device='device123',
            recipe=None,
            temp=200.0,
            unit='C',
            duration=1800,
            fan_speed=80
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.start_cook = AsyncMock()
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "200" in captured.out and "°C" in captured.out
            assert "30m 0s" in captured.out
            assert "Cook started successfully" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_cook_simple_without_duration(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test simple cook command without duration."""
        args = argparse.Namespace(
            device='device123',
            recipe=None,
            temp=180.0,
            unit='F',
            duration=None,
            fan_speed=100
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.start_cook = AsyncMock()
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "180" in captured.out and "°F" in captured.out
            assert "Duration:" not in captured.out

    @pytest.mark.asyncio
    async def test_cmd_cook_device_not_found(self, capsys) -> None:
        """Test cook command with device not found."""
        args = argparse.Namespace(
            device='nonexistent',
            recipe=None,
            temp=200.0,
            unit='C',
            duration=None,
            fan_speed=100
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Device 'nonexistent' not found" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_cook_no_recipe_or_temp(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test cook command without recipe or temperature."""
        args = argparse.Namespace(
            device='device123',
            recipe=None,
            temp=None,
            unit='C',
            duration=None,
            fan_speed=100
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Provide either --recipe or --temp" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_cook_anova_error(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test cook command with AnovaError."""
        args = argparse.Namespace(
            device='device123',
            recipe=None,
            temp=200.0,
            unit='C',
            duration=None,
            fan_speed=100
        )

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.start_cook = AsyncMock(side_effect=AnovaError("Cook failed"))
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_cook(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error: Cook failed" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_stop_success(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test stop command."""
        args = argparse.Namespace(device='device123')

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.stop_cook = AsyncMock()
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_stop(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Cook stopped successfully" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_stop_device_not_found(self, capsys) -> None:
        """Test stop command with device not found."""
        args = argparse.Namespace(device='nonexistent')

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[])
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_stop(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Device 'nonexistent' not found" in captured.err

    @pytest.mark.asyncio
    async def test_cmd_stop_anova_error(
        self,
        mock_oven_device: Device,
        capsys
    ) -> None:
        """Test stop command with AnovaError."""
        args = argparse.Namespace(device='device123')

        with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
            mock_oven = AsyncMock()
            mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
            mock_oven.stop_cook = AsyncMock(side_effect=AnovaError("Stop failed"))
            mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
            mock_oven.__aexit__ = AsyncMock(return_value=None)
            mock_oven_class.return_value = mock_oven

            cli = AnovaOvenCLI()
            exit_code = await cli.cmd_stop(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error: Stop failed" in captured.err


# ============================================================================
# Parser Tests
# ============================================================================


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_creation(self) -> None:
        """Test parser is created correctly."""
        parser = create_parser()
        assert parser is not None
        assert parser.description == "Anova Oven CLI - Control your Anova Precision Oven"

    def test_parser_global_arguments(self) -> None:
        """Test global arguments are defined."""
        parser = create_parser()

        # Parse with recipe file
        args = parser.parse_args(['--recipe-file', 'test.yml', 'discover'])
        assert args.recipe_file == 'test.yml'

        # Parse with environment
        args = parser.parse_args(['--env', 'dev', 'discover'])
        assert args.env == 'dev'

    def test_parser_discover_command(self) -> None:
        """Test discover command arguments."""
        parser = create_parser()
        args = parser.parse_args(['discover', '--timeout', '10', '--json'])

        assert args.command == 'discover'
        assert args.timeout == 10.0
        assert args.json is True

    def test_parser_recipes_list_command(self) -> None:
        """Test recipes list command arguments."""
        parser = create_parser()
        args = parser.parse_args(['recipes', 'list', '--json'])

        assert args.command == 'recipes'
        assert args.recipes_command == 'list'
        assert args.json is True

    def test_parser_recipes_show_command(self) -> None:
        """Test recipes show command arguments."""
        parser = create_parser()
        args = parser.parse_args(['recipes', 'show', 'test_recipe', '--json'])

        assert args.command == 'recipes'
        assert args.recipes_command == 'show'
        assert args.recipe_id == 'test_recipe'
        assert args.json is True

    def test_parser_cook_command_with_recipe(self) -> None:
        """Test cook command with recipe."""
        parser = create_parser()
        args = parser.parse_args([
            'cook',
            '--device', 'device123',
            '--recipe', 'test_recipe'
        ])

        assert args.command == 'cook'
        assert args.device == 'device123'
        assert args.recipe == 'test_recipe'

    def test_parser_cook_command_simple(self) -> None:
        """Test cook command with simple parameters."""
        parser = create_parser()
        args = parser.parse_args([
            'cook',
            '--device', 'device123',
            '--temp', '200',
            '--unit', 'F',
            '--duration', '1800',
            '--fan-speed', '80'
        ])

        assert args.command == 'cook'
        assert args.device == 'device123'
        assert args.temp == 200.0
        assert args.unit == 'F'
        assert args.duration == 1800
        assert args.fan_speed == 80

    def test_parser_cook_command_defaults(self) -> None:
        """Test cook command default values."""
        parser = create_parser()
        args = parser.parse_args(['cook', '--device', 'device123', '--temp', '200'])

        assert args.unit == 'C'
        assert args.fan_speed == 100

    def test_parser_stop_command(self) -> None:
        """Test stop command arguments."""
        parser = create_parser()
        args = parser.parse_args(['stop', '--device', 'device123'])

        assert args.command == 'stop'
        assert args.device == 'device123'


# ============================================================================
# Main Function Tests
# ============================================================================


class TestAsyncMain:
    """Tests for async_main function."""

    @pytest.mark.asyncio
    async def test_async_main_no_command(self, capsys) -> None:
        """Test async_main with no command prints help."""
        with patch('sys.argv', ['anova_oven_cli.py']):
            exit_code = await async_main()

            assert exit_code == 1

    @pytest.mark.asyncio
    async def test_async_main_discover_command(self) -> None:
        """Test async_main with discover command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'discover']):
            with patch.object(AnovaOvenCLI, 'cmd_discover', return_value=0) as mock_cmd:
                exit_code = await async_main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_recipes_list_command(self) -> None:
        """Test async_main with recipes list command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'recipes', 'list']):
            with patch.object(AnovaOvenCLI, 'cmd_recipes_list', return_value=0) as mock_cmd:
                exit_code = await async_main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_recipes_show_command(self) -> None:
        """Test async_main with recipes show command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'recipes', 'show', 'test']):
            with patch.object(AnovaOvenCLI, 'cmd_recipes_show', return_value=0) as mock_cmd:
                exit_code = await async_main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_recipes_no_subcommand(self, capsys) -> None:
        """Test async_main with recipes command but no subcommand."""
        with patch('sys.argv', ['anova_oven_cli.py', 'recipes']):
            # parser.parse_args will raise SystemExit when showing help
            with pytest.raises(SystemExit) as exc_info:
                await async_main()

            # Exit code 0 means help was shown (not an error)
            assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_async_main_cook_command(self) -> None:
        """Test async_main with cook command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'cook', '--device', 'test', '--temp', '200']):
            with patch.object(AnovaOvenCLI, 'cmd_cook', return_value=0) as mock_cmd:
                exit_code = await async_main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_stop_command(self) -> None:
        """Test async_main with stop command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'stop', '--device', 'test']):
            with patch.object(AnovaOvenCLI, 'cmd_stop', return_value=0) as mock_cmd:
                exit_code = await async_main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_unknown_command(self, capsys) -> None:
        """Test async_main with unknown command."""
        with patch('sys.argv', ['anova_oven_cli.py', 'unknown']):
            # Argparse raises SystemExit with code 2 for invalid arguments
            with pytest.raises(SystemExit) as exc_info:
                await async_main()

            # Exit code 2 means invalid argument
            assert exc_info.value.code == 2

    @pytest.mark.asyncio
    async def test_async_main_with_recipe_file(self) -> None:
        """Test async_main with recipe file argument."""
        with patch('sys.argv', ['anova_oven_cli.py', '--recipe-file', 'test.yml', 'discover']):
            with patch.object(AnovaOvenCLI, 'cmd_discover', return_value=0):
                exit_code = await async_main()

                assert exit_code == 0

    @pytest.mark.asyncio
    async def test_async_main_with_environment(self) -> None:
        """Test async_main with environment argument."""
        with patch('sys.argv', ['anova_oven_cli.py', '--env', 'dev', 'discover']):
            with patch.object(AnovaOvenCLI, 'cmd_discover', return_value=0):
                exit_code = await async_main()

                assert exit_code == 0


class TestMain:
    """Tests for main function."""

    def test_main_success(self) -> None:
        """Test main function with successful execution."""
        with patch('anova_oven_cli.async_main', return_value=0):
            exit_code = main()

            assert exit_code == 0

    def test_main_keyboard_interrupt(self, capsys) -> None:
        """Test main function with keyboard interrupt."""
        with patch('anova_oven_cli.async_main', side_effect=KeyboardInterrupt()):
            exit_code = main()

            assert exit_code == 130
            captured = capsys.readouterr()
            assert "Interrupted by user" in captured.err

    def test_main_unexpected_error(self, capsys) -> None:
        """Test main function with unexpected error."""
        with patch('anova_oven_cli.async_main', side_effect=RuntimeError("Unexpected")):
            exit_code = main()

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Unexpected error" in captured.err


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for CLI."""

    @pytest.mark.asyncio
    async def test_full_discover_workflow(
        self,
        mock_oven_device: Device
    ) -> None:
        """Test complete discover workflow."""
        with patch('sys.argv', ['anova_oven_cli.py', 'discover', '--timeout', '2']):
            with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
                mock_oven = AsyncMock()
                mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
                mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
                mock_oven.__aexit__ = AsyncMock(return_value=None)
                mock_oven_class.return_value = mock_oven

                exit_code = await async_main()

                assert exit_code == 0

    @pytest.mark.asyncio
    async def test_full_cook_workflow(
        self,
        temp_recipe_file: Path,
        mock_oven_device: Device
    ) -> None:
        """Test complete cook workflow with recipe."""
        with patch('sys.argv', [
            'anova_oven_cli.py',
            '--recipe-file', str(temp_recipe_file),
            'cook',
            '--device', 'device123',
            '--recipe', 'test_recipe'
        ]):
            with patch('anova_oven_cli.AnovaOven') as mock_oven_class:
                mock_oven = AsyncMock()
                mock_oven.discover_devices = AsyncMock(return_value=[mock_oven_device])
                mock_oven.get_device = Mock(return_value=mock_oven_device)
                mock_oven.start_cook = AsyncMock()
                mock_oven.__aenter__ = AsyncMock(return_value=mock_oven)
                mock_oven.__aexit__ = AsyncMock(return_value=None)
                mock_oven_class.return_value = mock_oven

                exit_code = await async_main()

                assert exit_code == 0
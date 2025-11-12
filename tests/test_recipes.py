# ============================================================================
# Recipe System Tests
# ============================================================================
"""
Tests for recipe models and functionality.

Run with:
    pytest test_recipes.py -v
"""

import pytest
from pathlib import Path
import tempfile

from anova_oven_sdk.models import (
    Temperature,
    OvenVersion,
    CookStage,
    HeatingElements,
    Recipe,
    RecipeLibrary,
    RecipeStageConfig,
    TemperatureMode
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_recipe_yaml():
    """Sample recipe YAML content."""
    return """
recipes:
  - test_recipe:
      name: "Test Recipe"
      description: "A test recipe"
      oven_version: "v1"
      stages:
        - name: "Stage 1"
          temperature:
            value: 200
            temperature_unit: "C"
            mode: "DRY"
          timer:
            seconds: 300
          heating_elements:
            top: true
            bottom: false
            rear: false
          fan_speed: 100
          rack_position: 3

  - fahrenheit_recipe:
      name: "Fahrenheit Recipe"
      description: "Recipe using Fahrenheit"
      stages:
        - name: "Fahrenheit Stage"
          temperature:
            value: 392
            temperature_unit: "F"
            mode: "DRY"
          timer:
            seconds: 600
          heating_elements:
            top: false
            bottom: false
            rear: true
          fan_speed: 100
          rack_position: 3
"""


@pytest.fixture
def recipe_file(sample_recipe_yaml):
    """Create temporary recipe file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(sample_recipe_yaml)
        filepath = f.name

    yield filepath

    # Cleanup
    Path(filepath).unlink(missing_ok=True)


@pytest.fixture
def sample_stage_config():
    """Sample RecipeStageConfig."""
    return RecipeStageConfig(
        name="Test Stage",
        temperature={
            "value": 180,
            "temperature_unit": "C",
            "mode": "DRY"
        },
        timer={"seconds": 300},
        heating_elements={
            "top": False,
            "bottom": False,
            "rear": True
        },
        fan_speed=100,
        rack_position=3
    )


# ============================================================================
# RecipeStageConfig Tests
# ============================================================================

class TestRecipeStageConfig:
    """Tests for RecipeStageConfig model."""

    def test_valid_stage_config(self, sample_stage_config):
        """Test creating valid stage config."""
        assert sample_stage_config.name == "Test Stage"
        assert sample_stage_config.temperature["value"] == 180
        assert sample_stage_config.fan_speed == 100

    def test_temperature_validation(self):
        """Test temperature configuration validation."""
        # Missing value should raise error
        with pytest.raises(ValueError, match="Temperature must include 'value'"):
            RecipeStageConfig(
                name="Invalid",
                temperature={"temperature_unit": "C"}
            )

    def test_default_temperature_unit(self):
        """Test default temperature unit is Celsius."""
        config = RecipeStageConfig(
            name="Test",
            temperature={"value": 200}
        )
        assert config.temperature["temperature_unit"] == "C"

    def test_default_mode(self):
        """Test default temperature mode is DRY."""
        config = RecipeStageConfig(
            name="Test",
            temperature={"value": 200}
        )
        assert config.temperature["mode"] == "DRY"

    def test_invalid_temperature_unit(self):
        """Test invalid temperature unit raises error."""
        with pytest.raises(ValueError, match="temperature_unit must be"):
            RecipeStageConfig(
                name="Test",
                temperature={
                    "value": 200,
                    "temperature_unit": "K"  # Invalid
                }
            )

    def test_to_cook_stage_celsius(self, sample_stage_config):
        """Test converting stage config to CookStage with Celsius."""
        cook_stage = sample_stage_config.to_cook_stage()

        assert isinstance(cook_stage, CookStage)
        assert isinstance(cook_stage.temperature, Temperature)
        assert cook_stage.temperature.celsius == 180
        assert cook_stage.mode == TemperatureMode.DRY
        assert cook_stage.fan_speed == 100

    def test_to_cook_stage_fahrenheit(self):
        """Test converting stage config to CookStage with Fahrenheit."""
        config = RecipeStageConfig(
            name="Test",
            temperature={
                "value": 392,
                "temperature_unit": "F",
                "mode": "DRY"
            }
        )

        cook_stage = config.to_cook_stage()
        assert abs(cook_stage.temperature.celsius - 200) < 0.1
        assert abs(cook_stage.temperature.fahrenheit - 392) < 0.1

    def test_to_cook_stage_with_steam(self):
        """Test converting stage with steam settings."""
        config = RecipeStageConfig(
            name="Steam Test",
            temperature={"value": 100, "mode": "WET"},
            steam={"steam_percentage": 100}
        )

        cook_stage = config.to_cook_stage()
        assert cook_stage.steam is not None
        assert cook_stage.steam.steam_percentage == 100


# ============================================================================
# Recipe Tests
# ============================================================================

class TestRecipe:
    """Tests for Recipe model."""

    def test_load_from_yaml_file(self, recipe_file):
        """Test loading recipe from YAML file."""
        recipe = Recipe.from_yaml_file(recipe_file, "test_recipe")

        assert recipe.recipe_id == "test_recipe"
        assert recipe.name == "Test Recipe"
        assert recipe.description == "A test recipe"
        assert recipe.oven_version == OvenVersion.V1
        assert len(recipe.stages) == 1

    def test_recipe_not_found(self, recipe_file):
        """Test loading non-existent recipe raises error."""
        with pytest.raises(ValueError, match="Recipe 'nonexistent' not found"):
            Recipe.from_yaml_file(recipe_file, "nonexistent")

    def test_file_not_found(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            Recipe.from_yaml_file("nonexistent.yml", "test")

    def test_to_cook_stages(self, recipe_file):
        """Test converting recipe to cook stages."""
        recipe = Recipe.from_yaml_file(recipe_file, "test_recipe")
        stages = recipe.to_cook_stages()

        assert len(stages) == 1
        assert isinstance(stages[0], CookStage)
        assert stages[0].title == "Stage 1"

    def test_validate_for_oven_compatible(self, recipe_file):
        """Test recipe validation for compatible oven."""
        recipe = Recipe.from_yaml_file(recipe_file, "test_recipe")

        # Should not raise error
        recipe.validate_for_oven(OvenVersion.V1)

    def test_validate_for_oven_incompatible(self, recipe_file):
        """Test recipe validation for incompatible oven."""
        recipe = Recipe.from_yaml_file(recipe_file, "test_recipe")

        # Should raise error - recipe is for v1, but checking v2
        with pytest.raises(ValueError, match="designed for"):
            recipe.validate_for_oven(OvenVersion.V2)

    def test_recipe_without_version(self, recipe_file):
        """Test recipe without oven_version works with any oven."""
        recipe = Recipe.from_yaml_file(recipe_file, "fahrenheit_recipe")

        # Should work with both versions
        recipe.validate_for_oven(OvenVersion.V1)
        recipe.validate_for_oven(OvenVersion.V2)

    def test_empty_stages_error(self):
        """Test recipe with no stages raises error."""
        with pytest.raises(ValueError, match="at least one stage"):
            Recipe(
                recipe_id="test",
                name="Test",
                stages=[]
            )

    def test_to_dict(self, recipe_file):
        """Test converting recipe to dictionary."""
        recipe = Recipe.from_yaml_file(recipe_file, "test_recipe")
        recipe_dict = recipe.to_dict()

        assert recipe_dict["recipe_id"] == "test_recipe"
        assert recipe_dict["name"] == "Test Recipe"
        assert len(recipe_dict["stages"]) == 1
        assert recipe_dict["oven_version"] == "oven_v1"


# ============================================================================
# RecipeLibrary Tests
# ============================================================================

class TestRecipeLibrary:
    """Tests for RecipeLibrary model."""

    def test_load_from_yaml_file(self, recipe_file):
        """Test loading recipe library from YAML file."""
        library = RecipeLibrary.from_yaml_file(recipe_file)

        assert len(library.recipes) == 2
        assert "test_recipe" in library.recipes
        assert "fahrenheit_recipe" in library.recipes

    def test_get_recipe(self, recipe_file):
        """Test getting recipe by ID."""
        library = RecipeLibrary.from_yaml_file(recipe_file)
        recipe = library.get_recipe("test_recipe")

        assert recipe.name == "Test Recipe"

    def test_get_nonexistent_recipe(self, recipe_file):
        """Test getting non-existent recipe raises error."""
        library = RecipeLibrary.from_yaml_file(recipe_file)

        with pytest.raises(ValueError, match="not found"):
            library.get_recipe("nonexistent")

    def test_list_recipes(self, recipe_file):
        """Test listing all recipe IDs."""
        library = RecipeLibrary.from_yaml_file(recipe_file)
        recipe_ids = library.list_recipes()

        assert len(recipe_ids) == 2
        assert "test_recipe" in recipe_ids
        assert "fahrenheit_recipe" in recipe_ids

    def test_list_recipes_with_info(self, recipe_file):
        """Test listing recipes with detailed info."""
        library = RecipeLibrary.from_yaml_file(recipe_file)
        info_list = library.list_recipes_with_info()

        assert len(info_list) == 2

        # Check first recipe info
        info = next(i for i in info_list if i['id'] == 'test_recipe')
        assert info['name'] == "Test Recipe"
        assert info['description'] == "A test recipe"
        assert info['stages'] == 1
        assert info['oven_version'] == "oven_v1"

    def test_save_to_yaml(self, recipe_file):
        """Test saving library to YAML file."""
        library = RecipeLibrary.from_yaml_file(recipe_file)

        # Save to new file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            output_file = f.name

        try:
            library.save_to_yaml(output_file)

            # Load back and verify
            loaded_library = RecipeLibrary.from_yaml_file(output_file)
            assert len(loaded_library.recipes) == 2
            assert "test_recipe" in loaded_library.recipes

        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_empty_library(self):
        """Test creating empty library."""
        library = RecipeLibrary()

        assert len(library.recipes) == 0
        assert library.list_recipes() == []


# ============================================================================
# Integration Tests
# ============================================================================

class TestRecipeIntegration:
    """Integration tests for recipe system."""

    def test_full_recipe_workflow(self, recipe_file):
        """Test complete workflow from YAML to CookStage."""
        # Load library
        library = RecipeLibrary.from_yaml_file(recipe_file)

        # Get recipe
        recipe = library.get_recipe("test_recipe")

        # Validate for oven
        recipe.validate_for_oven(OvenVersion.V1)

        # Convert to cook stages
        stages = recipe.to_cook_stages()

        # Verify stages are ready to use
        assert len(stages) == 1
        assert isinstance(stages[0], CookStage)
        assert stages[0].temperature.celsius == 200
        assert stages[0].timer is not None
        assert stages[0].timer.initial == 300

    def test_fahrenheit_to_celsius_conversion(self, recipe_file):
        """Test automatic Fahrenheit to Celsius conversion."""
        recipe = Recipe.from_yaml_file(recipe_file, "fahrenheit_recipe")
        stages = recipe.to_cook_stages()

        # Recipe specifies 392°F, should convert to 200°C
        assert abs(stages[0].temperature.celsius - 200) < 0.1
        assert abs(stages[0].temperature.fahrenheit - 392) < 0.1

    def test_create_and_save_recipe(self):
        """Test creating recipe programmatically and saving."""
        # Create recipe
        stages = [
            RecipeStageConfig(
                name="Test Stage",
                temperature={
                    "value": 180,
                    "temperature_unit": "C",
                    "mode": "DRY"
                },
                timer={"seconds": 300},
                heating_elements={
                    "top": False,
                    "bottom": False,
                    "rear": True
                }
            )
        ]

        recipe = Recipe(
            recipe_id="programmatic_recipe",
            name="Programmatic Recipe",
            description="Created in code",
            stages=stages
        )

        # Create library
        library = RecipeLibrary(recipes={"programmatic_recipe": recipe})

        # Save to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            output_file = f.name

        try:
            library.save_to_yaml(output_file)

            # Verify we can load it back
            loaded = RecipeLibrary.from_yaml_file(output_file)
            assert "programmatic_recipe" in loaded.recipes
            assert loaded.get_recipe("programmatic_recipe").name == "Programmatic Recipe"

        finally:
            Path(output_file).unlink(missing_ok=True)

class TestRecipeStageConfigSteamCoverage:
    """Tests for RecipeStageConfig steam settings coverage."""

    def test_to_cook_stage_with_relative_humidity(self):
        """Test converting stage with relative_humidity steam (covers line 504)."""
        config = RecipeStageConfig(
            name="Steam Test",
            temperature={
                "value": 100,
                "temperature_unit": "C",
                "mode": "WET"
            },
            steam={
                "relative_humidity": 85
            }
        )

        cook_stage = config.to_cook_stage()

        # Verify steam settings were created correctly
        assert cook_stage.steam is not None
        assert cook_stage.steam.relative_humidity == 85
        assert cook_stage.steam.mode.value == "relative-humidity"

    def test_to_cook_stage_with_steam_percentage(self):
        """Test converting stage with steam_percentage (already covered but for completeness)."""
        config = RecipeStageConfig(
            name="Steam Test",
            temperature={
                "value": 100,
                "temperature_unit": "C",
                "mode": "WET"
            },
            steam={
                "steam_percentage": 100
            }
        )

        cook_stage = config.to_cook_stage()

        # Verify steam settings were created correctly
        assert cook_stage.steam is not None
        assert cook_stage.steam.steam_percentage == 100
        assert cook_stage.steam.mode.value == "steam-percentage"


class TestRecipeValidationCoverage:
    """Tests for Recipe validation coverage."""

    def test_validate_for_oven_with_stage_validation_failure(self):
        """Test Recipe.validate_for_oven when stage validation fails (covers lines 595-596)."""
        # Create a recipe with an invalid temperature for wet bulb mode
        # Wet bulb mode only allows temps between 25-100°C
        stage = RecipeStageConfig(
            name="Invalid Stage",
            temperature={
                "value": 150,  # Too high for wet bulb mode
                "temperature_unit": "C",
                "mode": "WET"  # Wet mode has stricter limits
            }
        )

        recipe = Recipe(
            recipe_id="test_invalid",
            name="Test Invalid Recipe",
            description="Recipe with invalid stage",
            stages=[stage]
        )

        # This should raise ValueError with "Stage 1 validation failed" message
        with pytest.raises(ValueError, match=r"Stage \d+ validation failed"):
            recipe.validate_for_oven(OvenVersion.V2)

    def test_validate_for_oven_with_multiple_stages_failure(self):
        """Test validation failure on second stage."""
        # First stage is valid
        stage1 = RecipeStageConfig(
            name="Valid Stage",
            temperature={
                "value": 200,
                "temperature_unit": "C",
                "mode": "DRY"
            }
        )

        # Second stage is invalid
        stage2 = RecipeStageConfig(
            name="Invalid Stage",
            temperature={
                "value": 110,  # Too high for wet bulb
                "temperature_unit": "C",
                "mode": "WET"
            }
        )

        recipe = Recipe(
            recipe_id="test_multi_stage",
            name="Multi Stage Test",
            stages=[stage1, stage2]
        )

        # Should fail on stage 2
        with pytest.raises(ValueError, match="Stage 2 validation failed"):
            recipe.validate_for_oven(OvenVersion.V2)


class TestRecipeFromYamlDictCoverage:
    """Tests for Recipe.from_yaml_dict coverage."""

    def test_from_yaml_dict_with_v2_oven_version(self):
        """Test from_yaml_dict with oven_version='v2' (covers line 617)."""
        data = {
            'name': 'Test V2 Recipe',
            'description': 'Recipe for V2 oven',
            'oven_version': 'v2',  # This should trigger line 617
            'stages': [
                {
                    'name': 'Test Stage',
                    'temperature': {
                        'value': 200,
                        'temperature_unit': 'C',
                        'mode': 'DRY'
                    }
                }
            ]
        }

        recipe = Recipe.from_yaml_dict('test_v2', data)

        assert recipe.recipe_id == 'test_v2'
        assert recipe.name == 'Test V2 Recipe'
        assert recipe.oven_version == OvenVersion.V2
        assert len(recipe.stages) == 1

    def test_from_yaml_dict_with_v1_oven_version(self):
        """Test from_yaml_dict with oven_version='v1' (for completeness)."""
        data = {
            'name': 'Test V1 Recipe',
            'description': 'Recipe for V1 oven',
            'oven_version': 'v1',
            'stages': [
                {
                    'name': 'Test Stage',
                    'temperature': {
                        'value': 200,
                        'temperature_unit': 'C',
                        'mode': 'DRY'
                    }
                }
            ]
        }

        recipe = Recipe.from_yaml_dict('test_v1', data)

        assert recipe.recipe_id == 'test_v1'
        assert recipe.oven_version == OvenVersion.V1

    def test_from_yaml_dict_with_no_oven_version(self):
        """Test from_yaml_dict without oven_version (should be None)."""
        data = {
            'name': 'Universal Recipe',
            'description': 'Works on any oven',
            'stages': [
                {
                    'name': 'Test Stage',
                    'temperature': {
                        'value': 200,
                        'temperature_unit': 'C',
                        'mode': 'DRY'
                    }
                }
            ]
        }

        recipe = Recipe.from_yaml_dict('test_universal', data)

        assert recipe.recipe_id == 'test_universal'
        assert recipe.oven_version is None


class TestRecipeLibraryFromYamlFileCoverage:
    """Tests for RecipeLibrary.from_yaml_file coverage."""

    def test_from_yaml_file_with_nonexistent_file(self):
        """Test from_yaml_file with non-existent file (covers line 788)."""
        nonexistent_path = "/tmp/this_file_definitely_does_not_exist_12345.yml"

        # Ensure file doesn't exist
        path = Path(nonexistent_path)
        if path.exists():
            path.unlink()

        # This should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Recipe file not found"):
            RecipeLibrary.from_yaml_file(nonexistent_path)

    def test_from_yaml_file_with_valid_file(self):
        """Test from_yaml_file with valid file (for completeness)."""
        # Create temporary YAML file
        yaml_content = """
recipes:
  - test_recipe:
      name: "Test Recipe"
      description: "A test recipe"
      stages:
        - name: "Stage 1"
          temperature:
            value: 200
            temperature_unit: "C"
            mode: "DRY"
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            library = RecipeLibrary.from_yaml_file(temp_path)

            assert len(library.recipes) == 1
            assert 'test_recipe' in library.recipes
            assert library.recipes['test_recipe'].name == "Test Recipe"

        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestIntegrationCoverage:
    """Integration tests to ensure all paths are covered."""

    def test_full_recipe_workflow_with_relative_humidity(self):
        """Test complete workflow with relative humidity steam."""
        # Create YAML with relative humidity
        yaml_content = """
recipes:
  - steam_recipe:
      name: "Steam Recipe"
      description: "Recipe with relative humidity"
      oven_version: "v2"
      stages:
        - name: "Steam Stage"
          temperature:
            value: 90
            temperature_unit: "C"
            mode: "WET"
          steam:
            relative_humidity: 90
          timer:
            seconds: 600
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            # Load recipe
            recipe = Recipe.from_yaml_file(temp_path, 'steam_recipe')

            # Verify recipe details
            assert recipe.name == "Steam Recipe"
            assert recipe.oven_version == OvenVersion.V2

            # Convert to cook stages
            cook_stages = recipe.to_cook_stages()
            assert len(cook_stages) == 1

            # Verify steam settings
            stage = cook_stages[0]
            assert stage.steam is not None
            assert stage.steam.relative_humidity == 90

            # Validate for oven
            recipe.validate_for_oven(OvenVersion.V2)

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_recipe_validation_error_propagation(self):
        """Test that validation errors are properly caught and re-raised."""
        # Create recipe with bottom-only heating at too high temperature for V1
        stage = RecipeStageConfig(
            name="Bottom Only",
            temperature={
                "value": 200,  # Too high for bottom-only on V1 (max 180°C)
                "temperature_unit": "C",
                "mode": "DRY"
            },
            heating_elements={
                "top": False,
                "bottom": True,
                "rear": False
            }
        )

        recipe = Recipe(
            recipe_id="bottom_only_test",
            name="Bottom Only Test",
            stages=[stage]
        )

        # Should fail validation for V1
        with pytest.raises(ValueError, match="Stage 1 validation failed"):
            recipe.validate_for_oven(OvenVersion.V1)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
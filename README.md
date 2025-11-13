# Anova Precision Oven SDK

**⚠️ DISCLAIMER**

This software is provided "as is" without warranty of any kind, express or implied. The authors and contributors are not liable for any damages, losses, or issues arising from the use of this software, including but not limited to:
- Device malfunction or damage
- Property damage
- Food safety issues
- Data loss
- Service interruptions

Use at your own risk. Always supervise cooking operations and follow manufacturer guidelines for your Anova Precision Oven. This is unofficial software not endorsed by Anova Culinary.

---

Python SDK for controlling Anova Precision Ovens using the official Anova API ([https://developer.anovaculinary.com/docs/devices/wifi/oven-commands](https://developer.anovaculinary.com/docs/devices/wifi/oven-commands)). The goal of this final project is to create an integration for Home Assistant which leverages this SDK for operation. The majority of this code was written using Anthropic Claude ([https://claude.ai](https://claude.ai))

## Installation

```bash
# Using pip
pip install .
```

## Configuration

### Settings File

Create `settings.yaml`:

```yaml
default:
  log_level: INFO
  supported_accessories:
    - APO
```

### Authentication

Create `.secrets.yaml` (add to .gitignore):

```yaml
default:
  token: "anova-your-token-here"
```

Or use environment variables:

```bash
export ANOVA_TOKEN="anova-your-token-here"
```

## Quick Start

```python
from anova_oven_sdk import AnovaOven
from anova_oven_sdk import CookingPresets

async def main():
    async with AnovaOven() as oven:
        # Discover devices
        devices = await oven.discover_devices()
        device_id = devices[0].id
        
        # Simple roast
        await oven.start_cook(
            device_id=device_id,
            temperature=200,
            duration=1800  # 30 minutes
        )
        
        # Or use presets
        await CookingPresets.roast(
            oven, device_id,
            temperature=200,
            duration_minutes=30
        )

import asyncio
asyncio.run(main())
```

## Environment Configuration

Switch environments using `ANOVA_ENV`:

```bash
# Development (debug logging, more retries)
export ANOVA_ENV=development
python your_script.py

# Production (warning logging, optimized)
export ANOVA_ENV=production
python your_script.py
```

## Command Line Interface (CLI)

The `anova_oven_cli.py` provides a powerful command-line interface for controlling your oven and managing recipes.

### Global Options

```bash
# Specify custom recipe file location
python anova_oven_cli.py --recipe-file /path/to/recipes.yml <command>

# Set environment
python anova_oven_cli.py --env development <command>
```

### Device Discovery

```bash
# Discover devices
python anova_oven_cli.py discover

# With custom timeout
python anova_oven_cli.py discover --timeout 10.0

# Output as JSON (for scripting)
python anova_oven_cli.py discover --json
```

Example output:
```
Discovering devices...

Found 1 device(s):

  Name:    My Anova Oven
  ID:      anova-abc123def456
  Type:    APO
  State:   idle
  Temp:    25°C
```

### Recipe Management

#### List Available Recipes

```bash
# List all recipes
python anova_oven_cli.py recipes list

# Output as JSON
python anova_oven_cli.py recipes list --json
```

Example output:
```
Available recipes from recipes.yml:

  perfect_toast_v1
    Name:         Perfect Toast (V1 Oven)
    Description:  Replicate the Anova V1 Toast Recipe
    Stages:       2
    Oven Version: v1

  sous_vide_steak
    Name:         Sous Vide Steak
    Description:  Perfectly cooked steak with steam
    Stages:       2
    Oven Version: any
```

#### Show Recipe Details

```bash
# Show detailed recipe information
python anova_oven_cli.py recipes show perfect_toast_v1

# Output as JSON
python anova_oven_cli.py recipes show perfect_toast_v1 --json
```

Example output:
```
Recipe: Perfect Toast (V1 Oven)
ID: perfect_toast_v1
Description: Replicate the Anova V1 Toast Recipe
Oven Version: v1

Stages (2):

  Stage 1: Preheat
    Temperature: 450°F
    Mode: DRY
    Timer: 3m 0s
    Heating: top, bottom
    Fan Speed: 100%

  Stage 2: Toast
    Temperature: 450°F
    Mode: DRY
    Timer: 4m 0s
    Heating: top, bottom
    Fan Speed: 100%
```

### Recipe File Format

The CLI automatically searches for recipe files in the following locations:
1. `recipes.yml` (current directory)
2. `recipes.yaml` (current directory)
3. `~/.anova/recipes.yml` (user home directory)
4. `recipes.yml` (same directory as anova_oven_cli.py)

Create a `recipes.yml` file with your custom recipes:

```yaml
recipes:
  my_roast:
    name: "Perfect Roast Chicken"
    description: "Juicy roast chicken with crispy skin"
    oven_version: "v2"  # or "v1", or omit for any version
    stages:
      - name: "Roast"
        temperature:
          value: 180
          temperature_unit: "C"
          mode: "DRY"
        heating_elements:
          top: true
          bottom: true
          rear: true
        fan_speed: 100
        timer:
          seconds: 3600  # 1 hour
      
      - name: "Crisp Skin"
        temperature:
          value: 220
          temperature_unit: "C"
          mode: "DRY"
        heating_elements:
          top: true
          bottom: false
          rear: false
        fan_speed: 100
        timer:
          seconds: 600  # 10 minutes

  sous_vide_salmon:
    name: "Sous Vide Salmon"
    description: "Perfectly cooked salmon with steam"
    stages:
      - name: "Sous Vide"
        temperature:
          value: 50
          temperature_unit: "C"
          mode: "WET"
        heating_elements:
          rear: true
        fan_speed: 100
        steam:
          steam_percentage: 100
        timer:
          seconds: 1800  # 30 minutes
```

## Python SDK Usage

### Multi-Stage Cooking

```python
from anova_oven_sdk import (
    AnovaOven, CookStage, Temperature, Timer,
    SteamSettings, SteamMode, HeatingElements,
    TemperatureMode, TimerStartType
)

async with AnovaOven() as oven:
    devices = await oven.discover_devices()
    
    # Sous vide then sear
    stages = [
        CookStage(
            temperature=Temperature.from_celsius(60),
            mode=TemperatureMode.WET,
            timer=Timer(initial=3600),
            steam=SteamSettings(
                mode=SteamMode.STEAM_PERCENTAGE,
                steam_percentage=100
            ),
            title="Sous Vide"
        ),
        CookStage(
            temperature=Temperature.from_celsius(250),
            timer=Timer(
                initial=300,
                start_type=TimerStartType.WHEN_PREHEATED
            ),
            heating_elements=HeatingElements(
                top=True,
                bottom=True,
                rear=False
            ),
            title="Sear"
        )
    ]
    
    await oven.start_cook(devices[0].id, stages=stages)
```

### Using Recipe Library in Code

```python
from anova_oven_sdk import AnovaOven, RecipeLibrary

async with AnovaOven() as oven:
    # Load recipes from file
    library = RecipeLibrary.from_yaml_file('recipes.yml')
    
    # Get a specific recipe
    recipe = library.get_recipe('perfect_toast_v1')
    
    # Validate recipe for device
    devices = await oven.discover_devices()
    device = devices[0]
    recipe.validate_for_oven(device.oven_version)
    
    # Convert recipe to cook stages
    stages = recipe.to_cook_stages()
    
    # Start cooking
    await oven.start_cook(device.id, stages=stages)
```

### Settings Configuration

See `settings.yaml` for all available configuration options:
- WebSocket settings (timeout, retries)
- Logging configuration (level, file, rotation)
- Environment-specific overrides
- Feature flags

### Model Validation

All models are validated automatically:

```python
from anova_oven_sdk import Temperature, HeatingElements

# Automatic validation
temp = Temperature(celsius=200)  # ✓ Valid
# temp = Temperature(celsius=-300)  # ✗ ValidationError

# Heating elements validation
heating = HeatingElements(rear=True)  # ✓ Valid
# heating = HeatingElements(top=True, bottom=True, rear=True)  # ✗ ValidationError
```

## Error Handling

```python
from anova_oven_sdk import (
    AnovaOven, ConfigurationError,
    DeviceNotFoundError
)

try:
    async with AnovaOven() as oven:
        devices = await oven.discover_devices()
        await oven.start_cook(devices[0].id, temperature=200)
except ConfigurationError as e:
    print(f"Config error: {e}")
except DeviceNotFoundError as e:
    print(f"Device not found: {e}")
except ValueError as e:
    print(f"Invalid parameters: {e}")
```

## Testing

```python
import pytest
from anova_oven_sdk import Temperature, CookStage, HeatingElements, AnovaOven

def test_temperature_validation():
    temp = Temperature.from_celsius(200)
    assert temp.celsius == 200
    assert temp.fahrenheit == 392

def test_heating_elements_validation():
    # Valid configuration
    heating = HeatingElements(rear=True)
    assert heating.rear is True
    
    # Invalid - all elements
    with pytest.raises(ValueError):
        HeatingElements(top=True, bottom=True, rear=True)

@pytest.mark.asyncio
async def test_oven_connection():
    async with AnovaOven() as oven:
        devices = await oven.discover_devices()
        assert len(devices) > 0
```

## Project Structure

```
anova-oven-project/
├── settings.yaml          # Main configuration
├── .secrets.yaml          # Secrets (gitignored)
├── recipes.yml            # Recipe definitions
├── .env                   # Environment variables (gitignored)
├── .gitignore             # Git ignore file
├── pyproject.toml         # Project configuration
├── anova_oven_cli.py      # Anova SDK Command-line Interface (CLI)
├── logs/                  # Log files (gitignored)
│   ├── anova_dev.log
│   └── anova_prod.log
└── tests/                 # Test files
    ├── __init__.py
    ├── conftest.py
    ├── test_client.py
    ├── test_commands.py
    ├── test_exceptions.py
    ├── test_logging_config.py
    ├── test_models.py
    ├── test_oven_part1.py
    ├── test_oven_part2.py
    ├── test_presets.py
    ├── test_settings.py
    └── test_utils.py
```

## CLI Examples Workflow

### Complete Workflow Example

```bash
# 1. Discover your oven
python anova_oven_cli.py discover
# Output: Note your device ID (e.g., anova-abc123def456)

# 2. List available recipes
python anova_oven_cli.py recipes list

# 3. View recipe details
python anova_oven_cli.py recipes show perfect_toast_v1

# 4. Start cooking with a recipe
python anova_oven_cli.py cook --device anova-abc123def456 --recipe perfect_toast_v1

# 5. Stop cooking when done
python anova_oven_cli.py stop --device anova-abc123def456
```

### Scripting with JSON Output

```bash
# Get device ID programmatically
DEVICE_ID=$(python anova_oven_cli.py discover --json | jq -r '.[0].id')

# List recipes as JSON
python anova_oven_cli.py recipes list --json | jq '.[] | {id, name, stages}'

# Start cook with the device ID
python anova_oven_cli.py cook --device "$DEVICE_ID" --recipe sous_vide_steak
```

## Tips and Best Practices

### Recipe Development
1. Start with simple single-stage recipes to test your setup
2. Use `recipes show` to validate recipe structure before cooking
3. Test new recipes with the oven door open to verify timing
4. Always validate recipes are compatible with your oven version

### CLI Usage
- Use `--json` flag for integration with other tools
- Set `--recipe-file` to manage multiple recipe collections
- Use `--env development` for more detailed logging during testing

### Safety
- Always supervise cooking operations
- Test new recipes with attention to timing and temperature
- Keep recipe files in version control for repeatability
- Validate device IDs before starting cooks

## License & Credits

This project uses the Anova Precision Oven API documented at [https://developer.anovaculinary.com](https://developer.anovaculinary.com).

The majority of this code was created using Anthropic Claude AI assistant ([https://claude.ai](https://claude.ai)).

**This is unofficial software not affiliated with or endorsed by Anova Culinary.**

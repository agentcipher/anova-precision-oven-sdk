## ⚠️ Disclaimer

This software is provided "as is" without warranty of any kind, express or implied. The authors and contributors are not liable for any damages, losses, or issues arising from the use of this software, including but not limited to:

- Device malfunction or damage
- Property damage
- Food safety issues
- Data loss
- Service interruptions

**Use at your own risk.** Always supervise cooking operations and follow manufacturer guidelines for your Anova Precision Oven. This is unofficial software not endorsed by Anova Culinary.

# Anova Precision Oven Python SDK

Python SDK for controlling Anova Precision Ovens using the official Anova API(https://developer.anovaculinary.com/docs/devices/wifi/oven-commands).  The goal of this final project is to create an
integration for Home Assistant which leverages this SDK for operation.  The majority of this code was written using Anthropic Claude(https://claude.ai)

## Installation

```bash
# Using pip
pip install .
```

## Quick Start

### 1. Create configuration files

Create `settings.yaml`:
```yaml
default:
  log_level: INFO
  supported_accessories:
    - APO
```

Create `.secrets.yaml` (add to .gitignore):
```yaml
default:
  token: "anova-your-token-here"
```

Or use environment variables:
```bash
export ANOVA_TOKEN="anova-your-token-here"
```

### 2. Basic usage

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

## Environment Management

Switch environments using `ANOVA_ENV`:

```bash
# Development (debug logging, more retries)
export ANOVA_ENV=development
python your_script.py

# Production (warning logging, optimized)
export ANOVA_ENV=production
python your_script.py
```

## CLI Usage

```bash
# Discover devices
python anova_oven_cli.py discover

# Start cooking
python anova_oven_cli.py cook --device DEVICE_ID --temp 200 --duration 30

# Stop cooking
python anova_oven_cli.py stop --device DEVICE_ID

# Run example
python anova_oven_cli.py example --env development
```

## Advanced Usage

### Multi-stage cooking

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

## Configuration Reference

See `settings.yaml` for all available configuration options:
- WebSocket settings (timeout, retries)
- Logging configuration (level, file, rotation)
- Environment-specific overrides
- Feature flags

## Pydantic Validation

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

## Cooking Presets

Available presets:
- `roast()` - High heat roasting
- `steam()` - Steam cooking
- `sous_vide()` - Precise temperature control
- `bake()` - Conventional baking
- `dehydrate()` - Bread proofing
- `toast_v1_oven()` - Replicate the Anova v1 Toast Recipe

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
├── settings.yaml           # Main configuration
├── .secrets.yaml          # Secrets (gitignored)
├── .env                   # Environment variables (gitignored)
├── .gitignore            # Git ignore file
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Poetry configuration
├── anova_oven_sdk.py     # SDK code
├── logs/                 # Log files (gitignored)
│   ├── anova_dev.log
│   └── anova_prod.log
└── tests/                # Test files
    ├── __init__.py
    ├── test_models.py
    └── test_commands.py
```
# ============================================================================
# Pydantic Models
# ============================================================================
from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import (
    BaseModel, Field, field_validator, model_validator,
    ConfigDict
)
from datetime import datetime


class OvenVersion(str, Enum):
    """Oven device version."""
    V1 = "oven_v1"
    V2 = "oven_v2"


class TemperatureMode(str, Enum):
    """Temperature bulb mode."""
    DRY = "dry"
    WET = "wet"


class SteamMode(str, Enum):
    """Steam generator mode."""
    IDLE = "idle"
    RELATIVE_HUMIDITY = "relative-humidity"
    STEAM_PERCENTAGE = "steam-percentage"


class TimerStartType(str, Enum):
    """Timer start trigger."""
    IMMEDIATELY = "immediately"
    WHEN_PREHEATED = "when-preheated"
    MANUAL = "manual"


class VentState(str, Enum):
    """Oven vent state."""
    OPEN = "open"
    CLOSED = "closed"


class DeviceState(str, Enum):
    """Device operational state."""
    IDLE = "idle"
    PREHEATING = "preheating"
    COOKING = "cooking"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


# ============================================================================
# TEMPERATURE MODEL - Enhanced with Full C/F Support
# ============================================================================

class Temperature(BaseModel):
    """
    Temperature with automatic Fahrenheit/Celsius conversion.

    Examples:
        # Create from Celsius
        temp = Temperature.from_celsius(100)
        print(temp.fahrenheit)  # 212.0

        # Create from Fahrenheit
        temp = Temperature.from_fahrenheit(212)
        print(temp.celsius)  # 100.0

        # Create with either (auto-converts)
        temp = Temperature(celsius=100)  # Fahrenheit auto-calculated
        temp = Temperature(fahrenheit=212)  # Celsius auto-calculated

        # Comparison
        temp1 = Temperature(celsius=100)
        temp2 = Temperature(fahrenheit=212)
        assert temp1 == temp2
    """
    model_config = ConfigDict(frozen=False)

    celsius: Optional[float] = Field(None, description="Temperature in Celsius")
    fahrenheit: Optional[float] = Field(None, description="Temperature in Fahrenheit")

    @model_validator(mode='after')
    def validate_and_convert(self):
        """Validate and convert between units."""
        if self.celsius is None and self.fahrenheit is None:
            raise ValueError("Either celsius or fahrenheit must be provided")

        # Convert if only one is provided
        if self.celsius is not None and self.fahrenheit is None:
            self.fahrenheit = (self.celsius * 9 / 5) + 32
        elif self.fahrenheit is not None and self.celsius is None:
            self.celsius = (self.fahrenheit - 32) * 5 / 9

        # Validate absolute zero
        if self.celsius < -273.15:
            raise ValueError("Temperature cannot be below absolute zero (-273.15°C / -459.67°F)")

        return self

    @classmethod
    def from_celsius(cls, celsius: float) -> 'Temperature':
        """Create from Celsius."""
        return cls(celsius=celsius)

    @classmethod
    def from_fahrenheit(cls, fahrenheit: float) -> 'Temperature':
        """Create from Fahrenheit."""
        return cls(fahrenheit=fahrenheit)

    def to_dict(self, include_fahrenheit: bool = True) -> Dict[str, float]:
        """Convert to API format."""
        result = {"celsius": self.celsius}
        if include_fahrenheit:
            result["fahrenheit"] = self.fahrenheit
        return result

    def in_celsius(self) -> float:
        """Get temperature in Celsius."""
        return self.celsius

    def in_fahrenheit(self) -> float:
        """Get temperature in Fahrenheit."""
        return self.fahrenheit

    def __str__(self) -> str:
        """String representation."""
        return f"{self.celsius:.1f}°C / {self.fahrenheit:.1f}°F"

    def __repr__(self) -> str:
        """Developer representation."""
        return f"Temperature(celsius={self.celsius:.2f}, fahrenheit={self.fahrenheit:.2f})"

    def __eq__(self, other) -> bool:
        """Compare temperatures."""
        if not isinstance(other, Temperature):
            return False
        return abs(self.celsius - other.celsius) < 0.01

    def __lt__(self, other) -> bool:
        """Less than comparison."""
        if not isinstance(other, Temperature):
            raise TypeError(f"Cannot compare Temperature with {type(other)}")
        return self.celsius < other.celsius

    def __le__(self, other) -> bool:
        """Less than or equal."""
        return self == other or self < other

    def __gt__(self, other) -> bool:
        """Greater than comparison."""
        if not isinstance(other, Temperature):
            raise TypeError(f"Cannot compare Temperature with {type(other)}")
        return self.celsius > other.celsius

    def __ge__(self, other) -> bool:
        """Greater than or equal."""
        return self == other or self > other


# ============================================================================
# TEMPERATURE UTILITIES
# ============================================================================

def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9 / 5) + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9


def ensure_temperature(temp: Union[float, Temperature], unit: str = "C") -> Temperature:
    """
    Ensure we have a Temperature object.

    Args:
        temp: Temperature as float or Temperature object
        unit: Unit if temp is a float ("C" or "F")

    Returns:
        Temperature object
    """
    if isinstance(temp, Temperature):
        return temp
    elif isinstance(temp, (int, float)):
        if unit.upper() == "F":
            return Temperature.from_fahrenheit(temp)
        else:
            return Temperature.from_celsius(temp)
    else:
        raise TypeError(f"Expected float or Temperature, got {type(temp)}")


class TemperatureRange:
    """Temperature range validators for different oven modes."""

    # Oven limits (in Celsius)
    WET_BULB_MIN = 25.0
    WET_BULB_MAX = 100.0

    DRY_BULB_MIN = 25.0
    DRY_BULB_MAX = 250.0

    DRY_BULB_BOTTOM_ONLY_V1_MAX = 180.0
    DRY_BULB_BOTTOM_ONLY_V2_MAX = 230.0

    PROBE_MIN = 1.0
    PROBE_MAX = 100.0

    @classmethod
    def validate_wet_bulb(cls, temp: Temperature) -> None:
        """Validate temperature for wet bulb mode."""
        if not (cls.WET_BULB_MIN <= temp.celsius <= cls.WET_BULB_MAX):
            raise ValueError(
                f"Wet bulb temperature must be between "
                f"{cls.WET_BULB_MIN}°C ({celsius_to_fahrenheit(cls.WET_BULB_MIN):.1f}°F) and "
                f"{cls.WET_BULB_MAX}°C ({celsius_to_fahrenheit(cls.WET_BULB_MAX):.1f}°F). "
                f"Got: {temp}"
            )

    @classmethod
    def validate_dry_bulb(
            cls,
            temp: Temperature,
            bottom_only: bool = False,
            oven_version: OvenVersion = OvenVersion.V2
    ) -> None:
        """Validate temperature for dry bulb mode."""
        if bottom_only:
            max_temp = (cls.DRY_BULB_BOTTOM_ONLY_V1_MAX
                        if oven_version == OvenVersion.V1
                        else cls.DRY_BULB_BOTTOM_ONLY_V2_MAX)

            if not (cls.DRY_BULB_MIN <= temp.celsius <= max_temp):
                raise ValueError(
                    f"Dry bulb temperature (bottom only) must be between "
                    f"{cls.DRY_BULB_MIN}°C and {max_temp}°C for {oven_version.value}. "
                    f"Got: {temp}"
                )
        else:
            if not (cls.DRY_BULB_MIN <= temp.celsius <= cls.DRY_BULB_MAX):
                raise ValueError(
                    f"Dry bulb temperature must be between "
                    f"{cls.DRY_BULB_MIN}°C and {cls.DRY_BULB_MAX}°C. "
                    f"Got: {temp}"
                )

    @classmethod
    def validate_probe(cls, temp: Temperature) -> None:
        """Validate temperature for probe."""
        if not (cls.PROBE_MIN <= temp.celsius <= cls.PROBE_MAX):
            raise ValueError(
                f"Probe temperature must be between "
                f"{cls.PROBE_MIN}°C and {cls.PROBE_MAX}°C. "
                f"Got: {temp}"
            )


# ============================================================================
# OTHER PYDANTIC MODELS
# ============================================================================

class HeatingElements(BaseModel):
    """Heating element configuration."""
    model_config = ConfigDict(frozen=False)

    top: bool = Field(False, description="Top heating element")
    bottom: bool = Field(False, description="Bottom heating element")
    rear: bool = Field(True, description="Rear heating element")

    @model_validator(mode='after')
    def validate_elements(self):
        """Ensure valid heating element configuration."""
        active = [self.top, self.bottom, self.rear]
        if not any(active):
            raise ValueError("At least one heating element must be enabled")
        if all(active):
            raise ValueError("All three heating elements cannot be enabled simultaneously")
        return self

    def to_dict(self) -> Dict[str, Dict[str, bool]]:
        """Convert to API format."""
        return {
            "top": {"on": self.top},
            "bottom": {"on": self.bottom},
            "rear": {"on": self.rear}
        }


class SteamSettings(BaseModel):
    """Steam generator configuration."""
    model_config = ConfigDict(frozen=False)

    mode: SteamMode = Field(SteamMode.IDLE, description="Steam mode")
    relative_humidity: Optional[float] = Field(
        None, ge=0, le=100, description="Relative humidity percentage"
    )
    steam_percentage: Optional[float] = Field(
        None, ge=0, le=100, description="Steam percentage"
    )

    @model_validator(mode='after')
    def validate_steam_settings(self):
        """Validate steam configuration."""
        if self.mode == SteamMode.RELATIVE_HUMIDITY:
            if self.relative_humidity is None:
                raise ValueError("relative_humidity required when mode is RELATIVE_HUMIDITY")
        elif self.mode == SteamMode.STEAM_PERCENTAGE:
            if self.steam_percentage is None:
                raise ValueError("steam_percentage required when mode is STEAM_PERCENTAGE")
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result = {"mode": self.mode.value}
        if self.mode == SteamMode.RELATIVE_HUMIDITY and self.relative_humidity is not None:
            result["relativeHumidity"] = {"setpoint": self.relative_humidity}
        elif self.mode == SteamMode.STEAM_PERCENTAGE and self.steam_percentage is not None:
            result["steamPercentage"] = {"setpoint": self.steam_percentage}
        return result


class Timer(BaseModel):
    """Timer configuration."""
    model_config = ConfigDict(frozen=False)

    initial: int = Field(..., ge=0, description="Timer duration in seconds")
    start_type: TimerStartType = Field(
        TimerStartType.IMMEDIATELY, description="When to start timer"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        result = {"initial": self.initial}
        if self.start_type != TimerStartType.IMMEDIATELY:
            result["startType"] = self.start_type.value
        return result


class Probe(BaseModel):
    """Temperature probe configuration."""
    model_config = ConfigDict(frozen=False)

    setpoint: Temperature = Field(..., description="Target probe temperature")

    @field_validator('setpoint')
    @classmethod
    def validate_probe_temp(cls, v):
        """Validate probe temperature range."""
        TemperatureRange.validate_probe(v)
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        return {"setpoint": self.setpoint.to_dict()}


class CookStage(BaseModel):
    """Cooking stage configuration."""
    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    temperature: Temperature = Field(..., description="Target temperature")
    mode: TemperatureMode = Field(TemperatureMode.DRY, description="Cooking mode")
    heating_elements: HeatingElements = Field(
        default_factory=HeatingElements, description="Heating elements"
    )
    fan_speed: int = Field(100, ge=0, le=100, description="Fan speed percentage")
    vent_open: bool = Field(False, description="Vent state")
    rack_position: int = Field(3, ge=1, le=7, description="Rack position")
    timer: Optional[Timer] = Field(None, description="Stage timer")
    probe: Optional[Probe] = Field(None, description="Temperature probe")
    steam: Optional[SteamSettings] = Field(None, description="Steam settings")
    title: str = Field("", description="Stage title")
    description: str = Field("", description="Stage description")
    user_action_required: bool = Field(False, description="Require manual transition")

    def validate_for_oven(self, oven_version: OvenVersion):
        """Validate stage for specific oven version."""
        # Validate temperature limits
        if self.mode == TemperatureMode.WET:
            TemperatureRange.validate_wet_bulb(self.temperature)
        else:
            bottom_only = (self.heating_elements.bottom and
                           not self.heating_elements.top and
                           not self.heating_elements.rear)
            TemperatureRange.validate_dry_bulb(
                self.temperature,
                bottom_only=bottom_only,
                oven_version=oven_version
            )


class Device(BaseModel):
    """Anova device representation."""
    model_config = ConfigDict(frozen=False)

    cooker_id: str = Field(..., alias="cookerId", description="Device ID")
    name: str = Field(..., description="Device name")
    paired_at: str = Field(..., alias="pairedAt", description="Pairing timestamp")
    device_type: OvenVersion = Field(..., alias="type", description="Device type")
    state: DeviceState = Field(DeviceState.IDLE, description="Current state")
    current_temperature: Optional[float] = Field(None, description="Current temp")
    target_temperature: Optional[float] = Field(None, description="Target temp")
    last_update: Optional[datetime] = Field(None, description="Last update time")

    @property
    def id(self) -> str:
        """Alias for cooker_id."""
        return self.cooker_id

    @property
    def oven_version(self) -> OvenVersion:
        """Get oven version."""
        return self.device_type

    @property
    def is_cooking(self) -> bool:
        """Check if currently cooking."""
        return self.state in [DeviceState.COOKING, DeviceState.PREHEATING]
"""
Comprehensive tests for models.py - 100% coverage
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from anova_oven_sdk.models import (
    Temperature, TemperatureRange, celsius_to_fahrenheit, fahrenheit_to_celsius,
    ensure_temperature, HeatingElements, SteamSettings, Timer, Probe, CookStage,
    Device, OvenVersion, TemperatureMode, SteamMode, TimerStartType, VentState,
    DeviceState
)


class TestTemperature:
    """Test Temperature model."""

    def test_from_celsius(self):
        """Test creating temperature from Celsius."""
        temp = Temperature.from_celsius(100)
        assert temp.celsius == 100
        assert abs(temp.fahrenheit - 212.0) < 0.01

    def test_from_fahrenheit(self):
        """Test creating temperature from Fahrenheit."""
        temp = Temperature.from_fahrenheit(212)
        assert abs(temp.celsius - 100.0) < 0.01
        assert temp.fahrenheit == 212

    def test_celsius_only(self):
        """Test creating with only Celsius."""
        temp = Temperature(celsius=50)
        assert temp.celsius == 50
        assert abs(temp.fahrenheit - 122.0) < 0.01

    def test_fahrenheit_only(self):
        """Test creating with only Fahrenheit."""
        temp = Temperature(fahrenheit=122)
        assert abs(temp.celsius - 50.0) < 0.01
        assert temp.fahrenheit == 122

    def test_both_provided(self):
        """Test creating with both units provided."""
        temp = Temperature(celsius=100, fahrenheit=212)
        assert temp.celsius == 100
        assert temp.fahrenheit == 212

    def test_neither_provided(self):
        """Test error when neither unit provided."""
        with pytest.raises(ValueError, match="Either celsius or fahrenheit must be provided"):
            Temperature()

    def test_below_absolute_zero(self):
        """Test validation of absolute zero."""
        with pytest.raises(ValueError, match="cannot be below absolute zero"):
            Temperature(celsius=-300)

    def test_to_dict_with_fahrenheit(self):
        """Test to_dict with Fahrenheit included."""
        temp = Temperature(celsius=100)
        result = temp.to_dict(include_fahrenheit=True)
        assert "celsius" in result
        assert "fahrenheit" in result
        assert result["celsius"] == 100

    def test_to_dict_without_fahrenheit(self):
        """Test to_dict without Fahrenheit."""
        temp = Temperature(celsius=100)
        result = temp.to_dict(include_fahrenheit=False)
        assert "celsius" in result
        assert "fahrenheit" not in result

    def test_in_celsius(self):
        """Test in_celsius method."""
        temp = Temperature(celsius=50)
        assert temp.in_celsius() == 50

    def test_in_fahrenheit(self):
        """Test in_fahrenheit method."""
        temp = Temperature(fahrenheit=100)
        assert temp.in_fahrenheit() == 100

    def test_str_representation(self):
        """Test string representation."""
        temp = Temperature(celsius=100)
        result = str(temp)
        assert "100.0°C" in result
        assert "212.0°F" in result

    def test_repr_representation(self):
        """Test repr representation."""
        temp = Temperature(celsius=100)
        result = repr(temp)
        assert "Temperature(celsius=100" in result
        assert "fahrenheit=212" in result

    def test_equality(self):
        """Test temperature equality."""
        temp1 = Temperature(celsius=100)
        temp2 = Temperature(fahrenheit=212)
        assert temp1 == temp2

    def test_equality_with_non_temperature(self):
        """Test equality with non-Temperature object."""
        temp = Temperature(celsius=100)
        assert not (temp == 100)

    def test_less_than(self):
        """Test less than comparison."""
        temp1 = Temperature(celsius=50)
        temp2 = Temperature(celsius=100)
        assert temp1 < temp2

    def test_less_than_with_non_temperature(self):
        """Test less than with non-Temperature raises error."""
        temp = Temperature(celsius=100)
        with pytest.raises(TypeError, match="Cannot compare Temperature"):
            temp < 100

    def test_less_than_or_equal(self):
        """Test less than or equal."""
        temp1 = Temperature(celsius=50)
        temp2 = Temperature(celsius=100)
        temp3 = Temperature(celsius=100)
        assert temp1 <= temp2
        assert temp2 <= temp3

    def test_greater_than(self):
        """Test greater than comparison."""
        temp1 = Temperature(celsius=100)
        temp2 = Temperature(celsius=50)
        assert temp1 > temp2

    def test_greater_than_with_non_temperature(self):
        """Test greater than with non-Temperature raises error."""
        temp = Temperature(celsius=100)
        with pytest.raises(TypeError, match="Cannot compare Temperature"):
            temp > 100

    def test_greater_than_or_equal(self):
        """Test greater than or equal."""
        temp1 = Temperature(celsius=100)
        temp2 = Temperature(celsius=50)
        temp3 = Temperature(celsius=100)
        assert temp1 >= temp2
        assert temp1 >= temp3


class TestTemperatureUtilities:
    """Test temperature utility functions."""

    def test_celsius_to_fahrenheit(self):
        """Test Celsius to Fahrenheit conversion."""
        assert abs(celsius_to_fahrenheit(0) - 32) < 0.01
        assert abs(celsius_to_fahrenheit(100) - 212) < 0.01

    def test_fahrenheit_to_celsius(self):
        """Test Fahrenheit to Celsius conversion."""
        assert abs(fahrenheit_to_celsius(32) - 0) < 0.01
        assert abs(fahrenheit_to_celsius(212) - 100) < 0.01

    def test_ensure_temperature_with_temperature_object(self):
        """Test ensure_temperature with Temperature object."""
        temp = Temperature(celsius=100)
        result = ensure_temperature(temp)
        assert result is temp

    def test_ensure_temperature_with_float_celsius(self):
        """Test ensure_temperature with float in Celsius."""
        result = ensure_temperature(100, "C")
        assert result.celsius == 100

    def test_ensure_temperature_with_float_fahrenheit(self):
        """Test ensure_temperature with float in Fahrenheit."""
        result = ensure_temperature(212, "F")
        assert abs(result.celsius - 100) < 0.01

    def test_ensure_temperature_with_int(self):
        """Test ensure_temperature with integer."""
        result = ensure_temperature(100, "C")
        assert result.celsius == 100

    def test_ensure_temperature_with_invalid_type(self):
        """Test ensure_temperature with invalid type."""
        with pytest.raises(TypeError, match="Expected float or Temperature"):
            ensure_temperature("100", "C")


class TestTemperatureRange:
    """Test TemperatureRange validators."""

    def test_validate_wet_bulb_valid(self):
        """Test valid wet bulb temperature."""
        temp = Temperature(celsius=50)
        TemperatureRange.validate_wet_bulb(temp)  # Should not raise

    def test_validate_wet_bulb_too_low(self):
        """Test wet bulb temperature too low."""
        temp = Temperature(celsius=20)
        with pytest.raises(ValueError, match="Wet bulb temperature must be between"):
            TemperatureRange.validate_wet_bulb(temp)

    def test_validate_wet_bulb_too_high(self):
        """Test wet bulb temperature too high."""
        temp = Temperature(celsius=110)
        with pytest.raises(ValueError, match="Wet bulb temperature must be between"):
            TemperatureRange.validate_wet_bulb(temp)

    def test_validate_dry_bulb_valid(self):
        """Test valid dry bulb temperature."""
        temp = Temperature(celsius=200)
        TemperatureRange.validate_dry_bulb(temp)  # Should not raise

    def test_validate_dry_bulb_too_low(self):
        """Test dry bulb temperature too low."""
        temp = Temperature(celsius=20)
        with pytest.raises(ValueError, match="Dry bulb temperature must be between"):
            TemperatureRange.validate_dry_bulb(temp)

    def test_validate_dry_bulb_too_high(self):
        """Test dry bulb temperature too high."""
        temp = Temperature(celsius=260)
        with pytest.raises(ValueError, match="Dry bulb temperature must be between"):
            TemperatureRange.validate_dry_bulb(temp)

    def test_validate_dry_bulb_bottom_only_v1(self):
        """Test dry bulb bottom only for V1."""
        temp = Temperature(celsius=190)
        with pytest.raises(ValueError, match="bottom only"):
            TemperatureRange.validate_dry_bulb(temp, bottom_only=True, oven_version=OvenVersion.V1)

    def test_validate_dry_bulb_bottom_only_v1_valid(self):
        """Test valid dry bulb bottom only for V1."""
        temp = Temperature(celsius=170)
        TemperatureRange.validate_dry_bulb(temp, bottom_only=True, oven_version=OvenVersion.V1)

    def test_validate_dry_bulb_bottom_only_v2(self):
        """Test dry bulb bottom only for V2."""
        temp = Temperature(celsius=240)
        with pytest.raises(ValueError, match="bottom only"):
            TemperatureRange.validate_dry_bulb(temp, bottom_only=True, oven_version=OvenVersion.V2)

    def test_validate_dry_bulb_bottom_only_v2_valid(self):
        """Test valid dry bulb bottom only for V2."""
        temp = Temperature(celsius=220)
        TemperatureRange.validate_dry_bulb(temp, bottom_only=True, oven_version=OvenVersion.V2)

    def test_validate_probe_valid(self):
        """Test valid probe temperature."""
        temp = Temperature(celsius=50)
        TemperatureRange.validate_probe(temp)

    def test_validate_probe_too_low(self):
        """Test probe temperature too low."""
        temp = Temperature(celsius=0.5)
        with pytest.raises(ValueError, match="Probe temperature must be between"):
            TemperatureRange.validate_probe(temp)

    def test_validate_probe_too_high(self):
        """Test probe temperature too high."""
        temp = Temperature(celsius=110)
        with pytest.raises(ValueError, match="Probe temperature must be between"):
            TemperatureRange.validate_probe(temp)


class TestHeatingElements:
    """Test HeatingElements model."""

    def test_default_heating_elements(self):
        """Test default heating elements."""
        elements = HeatingElements()
        assert elements.rear is True
        assert elements.top is False
        assert elements.bottom is False

    def test_custom_heating_elements(self):
        """Test custom heating elements."""
        elements = HeatingElements(top=True, bottom=True, rear=False)
        assert elements.top is True
        assert elements.bottom is True
        assert elements.rear is False

    def test_no_elements_active(self):
        """Test error when no elements active."""
        with pytest.raises(ValueError, match="At least one heating element must be enabled"):
            HeatingElements(top=False, bottom=False, rear=False)

    def test_all_elements_active(self):
        """Test error when all elements active."""
        with pytest.raises(ValueError, match="All three heating elements cannot be enabled"):
            HeatingElements(top=True, bottom=True, rear=True)

    def test_to_dict(self):
        """Test to_dict conversion."""
        elements = HeatingElements(top=True, rear=False, bottom=False)
        result = elements.to_dict()
        assert result["top"]["on"] is True
        assert result["bottom"]["on"] is False
        assert result["rear"]["on"] is False


class TestSteamSettings:
    """Test SteamSettings model."""

    def test_idle_mode(self):
        """Test idle steam mode."""
        steam = SteamSettings(mode=SteamMode.IDLE)
        assert steam.mode == SteamMode.IDLE

    def test_relative_humidity_mode(self):
        """Test relative humidity mode."""
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        assert steam.relative_humidity == 80

    def test_relative_humidity_without_value(self):
        """Test error when relative humidity mode without value."""
        with pytest.raises(ValueError, match="relative_humidity required"):
            SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY)

    def test_steam_percentage_mode(self):
        """Test steam percentage mode."""
        steam = SteamSettings(mode=SteamMode.STEAM_PERCENTAGE, steam_percentage=100)
        assert steam.steam_percentage == 100

    def test_steam_percentage_without_value(self):
        """Test error when steam percentage mode without value."""
        with pytest.raises(ValueError, match="steam_percentage required"):
            SteamSettings(mode=SteamMode.STEAM_PERCENTAGE)

    def test_to_dict_idle(self):
        """Test to_dict for idle mode."""
        steam = SteamSettings(mode=SteamMode.IDLE)
        result = steam.to_dict()
        assert result["mode"] == "idle"

    def test_to_dict_relative_humidity(self):
        """Test to_dict for relative humidity mode."""
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        result = steam.to_dict()
        assert result["mode"] == "relative-humidity"
        assert result["relativeHumidity"]["setpoint"] == 80

    def test_to_dict_steam_percentage(self):
        """Test to_dict for steam percentage mode."""
        steam = SteamSettings(mode=SteamMode.STEAM_PERCENTAGE, steam_percentage=100)
        result = steam.to_dict()
        assert result["mode"] == "steam-percentage"
        assert result["steamPercentage"]["setpoint"] == 100


class TestTimer:
    """Test Timer model."""

    def test_timer_default(self):
        """Test timer with default start type."""
        timer = Timer(initial=300)
        assert timer.initial == 300
        assert timer.start_type == TimerStartType.IMMEDIATELY

    def test_timer_custom_start_type(self):
        """Test timer with custom start type."""
        timer = Timer(initial=600, start_type=TimerStartType.WHEN_PREHEATED)
        assert timer.start_type == TimerStartType.WHEN_PREHEATED

    def test_timer_to_dict_immediately(self):
        """Test to_dict for immediate start."""
        timer = Timer(initial=300)
        result = timer.to_dict()
        assert result["initial"] == 300
        assert "startType" not in result

    def test_timer_to_dict_when_preheated(self):
        """Test to_dict for preheated start."""
        timer = Timer(initial=600, start_type=TimerStartType.WHEN_PREHEATED)
        result = timer.to_dict()
        assert result["initial"] == 600
        assert result["startType"] == "when-preheated"


class TestProbe:
    """Test Probe model."""

    def test_probe_valid(self):
        """Test probe with valid temperature."""
        temp = Temperature(celsius=60)
        probe = Probe(setpoint=temp)
        assert probe.setpoint == temp

    def test_probe_invalid_temperature(self):
        """Test probe with invalid temperature."""
        temp = Temperature(celsius=110)
        with pytest.raises(ValidationError):
            Probe(setpoint=temp)

    def test_probe_to_dict(self):
        """Test probe to_dict."""
        temp = Temperature(celsius=60)
        probe = Probe(setpoint=temp)
        result = probe.to_dict()
        assert "setpoint" in result
        assert result["setpoint"]["celsius"] == 60


class TestCookStage:
    """Test CookStage model."""

    def test_cook_stage_minimal(self):
        """Test cook stage with minimal parameters."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp)
        assert stage.temperature == temp
        assert stage.mode == TemperatureMode.DRY
        assert stage.fan_speed == 100

    def test_cook_stage_full(self):
        """Test cook stage with all parameters."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800)
        heating = HeatingElements(top=True, bottom=True, rear=False)
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        probe = Probe(setpoint=Temperature(celsius=65))

        stage = CookStage(
            temperature=temp,
            mode=TemperatureMode.WET,
            heating_elements=heating,
            fan_speed=75,
            vent_open=True,
            rack_position=4,
            timer=timer,
            probe=probe,
            steam=steam,
            title="Test Stage",
            description="Test Description",
            user_action_required=True
        )

        assert stage.temperature == temp
        assert stage.mode == TemperatureMode.WET
        assert stage.fan_speed == 75
        assert stage.vent_open is True
        assert stage.rack_position == 4
        assert stage.title == "Test Stage"
        assert stage.user_action_required is True

    def test_validate_for_oven_wet_mode(self):
        """Test validation for wet mode."""
        temp = Temperature(celsius=80)
        stage = CookStage(temperature=temp, mode=TemperatureMode.WET)
        stage.validate_for_oven(OvenVersion.V2)  # Should not raise

    def test_validate_for_oven_wet_mode_invalid(self):
        """Test validation for invalid wet mode temperature."""
        temp = Temperature(celsius=110)
        stage = CookStage(temperature=temp, mode=TemperatureMode.WET)
        with pytest.raises(ValueError):
            stage.validate_for_oven(OvenVersion.V2)

    def test_validate_for_oven_dry_mode(self):
        """Test validation for dry mode."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, mode=TemperatureMode.DRY)
        stage.validate_for_oven(OvenVersion.V2)  # Should not raise

    def test_validate_for_oven_dry_mode_bottom_only_v1(self):
        """Test validation for bottom only on V1."""
        temp = Temperature(celsius=170)
        heating = HeatingElements(bottom=True, top=False, rear=False)
        stage = CookStage(temperature=temp, heating_elements=heating)
        stage.validate_for_oven(OvenVersion.V1)  # Should not raise

    def test_validate_for_oven_dry_mode_bottom_only_v2(self):
        """Test validation for bottom only on V2."""
        temp = Temperature(celsius=220)
        heating = HeatingElements(bottom=True, top=False, rear=False)
        stage = CookStage(temperature=temp, heating_elements=heating)
        stage.validate_for_oven(OvenVersion.V2)  # Should not raise


class TestDevice:
    """Test Device model."""

    def test_device_creation(self):
        """Test device creation."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        assert device.cooker_id == "test-device-123"
        assert device.name == "My Oven"
        assert device.device_type == OvenVersion.V2

    def test_device_id_property(self):
        """Test device id property."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        assert device.id == "test-device-123"

    def test_device_oven_version_property(self):
        """Test oven_version property."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V1
        )
        assert device.oven_version == OvenVersion.V1

    def test_device_is_cooking_true(self):
        """Test is_cooking when cooking."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2,
            state=DeviceState.COOKING
        )
        assert device.is_cooking is True

    def test_device_is_cooking_preheating(self):
        """Test is_cooking when preheating."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2,
            state=DeviceState.PREHEATING
        )
        assert device.is_cooking is True

    def test_device_is_cooking_false(self):
        """Test is_cooking when idle."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2,
            state=DeviceState.IDLE
        )
        assert device.is_cooking is False

    def test_device_with_optional_fields(self):
        """Test device with optional fields."""
        device = Device(
            cookerId="test-device-123",
            name="My Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2,
            current_temperature=150.5,
            target_temperature=200.0,
            last_update=datetime.now()
        )
        assert device.current_temperature == 150.5
        assert device.target_temperature == 200.0
        assert device.last_update is not None


class TestEnums:
    """Test all enum types."""

    def test_oven_version_enum(self):
        """Test OvenVersion enum."""
        assert OvenVersion.V1.value == "oven_v1"
        assert OvenVersion.V2.value == "oven_v2"

    def test_temperature_mode_enum(self):
        """Test TemperatureMode enum."""
        assert TemperatureMode.DRY.value == "dry"
        assert TemperatureMode.WET.value == "wet"

    def test_steam_mode_enum(self):
        """Test SteamMode enum."""
        assert SteamMode.IDLE.value == "idle"
        assert SteamMode.RELATIVE_HUMIDITY.value == "relative-humidity"
        assert SteamMode.STEAM_PERCENTAGE.value == "steam-percentage"

    def test_timer_start_type_enum(self):
        """Test TimerStartType enum."""
        assert TimerStartType.IMMEDIATELY.value == "immediately"
        assert TimerStartType.WHEN_PREHEATED.value == "when-preheated"
        assert TimerStartType.MANUAL.value == "manual"

    def test_vent_state_enum(self):
        """Test VentState enum."""
        assert VentState.OPEN.value == "open"
        assert VentState.CLOSED.value == "closed"

    def test_device_state_enum(self):
        """Test DeviceState enum."""
        assert DeviceState.IDLE.value == "idle"
        assert DeviceState.PREHEATING.value == "preheating"
        assert DeviceState.COOKING.value == "cooking"
        assert DeviceState.PAUSED.value == "paused"
        assert DeviceState.COMPLETED.value == "completed"
        assert DeviceState.ERROR.value == "error"

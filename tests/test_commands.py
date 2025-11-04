import pytest

from anova_oven_sdk.commands import CommandBuilder
from anova_oven_sdk.models import (
    CookStage, Temperature, OvenVersion, HeatingElements,
    Timer, TimerStartType, SteamSettings, SteamMode, Probe,
    TemperatureMode
)


class TestCommandBuilder:
    """Test CommandBuilder class."""

    def test_build_start_command_v1(self):
        """Test building V1 start command."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, title="Test Cook")

        payload = CommandBuilder.build_start_command(
            "device-123",
            [stage],
            OvenVersion.V1
        )

        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_START"
        assert "cookId" in payload["payload"]
        assert "stages" in payload["payload"]
        assert len(payload["payload"]["stages"]) == 2  # Preheat + cook

    def test_build_start_command_v2(self):
        """Test building V2 start command."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, title="Test Cook V2")

        payload = CommandBuilder.build_start_command(
            "device-456",
            [stage],
            OvenVersion.V2
        )

        assert payload["id"] == "device-456"
        assert payload["type"] == "CMD_APO_START"
        assert "cookId" in payload["payload"]
        assert "stages" in payload["payload"]
        assert payload["payload"]["type"] == "oven_v2"

    def test_build_v1_start_with_timer(self):
        """Test V1 start with timer."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800, start_type=TimerStartType.WHEN_PREHEATED)
        stage = CookStage(temperature=temp, timer=timer)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        # Check cook stage (second stage) has timer
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["timerAdded"] is True
        assert cook_stage["timer"]["initial"] == 1800
        assert cook_stage["timerStartOnDetect"] is True

    def test_build_v1_start_without_timer(self):
        """Test V1 start without timer."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["timerAdded"] is False
        assert cook_stage["timerStartOnDetect"] is False

    def test_build_v1_start_with_timer_immediately(self):
        """Test V1 start with immediate timer."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800, start_type=TimerStartType.IMMEDIATELY)
        stage = CookStage(temperature=temp, timer=timer)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["timerAdded"] is True
        assert cook_stage["timerStartOnDetect"] is False

    def test_build_v1_start_with_probe(self):
        """Test V1 start with probe."""
        temp = Temperature(celsius=180)
        probe = Probe(setpoint=Temperature(celsius=65))
        stage = CookStage(temperature=temp, probe=probe)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["probeAdded"] is True
        assert "probe" in cook_stage

    def test_build_v1_start_without_probe(self):
        """Test V1 start without probe."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["probeAdded"] is False

    def test_build_v1_start_with_steam(self):
        """Test V1 start with steam."""
        temp = Temperature(celsius=100)
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        stage = CookStage(temperature=temp, steam=steam, mode=TemperatureMode.WET)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        preheat_stage = payload["payload"]["stages"][0]
        assert "steamGenerators" in preheat_stage

    def test_build_v1_start_multiple_stages(self):
        """Test V1 start with multiple stages."""
        stage1 = CookStage(temperature=Temperature(celsius=180))
        stage2 = CookStage(temperature=Temperature(celsius=200))

        payload = CommandBuilder._build_v1_start("device-123", [stage1, stage2])
        
        # 2 stages = 4 API stages (preheat + cook for each)
        assert len(payload["payload"]["stages"]) == 4

    def test_build_v1_start_with_user_action(self):
        """Test V1 start with user action required."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, user_action_required=True)

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        cook_stage = payload["payload"]["stages"][1]
        assert cook_stage["userActionRequired"] is True
        assert cook_stage["stageTransitionType"] == "manual"

    def test_build_v1_start_stage_properties(self):
        """Test V1 start with all stage properties."""
        temp = Temperature(celsius=180)
        heating = HeatingElements(top=True, bottom=True, rear=False)
        stage = CookStage(
            temperature=temp,
            mode=TemperatureMode.DRY,
            heating_elements=heating,
            fan_speed=75,
            vent_open=True,
            rack_position=4,
            title="Custom Stage",
            description="Test description"
        )

        payload = CommandBuilder._build_v1_start("device-123", [stage])
        
        preheat_stage = payload["payload"]["stages"][0]
        assert preheat_stage["title"] == "Custom Stage"
        assert preheat_stage["description"] == "Test description"
        assert preheat_stage["fan"]["speed"] == 75
        assert preheat_stage["vent"]["open"] is True
        assert preheat_stage["rackPosition"] == 4

    def test_build_v2_start_basic(self):
        """Test V2 start basic structure."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        assert payload["id"] == "device-789"
        assert payload["payload"]["cookerId"] == "device-789"
        assert payload["payload"]["type"] == "oven_v2"
        assert payload["payload"]["originSource"] == "api"

    def test_build_v2_start_with_timer(self):
        """Test V2 start with timer."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800)
        stage = CookStage(temperature=temp, timer=timer)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert "timer" in stage_data["do"]
        assert "nodes.timer.mode" in stage_data["exit"]["conditions"]["and"]

    def test_build_v2_start_without_timer(self):
        """Test V2 start without timer."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert "timer" not in stage_data["do"]

    def test_build_v2_start_with_probe(self):
        """Test V2 start with probe."""
        temp = Temperature(celsius=180)
        probe = Probe(setpoint=Temperature(celsius=65))
        stage = CookStage(temperature=temp, probe=probe)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert "probe" in stage_data["do"]

    def test_build_v2_start_with_steam(self):
        """Test V2 start with steam."""
        temp = Temperature(celsius=100)
        steam = SteamSettings(mode=SteamMode.STEAM_PERCENTAGE, steam_percentage=100)
        stage = CookStage(temperature=temp, steam=steam, mode=TemperatureMode.WET)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert "steamGenerators" in stage_data["do"]

    def test_build_v2_start_temperature_no_fahrenheit(self):
        """Test V2 start doesn't include Fahrenheit in temperature."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        temp_data = stage_data["do"]["temperatureBulbs"]["dry"]["setpoint"]
        assert "celsius" in temp_data
        assert "fahrenheit" not in temp_data

    def test_build_v2_start_vent_open(self):
        """Test V2 start with vent open."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, vent_open=True)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["exhaustVent"]["state"] == "open"

    def test_build_v2_start_vent_closed(self):
        """Test V2 start with vent closed."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, vent_open=False)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["exhaustVent"]["state"] == "closed"

    def test_build_stop_command(self):
        """Test building stop command."""
        payload = CommandBuilder.build_stop_command("device-123")
        
        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_STOP"

    def test_build_probe_command(self):
        """Test building probe command."""
        temp = Temperature(celsius=65)
        payload = CommandBuilder.build_probe_command("device-123", temp)
        
        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_SET_PROBE"
        assert "setpoint" in payload["payload"]
        assert payload["payload"]["setpoint"]["celsius"] == 65

    def test_build_temperature_unit_command_celsius(self):
        """Test building temperature unit command for Celsius."""
        payload = CommandBuilder.build_temperature_unit_command("device-123", "C")
        
        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_SET_TEMPERATURE_UNIT"
        assert payload["payload"]["temperatureUnit"] == "C"

    def test_build_temperature_unit_command_fahrenheit(self):
        """Test building temperature unit command for Fahrenheit."""
        payload = CommandBuilder.build_temperature_unit_command("device-123", "F")
        
        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_SET_TEMPERATURE_UNIT"
        assert payload["payload"]["temperatureUnit"] == "F"

    def test_build_temperature_unit_command_invalid(self):
        """Test building temperature unit command with invalid unit."""
        with pytest.raises(ValueError, match="Unit must be 'C' or 'F'"):
            CommandBuilder.build_temperature_unit_command("device-123", "K")

    def test_static_methods(self):
        """Test that all builder methods are static."""
        builder = CommandBuilder()
        
        # Should be able to call methods on instance
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp)
        
        payload = builder.build_start_command("device-123", [stage], OvenVersion.V1)
        assert payload is not None

    def test_build_v2_multiple_stages(self):
        """Test V2 start with multiple stages."""
        stage1 = CookStage(temperature=Temperature(celsius=180), title="Stage 1")
        stage2 = CookStage(temperature=Temperature(celsius=200), title="Stage 2")

        payload = CommandBuilder._build_v2_start("device-789", [stage1, stage2])
        
        assert len(payload["payload"]["stages"]) == 2
        assert payload["payload"]["stages"][0]["title"] == "Stage 1"
        assert payload["payload"]["stages"][1]["title"] == "Stage 2"

    def test_build_v2_entry_conditions(self):
        """Test V2 entry conditions are properly formatted."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, mode=TemperatureMode.DRY)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        conditions = stage_data["entry"]["conditions"]["and"]
        assert "nodes.temperatureBulbs.dry.current.celsius" in conditions
        assert conditions["nodes.temperatureBulbs.dry.current.celsius"][">="] == 200

    def test_build_v2_wet_mode(self):
        """Test V2 start with wet mode."""
        temp = Temperature(celsius=85)
        stage = CookStage(temperature=temp, mode=TemperatureMode.WET)

        payload = CommandBuilder._build_v2_start("device-789", [stage])
        
        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["temperatureBulbs"]["mode"] == "wet"
        assert "wet" in stage_data["do"]["temperatureBulbs"]

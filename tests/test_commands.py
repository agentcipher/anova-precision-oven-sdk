import pytest
from pydantic import ValidationError

from anova_oven_sdk.commands import CommandBuilder
from anova_oven_sdk.models import (
    CookStage, Temperature, OvenVersion, HeatingElements,
    Timer, TimerStartType, SteamSettings, SteamMode, Probe,
    TemperatureMode, StageType
)


class TestCommandBuilder:
    """Test CommandBuilder class."""

    def test_build_start_command_v1(self):
        """Test building V1 start command."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, title="Test Cook", stage_type=StageType.COOK)

        payload = CommandBuilder.build_start_command(
            "device-123",
            [stage],
            OvenVersion.V1
        )

        assert payload["id"] == "device-123"
        assert payload["type"] == "CMD_APO_START"
        assert "cookId" in payload["payload"]
        assert "stages" in payload["payload"]
        assert len(payload["payload"]["stages"]) == 1  # Single cook stage

    def test_build_start_command_v1_with_preheat(self):
        """Test building V1 start command with preheat and cook stages."""
        temp = Temperature(celsius=200)
        preheat = CookStage(temperature=temp, title="Preheat", stage_type=StageType.PREHEAT)
        cook = CookStage(temperature=temp, title="Cook", stage_type=StageType.COOK)

        payload = CommandBuilder.build_start_command(
            "device-123",
            [preheat, cook],
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
        stage = CookStage(temperature=temp, title="Test Cook V2", stage_type=StageType.COOK)

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
        stage = CookStage(temperature=temp, timer=timer, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        # Check cook stage has timer
        cook_stage = payload["payload"]["stages"][0]
        assert cook_stage["type"] == "cook"
        assert cook_stage["timer"]["initial"] == 1800

    def test_build_v1_start_without_timer(self):
        """Test V1 start without timer."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        cook_stage = payload["payload"]["stages"][0]
        assert cook_stage["type"] == "cook"
        assert "timer" not in cook_stage

    def test_build_v1_start_with_timer_immediately(self):
        """Test V1 start with immediate timer."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800, start_type=TimerStartType.IMMEDIATELY)
        stage = CookStage(temperature=temp, timer=timer, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        cook_stage = payload["payload"]["stages"][0]
        assert cook_stage["timerAdded"] is True
        assert cook_stage["timer"]["initial"] == 1800

    def test_build_v1_start_with_probe(self):
        """Test V1 start with probe."""
        temp = Temperature(celsius=180)
        probe = Probe(setpoint=Temperature(celsius=65))
        stage = CookStage(temperature=temp, probe=probe, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        cook_stage = payload["payload"]["stages"][0]
        assert cook_stage["probeAdded"] is True
        assert "probe" in cook_stage

    def test_build_v1_start_without_probe(self):
        """Test V1 start without probe."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        cook_stage = payload["payload"]["stages"][0]
        assert "probe" not in cook_stage

    def test_build_v1_preheat_stage(self):
        """Test V1 preheat stage doesn't include timer or probe fields."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, stage_type=StageType.PREHEAT)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        preheat_stage = payload["payload"]["stages"][0]
        assert preheat_stage["type"] == "preheat"
        assert "timerAdded" not in preheat_stage
        assert "probeAdded" not in preheat_stage
        assert "timer" not in preheat_stage

    def test_build_v1_start_with_steam(self):
        """Test V1 start with steam."""
        temp = Temperature(celsius=100)
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        stage = CookStage(temperature=temp, steam=steam, mode=TemperatureMode.WET, stage_type=StageType.PREHEAT)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        preheat_stage = payload["payload"]["stages"][0]
        assert "steamGenerators" in preheat_stage

    def test_build_v1_start_multiple_stages(self):
        """Test V1 start with multiple stages."""
        stage1 = CookStage(temperature=Temperature(celsius=180), stage_type=StageType.PREHEAT)
        stage2 = CookStage(temperature=Temperature(celsius=180), stage_type=StageType.COOK)
        stage3 = CookStage(temperature=Temperature(celsius=200), stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage1, stage2, stage3])

        # 3 stages = 3 API stages
        assert len(payload["payload"]["stages"]) == 3
        assert payload["payload"]["stages"][0]["type"] == "preheat"
        assert payload["payload"]["stages"][1]["type"] == "cook"
        assert payload["payload"]["stages"][2]["type"] == "cook"

    def test_build_v1_start_with_user_action(self):
        """Test V1 start with user action required."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, user_action_required=True, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        cook_stage = payload["payload"]["stages"][0]
        assert cook_stage["userActionRequired"] is True
        assert cook_stage["stageTransitionType"] == "manual"

    def test_build_v1_preheat_no_user_action(self):
        """Test V1 preheat stage never has user action required."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, user_action_required=True, stage_type=StageType.PREHEAT)

        payload = CommandBuilder._build_v1_start("device-123", [stage])

        preheat_stage = payload["payload"]["stages"][0]
        # Preheat stages should never have user action required
        assert preheat_stage["userActionRequired"] is False

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
            description="Test description",
            stage_type=StageType.PREHEAT
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
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        assert payload["id"] == "device-789"
        assert payload["payload"]["cookerId"] == "device-789"
        assert payload["payload"]["type"] == "oven_v2"
        assert payload["payload"]["originSource"] == "api"

    def test_build_v2_preheat_stage(self):
        """Test V2 preheat stage type."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, stage_type=StageType.PREHEAT)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["type"] == "preheat"

    def test_build_v2_cook_stage(self):
        """Test V2 cook stage type."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["type"] == "cook"

    def test_build_v2_start_with_timer(self):
        """Test V2 start with timer."""
        temp = Temperature(celsius=180)
        timer = Timer(initial=1800)
        stage = CookStage(temperature=temp, timer=timer, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert "timer" in stage_data["do"]
        assert "nodes.timer.mode" in stage_data["exit"]["conditions"]["and"]

    def test_build_v2_start_without_timer(self):
        """Test V2 start without timer."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert "timer" not in stage_data["do"]

    def test_build_v2_start_with_probe(self):
        """Test V2 start with probe."""
        temp = Temperature(celsius=180)
        probe = Probe(setpoint=Temperature(celsius=65))
        stage = CookStage(temperature=temp, probe=probe, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert "probe" in stage_data["do"]

    def test_build_v2_start_with_steam(self):
        """Test V2 start with steam."""
        temp = Temperature(celsius=100)
        steam = SteamSettings(mode=SteamMode.STEAM_PERCENTAGE, steam_percentage=100)
        stage = CookStage(temperature=temp, steam=steam, mode=TemperatureMode.WET, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert "steamGenerators" in stage_data["do"]

    def test_build_v2_start_temperature_no_fahrenheit(self):
        """Test V2 start doesn't include Fahrenheit in temperature."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        temp_data = stage_data["do"]["temperatureBulbs"]["dry"]["setpoint"]
        assert "celsius" in temp_data
        assert "fahrenheit" not in temp_data

    def test_build_v2_start_vent_open(self):
        """Test V2 start with vent open."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, vent_open=True, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["exhaustVent"]["state"] == "open"

    def test_build_v2_start_vent_closed(self):
        """Test V2 start with vent closed."""
        temp = Temperature(celsius=180)
        stage = CookStage(temperature=temp, vent_open=False, stage_type=StageType.COOK)

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
        with pytest.raises(ValidationError, match="Temperature unit must be 'C' or 'F'"):
            CommandBuilder.build_temperature_unit_command("device-123", "K")

    def test_static_methods(self):
        """Test that all builder methods are static."""
        builder = CommandBuilder()

        # Should be able to call methods on instance
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, stage_type=StageType.COOK)

        payload = builder.build_start_command("device-123", [stage], OvenVersion.V1)
        assert payload is not None

    def test_build_v2_multiple_stages(self):
        """Test V2 start with multiple stages."""
        stage1 = CookStage(temperature=Temperature(celsius=180), title="Stage 1", stage_type=StageType.PREHEAT)
        stage2 = CookStage(temperature=Temperature(celsius=200), title="Stage 2", stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage1, stage2])

        assert len(payload["payload"]["stages"]) == 2
        assert payload["payload"]["stages"][0]["title"] == "Stage 1"
        assert payload["payload"]["stages"][0]["do"]["type"] == "preheat"
        assert payload["payload"]["stages"][1]["title"] == "Stage 2"
        assert payload["payload"]["stages"][1]["do"]["type"] == "cook"

    def test_build_v2_entry_conditions(self):
        """Test V2 entry conditions are properly formatted."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp, mode=TemperatureMode.DRY, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        conditions = stage_data["entry"]["conditions"]["and"]
        assert "nodes.temperatureBulbs.dry.current.celsius" in conditions
        assert conditions["nodes.temperatureBulbs.dry.current.celsius"][">="] == 200

    def test_build_v2_wet_mode(self):
        """Test V2 start with wet mode."""
        temp = Temperature(celsius=85)
        stage = CookStage(temperature=temp, mode=TemperatureMode.WET, stage_type=StageType.COOK)

        payload = CommandBuilder._build_v2_start("device-789", [stage])

        stage_data = payload["payload"]["stages"][0]
        assert stage_data["do"]["temperatureBulbs"]["mode"] == "wet"
        assert "wet" in stage_data["do"]["temperatureBulbs"]

    def test_stage_type_default(self):
        """Test that stage_type defaults to COOK."""
        temp = Temperature(celsius=200)
        stage = CookStage(temperature=temp)  # No stage_type specified

        assert stage.stage_type == StageType.COOK

    def test_explicit_preheat_and_cook_sequence(self):
        """Test explicit preheat followed by cook stages."""
        temp = Temperature(celsius=180)
        preheat = CookStage(temperature=temp, title="Preheat", stage_type=StageType.PREHEAT)
        cook = CookStage(temperature=temp, title="Cook", timer=Timer(initial=1800), stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [preheat, cook])

        assert len(payload["payload"]["stages"]) == 2
        assert payload["payload"]["stages"][0]["type"] == "preheat"
        assert payload["payload"]["stages"][0]["title"] == "Preheat"
        assert payload["payload"]["stages"][1]["type"] == "cook"
        assert payload["payload"]["stages"][1]["title"] == "Cook"
        assert payload["payload"]["stages"][1]["timer"]["initial"] == 1800

    def test_multiple_cook_stages_no_preheat(self):
        """Test multiple cook stages without any preheat."""
        stage1 = CookStage(temperature=Temperature(celsius=180), timer=Timer(initial=600), stage_type=StageType.COOK)
        stage2 = CookStage(temperature=Temperature(celsius=200), timer=Timer(initial=900), stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [stage1, stage2])

        assert len(payload["payload"]["stages"]) == 2
        assert payload["payload"]["stages"][0]["type"] == "cook"
        assert payload["payload"]["stages"][1]["type"] == "cook"

    def test_multiple_preheat_stages(self):
        """Test multiple preheat stages followed by cook."""
        preheat1 = CookStage(temperature=Temperature(celsius=150), stage_type=StageType.PREHEAT)
        preheat2 = CookStage(temperature=Temperature(celsius=200), stage_type=StageType.PREHEAT)
        cook = CookStage(temperature=Temperature(celsius=200), timer=Timer(initial=1800), stage_type=StageType.COOK)

        payload = CommandBuilder._build_v1_start("device-123", [preheat1, preheat2, cook])

        assert len(payload["payload"]["stages"]) == 3
        assert payload["payload"]["stages"][0]["type"] == "preheat"
        assert payload["payload"]["stages"][1]["type"] == "preheat"
        assert payload["payload"]["stages"][2]["type"] == "cook"
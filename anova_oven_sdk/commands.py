# ============================================================================
# Command Builder
# ============================================================================

from typing import List, Dict, Any

from .models import CookStage, OvenVersion, TimerStartType, VentState, Temperature
from .command_models import (
    StartCommand, StartCommandPayloadV1, StartCommandPayloadV2,
    StopCommand, ProbeCommand, ProbeCommandPayload,
    TemperatureUnitCommand, TemperatureUnitCommandPayload,
    WebSocketCommand
)
from .utils import generate_uuid


class CommandBuilder:
    """Builds command payloads for oven API."""

    @staticmethod
    def build_start_command(
            device_id: str,
            stages: List[CookStage],
            oven_version: OvenVersion
    ) -> Dict[str, Any]:
        """Build start cook command."""
        if oven_version == OvenVersion.V1:
            return CommandBuilder._build_v1_start(device_id, stages)
        return CommandBuilder._build_v2_start(device_id, stages)

    @staticmethod
    def _build_v1_start(device_id: str, stages: List[CookStage]) -> Dict[str, Any]:
        """Build V1 start payload."""
        cook_id = generate_uuid()
        stage_payloads = []

        for stage in stages:
            # Preheat stage
            preheat = {
                "stepType": "stage",
                "id": generate_uuid(),
                "title": stage.title,
                "description": stage.description,
                "type": "preheat",
                "userActionRequired": False,
                "temperatureBulbs": {
                    "mode": stage.mode.value,
                    stage.mode.value: {"setpoint": stage.temperature.model_dump(exclude_none=True)}
                },
                "heatingElements": stage.heating_elements.model_dump(mode='json'),
                "fan": {"speed": stage.fan_speed},
                "vent": {"open": stage.vent_open},
                "rackPosition": stage.rack_position,
                "stageTransitionType": "automatic"
            }

            if stage.steam:
                preheat["steamGenerators"] = stage.steam.model_dump(by_alias=True, exclude_none=True, mode='json')

            stage_payloads.append(preheat)

            # Cook stage
            cook = preheat.copy()
            cook.update({
                "id": generate_uuid(),
                "type": "cook",
                "userActionRequired": stage.user_action_required,
            })

            # Add timer, probe, and transition fields in correct order
            # Add timer, probe, and transition fields in correct order
            if stage.timer:
                cook["stageTransitionType"] = "automatic" if not stage.user_action_required else "manual"
                # Timer should only have 'initial', no 'startType'
                cook["timer"] = {"initial": stage.timer.initial}
            else:
                cook["stageTransitionType"] = "automatic" if not stage.user_action_required else "manual"

            if stage.probe:
                cook["probe"] = stage.probe.model_dump(by_alias=True, exclude_none=True, mode='json')

            stage_payloads.append(cook)

        payload = StartCommandPayloadV1(
            cook_id=cook_id,
            stages=stage_payloads
        )
        command = StartCommand(id=device_id, payload=payload)

        # Return inner command directly (client wraps it)
        return command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def _build_v2_start(device_id: str, stages: List[CookStage]) -> Dict[str, Any]:
        """Build V2 start payload."""
        cook_id = generate_uuid()
        stage_payloads = []

        for stage in stages:
            stage_data = {
                "id": generate_uuid(),
                "title": stage.title,
                "description": stage.description,
                "rackPosition": stage.rack_position,
                "do": {
                    "type": "cook",
                    "fan": {"speed": stage.fan_speed},
                    "heatingElements": stage.heating_elements.model_dump(mode='json'),
                    "exhaustVent": {
                        "state": VentState.OPEN.value if stage.vent_open else VentState.CLOSED.value
                    },
                    "temperatureBulbs": {
                        "mode": stage.mode.value,
                        stage.mode.value: {
                            "setpoint": stage.temperature.model_dump(exclude={'fahrenheit'}, exclude_none=True)}
                    }
                },
                "exit": {"conditions": {"and": {}}}
            }

            # Entry conditions based on temperature
            stage_data["entry"] = {
                "conditions": {
                    "and": {
                        f"nodes.temperatureBulbs.{stage.mode.value}.current.celsius": {
                            ">=": stage.temperature.celsius
                        }
                    }
                }
            }



            if stage.steam:
                stage_data["do"]["steamGenerators"] = stage.steam.model_dump(by_alias=True, exclude_none=True,
                                                                             mode='json')

            if stage.timer:
                # Timer with entry conditions nested inside
                stage_data["do"]["timer"] = {
                    "initial": stage.timer.initial,
                    "entry": {
                        "conditions": {
                            "and": {
                                f"nodes.temperatureBulbs.{stage.mode.value}.current.celsius": {
                                    ">=": stage.temperature.celsius
                                }
                            }
                        }
                    }
                }
                stage_data["exit"]["conditions"]["and"]["nodes.timer.mode"] = {"=": "completed"}

            if stage.probe:
                stage_data["do"]["probe"] = stage.probe.model_dump(by_alias=True, exclude_none=True, mode='json')

            stage_payloads.append(stage_data)

        payload = StartCommandPayloadV2(
            stages=stage_payloads,
            cook_id=cook_id,
            cooker_id=device_id,
            cookable_id="",
            title="",
            type=OvenVersion.V2.value,
            origin_source="api",
            cookable_type="manual"
        )
        command = StartCommand(id=device_id, payload=payload)

        # Return inner command directly (client wraps it)
        return command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_stop_command(device_id: str) -> Dict[str, Any]:
        """Build stop command."""
        command = StopCommand(id=device_id)

        # Return inner command directly (client wraps it)
        return command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_probe_command(device_id: str, temp: Temperature) -> Dict[str, Any]:
        """Build probe command."""
        payload = ProbeCommandPayload(setpoint=temp.model_dump(exclude_none=True))
        command = ProbeCommand(id=device_id, payload=payload)

        # Return inner command directly (client wraps it)
        return command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_temperature_unit_command(device_id: str, unit: str) -> Dict[str, Any]:
        """Build temperature unit command."""
        payload = TemperatureUnitCommandPayload(temperature_unit=unit)
        command = TemperatureUnitCommand(id=device_id, payload=payload)

        # Return inner command directly (client wraps it)
        return command.model_dump(by_alias=True, exclude_none=True)
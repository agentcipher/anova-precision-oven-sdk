# ============================================================================
# Command Builder
# ============================================================================

from typing import List, Dict, Any

from .models import CookStage, OvenVersion, TimerStartType, VentState, Temperature
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
                    stage.mode.value: {"setpoint": stage.temperature.to_dict()}
                },
                "heatingElements": stage.heating_elements.to_dict(),
                "fan": {"speed": stage.fan_speed},
                "vent": {"open": stage.vent_open},
                "rackPosition": stage.rack_position,
                "stageTransitionType": "automatic"
            }

            if stage.steam:
                preheat["steamGenerators"] = stage.steam.to_dict()

            stage_payloads.append(preheat)

            # Cook stage
            cook = preheat.copy()
            cook.update({
                "id": generate_uuid(),
                "type": "cook",
                "userActionRequired": stage.user_action_required,
                "stageTransitionType": "automatic" if not stage.user_action_required else "manual"
            })

            if stage.timer:
                cook["timer"] = stage.timer.to_dict()
                cook["timerAdded"] = True
                cook["timerStartOnDetect"] = stage.timer.start_type != TimerStartType.IMMEDIATELY
            else:
                cook["timerAdded"] = False
                cook["timerStartOnDetect"] = False

            if stage.probe:
                cook["probeAdded"] = True
                cook["probe"] = stage.probe.to_dict()
            else:
                cook["probeAdded"] = False

            stage_payloads.append(cook)

        return {
            "id": device_id,
            "type": "CMD_APO_START",
            "payload": {
                "cookId": cook_id,
                "stages": stage_payloads
            }
        }

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
                    "heatingElements": stage.heating_elements.to_dict(),
                    "exhaustVent": {
                        "state": VentState.OPEN.value if stage.vent_open else VentState.CLOSED.value
                    },
                    "temperatureBulbs": {
                        "mode": stage.mode.value,
                        stage.mode.value: {"setpoint": stage.temperature.to_dict(include_fahrenheit=False)}
                    }
                },
                "entry": {
                    "conditions": {
                        "and": {
                            f"nodes.temperatureBulbs.{stage.mode.value}.current.celsius": {
                                ">=": stage.temperature.celsius
                            }
                        }
                    }
                },
                "exit": {"conditions": {"and": {}}}
            }

            if stage.steam:
                stage_data["do"]["steamGenerators"] = stage.steam.to_dict()

            if stage.timer:
                stage_data["do"]["timer"] = stage.timer.to_dict()
                stage_data["exit"]["conditions"]["and"]["nodes.timer.mode"] = {"=": "completed"}

            if stage.probe:
                stage_data["do"]["probe"] = stage.probe.to_dict()

            stage_payloads.append(stage_data)

        return {
            "id": device_id,
            "type": "CMD_APO_START",
            "payload": {
                "stages": stage_payloads,
                "cookId": cook_id,
                "cookerId": device_id,
                "cookableId": "",
                "title": "",
                "type": OvenVersion.V2.value,
                "originSource": "api",
                "cookableType": "manual"
            }
        }

    @staticmethod
    def build_stop_command(device_id: str) -> Dict[str, Any]:
        """Build stop command."""
        return {"id": device_id, "type": "CMD_APO_STOP"}

    @staticmethod
    def build_probe_command(device_id: str, temp: Temperature) -> Dict[str, Any]:
        """Build probe command."""
        return {
            "id": device_id,
            "type": "CMD_APO_SET_PROBE",
            "payload": {"setpoint": temp.to_dict()}
        }

    @staticmethod
    def build_temperature_unit_command(device_id: str, unit: str) -> Dict[str, Any]:
        """Build temperature unit command."""
        if unit not in ["C", "F"]:
            raise ValueError("Unit must be 'C' or 'F'")
        return {
            "id": device_id,
            "type": "CMD_APO_SET_TEMPERATURE_UNIT",
            "payload": {"temperatureUnit": unit}
        }

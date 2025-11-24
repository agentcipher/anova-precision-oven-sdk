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
            # Build in correct field order as per API documentation
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

            # Add steamGenerators to preheat stage
            # Only include for V1 when the stage has steam configured
            if stage.steam:
                preheat["steamGenerators"] = stage.steam.model_dump(by_alias=True, exclude_none=True, mode='json')

            stage_payloads.append(preheat)

            # Cook stage - build in correct field order
            # CRITICAL: Field order matters for API compatibility
            cook = {
                "stepType": "stage",
                "id": generate_uuid(),
                "title": stage.title,
                "description": stage.description,
                "type": "cook",
                "userActionRequired": stage.user_action_required,
                "temperatureBulbs": {
                    "mode": stage.mode.value,
                    stage.mode.value: {"setpoint": stage.temperature.model_dump(exclude_none=True)}
                },
                "heatingElements": stage.heating_elements.model_dump(mode='json'),
                "fan": {"speed": stage.fan_speed},
                "vent": {"open": stage.vent_open},
                "rackPosition": stage.rack_position,
            }

            # Add timer-related fields in correct order (before stageTransitionType)
            if stage.timer:
                cook["timerAdded"] = True
                cook["probeAdded"] = False
                cook["timerStartOnDetect"] = stage.timer.start_type != TimerStartType.IMMEDIATELY
                cook["stageTransitionType"] = "automatic" if not stage.user_action_required else "manual"
                # Timer should only have 'initial', no 'startType'
                cook["timer"] = {"initial": stage.timer.initial}
            else:
                cook["timerAdded"] = False
                cook["probeAdded"] = False
                cook["timerStartOnDetect"] = False
                cook["stageTransitionType"] = "automatic" if not stage.user_action_required else "manual"

            if stage.probe:
                cook["probeAdded"] = True
                cook["probe"] = stage.probe.model_dump(by_alias=True, exclude_none=True, mode='json')

            # IMPORTANT: Do NOT add steamGenerators to cook stage
            # This is different from preheat stage

            stage_payloads.append(cook)

        payload = StartCommandPayloadV1(
            cook_id=cook_id,
            stages=stage_payloads
        )
        command = StartCommand(id=device_id, payload=payload)

        # Wrap in WebSocket command structure
        ws_command = WebSocketCommand(
            command="CMD_APO_START",
            request_id=generate_uuid(),
            payload=command
        )
        return ws_command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def _build_v2_start(device_id: str, stages: List[CookStage]) -> Dict[str, Any]:
        """Build V2 start payload."""
        cook_id = generate_uuid()
        stage_payloads = []

        for stage in stages:
            # Build 'do' section with correct field order
            do_section = {
                "type": "cook",
                "fan": {"speed": stage.fan_speed},
                "heatingElements": stage.heating_elements.model_dump(mode='json'),
                "exhaustVent": {
                    "state": VentState.OPEN.value if stage.vent_open else VentState.CLOSED.value
                }
            }

            # Add steamGenerators BEFORE temperatureBulbs if present
            if stage.steam:
                do_section["steamGenerators"] = stage.steam.model_dump(by_alias=True, exclude_none=True, mode='json')

            # Add temperatureBulbs after steam (or after exhaustVent if no steam)
            do_section["temperatureBulbs"] = {
                "mode": stage.mode.value,
                stage.mode.value: {
                    "setpoint": stage.temperature.model_dump(exclude={'fahrenheit'}, exclude_none=True)
                }
            }

            # Build stage_data with correct field order: id, do, exit, [entry], title, description, rackPosition
            stage_data = {
                "id": generate_uuid(),
                "do": do_section,
                "exit": {"conditions": {"and": {}}}
            }

            # Determine if this stage needs entry conditions
            # Entry conditions are only added if timer has entry (preheating condition)
            has_timer_with_entry = stage.timer and stage.steam

            if has_timer_with_entry:
                stage_data["entry"] = {
                    "conditions": {
                        "and": {
                            f"nodes.temperatureBulbs.{stage.mode.value}.current.celsius": {
                                ">=": stage.temperature.celsius
                            }
                        }
                    }
                }

            # Add title, description, rackPosition after exit/entry
            stage_data["title"] = stage.title
            stage_data["description"] = stage.description
            stage_data["rackPosition"] = stage.rack_position

            # Add timer to do section
            if stage.timer:
                # Timer has entry conditions only if stage has steam (preheating)
                if has_timer_with_entry:
                    do_section["timer"] = {
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
                else:
                    # Timer without entry (no preheating needed)
                    do_section["timer"] = {"initial": stage.timer.initial}

                stage_data["exit"]["conditions"]["and"]["nodes.timer.mode"] = {"=": "completed"}

            if stage.probe:
                do_section["probe"] = stage.probe.model_dump(by_alias=True, exclude_none=True, mode='json')

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

        # Wrap in WebSocket command structure
        ws_command = WebSocketCommand(
            command="CMD_APO_START",
            request_id=generate_uuid(),
            payload=command
        )
        return ws_command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_stop_command(device_id: str) -> Dict[str, Any]:
        """Build stop command."""
        command = StopCommand(id=device_id)

        # Wrap in WebSocket command structure
        ws_command = WebSocketCommand(
            command="CMD_APO_STOP",
            request_id=generate_uuid(),
            payload=command
        )
        return ws_command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_probe_command(device_id: str, temp: Temperature) -> Dict[str, Any]:
        """Build probe command."""
        payload = ProbeCommandPayload(setpoint=temp.model_dump(exclude_none=True))
        command = ProbeCommand(id=device_id, payload=payload)

        # Wrap in WebSocket command structure
        ws_command = WebSocketCommand(
            command="CMD_APO_SET_PROBE",
            request_id=generate_uuid(),
            payload=command
        )
        return ws_command.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def build_temperature_unit_command(device_id: str, unit: str) -> Dict[str, Any]:
        """Build temperature unit command."""
        payload = TemperatureUnitCommandPayload(temperature_unit=unit)
        command = TemperatureUnitCommand(id=device_id, payload=payload)

        # Wrap in WebSocket command structure
        ws_command = WebSocketCommand(
            command="CMD_APO_SET_TEMPERATURE_UNIT",
            request_id=generate_uuid(),
            payload=command
        )
        return ws_command.model_dump(by_alias=True, exclude_none=True)
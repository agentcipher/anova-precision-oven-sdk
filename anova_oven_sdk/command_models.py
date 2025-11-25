# ============================================================================
# Command Models - Pydantic Models for Outbound API Commands
# ============================================================================

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum


class CommandType(str, Enum):
    """Command types for Anova oven API."""
    START = "CMD_APO_START"
    STOP = "CMD_APO_STOP"
    SET_PROBE = "CMD_APO_SET_PROBE"
    SET_TEMPERATURE_UNIT = "CMD_APO_SET_TEMPERATURE_UNIT"


class BaseCommand(BaseModel):
    """Base command structure for all oven commands.

    CRITICAL: Field order must be: id, payload, type
    This matches the working Anova example payloads.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Device ID")
    # payload will be added by subclass
    # type will be added by subclass after payload


# ============================================================================
# START COMMAND MODELS
# ============================================================================

class StartCommandPayloadV1(BaseModel):
    """Payload for V1 start command."""
    model_config = ConfigDict(populate_by_name=True)

    cook_id: str = Field(..., serialization_alias="cookId", description="Unique cook session ID")
    stages: List[Dict[str, Any]] = Field(..., description="Cooking stages")


class StartCommandPayloadV2(BaseModel):
    """Payload for V2 start command."""
    model_config = ConfigDict(populate_by_name=True)

    stages: List[Dict[str, Any]] = Field(..., description="Cooking stages")
    cook_id: str = Field(..., serialization_alias="cookId", description="Unique cook session ID")
    cooker_id: str = Field(..., serialization_alias="cookerId", description="Device ID")
    cookable_id: str = Field(default="", serialization_alias="cookableId", description="Recipe ID")
    title: str = Field(default="", description="Cook title")
    type: str = Field(default="oven_v2", description="Oven type")
    origin_source: str = Field(default="api", serialization_alias="originSource", description="Command origin")
    cookable_type: str = Field(default="manual", serialization_alias="cookableType", description="Recipe type")


class StartCommand(BaseCommand):
    """Start cooking command.

    Field order: id (from BaseCommand), payload, type
    """
    payload: StartCommandPayloadV1 | StartCommandPayloadV2 = Field(..., description="Command payload")
    type: str = Field(default=CommandType.START.value, description="Command type")


# ============================================================================
# STOP COMMAND MODEL
# ============================================================================

class StopCommand(BaseCommand):
    """Stop cooking command.

    Field order: id (from BaseCommand), type
    """
    type: str = Field(default=CommandType.STOP.value, description="Command type")


# ============================================================================
# PROBE COMMAND MODELS
# ============================================================================

class ProbeCommandPayload(BaseModel):
    """Payload for probe temperature command."""
    model_config = ConfigDict(populate_by_name=True)

    setpoint: Dict[str, float] = Field(..., description="Temperature setpoint")


class ProbeCommand(BaseCommand):
    """Set probe temperature command.

    Field order: id (from BaseCommand), payload, type
    """
    payload: ProbeCommandPayload = Field(..., description="Probe configuration")
    type: str = Field(default=CommandType.SET_PROBE.value, description="Command type")


# ============================================================================
# TEMPERATURE UNIT COMMAND MODELS
# ============================================================================

class TemperatureUnitCommandPayload(BaseModel):
    """Payload for temperature unit command."""
    model_config = ConfigDict(populate_by_name=True)

    temperature_unit: str = Field(..., serialization_alias="temperatureUnit", description="Temperature unit (C or F)")

    @field_validator('temperature_unit')
    @classmethod
    def validate_unit(cls, v: str) -> str:
        """Validate temperature unit."""
        if v not in ["C", "F"]:
            raise ValueError("Temperature unit must be 'C' or 'F'")
        return v


class TemperatureUnitCommand(BaseCommand):
    """Set temperature unit command.

    Field order: id (from BaseCommand), payload, type
    """
    payload: TemperatureUnitCommandPayload = Field(..., description="Temperature unit configuration")
    type: str = Field(default=CommandType.SET_TEMPERATURE_UNIT.value, description="Command type")


class WebSocketCommand(BaseModel):
    """Wrapper for WebSocket command with proper structure.

    CRITICAL: Field order must match API documentation exactly:
    - command
    - payload
    - requestId
    """
    model_config = ConfigDict(populate_by_name=True)

    command: str = Field(..., description="Command type")
    payload: Union[StartCommand, StopCommand, ProbeCommand, TemperatureUnitCommand] = Field(...,
                                                                                            description="Command payload")
    request_id: str = Field(..., serialization_alias="requestId", description="Unique request ID")
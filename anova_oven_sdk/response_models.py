# ============================================================================
# Response Models - Pydantic Models for Inbound API Responses
# ============================================================================

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator
from enum import Enum


class ResponseCommand(str, Enum):
    """Response command types from Anova oven API."""
    DEVICE_LIST = "EVENT_APO_WIFI_LIST"
    COMMAND_RESPONSE = "RESPONSE"
    ERROR = "ERROR"


class BaseResponse(BaseModel):
    """Base response structure for all oven responses."""
    model_config = ConfigDict(populate_by_name=True)
    
    command: str = Field(..., description="Response command type")
    request_id: Optional[str] = Field(None, alias="requestId", description="Request ID if applicable")


# ============================================================================
# DEVICE LIST RESPONSE
# ============================================================================

class DeviceListResponse(BaseResponse):
    """Response for device list event."""
    command: str = Field(default=ResponseCommand.DEVICE_LIST.value, description="Command type")
    payload: List[Dict[str, Any]] = Field(default_factory=list, description="List of device data")


# ============================================================================
# COMMAND RESPONSE
# ============================================================================

class CommandResponsePayload(BaseModel):
    """Payload for command response."""
    model_config = ConfigDict(populate_by_name=True, extra='allow')
    
    status: Optional[str] = None
    message: Optional[str] = None


class CommandResponse(BaseResponse):
    """Generic command response."""
    command: str = Field(default=ResponseCommand.COMMAND_RESPONSE.value, description="Command type")
    payload: Optional[CommandResponsePayload] = Field(None, description="Response payload")
    success: Optional[bool] = None


# ============================================================================
# ERROR RESPONSE
# ============================================================================

class ErrorResponsePayload(BaseModel):
    """Payload for error response."""
    model_config = ConfigDict(populate_by_name=True)
    
    error_code: Optional[str] = Field(None, alias="errorCode", description="Error code")
    error_message: str = Field(..., alias="errorMessage", description="Error message")
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseResponse):
    """Error response from API."""
    command: str = Field(default=ResponseCommand.ERROR.value, description="Command type")
    payload: ErrorResponsePayload = Field(..., description="Error details")


# ============================================================================
# APO STATE RESPONSE
# ============================================================================

class SystemInfo(BaseModel):
    """System information."""
    model_config = ConfigDict(populate_by_name=True)

    online: bool
    hardware_version: str = Field(..., alias="hardwareVersion")
    power_mains: int = Field(..., alias="powerMains")
    power_hertz: int = Field(..., alias="powerHertz")
    firmware_version: str = Field(..., alias="firmwareVersion")
    ui_hardware_version: str = Field(..., alias="uiHardwareVersion")
    ui_firmware_version: str = Field(..., alias="uiFirmwareVersion")
    firmware_updated_timestamp: Optional[str] = Field(None, alias="firmwareUpdatedTimestamp")
    last_connected_timestamp: Optional[str] = Field(None, alias="lastConnectedTimestamp")
    last_disconnected_timestamp: Optional[str] = Field(None, alias="lastDisconnectedTimestamp")
    triacs_failed: bool = Field(..., alias="triacsFailed")


class OvenState(BaseModel):
    """Oven high-level state."""
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    mode: Optional[str] = None
    temperature_unit: Optional[str] = Field(None, alias="temperatureUnit")
    processed_command_ids: Optional[List[str]] = Field(default_factory=list, alias="processedCommandIds")


class TemperatureBulbState(BaseModel):
    """State of a single temperature bulb."""
    model_config = ConfigDict(populate_by_name=True)

    current: Dict[str, float]
    setpoint: Optional[Dict[str, float]] = None
    dosed: Optional[bool] = None
    dose_failed: Optional[bool] = Field(None, alias="doseFailed")
    overheated: Optional[bool] = None


class TemperatureBulbs(BaseModel):
    """Collection of temperature bulbs."""
    model_config = ConfigDict(populate_by_name=True)

    mode: str
    wet: TemperatureBulbState
    dry: TemperatureBulbState
    dry_top: TemperatureBulbState = Field(..., alias="dryTop")
    dry_bottom: TemperatureBulbState = Field(..., alias="dryBottom")


class TimerState(BaseModel):
    """Timer state."""
    model_config = ConfigDict(populate_by_name=True)

    mode: str
    initial: int
    current: int
    start_type: Optional[str] = Field(None, alias="startType")


class ProbeState(BaseModel):
    """Probe state."""
    model_config = ConfigDict(populate_by_name=True)

    connected: bool
    current: Optional[Dict[str, float]] = None
    setpoint: Optional[Dict[str, float]] = None


class SteamGeneratorState(BaseModel):
    """State of a steam generator component."""
    model_config = ConfigDict(populate_by_name=True)

    current: Optional[float] = None
    setpoint: Optional[float] = None
    failed: Optional[bool] = None
    overheated: Optional[bool] = None
    celsius: Optional[float] = None
    watts: Optional[int] = None
    descale_required: Optional[bool] = Field(None, alias="descaleRequired")
    dosed: Optional[bool] = None


class SteamGenerators(BaseModel):
    """Steam generators state."""
    model_config = ConfigDict(populate_by_name=True)

    mode: str
    relative_humidity: Optional[SteamGeneratorState] = Field(None, alias="relativeHumidity")
    steam_percentage: Optional[SteamGeneratorState] = Field(None, alias="steamPercentage")
    evaporator: SteamGeneratorState
    boiler: SteamGeneratorState

    @model_validator(mode='after')
    def validate_steam_generators(self):
        """Validate steam generators state."""
        if self.mode == "relative-humidity" and self.relative_humidity is None:
             raise ValueError("relativeHumidity is required when mode is 'relative-humidity'")
        return self


class HeatingElementState(BaseModel):
    """State of a heating element."""
    model_config = ConfigDict(populate_by_name=True)

    on: bool
    failed: bool
    watts: int


class HeatingElementsState(BaseModel):
    """Heating elements state."""
    model_config = ConfigDict(populate_by_name=True)

    top: HeatingElementState
    bottom: HeatingElementState
    rear: HeatingElementState


class FanState(BaseModel):
    """Fan state."""
    model_config = ConfigDict(populate_by_name=True)

    speed: int
    failed: bool


class VentState(BaseModel):
    """Vent state."""
    model_config = ConfigDict(populate_by_name=True)

    open: bool


class WaterTankState(BaseModel):
    """Water tank state."""
    model_config = ConfigDict(populate_by_name=True)

    empty: bool


class DoorState(BaseModel):
    """Door state."""
    model_config = ConfigDict(populate_by_name=True)

    closed: bool


class LampState(BaseModel):
    """Lamp state."""
    model_config = ConfigDict(populate_by_name=True)

    on: bool
    failed: bool
    preference: str


class UserInterfaceCircuitState(BaseModel):
    """UI circuit state."""
    model_config = ConfigDict(populate_by_name=True)

    communication_failed: bool = Field(..., alias="communicationFailed")


class Nodes(BaseModel):
    """Detailed device nodes."""
    model_config = ConfigDict(populate_by_name=True)

    temperature_bulbs: TemperatureBulbs = Field(..., alias="temperatureBulbs")
    timer: TimerState
    temperature_probe: ProbeState = Field(..., alias="temperatureProbe")
    steam_generators: SteamGenerators = Field(..., alias="steamGenerators")
    heating_elements: HeatingElementsState = Field(..., alias="heatingElements")
    fan: FanState
    vent: VentState
    water_tank: WaterTankState = Field(..., alias="waterTank")
    door: DoorState
    lamp: LampState
    user_interface_circuit: UserInterfaceCircuitState = Field(..., alias="userInterfaceCircuit")


class CookStageInfo(BaseModel):
    """Information about a single stage of an active cook session."""
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    id: Optional[str] = None
    step_type: Optional[str] = Field(None, alias="stepType")
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    rack_position: Optional[int] = Field(None, alias="rackPosition")
    user_action_required: Optional[bool] = Field(None, alias="userActionRequired")


class CookData(BaseModel):
    """
    Active cook session data, aggregated from top-level cook session fields.

    `stages` semantics are UNVERIFIED: it is unknown whether this list is
    the full, constant stage plan for the cook, or shrinks to only the
    remaining stages as the cook progresses. `Device.current_stage` treats
    `stages[0]` as "the current stage", which is correct either way only if
    the list shrinks -- if it's a constant full plan, `stages[0]` would
    always describe stage 1 regardless of actual progress.

    `Device.total_stage_count`/`current_stage_index` sidestep this ambiguity
    for cooks started via `AnovaOven.start_cook()`: the SDK records the
    ordered stage ids it sent in `CMD_APO_START` (see
    `Device.register_cook_plan`) and matches `stages[0].id` against that
    plan, so "stage X of Y" works regardless of how `stages` itself behaves.
    They return `None` for cooks started outside this SDK instance (e.g. the
    Anova app), where no such plan exists.

    Confirming the `stages` list behavior itself (for `current_stage`'s own
    correctness) requires capturing raw `EVENT_APO_STATE` payloads across a
    real multi-stage cook and checking whether `stages` shrinks, stays
    constant, or something else as stages progress, and whether
    `model_extra` on this model or on `CookStageInfo` carries an explicit
    stage index/count field.
    """
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    cook_id: Optional[str] = Field(None, alias="cookId")
    origin_source: Optional[str] = Field(None, alias="originSource")
    type: Optional[str] = None
    stages: Optional[List[CookStageInfo]] = None
    rack_position: Optional[int] = Field(None, alias="rackPosition")


class ApoStateData(BaseModel):
    """
    Nested state data for V1 ovens.

    V1 ovens nest the actual state data under a 'state' key in the payload.
    Active cook session fields (cookId, originSource, stages, rackPosition)
    are reported as top-level siblings of 'nodes'/'systemInfo' here, not
    nested under a 'cook' object.
    """
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    cooker_id: Optional[str] = Field(None, alias="cookerId")
    version: Optional[int] = None
    updated_timestamp: Optional[str] = Field(None, alias="updatedTimestamp")
    system_info: Optional[SystemInfo] = Field(None, alias="systemInfo")
    state: Optional[OvenState] = None
    nodes: Optional[Nodes] = None

    # Active cook session fields (present while a cook is running)
    cook_id: Optional[str] = Field(None, alias="cookId")
    origin_source: Optional[str] = Field(None, alias="originSource")
    type: Optional[str] = None
    stages: Optional[List[CookStageInfo]] = None
    rack_position: Optional[int] = Field(None, alias="rackPosition")



class ApoStateResponsePayload(BaseModel):
    """Payload for APO state event."""
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    cooker_id: Optional[str] = Field(None, alias="cookerId")
    type: Optional[str] = None
    version: Optional[int] = None
    updated_timestamp: Optional[str] = Field(None, alias="updatedTimestamp")
    system_info: Optional[SystemInfo] = Field(None, alias="systemInfo")

    # State can be OvenState (V2/Flat) or ApoStateData (V1/Nested)
    state: Optional[Union[ApoStateData, OvenState]] = None

    nodes: Optional[Nodes] = None

    # Active cook session fields (V2/flat ovens report these at the payload level)
    cook_id: Optional[str] = Field(None, alias="cookId")
    origin_source: Optional[str] = Field(None, alias="originSource")
    stages: Optional[List[CookStageInfo]] = None
    rack_position: Optional[int] = Field(None, alias="rackPosition")


class ApoStateResponse(BaseResponse):
    """Response for APO state event."""
    command: str = Field(default="EVENT_APO_STATE", description="Command type")
    payload: ApoStateResponsePayload = Field(..., description="State payload")

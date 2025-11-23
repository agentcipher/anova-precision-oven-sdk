# ============================================================================
# Response Models - Pydantic Models for Inbound API Responses
# ============================================================================

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
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

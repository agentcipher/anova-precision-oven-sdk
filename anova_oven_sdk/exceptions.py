# ============================================================================
# Exceptions
# ============================================================================

from typing import Dict, Any

class AnovaError(Exception):
    """Base exception for all Anova SDK errors."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | {self.details}"
        return self.message


class ConfigurationError(AnovaError):
    """Configuration error."""
    pass


class ConnectionError(AnovaError):
    """WebSocket connection error."""
    pass


class AuthenticationError(AnovaError):
    """Authentication failure."""
    pass


class CommandError(AnovaError):
    """Command execution error."""
    pass


class ValidationError(AnovaError):
    """Input validation error."""
    pass


class DeviceNotFoundError(AnovaError):
    """Device not found."""
    pass


class TimeoutError(AnovaError):
    """Operation timeout."""
    pass
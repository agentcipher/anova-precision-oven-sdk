from anova_oven_sdk.exceptions import (
    AnovaError, ConfigurationError, ConnectionError, AuthenticationError,
    CommandError, ValidationError, DeviceNotFoundError, TimeoutError
)


class TestAnovaError:
    """Test base AnovaError exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = AnovaError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_error_with_details(self):
        """Test error with details."""
        details = {"code": 500, "reason": "Internal error"}
        error = AnovaError("Test error", details)
        assert error.message == "Test error"
        assert error.details == details
        assert "Test error" in str(error)
        assert "500" in str(error)

    def test_error_string_representation(self):
        """Test error string representation with details."""
        details = {"device_id": "abc123"}
        error = AnovaError("Device error", details)
        error_str = str(error)
        assert "Device error" in error_str
        assert "abc123" in error_str


class TestConfigurationError:
    """Test ConfigurationError."""

    def test_configuration_error(self):
        """Test configuration error."""
        error = ConfigurationError("Invalid config")
        assert isinstance(error, AnovaError)
        assert str(error) == "Invalid config"

    def test_configuration_error_with_details(self):
        """Test configuration error with details."""
        details = {"field": "token", "reason": "missing"}
        error = ConfigurationError("Config missing", details)
        assert error.details["field"] == "token"


class TestConnectionError:
    """Test ConnectionError."""

    def test_connection_error(self):
        """Test connection error."""
        error = ConnectionError("Connection failed")
        assert isinstance(error, AnovaError)
        assert str(error) == "Connection failed"

    def test_connection_error_with_details(self):
        """Test connection error with details."""
        details = {"host": "ws://example.com", "timeout": 30}
        error = ConnectionError("Timeout", details)
        assert error.details["timeout"] == 30


class TestAuthenticationError:
    """Test AuthenticationError."""

    def test_authentication_error(self):
        """Test authentication error."""
        error = AuthenticationError("Invalid token")
        assert isinstance(error, AnovaError)
        assert str(error) == "Invalid token"

    def test_authentication_error_with_details(self):
        """Test authentication error with details."""
        details = {"token": "invalid-token"}
        error = AuthenticationError("Auth failed", details)
        assert "invalid-token" in error.details["token"]


class TestCommandError:
    """Test CommandError."""

    def test_command_error(self):
        """Test command error."""
        error = CommandError("Command failed")
        assert isinstance(error, AnovaError)
        assert str(error) == "Command failed"

    def test_command_error_with_details(self):
        """Test command error with details."""
        details = {"command": "CMD_APO_START", "reason": "invalid payload"}
        error = CommandError("Execution failed", details)
        assert error.details["command"] == "CMD_APO_START"


class TestValidationError:
    """Test ValidationError."""

    def test_validation_error(self):
        """Test validation error."""
        error = ValidationError("Invalid input")
        assert isinstance(error, AnovaError)
        assert str(error) == "Invalid input"

    def test_validation_error_with_details(self):
        """Test validation error with details."""
        details = {"field": "temperature", "value": -300, "reason": "below absolute zero"}
        error = ValidationError("Temperature invalid", details)
        assert error.details["field"] == "temperature"


class TestDeviceNotFoundError:
    """Test DeviceNotFoundError."""

    def test_device_not_found_error(self):
        """Test device not found error."""
        error = DeviceNotFoundError("Device not found")
        assert isinstance(error, AnovaError)
        assert str(error) == "Device not found"

    def test_device_not_found_error_with_details(self):
        """Test device not found error with details."""
        details = {"device_id": "unknown-123", "available": ["device-1", "device-2"]}
        error = DeviceNotFoundError("Device missing", details)
        assert error.details["device_id"] == "unknown-123"
        assert len(error.details["available"]) == 2


class TestTimeoutError:
    """Test TimeoutError."""

    def test_timeout_error(self):
        """Test timeout error."""
        error = TimeoutError("Operation timeout")
        assert isinstance(error, AnovaError)
        assert str(error) == "Operation timeout"

    def test_timeout_error_with_details(self):
        """Test timeout error with details."""
        details = {"timeout": 30, "operation": "connect"}
        error = TimeoutError("Timeout exceeded", details)
        assert error.details["timeout"] == 30


class TestErrorInheritance:
    """Test error inheritance and hierarchy."""

    def test_all_inherit_from_anova_error(self):
        """Test all errors inherit from AnovaError."""
        assert issubclass(ConfigurationError, AnovaError)
        assert issubclass(ConnectionError, AnovaError)
        assert issubclass(AuthenticationError, AnovaError)
        assert issubclass(CommandError, AnovaError)
        assert issubclass(ValidationError, AnovaError)
        assert issubclass(DeviceNotFoundError, AnovaError)
        assert issubclass(TimeoutError, AnovaError)

    def test_all_inherit_from_exception(self):
        """Test all errors inherit from Exception."""
        assert issubclass(AnovaError, Exception)
        assert issubclass(ConfigurationError, Exception)
        assert issubclass(ConnectionError, Exception)

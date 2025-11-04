import pytest
from unittest.mock import Mock, AsyncMock, patch

from anova_oven_sdk.oven import AnovaOven
from anova_oven_sdk.models import (
    Device, OvenVersion, Temperature, CookStage,
    TemperatureMode
)
from anova_oven_sdk.exceptions import ConfigurationError, DeviceNotFoundError


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch('anova_oven_sdk.oven.settings') as mock:
        mock.current_env = "test"
        mock.token = "anova-test-token"
        mock.get.return_value = None
        mock.validators = Mock()
        mock.validators.validate_all = Mock()
        yield mock


@pytest.fixture
def mock_client():
    """Mock WebSocketClient."""
    with patch('anova_oven_sdk.oven.WebSocketClient') as mock:
        client_instance = AsyncMock()
        client_instance.is_connected = False
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_logger():
    """Mock logger."""
    with patch('anova_oven_sdk.oven.setup_logging') as mock:
        logger_instance = Mock()
        mock.return_value = logger_instance
        yield logger_instance


class TestAnovaOvenInit:
    """Test AnovaOven initialization."""

    def test_init_default(self, mock_settings, mock_client, mock_logger):
        """Test default initialization."""
        oven = AnovaOven()
        
        assert oven.client is not None
        assert oven.command_builder is not None
        assert oven._devices == {}

    def test_init_with_environment(self, mock_settings, mock_client, mock_logger):
        """Test initialization with custom environment."""
        oven = AnovaOven(environment="staging")
        
        mock_settings.setenv.assert_called_once_with("staging")

    def test_init_configuration_error(self, mock_settings, mock_client, mock_logger):
        """Test initialization with configuration error."""
        mock_settings.validators.validate_all.side_effect = Exception("Config error")
        
        with pytest.raises(ConfigurationError):
            AnovaOven()

    def test_init_adds_callback(self, mock_settings, mock_client, mock_logger):
        """Test initialization adds device list callback."""
        oven = AnovaOven()
        
        mock_client.add_callback.assert_called_once()


class TestAnovaOvenConnection:
    """Test AnovaOven connection methods."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_settings, mock_client, mock_logger):
        """Test connecting to server."""
        oven = AnovaOven()
        
        await oven.connect()
        
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_settings, mock_client, mock_logger):
        """Test disconnecting from server."""
        oven = AnovaOven()
        
        await oven.disconnect()
        
        mock_client.disconnect.assert_called_once()


class TestAnovaOvenDeviceDiscovery:
    """Test device discovery."""

    @pytest.mark.asyncio
    async def test_discover_devices_when_connected(self, mock_settings, mock_client, mock_logger):
        """Test discovering devices when already connected."""
        mock_client.is_connected = True
        oven = AnovaOven()
        
        # Add a device
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        devices = await oven.discover_devices(timeout=0.1)
        
        assert len(devices) == 1
        assert devices[0].id == "test-123"

    @pytest.mark.asyncio
    async def test_discover_devices_when_not_connected(self, mock_settings, mock_client, mock_logger):
        """Test discovering devices connects first."""
        mock_client.is_connected = False
        oven = AnovaOven()
        
        devices = await oven.discover_devices(timeout=0.1)
        
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_devices_no_devices(self, mock_settings, mock_client, mock_logger):
        """Test discovering when no devices found."""
        mock_client.is_connected = True
        oven = AnovaOven()
        
        devices = await oven.discover_devices(timeout=0.1)
        
        assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_discover_devices_multiple(self, mock_settings, mock_client, mock_logger):
        """Test discovering multiple devices."""
        mock_client.is_connected = True
        oven = AnovaOven()
        
        device1 = Device(
            cookerId="test-1",
            name="Oven 1",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V1
        )
        device2 = Device(
            cookerId="test-2",
            name="Oven 2",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-1"] = device1
        oven._devices["test-2"] = device2
        
        devices = await oven.discover_devices(timeout=0.1)
        
        assert len(devices) == 2


class TestAnovaOvenHandleDeviceList:
    """Test device list handling."""

    def test_handle_device_list_valid(self, mock_settings, mock_client, mock_logger):
        """Test handling valid device list."""
        oven = AnovaOven()
        
        data = {
            "command": "EVENT_APO_WIFI_LIST",
            "payload": [{
                "cookerId": "test-123",
                "name": "My Oven",
                "pairedAt": "2024-01-01T00:00:00Z",
                "type": "oven_v2"
            }]
        }
        
        oven._handle_device_list(data)
        
        assert "test-123" in oven._devices
        assert oven._devices["test-123"].name == "My Oven"

    def test_handle_device_list_wrong_command(self, mock_settings, mock_client, mock_logger):
        """Test handling wrong command type."""
        oven = AnovaOven()
        
        data = {"command": "OTHER_COMMAND", "payload": []}
        
        oven._handle_device_list(data)
        
        assert len(oven._devices) == 0

    def test_handle_device_list_validation_error(self, mock_settings, mock_client, mock_logger):
        """Test handling device with validation error."""
        oven = AnovaOven()
        
        data = {
            "command": "EVENT_APO_WIFI_LIST",
            "payload": [{
                "cookerId": "test-123",
                # Missing required fields
            }]
        }
        
        oven._handle_device_list(data)
        
        assert len(oven._devices) == 0

    def test_handle_device_list_multiple_devices(self, mock_settings, mock_client, mock_logger):
        """Test handling multiple devices."""
        oven = AnovaOven()
        
        data = {
            "command": "EVENT_APO_WIFI_LIST",
            "payload": [
                {
                    "cookerId": "test-1",
                    "name": "Oven 1",
                    "pairedAt": "2024-01-01T00:00:00Z",
                    "type": "oven_v1"
                },
                {
                    "cookerId": "test-2",
                    "name": "Oven 2",
                    "pairedAt": "2024-01-01T00:00:00Z",
                    "type": "oven_v2"
                }
            ]
        }
        
        oven._handle_device_list(data)
        
        assert len(oven._devices) == 2


class TestAnovaOvenGetDevice:
    """Test get_device method."""

    def test_get_device_exists(self, mock_settings, mock_client, mock_logger):
        """Test getting existing device."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        result = oven.get_device("test-123")
        
        assert result == device

    def test_get_device_not_found(self, mock_settings, mock_client, mock_logger):
        """Test getting non-existent device."""
        oven = AnovaOven()
        
        with pytest.raises(DeviceNotFoundError):
            oven.get_device("non-existent")

    def test_get_device_not_found_details(self, mock_settings, mock_client, mock_logger):
        """Test device not found error includes details."""
        oven = AnovaOven()
        oven._devices["device-1"] = Mock()
        oven._devices["device-2"] = Mock()
        
        try:
            oven.get_device("non-existent")
        except DeviceNotFoundError as e:
            assert "non-existent" in e.details["device_id"]
            assert len(e.details["available"]) == 2


class TestAnovaOvenStartCook:
    """Test start_cook method."""

    @pytest.mark.asyncio
    async def test_start_cook_simple_celsius(self, mock_settings, mock_client, mock_logger):
        """Test simple cook with Celsius."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=200, duration=1800)
            
            mock_client.send_command.assert_called_once()
            assert mock_build.called

    @pytest.mark.asyncio
    async def test_start_cook_simple_fahrenheit(self, mock_settings, mock_client, mock_logger):
        """Test simple cook with Fahrenheit."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=350, temperature_unit="F", duration=1800)
            
            mock_client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_with_temperature_object(self, mock_settings, mock_client, mock_logger):
        """Test cook with Temperature object."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        temp = Temperature(celsius=200)
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=temp, duration=1800)
            
            mock_client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_no_temperature_no_stages(self, mock_settings, mock_client, mock_logger):
        """Test cook without temperature or stages raises error."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        with pytest.raises(ValueError):
            await oven.start_cook("test-123")

    @pytest.mark.asyncio
    async def test_start_cook_with_stages(self, mock_settings, mock_client, mock_logger):
        """Test cook with custom stages."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        stage = CookStage(temperature=Temperature(celsius=200))
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", stages=[stage])
            
            mock_client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_device_not_found(self, mock_settings, mock_client, mock_logger):
        """Test cook with non-existent device."""
        oven = AnovaOven()
        
        with pytest.raises(DeviceNotFoundError):
            await oven.start_cook("non-existent", temperature=200)

    @pytest.mark.asyncio
    async def test_start_cook_with_custom_parameters(self, mock_settings, mock_client, mock_logger):
        """Test cook with custom parameters."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook(
                "test-123",
                temperature=30,
                duration=1800,
                fan_speed=75,
                mode=TemperatureMode.WET,
                vent_open=True,
                rack_position=4
            )
            
            mock_client.send_command.assert_called_once()

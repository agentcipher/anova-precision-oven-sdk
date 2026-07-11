import pytest
from unittest.mock import Mock, AsyncMock, patch

from anova_oven_sdk.oven import AnovaOven
from anova_oven_sdk.models import (
    Device, DeviceState, OvenVersion, Temperature, CookStage,
    TemperatureMode
)
from anova_oven_sdk.exceptions import ConfigurationError, DeviceNotFoundError

# Minimal valid `nodes` payload satisfying Nodes' required sub-fields, reused
# by tests that need a validating nodes-only EVENT_APO_STATE update.
NODES_FIXTURE = {
    "temperatureBulbs": {
        "mode": "dry",
        "wet": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
        "dry": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
        "dryTop": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
        "dryBottom": {"current": {"celsius": 20.0, "fahrenheit": 68.0}}
    },
    "timer": {"mode": "idle", "initial": 0, "current": 0},
    "temperatureProbe": {"connected": False},
    "steamGenerators": {
        "mode": "idle",
        "relativeHumidity": {"current": 0},
        "evaporator": {},
        "boiler": {}
    },
    "heatingElements": {
        "top": {"on": False, "failed": False, "watts": 0},
        "bottom": {"on": False, "failed": False, "watts": 0},
        "rear": {"on": False, "failed": False, "watts": 0}
    },
    "fan": {"speed": 0, "failed": False},
    "vent": {"open": False},
    "waterTank": {"empty": False},
    "door": {"closed": True},
    "lamp": {"on": False, "failed": False, "preference": "on"},
    "userInterfaceCircuit": {"communicationFailed": False}
}


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
    logger_instance = Mock()
    with patch('anova_oven_sdk.oven.logger', logger_instance):
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


class TestAnovaOvenHandleMessage:
    """Test message handling."""

    def test_handle_message_device_list_valid(self, mock_settings, mock_client, mock_logger):
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
        
        oven._handle_message(data)
        
        assert "test-123" in oven._devices
        assert oven._devices["test-123"].name == "My Oven"

    def test_handle_message_wrong_command(self, mock_settings, mock_client, mock_logger):
        """Test handling wrong command type."""
        oven = AnovaOven()
        
        data = {"command": "OTHER_COMMAND", "payload": []}
        
        oven._handle_message(data)
        
        assert len(oven._devices) == 0

    def test_handle_message_device_list_validation_error(self, mock_settings, mock_client, mock_logger):
        """Test handling device with validation error."""
        oven = AnovaOven()
        
        data = {
            "command": "EVENT_APO_WIFI_LIST",
            "payload": [{
                "cookerId": "test-123",
                # Missing required fields
            }]
        }
        
        oven._handle_message(data)
        
        assert len(oven._devices) == 0

    def test_handle_message_device_list_multiple_devices(self, mock_settings, mock_client, mock_logger):
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
        
        oven._handle_message(data)
        
        assert len(oven._devices) == 2

    def test_handle_message_device_list_invalid_response_structure(self, mock_settings, mock_client, mock_logger):
        """Test handling device list with invalid response structure."""
        oven = AnovaOven()
        
        # Invalid payload type (should be a list)
        data = {
            "command": "EVENT_APO_WIFI_LIST",
            "payload": "not-a-list"
        }
        
        oven._handle_message(data)
        
        # Verify that the error was logged
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args[0][0]
        assert "Invalid device list response" in call_args

    def test_handle_message_apo_state_valid(self, mock_settings, mock_client, mock_logger):
        """Test handling valid APO state event."""
        oven = AnovaOven()
        
        # Add a device
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        # Mock payload with cookerId and nodes
        payload = {
            "cookerId": "test-123",
            "version": 1,
            "updatedTimestamp": "2025-11-22T14:59:33Z",
            "systemInfo": {
                "online": True,
                "hardwareVersion": "120V1",
                "powerMains": 120,
                "powerHertz": 60,
                "firmwareVersion": "2.1.16",
                "uiHardwareVersion": "UI_ORIGINAL_2",
                "uiFirmwareVersion": "0.0.0",
                "triacsFailed": False
            },
            "state": {
                "mode": "idle",
                "temperatureUnit": "F",
                "processedCommandIds": []
            },
            "nodes": {
                "temperatureBulbs": {
                    "mode": "dry",
                    "wet": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dry": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dryTop": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dryBottom": {"current": {"celsius": 20.0, "fahrenheit": 68.0}}
                },
                "timer": {"mode": "idle", "initial": 0, "current": 0},
                "temperatureProbe": {"connected": False},
                "steamGenerators": {
                    "mode": "idle",
                    "relativeHumidity": {"current": 0},
                    "evaporator": {},
                    "boiler": {}
                },
                "heatingElements": {
                    "top": {"on": False, "failed": False, "watts": 0},
                    "bottom": {"on": False, "failed": False, "watts": 0},
                    "rear": {"on": False, "failed": False, "watts": 0}
                },
                "fan": {"speed": 0, "failed": False},
                "vent": {"open": False},
                "waterTank": {"empty": False},
                "door": {"closed": True},
                "lamp": {"on": False, "failed": False, "preference": "on"},
                "userInterfaceCircuit": {"communicationFailed": False}
            }
        }
        
        data = {
            "command": "EVENT_APO_STATE",
            "payload": payload
        }
        
        oven._handle_message(data)
        
        assert device.nodes is not None
        assert device.nodes.temperature_bulbs.mode == "dry"
        assert device.last_update is not None

    def test_handle_message_apo_state_missing_nodes(self, mock_settings, mock_client, mock_logger):
        """Test handling APO state event with missing nodes."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        # Payload with cookerId but no nodes
        payload = {
            "cookerId": "test-123",
            "state": {"cook": {}} # Extra field allowed
        }
        
        data = {
            "command": "EVENT_APO_STATE",
            "payload": payload
        }
        
        oven._handle_message(data)
        
        # Should not crash and should update timestamp
        assert device.last_update is not None
        # Nodes should remain None
        assert device.nodes is None

    def test_handle_message_nodes_only_update_preserves_active_cook(
        self, mock_settings, mock_client, mock_logger
    ):
        """A nodes-only EVENT_APO_STATE push (no cook data) must not clear
        an already-active cook session -- see Fix 1.1."""
        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        # First update: cook starts (flat/V2 fallback cook fields at the
        # top level of payload, alongside state.mode="cooking").
        start_payload = {
            "cookerId": "test-123",
            "state": {"mode": "cooking", "temperatureUnit": "F"},
            "cookId": "cook-abc-123",
            "stages": [{"id": "stage-1", "title": "Sear"}],
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": start_payload})

        assert device.state == DeviceState.COOKING
        assert device.cook is not None
        assert device.cook.cook_id == "cook-abc-123"

        # Second update: pure telemetry, no `state` and no cook fields at
        # all -- this is the "nodes-only" push that used to wipe device.cook.
        telemetry_payload = {
            "cookerId": "test-123",
            "nodes": NODES_FIXTURE,
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": telemetry_payload})

        # Cook session and cooking state must survive the telemetry-only update.
        assert device.cook is not None
        assert device.cook.cook_id == "cook-abc-123"
        assert device.state == DeviceState.COOKING
        # But the telemetry itself was still applied.
        assert device.nodes is not None

    def test_handle_message_nodes_only_update_preserves_paused_cook(
        self, mock_settings, mock_client, mock_logger
    ):
        """A nodes-only update while paused must also preserve the cook session."""
        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        start_payload = {
            "cookerId": "test-123",
            "state": {"mode": "paused", "temperatureUnit": "F"},
            "cookId": "cook-abc-123",
            "stages": [{"id": "stage-1", "title": "Sear"}],
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": start_payload})

        assert device.state == DeviceState.PAUSED
        assert device.cook is not None

        telemetry_payload = {
            "cookerId": "test-123",
            "nodes": NODES_FIXTURE,
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": telemetry_payload})

        assert device.cook is not None
        assert device.state == DeviceState.PAUSED
        assert device.nodes is not None

    def test_handle_message_cook_cleared_once_idle(self, mock_settings, mock_client, mock_logger):
        """Once the oven genuinely reports a non-cooking mode with no cook
        data, the stale cook session should be cleared."""
        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        start_payload = {
            "cookerId": "test-123",
            "state": {"mode": "cooking", "temperatureUnit": "F"},
            "cookId": "cook-abc-123",
            "stages": [{"id": "stage-1", "title": "Sear"}],
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": start_payload})
        assert device.cook is not None

        idle_payload = {
            "cookerId": "test-123",
            "state": {"mode": "idle", "temperatureUnit": "F"},
        }
        oven._handle_message({"command": "EVENT_APO_STATE", "payload": idle_payload})

        assert device.state == DeviceState.IDLE
        assert device.cook is None

    def test_handle_message_apo_state_fallback_single_device(self, mock_settings, mock_client, mock_logger):
        """Test handling APO state event with fallback to single device."""
        oven = AnovaOven()
        
        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device
        
        # Payload without cookerId
        payload = {
            "version": 1,
            "updatedTimestamp": "2025-11-22T14:59:33Z",
            "systemInfo": {
                "online": True,
                "hardwareVersion": "120V1",
                "powerMains": 120,
                "powerHertz": 60,
                "firmwareVersion": "2.1.16",
                "uiHardwareVersion": "UI_ORIGINAL_2",
                "uiFirmwareVersion": "0.0.0",
                "triacsFailed": False
            },
            "state": {"mode": "idle", "temperatureUnit": "F"},
            "nodes": {
                "temperatureBulbs": {
                    "mode": "dry",
                    "wet": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dry": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dryTop": {"current": {"celsius": 20.0, "fahrenheit": 68.0}},
                    "dryBottom": {"current": {"celsius": 20.0, "fahrenheit": 68.0}}
                },
                "timer": {"mode": "idle", "initial": 0, "current": 0},
                "temperatureProbe": {"connected": False},
                "steamGenerators": {
                    "mode": "idle",
                    "relativeHumidity": {"current": 0},
                    "evaporator": {},
                    "boiler": {}
                },
                "heatingElements": {
                    "top": {"on": False, "failed": False, "watts": 0},
                    "bottom": {"on": False, "failed": False, "watts": 0},
                    "rear": {"on": False, "failed": False, "watts": 0}
                },
                "fan": {"speed": 0, "failed": False},
                "vent": {"open": False},
                "waterTank": {"empty": False},
                "door": {"closed": True},
                "lamp": {"on": False, "failed": False, "preference": "on"},
                "userInterfaceCircuit": {"communicationFailed": False}
            }
        }
        
        data = {
            "command": "EVENT_APO_STATE",
            "payload": payload
        }
        
        oven._handle_message(data)
        
        # Should update the single device
        assert device.nodes is not None
        assert device.last_update is not None

    def test_handle_message_apo_state_unknown_device(self, mock_settings, mock_client, mock_logger):
        """Test handling APO state event for unknown device."""
        oven = AnovaOven()
        
        # Add two devices so fallback doesn't apply
        device1 = Device(cookerId="d1", name="Oven 1", pairedAt="2024-01-01", type=OvenVersion.V2)
        device2 = Device(cookerId="d2", name="Oven 2", pairedAt="2024-01-01", type=OvenVersion.V2)
        oven._devices["d1"] = device1
        oven._devices["d2"] = device2
        
        # Payload with unknown ID
        payload = {
            "cookerId": "unknown-id",
            "version": 1,
            "updatedTimestamp": "2025-11-22T14:59:33Z",
            "systemInfo": {"online": True, "hardwareVersion": "v1", "powerMains": 120, "powerHertz": 60, "firmwareVersion": "1", "uiHardwareVersion": "1", "uiFirmwareVersion": "1", "triacsFailed": False},
            "state": {"mode": "idle", "temperatureUnit": "F"}
        }
        
        data = {
            "command": "EVENT_APO_STATE",
            "payload": payload
        }
        
        oven._handle_message(data)
        
        # Verify warning logged
        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args[0][0]
        assert "unknown device" in call_args
        
        # Devices should not be updated (checking one property)
        assert device1.nodes is None
        assert device2.nodes is None

    def test_handle_message_apo_state_invalid(self, mock_settings, mock_client, mock_logger):
        """Test handling invalid APO state event."""
        oven = AnovaOven()
        
        # Completely invalid payload (not a dict)
        data = {
            "command": "EVENT_APO_STATE",
            "payload": "invalid"
        }
        
        oven._handle_message(data)
        
        # Verify that the error was logged
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args[0][0]
        assert "Invalid state response" in call_args


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
    async def test_start_cook_registers_stage_plan(self, mock_settings, mock_client, mock_logger):
        """
        start_cook() records the cookId -> ordered stage id mapping from the
        built CMD_APO_START payload, so total_stage_count/current_stage_index
        can later resolve "stage X of Y" from EVENT_APO_STATE updates.
        """
        from anova_oven_sdk.response_models import CookSessionState

        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {
                "payload": {
                    "cookId": "cook-1",
                    "stages": [
                        {"id": "stage-1", "title": "Sear"},
                        {"id": "stage-2", "title": "Roast"},
                        {"id": "stage-3", "title": "Rest"},
                    ],
                }
            }

            await oven.start_cook("test-123", temperature=200, duration=1800)

        # Simulate the live state reporting stage 2 of the cook as current.
        device.cook = CookSessionState.model_validate({
            "cookId": "cook-1",
            "stages": [
                {"id": "stage-2", "title": "Roast"},
                {"id": "stage-3", "title": "Rest"},
            ],
        })
        assert device.total_stage_count == 3
        assert device.current_stage_index == 2

    @pytest.mark.asyncio
    async def test_start_cook_returns_cook_id(self, mock_settings, mock_client, mock_logger):
        """start_cook() should return the generated cook_id so callers can
        track which cook session a recipe start corresponds to."""
        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {
                "payload": {
                    "cookId": "cook-xyz-789",
                    "stages": [{"id": "stage-1", "title": "Sear"}],
                }
            }

            result = await oven.start_cook("test-123", temperature=200, duration=1800)

        assert result == "cook-xyz-789"

    @pytest.mark.asyncio
    async def test_start_cook_returns_none_when_no_cook_id(self, mock_settings, mock_client, mock_logger):
        """start_cook() should return None if the built payload has no cookId."""
        oven = AnovaOven()

        device = Device(
            cookerId="test-123",
            name="Test Oven",
            pairedAt="2024-01-01T00:00:00Z",
            type=OvenVersion.V2
        )
        oven._devices["test-123"] = device

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"payload": {}}

            result = await oven.start_cook("test-123", temperature=200, duration=1800)

        assert result is None

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

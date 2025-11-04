import pytest
from unittest.mock import Mock, AsyncMock, patch

from anova_oven_sdk.oven import AnovaOven
from anova_oven_sdk.models import (
    Device, OvenVersion, Temperature, CookStage,
    HeatingElements, SteamSettings, SteamMode, Probe
)


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
def setup_oven(mock_settings):
    """Setup oven with device."""
    with patch('anova_oven_sdk.oven.WebSocketClient'):
        with patch('anova_oven_sdk.oven.setup_logging'):
            oven = AnovaOven()
            oven.client = AsyncMock()
            
            device = Device(
                cookerId="test-123",
                name="Test Oven",
                pairedAt="2024-01-01T00:00:00Z",
                type=OvenVersion.V2
            )
            oven._devices["test-123"] = device
            
            yield oven


class TestAnovaOvenStartCookAdvanced:
    """Test advanced start_cook scenarios."""

    @pytest.mark.asyncio
    async def test_start_cook_with_heating_elements(self, setup_oven):
        """Test cook with custom heating elements."""
        oven = setup_oven
        heating = HeatingElements(top=True, bottom=True, rear=False)
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=200, heating_elements=heating)
            
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_with_steam(self, setup_oven):
        """Test cook with steam settings."""
        oven = setup_oven
        steam = SteamSettings(mode=SteamMode.RELATIVE_HUMIDITY, relative_humidity=80)
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=100, steam=steam)
            
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_with_probe(self, setup_oven):
        """Test cook with probe."""
        oven = setup_oven
        probe = Probe(setpoint=Temperature(celsius=65))
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook("test-123", temperature=180, probe=probe)
            
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_with_timer_start_type(self, setup_oven):
        """Test cook with timer start type."""
        oven = setup_oven
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook(
                "test-123",
                temperature=180,
                duration=1800,
                timer_start_type="when-preheated"
            )
            
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_with_title_description(self, setup_oven):
        """Test cook with title and description."""
        oven = setup_oven
        
        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}
            
            await oven.start_cook(
                "test-123",
                temperature=180,
                title="My Cook",
                description="Test description"
            )
            
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cook_stage_validation_error(self, setup_oven):
        """Test cook with invalid stage raises error."""
        oven = setup_oven
        
        # This should trigger validation error
        with pytest.raises(Exception):  # ValidationError
            await oven.start_cook("test-123", temperature=-300)

    @pytest.mark.asyncio
    async def test_start_cook_stage_construction_validation_error(self, setup_oven):
        """Test that ValueError during CookStage construction is caught and re-raised with context."""
        oven = setup_oven

        # Mock CookStage to raise ValueError during construction
        with patch('anova_oven_sdk.oven.CookStage') as mock_cook_stage:
            mock_cook_stage.side_effect = ValueError("Invalid fan_speed value")

            with pytest.raises(ValueError, match="Stage validation failed: Invalid fan_speed value"):
                await oven.start_cook("test-123", temperature=200, duration=1800)

    @pytest.mark.asyncio
    async def test_start_cook_validates_for_oven_version(self, setup_oven):
        """Test cook validates stages for oven version."""
        oven = setup_oven

        # Set device to V1
        oven._devices["test-123"].device_type = OvenVersion.V1

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            stage = CookStage(temperature=Temperature(celsius=200))
            with patch.object(CookStage, 'validate_for_oven') as mock_validate:
                await oven.start_cook("test-123", stages=[stage])

                mock_validate.assert_called_once_with(OvenVersion.V1)

    @pytest.mark.asyncio
    async def test_start_cook_logging_both_units(self, setup_oven):
        """Test cook logs both temperature units."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            with patch('anova_oven_sdk.oven.settings') as mock_settings:
                mock_settings.get.side_effect = lambda key, default=None: {
                    'display_both_units': True
                }.get(key, default)

                await oven.start_cook("test-123", temperature=200, duration=1800)

                # Just verify it completes without error

    @pytest.mark.asyncio
    async def test_start_cook_logging_celsius_only(self, setup_oven):
        """Test cook logs Celsius only."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            with patch('anova_oven_sdk.oven.settings') as mock_settings:
                mock_settings.get.side_effect = lambda key, default=None: {
                    'display_both_units': False,
                    'default_temperature_unit': 'C'
                }.get(key, default)

                await oven.start_cook("test-123", temperature=200, duration=1800)

    @pytest.mark.asyncio
    async def test_start_cook_logging_fahrenheit_only(self, setup_oven):
        """Test cook logs Fahrenheit only."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_start_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            with patch('anova_oven_sdk.oven.settings') as mock_settings:
                mock_settings.get.side_effect = lambda key, default=None: {
                    'display_both_units': False,
                    'default_temperature_unit': 'F'
                }.get(key, default)

                await oven.start_cook("test-123", temperature=200, duration=1800)


class TestAnovaOvenStopCook:
    """Test stop_cook method."""

    @pytest.mark.asyncio
    async def test_stop_cook(self, setup_oven):
        """Test stopping cook."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_stop_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.stop_cook("test-123")

            oven.client.send_command.assert_called_once_with("CMD_APO_STOP", {"test": "payload"})

    @pytest.mark.asyncio
    async def test_stop_cook_device_not_found(self, setup_oven):
        """Test stop cook with non-existent device."""
        oven = setup_oven

        with pytest.raises(Exception):  # DeviceNotFoundError
            await oven.stop_cook("non-existent")


class TestAnovaOvenSetProbe:
    """Test set_probe method."""

    @pytest.mark.asyncio
    async def test_set_probe_celsius(self, setup_oven):
        """Test setting probe with Celsius."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_probe_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_probe("test-123", target=65, temperature_unit="C")

            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_probe_fahrenheit(self, setup_oven):
        """Test setting probe with Fahrenheit."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_probe_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_probe("test-123", target=150, temperature_unit="F")

            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_probe_temperature_object(self, setup_oven):
        """Test setting probe with Temperature object."""
        oven = setup_oven
        temp = Temperature(celsius=65)

        with patch.object(oven.command_builder, 'build_probe_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_probe("test-123", target=temp)

            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_probe_invalid_temperature(self, setup_oven):
        """Test setting probe with invalid temperature."""
        oven = setup_oven

        with pytest.raises(Exception):  # ValidationError
            await oven.set_probe("test-123", target=150)  # Too high for Celsius

    @pytest.mark.asyncio
    async def test_set_probe_v1_oven(self, setup_oven):
        """Test setting probe on V1 oven."""
        oven = setup_oven
        oven._devices["test-123"].device_type = OvenVersion.V1

        with patch.object(oven.command_builder, 'build_probe_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_probe("test-123", target=65)

            # V1 should use temperature as-is
            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_probe_v2_oven(self, setup_oven):
        """Test setting probe on V2 oven."""
        oven = setup_oven
        oven._devices["test-123"].device_type = OvenVersion.V2

        with patch.object(oven.command_builder, 'build_probe_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_probe("test-123", target=65)

            oven.client.send_command.assert_called_once()


class TestAnovaOvenSetTemperatureUnit:
    """Test set_temperature_unit method."""

    @pytest.mark.asyncio
    async def test_set_temperature_unit_celsius(self, setup_oven):
        """Test setting temperature unit to Celsius."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_temperature_unit_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_temperature_unit("test-123", "C")

            oven.client.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_temperature_unit_fahrenheit(self, setup_oven):
        """Test setting temperature unit to Fahrenheit."""
        oven = setup_oven

        with patch.object(oven.command_builder, 'build_temperature_unit_command') as mock_build:
            mock_build.return_value = {"test": "payload"}

            await oven.set_temperature_unit("test-123", "F")

            oven.client.send_command.assert_called_once()


class TestAnovaOvenContextManager:
    """Test context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_enter(self, mock_settings, mock_client):
        """Test context manager __aenter__."""
        with patch('anova_oven_sdk.oven.setup_logging'):
            async with AnovaOven() as oven:
                pass

            oven.client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, mock_settings, mock_client):
        """Test context manager __aexit__."""
        with patch('anova_oven_sdk.oven.setup_logging'):
            async with AnovaOven() as oven:
                pass

            oven.client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, mock_settings, mock_client):
        """Test context manager handles exceptions."""
        with patch('anova_oven_sdk.oven.setup_logging'):
            try:
                async with AnovaOven() as oven:
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should still disconnect
            oven.client.disconnect.assert_called_once()
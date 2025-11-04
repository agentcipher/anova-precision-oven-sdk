import pytest
from unittest.mock import Mock, AsyncMock, patch

from anova_oven_sdk.presets import CookingPresets
from anova_oven_sdk.models import Temperature


@pytest.fixture
def mock_oven():
    """Mock AnovaOven."""
    oven = Mock()
    oven.start_cook = AsyncMock()
    oven.discover_devices = AsyncMock()
    return oven


class TestCookingPresets:
    """Test CookingPresets class."""

    @pytest.mark.asyncio
    async def test_roast_default(self, mock_oven):
        """Test roast preset with defaults."""
        await CookingPresets.roast(mock_oven, "device-123")
        
        mock_oven.start_cook.assert_called_once()
        call_args = mock_oven.start_cook.call_args
        
        assert call_args[1]["device_id"] == "device-123"
        assert call_args[1]["temperature"] == 200
        assert call_args[1]["temperature_unit"] == "C"
        assert call_args[1]["duration"] == 1800  # 30 * 60

    @pytest.mark.asyncio
    async def test_roast_custom_celsius(self, mock_oven):
        """Test roast with custom Celsius temperature."""
        await CookingPresets.roast(
            mock_oven,
            "device-123",
            temperature=180,
            duration_minutes=45,
            fan_speed=80
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 180
        assert call_args[1]["duration"] == 2700  # 45 * 60
        assert call_args[1]["fan_speed"] == 80

    @pytest.mark.asyncio
    async def test_roast_fahrenheit(self, mock_oven):
        """Test roast with Fahrenheit."""
        await CookingPresets.roast(
            mock_oven,
            "device-123",
            temperature=392,
            temperature_unit="F"
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 392
        assert call_args[1]["temperature_unit"] == "F"

    @pytest.mark.asyncio
    async def test_steam_default(self, mock_oven):
        """Test steam preset with defaults."""
        await CookingPresets.steam(mock_oven, "device-123")
        
        mock_oven.start_cook.assert_called_once()
        call_args = mock_oven.start_cook.call_args
        
        assert call_args[1]["temperature"] == 100
        assert call_args[1]["duration"] == 1200  # 20 * 60
        assert "steam" in call_args[1]

    @pytest.mark.asyncio
    async def test_steam_custom(self, mock_oven):
        """Test steam with custom settings."""
        await CookingPresets.steam(
            mock_oven,
            "device-123",
            temperature=90,
            duration_minutes=15,
            humidity=80
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 90
        assert call_args[1]["duration"] == 900  # 15 * 60

    @pytest.mark.asyncio
    async def test_steam_fahrenheit(self, mock_oven):
        """Test steam with Fahrenheit."""
        await CookingPresets.steam(
            mock_oven,
            "device-123",
            temperature=212,
            temperature_unit="F"
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 212
        assert call_args[1]["temperature_unit"] == "F"

    @pytest.mark.asyncio
    async def test_sous_vide_default(self, mock_oven):
        """Test sous vide preset with defaults."""
        await CookingPresets.sous_vide(mock_oven, "device-123")
        
        mock_oven.start_cook.assert_called_once()
        call_args = mock_oven.start_cook.call_args
        
        assert call_args[1]["temperature"] == 60
        assert call_args[1]["duration"] == 3600  # 60 * 60
        assert "steam" in call_args[1]

    @pytest.mark.asyncio
    async def test_sous_vide_custom(self, mock_oven):
        """Test sous vide with custom settings."""
        await CookingPresets.sous_vide(
            mock_oven,
            "device-123",
            temperature=55,
            duration_minutes=120
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 55
        assert call_args[1]["duration"] == 7200  # 120 * 60

    @pytest.mark.asyncio
    async def test_sous_vide_fahrenheit(self, mock_oven):
        """Test sous vide with Fahrenheit."""
        await CookingPresets.sous_vide(
            mock_oven,
            "device-123",
            temperature=140,
            temperature_unit="F"
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 140
        assert call_args[1]["temperature_unit"] == "F"

    @pytest.mark.asyncio
    async def test_bake_default(self, mock_oven):
        """Test bake preset with defaults."""
        await CookingPresets.bake(mock_oven, "device-123")
        
        mock_oven.start_cook.assert_called_once()
        call_args = mock_oven.start_cook.call_args
        
        assert call_args[1]["temperature"] == 180
        assert call_args[1]["duration"] == 2700  # 45 * 60
        assert call_args[1]["fan_speed"] == 50
        assert "heating_elements" in call_args[1]

    @pytest.mark.asyncio
    async def test_bake_custom(self, mock_oven):
        """Test bake with custom settings."""
        await CookingPresets.bake(
            mock_oven,
            "device-123",
            temperature=175,
            duration_minutes=30,
            fan_speed=60
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 175
        assert call_args[1]["duration"] == 1800  # 30 * 60
        assert call_args[1]["fan_speed"] == 60

    @pytest.mark.asyncio
    async def test_bake_fahrenheit(self, mock_oven):
        """Test bake with Fahrenheit."""
        await CookingPresets.bake(
            mock_oven,
            "device-123",
            temperature=350,
            temperature_unit="F"
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 350
        assert call_args[1]["temperature_unit"] == "F"

    @pytest.mark.asyncio
    async def test_dehydrate_default(self, mock_oven):
        """Test dehydrate preset with defaults."""
        await CookingPresets.dehydrate(mock_oven, "device-123")
        
        mock_oven.start_cook.assert_called_once()
        call_args = mock_oven.start_cook.call_args
        
        assert call_args[1]["temperature"] == 60
        assert call_args[1]["duration"] == 28800  # 8 * 3600
        assert call_args[1]["fan_speed"] == 100
        assert call_args[1]["vent_open"] is True
        assert "heating_elements" in call_args[1]

    @pytest.mark.asyncio
    async def test_dehydrate_custom(self, mock_oven):
        """Test dehydrate with custom settings."""
        await CookingPresets.dehydrate(
            mock_oven,
            "device-123",
            temperature=65,
            duration_hours=12
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 65
        assert call_args[1]["duration"] == 43200  # 12 * 3600

    @pytest.mark.asyncio
    async def test_dehydrate_fahrenheit(self, mock_oven):
        """Test dehydrate with Fahrenheit."""
        await CookingPresets.dehydrate(
            mock_oven,
            "device-123",
            temperature=140,
            temperature_unit="F"
        )
        
        call_args = mock_oven.start_cook.call_args
        assert call_args[1]["temperature"] == 140
        assert call_args[1]["temperature_unit"] == "F"

    @pytest.mark.asyncio
    async def test_toast_v1_oven(self):
        """Test toast V1 recipe."""
        # This test is for the toast_v1_oven method which creates a full context
        # We'll test that it can be called without errors
        
        with patch('anova_oven_sdk.presets.AnovaOven') as MockOven:
            mock_oven_instance = AsyncMock()
            mock_device = Mock()
            mock_device.id = "device-123"
            mock_oven_instance.discover_devices.return_value = [mock_device]
            mock_oven_instance.start_cook = AsyncMock()
            
            MockOven.return_value.__aenter__.return_value = mock_oven_instance
            MockOven.return_value.__aexit__.return_value = AsyncMock()
            
            await CookingPresets.toast_v1_oven()
            
            # Verify the stages were created and start_cook was called
            mock_oven_instance.start_cook.assert_called_once()
            call_args = mock_oven_instance.start_cook.call_args
            
            # Should have stages parameter
            assert "stages" in call_args[1]
            stages = call_args[1]["stages"]
            
            # Toast recipe has 3 stages
            assert len(stages) == 3

    @pytest.mark.asyncio
    async def test_roast_with_temperature_object(self, mock_oven):
        """Test roast with Temperature object."""
        temp = Temperature(celsius=200)
        
        await CookingPresets.roast(mock_oven, "device-123", temperature=temp)
        
        call_args = mock_oven.start_cook.call_args
        # Temperature object should be passed through
        assert isinstance(call_args[1]["temperature"], Temperature) or call_args[1]["temperature"] == temp

    @pytest.mark.asyncio
    async def test_steam_with_temperature_object(self, mock_oven):
        """Test steam with Temperature object."""
        temp = Temperature(fahrenheit=212)
        
        await CookingPresets.steam(mock_oven, "device-123", temperature=temp)
        
        mock_oven.start_cook.assert_called_once()

    @pytest.mark.asyncio
    async def test_sous_vide_with_temperature_object(self, mock_oven):
        """Test sous vide with Temperature object."""
        temp = Temperature(celsius=60)
        
        await CookingPresets.sous_vide(mock_oven, "device-123", temperature=temp)
        
        mock_oven.start_cook.assert_called_once()

    @pytest.mark.asyncio
    async def test_bake_with_temperature_object(self, mock_oven):
        """Test bake with Temperature object."""
        temp = Temperature(celsius=180)
        
        await CookingPresets.bake(mock_oven, "device-123", temperature=temp)
        
        mock_oven.start_cook.assert_called_once()

    @pytest.mark.asyncio
    async def test_dehydrate_with_temperature_object(self, mock_oven):
        """Test dehydrate with Temperature object."""
        temp = Temperature(celsius=60)
        
        await CookingPresets.dehydrate(mock_oven, "device-123", temperature=temp)
        
        mock_oven.start_cook.assert_called_once()

    def test_cooking_presets_is_static(self):
        """Test that CookingPresets methods are static."""
        # Should be able to call without instantiation
        assert hasattr(CookingPresets, 'roast')
        assert hasattr(CookingPresets, 'steam')
        assert hasattr(CookingPresets, 'sous_vide')
        assert hasattr(CookingPresets, 'bake')
        assert hasattr(CookingPresets, 'dehydrate')
        assert hasattr(CookingPresets, 'toast_v1_oven')

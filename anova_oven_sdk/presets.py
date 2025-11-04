# ============================================================================
# Cooking Presets
# ============================================================================
from .models import CookStage, SteamSettings, SteamMode, Temperature, Timer, HeatingElements, TemperatureMode
from .oven import AnovaOven
from typing import Union


class CookingPresets:
    """Convenient cooking presets with flexible temperature input."""

    @staticmethod
    async def roast(
            oven: AnovaOven,
            device_id: str,
            temperature: Union[float, Temperature] = 200,
            temperature_unit: str = "C",
            duration_minutes: int = 30,
            fan_speed: int = 100
    ) -> None:
        """
        Roasting preset.

        Examples:
            # Celsius
            await CookingPresets.roast(oven, device_id, temperature=200)

            # Fahrenheit
            await CookingPresets.roast(
                oven, device_id,
                temperature=392,
                temperature_unit="F"
            )
        """
        await oven.start_cook(
            device_id=device_id,
            temperature=temperature,
            temperature_unit=temperature_unit,
            duration=duration_minutes * 60,
            fan_speed=fan_speed,
            mode=TemperatureMode.DRY
        )

    @staticmethod
    async def steam(
            oven: AnovaOven,
            device_id: str,
            temperature: Union[float, Temperature] = 100,
            temperature_unit: str = "C",
            duration_minutes: int = 20,
            humidity: int = 100
    ) -> None:
        """Steam cooking preset."""
        steam_settings = SteamSettings(
            mode=SteamMode.RELATIVE_HUMIDITY,
            relative_humidity=humidity
        )

        await oven.start_cook(
            device_id=device_id,
            temperature=temperature,
            temperature_unit=temperature_unit,
            duration=duration_minutes * 60,
            steam=steam_settings
        )

    @staticmethod
    async def sous_vide(
            oven: AnovaOven,
            device_id: str,
            temperature: Union[float, Temperature] = 60,
            temperature_unit: str = "C",
            duration_minutes: int = 60
    ) -> None:
        """Sous vide preset."""
        steam_settings = SteamSettings(
            mode=SteamMode.STEAM_PERCENTAGE,
            steam_percentage=100
        )

        await oven.start_cook(
            device_id=device_id,
            temperature=temperature,
            temperature_unit=temperature_unit,
            duration=duration_minutes * 60,
            steam=steam_settings,
            mode=TemperatureMode.WET
        )

    @staticmethod
    async def bake(
            oven: AnovaOven,
            device_id: str,
            temperature: Union[float, Temperature] = 180,
            temperature_unit: str = "C",
            duration_minutes: int = 45,
            fan_speed: int = 50
    ) -> None:
        """Baking preset."""
        heating = HeatingElements(top=True, bottom=True, rear=False)

        await oven.start_cook(
            device_id=device_id,
            temperature=temperature,
            temperature_unit=temperature_unit,
            duration=duration_minutes * 60,
            heating_elements=heating,
            fan_speed=fan_speed
        )

    @staticmethod
    async def dehydrate(
            oven: AnovaOven,
            device_id: str,
            temperature: Union[float, Temperature] = 60,
            temperature_unit: str = "C",
            duration_hours: int = 8
    ) -> None:
        """Dehydrating preset."""
        heating = HeatingElements(rear=True, top=False, bottom=False)

        await oven.start_cook(
            device_id=device_id,
            temperature=temperature,
            temperature_unit=temperature_unit,
            duration=duration_hours * 3600,
            heating_elements=heating,
            fan_speed=100,
            vent_open=True
        )

    @staticmethod
    async def toast_v1_oven():
        async with AnovaOven(environment="production") as oven:
            devices = await oven.discover_devices()
            device_id = devices[0].id

            # Multi-stage: Anova Oven v1 Toast Recipe
            stages = [
                CookStage(
                    temperature=Temperature.from_fahrenheit(482),
                    mode=TemperatureMode.DRY,
                    timer=Timer(initial=180),
                    fan_speed=100,
                    heating_elements=HeatingElements(top=True, bottom=False, rear=False),
                    title="Stage 1 Toast",
                    description="Stage 1 of Toast Recipe1",
                    rack_position=3
                ),
                CookStage(
                    temperature=Temperature.from_fahrenheit(482),
                    mode=TemperatureMode.WET,
                    steam=SteamSettings(
                        mode=SteamMode.STEAM_PERCENTAGE,
                        steam_percentage=100
                    ),
                    timer=Timer(initial=240),
                    heating_elements=HeatingElements(top=False, bottom=False, rear=True),
                    fan_speed=100,
                    title="Stage 2 Toast",
                    description="Stage 2 of Toast Recipe",
                    rack_position=3
                ),
                CookStage(
                    temperature=Temperature.from_fahrenheit(77),
                    mode=TemperatureMode.DRY,
                    timer=Timer(initial=60),
                    heating_elements=HeatingElements(top=False, bottom=True, rear=False),
                    fan_speed=100,
                    title="Stage 3 Toast",
                    description="Stage 3 of Toast Recipe",
                    rack_position=3
                )
            ]

            await oven.start_cook(device_id, stages=stages)
# ============================================================================
# Main SDK Interface
# ============================================================================
from .settings import settings
import asyncio
from typing import Optional, List, Dict, Any, Union
from .exceptions import ConfigurationError, DeviceNotFoundError
from .commands import CommandBuilder
from .client import WebSocketClient
from .models import Device, CookStage, OvenVersion, Probe, Temperature, TimerStartType, Timer, HeatingElements, \
    TemperatureMode, ensure_temperature
from .logging_config import setup_logging
from .utils import get_masked_token

class AnovaOven:
    """
    Main SDK interface for Anova Precision Ovens.

    Enhanced with full Fahrenheit and Celsius support.

    Examples:
        # Celsius (default)
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()
            await oven.start_cook(devices[0].id, temperature=200, duration=1800)

        # Fahrenheit
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()
            await oven.start_cook(
                devices[0].id,
                temperature=350,
                temperature_unit="F",
                duration=1800
            )

        # Temperature object
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()
            temp = Temperature.from_fahrenheit(350)
            await oven.start_cook(devices[0].id, temperature=temp, duration=1800)
    """

    def __init__(self, environment: Optional[str] = None):
        """
        Initialize Anova Oven SDK.

        Args:
            environment: Override environment (dev/staging/production)
        """
        if environment:
            settings.setenv(environment)

        try:
            settings.validators.validate_all()
        except Exception as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")

        self.logger = setup_logging()
        self.client = WebSocketClient(self.logger)
        self.command_builder = CommandBuilder()
        self._devices: Dict[str, Device] = {}

        self.client.add_callback(self._handle_device_list)

        self.logger.info(
            f"Anova SDK initialized [env: {settings.current_env}] "
            f"[token: {get_masked_token(settings.token)}]"
        )

    async def connect(self) -> None:
        """Connect to Anova servers."""
        await self.client.connect()

    async def disconnect(self) -> None:
        """Disconnect from servers."""
        await self.client.disconnect()

    async def discover_devices(self, timeout: float = 5.0) -> List[Device]:
        """
        Discover connected devices.

        Args:
            timeout: Discovery wait time

        Returns:
            List of Device objects
        """
        if not self.client.is_connected:
            await self.connect()

        self.logger.info(f"Discovering devices ({timeout}s)...")
        await asyncio.sleep(timeout)

        devices = list(self._devices.values())
        self.logger.info(f"Found {len(devices)} device(s)")

        return devices

    def _handle_device_list(self, data: Dict[str, Any]) -> None:
        """Handle device discovery messages."""
        if data.get('command') == 'EVENT_APO_WIFI_LIST':
            payload = data.get('payload', [])
            for device_data in payload:
                try:
                    device = Device.model_validate(device_data)
                    self._devices[device.cooker_id] = device
                    self.logger.info(f"  → {device.name} ({device.oven_version.value})")
                except ValueError as e:
                    self.logger.error(f"Device validation error: {e}")

    def get_device(self, device_id: str) -> Device:
        """Get device by ID."""
        device = self._devices.get(device_id)
        if not device:
            raise DeviceNotFoundError(
                f"Device not found: {device_id}",
                {"device_id": device_id, "available": list(self._devices.keys())}
            )
        return device

    async def start_cook(
            self,
            device_id: str,
            stages: Optional[List[CookStage]] = None,
            temperature: Optional[Union[float, Temperature]] = None,
            temperature_unit: str = "C",
            duration: Optional[int] = None,
            **kwargs
    ) -> None:
        """
        Start cooking with flexible temperature input.

        Args:
            device_id: Device ID
            stages: Cooking stages (advanced)
            temperature: Temperature as float or Temperature object
            temperature_unit: Unit for float temperature ("C" or "F")
            duration: Duration in seconds
            **kwargs: Additional parameters

        Examples:
            # Celsius (default)
            await oven.start_cook(device_id, temperature=200, duration=1800)

            # Fahrenheit
            await oven.start_cook(
                device_id,
                temperature=350,
                temperature_unit="F",
                duration=1800
            )

            # Temperature object
            temp = Temperature.from_fahrenheit(350)
            await oven.start_cook(device_id, temperature=temp, duration=1800)
        """
        device = self.get_device(device_id)

        # Simple mode
        if stages is None:
            if temperature is None:
                raise ValueError("Provide either 'stages' or 'temperature'")

            # Convert temperature to Temperature object
            temp_obj = ensure_temperature(temperature, temperature_unit)

            # Build stage
            stage_kwargs = {
                'temperature': temp_obj,
                'mode': kwargs.get('mode', TemperatureMode.DRY),
                'heating_elements': kwargs.get('heating_elements', HeatingElements()),
                'fan_speed': kwargs.get('fan_speed', 100),
                'vent_open': kwargs.get('vent_open', False),
                'rack_position': kwargs.get('rack_position', 3),
                'steam': kwargs.get('steam'),
                'probe': kwargs.get('probe'),
                'title': kwargs.get('title', ''),
                'description': kwargs.get('description', '')
            }

            if duration:
                stage_kwargs['timer'] = Timer(
                    initial=duration,
                    start_type=kwargs.get('timer_start_type', TimerStartType.IMMEDIATELY)
                )

            try:
                stage = CookStage(**stage_kwargs)
                stages = [stage]
            except ValueError as e:
                raise ValueError(f"Stage validation failed: {e}")

        # Validate stages
        for stage in stages:
            stage.validate_for_oven(device.oven_version)

        # Build and send command
        payload = self.command_builder.build_start_command(
            device_id, stages, device.oven_version
        )

        await self.client.send_command("CMD_APO_START", payload)

        # Log with temperature display
        first_temp = stages[0].temperature
        if settings.get('display_both_units', True):
            self.logger.info(f"✓ Started cook on {device.name} at {first_temp}")
        else:
            unit = settings.get('default_temperature_unit', 'C')
            if unit == 'F':
                self.logger.info(f"✓ Started cook on {device.name} at {first_temp.fahrenheit:.1f}°F")
            else:
                self.logger.info(f"✓ Started cook on {device.name} at {first_temp.celsius:.1f}°C")

    async def stop_cook(self, device_id: str) -> None:
        """Stop cooking."""
        device = self.get_device(device_id)
        payload = self.command_builder.build_stop_command(device_id)

        await self.client.send_command("CMD_APO_STOP", payload)
        self.logger.info(f"✓ Stopped cook on {device.name}")

    async def set_probe(
            self,
            device_id: str,
            target: Union[float, Temperature],
            temperature_unit: str = "C"
    ) -> None:
        """
        Set probe temperature.

        Args:
            device_id: Device ID
            target: Target temperature (float or Temperature object)
            temperature_unit: Unit if target is float ("C" or "F")
        """
        device = self.get_device(device_id)

        # Convert to Temperature object
        temp_obj = ensure_temperature(target, temperature_unit)

        # Validate probe temperature
        try:
            probe = Probe(setpoint=temp_obj)
        except ValueError as e:
            raise ValueError(f"Probe validation failed: {e}")

        # Auto-add Fahrenheit for v1
        if device.oven_version == OvenVersion.V1:
            temp_for_api = temp_obj
        else:
            temp_for_api = Temperature(celsius=temp_obj.celsius)

        payload = self.command_builder.build_probe_command(device_id, temp_for_api)

        await self.client.send_command("CMD_APO_SET_PROBE", payload)
        self.logger.info(f"✓ Set probe to {temp_obj} on {device.name}")

    async def set_temperature_unit(self, device_id: str, unit: str) -> None:
        """Set temperature unit display."""
        device = self.get_device(device_id)
        payload = self.command_builder.build_temperature_unit_command(device_id, unit)

        await self.client.send_command("CMD_APO_SET_TEMPERATURE_UNIT", payload)
        self.logger.info(f"✓ Set unit to {unit} on {device.name}")

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
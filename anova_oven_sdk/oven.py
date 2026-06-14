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
from .response_models import DeviceListResponse, ApoStateResponse, CommandResponse, ErrorResponse
from .logging_config import setup_logging
from .utils import get_masked_token
from datetime import datetime


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

        self.client.add_callback(self._handle_message)

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

    def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages."""
        command = data.get('command')

        if command == 'EVENT_APO_WIFI_LIST':
            try:
                # Validate response structure
                response = DeviceListResponse.model_validate(data)

                # Process each device in the payload
                for device_data in response.payload:
                    try:
                        device = Device.model_validate(device_data)
                        self._devices[device.cooker_id] = device
                        self.logger.info(f"  → {device.name} ({device.oven_version.value})")
                    except ValueError as e:
                        self.logger.error(f"Device validation error: {e}")
            except ValueError as e:
                self.logger.error(f"Invalid device list response: {e}")

        elif command == 'EVENT_APO_STATE':
            try:
                # Validate response structure
                response = ApoStateResponse.model_validate(data)

                # Try to identify device
                device_id = response.payload.cooker_id
                device = None

                if device_id and device_id in self._devices:
                    device = self._devices[device_id]
                elif len(self._devices) == 1:
                    # Fallback to single device if ID not provided or not found (but we have only one)
                    device = list(self._devices.values())[0]

                if device:
                    self.logger.info(f"Received state update for {device.name}")
                    
                    from .response_models import ApoStateData, OvenState, SystemInfo, CookSessionState

                    # Determine data source based on payload structure (V1 nested vs V2 flat)
                    payload_state = response.payload.state

                    nodes = None
                    oven_state = None
                    system_info = None
                    cook = None

                    if isinstance(payload_state, ApoStateData):
                        # V1 Nested Structure. Active cook session state is
                        # nested under state.cook (confirmed against a real
                        # mid-cook capture).
                        nodes = payload_state.nodes
                        oven_state = payload_state.state
                        system_info = payload_state.system_info
                        cook = payload_state.cook
                    elif isinstance(payload_state, OvenState):
                        # V2 Flat Structure (state is just OvenState)
                        nodes = response.payload.nodes
                        oven_state = payload_state
                        system_info = response.payload.system_info
                        cook = response.payload.cook
                    else:
                        # Fallback (state might be None)
                        nodes = response.payload.nodes
                        system_info = response.payload.system_info
                        cook = response.payload.cook

                    # V2/fallback: no nested `cook` object confirmed yet, so
                    # fall back to the legacy flat cook session fields
                    # reported alongside nodes/systemInfo.
                    if cook is None and not isinstance(payload_state, ApoStateData):
                        cook_source = response.payload
                        if cook_source.cook_id:
                            cook = CookSessionState(
                                cookId=cook_source.cook_id,
                                originSource=cook_source.origin_source,
                                stages=cook_source.stages,
                                rackPosition=cook_source.rack_position,
                            )

                    if cook:
                        # Diagnostic logging to help verify the V2 cook
                        # session shape against the V1 `state.cook` shape
                        # (CookSessionState) once a V2 sample with an active
                        # cook is captured.
                        self.logger.debug(
                            "Cook session %s: %d stage(s), activeStageIndex=%s, extra=%s",
                            cook.cook_id, len(cook.stages or []), cook.active_stage_index, cook.model_extra,
                        )
                        for i, stage in enumerate(cook.stages or []):
                            self.logger.debug(
                                "  stage[%d]: id=%s title=%r rackPosition=%s extra=%s",
                                i, stage.id, stage.title, stage.rack_position, stage.model_extra,
                            )

                    # Update nodes
                    if nodes:
                        device.nodes = nodes
                        self.logger.info(f"Updated nodes for {device.name}")

                    # Update state_info (mode, temperatureUnit, etc.)
                    if oven_state:
                        device.state_info = oven_state

                        # Update device.state enum based on mode
                        if oven_state.mode:
                            from .models import DeviceState
                            mode = oven_state.mode.lower()
                            state_mapping = {
                                "cook": DeviceState.COOKING,
                                "cooking": DeviceState.COOKING,
                                "preheat": DeviceState.PREHEATING,
                                "preheating": DeviceState.PREHEATING,
                                "idle": DeviceState.IDLE,
                                "paused": DeviceState.PAUSED,
                                "completed": DeviceState.COMPLETED,
                                "error": DeviceState.ERROR,
                            }
                            device.state = state_mapping.get(mode, DeviceState.IDLE)
                            self.logger.debug(f"Updated device state to {device.state} (from mode: {mode})")

                    # Update system_info
                    if system_info:
                        device.system_info = system_info

                    # Update cook session data
                    device.cook = cook

                    # Update timestamp
                    device.last_update = datetime.now()
                else:
                    self.logger.warning(f"Received state update for unknown device: {device_id}")

            except ValueError as e:
                self.logger.error(f"Invalid state response: {e}")
                self.logger.debug(f"Payload: {data}")

        elif command == 'RESPONSE':
            try:
                response = CommandResponse.model_validate(data)
                if response.payload:
                    status = response.payload.status
                    msg = response.payload.message
                    if status == "success":
                        self.logger.debug(f"Command success: {msg}")
                    else:
                        self.logger.warning(f"Command response: {status} - {msg} - {data}")
            except ValueError as e:
                self.logger.error(f"Invalid command response: {e}")

        elif command == 'ERROR':
            try:
                response = ErrorResponse.model_validate(data)
                error_msg = response.payload.error_message
                error_code = response.payload.error_code
                self.logger.error(f"Server Error [{error_code}]: {error_msg}")
                if response.payload.details:
                    self.logger.debug(f"Error details: {response.payload.details}")
            except ValueError as e:
                self.logger.error(f"Invalid error response: {e}")

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
            wait_for_response: bool = False,
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
            wait_for_response: Wait for API response confirmation
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

        # Log the full command payload for debugging
        import json
        self.logger.debug(f"CMD_APO_START payload:\n{json.dumps(payload, indent=2, default=str)}")

        # Record the cook_id -> ordered stage id mapping so total_stage_count/
        # current_stage_index can later resolve "stage X of Y" from live
        # EVENT_APO_STATE updates (see Device.register_cook_plan).
        start_payload = payload.get("payload", {})
        cook_id = start_payload.get("cookId")
        if cook_id:
            stage_ids = [stage.get("id") for stage in start_payload.get("stages", [])]
            device.register_cook_plan(cook_id, stage_ids)

        await self.client.send_command("CMD_APO_START", payload, wait_response=wait_for_response)

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
#!/usr/bin/env python3
# ============================================================================
# Enhanced Command Line Interface for Interactive Testing
# ============================================================================
"""
Anova Oven CLI - Enhanced command-line interface for testing and development.

Usage:
    # Discover devices with detailed output
    python anova_oven_cli.py discover --verbose

    # Monitor device status in real-time
    python anova_oven_cli.py monitor --device <device_id>

    # Check device status
    python anova_oven_cli.py status --device <device_id>

    # Test payload without sending (dry-run)
    python anova_oven_cli.py cook --device <device_id> --temp 200 --dry-run

    # Start cook with payload inspection
    python anova_oven_cli.py cook --device <device_id> --recipe perfect_toast_v1 --show-payload

    # Interactive mode (step-by-step confirmation)
    python anova_oven_cli.py cook --device <device_id> --temp 200 --duration 1800 --interactive

    # Run test sequence
    python anova_oven_cli.py test --device <device_id> --test-type basic
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from anova_oven_sdk.oven import AnovaOven
from anova_oven_sdk.models import RecipeLibrary, Device, CookStage, Temperature, DeviceState
from anova_oven_sdk.settings import settings
from anova_oven_sdk.exceptions import AnovaError


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AnovaOvenCLI:
    """Enhanced CLI for Anova Oven SDK with testing capabilities."""

    def __init__(self, recipe_file: Optional[str] = None, environment: Optional[str] = None, verbose: bool = False):
        """
        Initialize CLI.

        Args:
            recipe_file: Path to recipes YAML file
            environment: Environment name (dev/staging/production)
            verbose: Enable verbose output
        """
        self.recipe_file = recipe_file or self._find_recipe_file()
        self.environment = environment
        self.verbose = verbose
        self.library: Optional[RecipeLibrary] = None

    def _find_recipe_file(self) -> str:
        """Find recipes.yml in common locations."""
        possible_paths = [
            "recipes.yml",
            "recipes.yaml",
            Path.home() / ".anova" / "recipes.yml",
            Path(__file__).parent / "recipes.yml",
        ]

        for path in possible_paths:
            if Path(path).exists():
                return str(path)

        return "recipes.yml"

    def _load_recipes(self) -> RecipeLibrary:
        """Load recipe library."""
        if self.library is None:
            try:
                self.library = RecipeLibrary.from_yaml_file(self.recipe_file)
            except FileNotFoundError:
                print(f"{Colors.WARNING}Warning: Recipe file not found: {self.recipe_file}{Colors.ENDC}")
                self.library = RecipeLibrary()
        return self.library

    def _print_header(self, text: str):
        """Print formatted header."""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")

    def _print_success(self, text: str):
        """Print success message."""
        print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

    def _print_error(self, text: str):
        """Print error message."""
        print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

    def _print_warning(self, text: str):
        """Print warning message."""
        print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

    def _print_info(self, text: str):
        """Print info message."""
        print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

    def _format_device_info(self, device: Device, detailed: bool = False) -> str:
        """Format device information."""
        lines = []
        lines.append(f"{Colors.BOLD}{device.name}{Colors.ENDC}")
        lines.append(f"  ID:      {device.id}")
        lines.append(f"  Type:    {device.oven_version.value}")
        lines.append(f"  State:   {device.state.value}")

        if device.current_temperature:
            lines.append(f"  Temp:    {device.current_temperature}°C ({device.current_temperature * 9 / 5 + 32:.1f}°F)")

        if detailed and device.state_info:
            lines.append(f"\n  {Colors.BOLD}State Details:{Colors.ENDC}")
            if hasattr(device.state_info, 'mode'):
                lines.append(f"    Mode:           {device.state_info.mode}")
            if hasattr(device.state_info, 'temperature_unit'):
                lines.append(f"    Display Unit:   {device.state_info.temperature_unit}")

        # Get temperature info from nodes if available
        if detailed and device.nodes:
            try:
                # Get current temperature from dry bulb
                if hasattr(device.nodes.temperature_bulbs, 'dry'):
                    temp_c = device.nodes.temperature_bulbs.dry.current.get('celsius', 0)
                    temp_f = temp_c * 9 / 5 + 32
                    lines.append(f"    Bulb Temp:      {temp_c}°C ({temp_f:.1f}°F)")

                    # Get setpoint if available
                    if device.nodes.temperature_bulbs.dry.setpoint:
                        sp_c = device.nodes.temperature_bulbs.dry.setpoint.get('celsius', 0)
                        sp_f = sp_c * 9 / 5 + 32
                        lines.append(f"    Set Point:      {sp_c}°C ({sp_f:.1f}°F)")
            except (AttributeError, KeyError):
                pass  # Skip if structure not available

        if detailed and device.nodes:
            lines.append(f"\n  {Colors.BOLD}Nodes:{Colors.ENDC}")
            lines.append(f"    Temperature:    {device.nodes.temperature_bulbs}")
            lines.append(f"    Heaters:        {device.nodes.heating_elements}")
            lines.append(f"    Water Tank:     {device.nodes.water_tank}")
            lines.append(f"    Steam:          {device.nodes.steam_generators}")
            lines.append(f"    Timer:          {device.nodes.timer}")

        return "\n".join(lines)

    def _build_cook_payload(self, oven: AnovaOven, device_id: str, args: argparse.Namespace) -> Dict[str, Any]:
        """Build cook command payload from arguments."""
        device = oven.get_device(device_id)
        stages = None

        if args.recipe:
            # Load recipe
            library = self._load_recipes()
            recipe = library.get_recipe(args.recipe)
            recipe.validate_for_oven(device.oven_version)
            stages = recipe.to_cook_stages()
        else:
            # Build simple stage
            from anova_oven_sdk.models import (
                CookStage, Temperature, Timer, TimerStartType,
                HeatingElements, TemperatureMode
            )

            temp = Temperature.from_celsius(args.temp) if args.unit == 'C' else Temperature.from_fahrenheit(args.temp)

            stage_kwargs = {
                'temperature': temp,
                'mode': TemperatureMode.DRY,
                'heating_elements': HeatingElements(),
                'fan_speed': args.fan_speed,
                'vent_open': False,
                'rack_position': 3,
            }

            if args.duration:
                stage_kwargs['timer'] = Timer(
                    initial=args.duration,
                    start_type=TimerStartType.IMMEDIATELY
                )

            stages = [CookStage(**stage_kwargs)]

        # Build payload using command builder
        payload = oven.command_builder.build_start_command(
            device_id, stages, device.oven_version
        )

        return payload

    async def cmd_discover(self, args: argparse.Namespace) -> int:
        """Discover connected devices with optional verbose output."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                if not args.json:
                    self._print_header("DISCOVERING DEVICES")

                devices = await oven.discover_devices(timeout=args.timeout)

                if not devices:
                    if not args.json:
                        self._print_warning("No devices found.")
                    return 1

                if args.json:
                    output = [
                        {
                            'id': d.id,
                            'name': d.name,
                            'type': d.oven_version.value,
                            'state': d.state.value,
                            'current_temperature': d.current_temperature,
                        }
                        for d in devices
                    ]
                    print(json.dumps(output, indent=2))
                else:
                    print(f"Found {len(devices)} device(s):\n")
                    for device in devices:
                        print(self._format_device_info(device, detailed=self.verbose))
                        print()

                    self._print_success("Discovery complete")

                return 0

        except AnovaError as e:
            self._print_error(f"Discovery failed: {e}")
            return 1

    async def cmd_status(self, args: argparse.Namespace) -> int:
        """Check device status."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                # Discover to get latest state
                await oven.discover_devices(timeout=2.0)
                device = oven.get_device(args.device)

                if args.json:
                    output = {
                        'id': device.id,
                        'name': device.name,
                        'type': device.oven_version.value,
                        'state': device.state.value,
                        'current_temperature': device.current_temperature,
                        'last_update': device.last_update.isoformat() if device.last_update else None,
                    }

                    if device.state_info:
                        output['state_info'] = device.state_info.model_dump()
                    if device.nodes:
                        output['nodes'] = device.nodes.model_dump()

                    print(json.dumps(output, indent=2))
                else:
                    self._print_header(f"DEVICE STATUS: {device.name}")
                    print(self._format_device_info(device, detailed=True))

                    if device.last_update:
                        print(f"\n  Last Update: {device.last_update.strftime('%Y-%m-%d %H:%M:%S')}")

                return 0

        except AnovaError as e:
            self._print_error(f"Status check failed: {e}")
            return 1

    async def cmd_monitor(self, args: argparse.Namespace) -> int:
        """Monitor device status in real-time."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                self._print_header(f"MONITORING DEVICE: {args.device}")
                self._print_info("Press Ctrl+C to stop monitoring\n")

                # Initial discovery
                await oven.discover_devices(timeout=2.0)

                last_state = None
                update_count = 0

                while True:
                    try:
                        device = oven.get_device(args.device)

                        # Check if state changed
                        current_state = {
                            'state': device.state.value,
                            'temp': device.current_temperature,
                        }

                        if current_state != last_state:
                            update_count += 1
                            timestamp = datetime.now().strftime('%H:%M:%S')

                            print(f"\n[{timestamp}] Update #{update_count}")
                            print(f"  State: {device.state.value}")

                            if device.current_temperature:
                                temp_f = device.current_temperature * 9 / 5 + 32
                                print(f"  Temperature: {device.current_temperature}°C ({temp_f:.1f}°F)")

                            # Get target temperature from nodes if available
                            if device.nodes:
                                try:
                                    if hasattr(device.nodes.temperature_bulbs,
                                               'dry') and device.nodes.temperature_bulbs.dry.setpoint:
                                        sp_c = device.nodes.temperature_bulbs.dry.setpoint.get('celsius', 0)
                                        sp_f = sp_c * 9 / 5 + 32
                                        print(f"  Target: {sp_c}°C ({sp_f:.1f}°F)")
                                except (AttributeError, KeyError):
                                    pass

                            last_state = current_state

                        await asyncio.sleep(args.interval)

                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        self._print_error(f"Monitor error: {e}")
                        await asyncio.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n")
            self._print_info("Monitoring stopped")
            return 0
        except AnovaError as e:
            self._print_error(f"Monitoring failed: {e}")
            return 1

    async def cmd_cook(self, args: argparse.Namespace) -> int:
        """Start cooking with optional payload inspection."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                # Discover devices
                devices = await oven.discover_devices(timeout=2.0)
                device_ids = [d.id for d in devices]

                if args.device not in device_ids:
                    self._print_error(f"Device '{args.device}' not found.")
                    print(f"Available devices: {', '.join(device_ids)}")
                    return 1

                device = oven.get_device(args.device)

                # Build payload
                if args.recipe:
                    library = self._load_recipes()
                    recipe = library.get_recipe(args.recipe)

                    if not args.json:
                        self._print_header("RECIPE COOK")
                        print(f"Recipe:  {recipe.name}")
                        print(f"Device:  {device.name}")
                        print(f"Stages:  {len(recipe.stages)}")

                    recipe.validate_for_oven(device.oven_version)
                    stages = recipe.to_cook_stages()
                else:
                    if args.temp is None:
                        self._print_error("Provide either --recipe or --temp")
                        return 1

                    if not args.json:
                        self._print_header("SIMPLE COOK")
                        print(f"Device:      {device.name}")
                        print(f"Temperature: {args.temp}°{args.unit}")
                        if args.duration:
                            mins = args.duration // 60
                            secs = args.duration % 60
                            print(f"Duration:    {mins}m {secs}s")
                        print(f"Fan Speed:   {args.fan_speed}%")

                    # Build stage
                    from anova_oven_sdk.models import (
                        CookStage, Temperature, Timer, TimerStartType,
                        HeatingElements, TemperatureMode
                    )

                    temp = Temperature.from_celsius(args.temp) if args.unit == 'C' else Temperature.from_fahrenheit(
                        args.temp)

                    # Default heating elements if not specified
                    if not any([args.top, args.bottom, args.rear]):
                        # Default to Bottom + Rear for roast/cook (matches anova_interactive.py)
                        heating_elements = HeatingElements(rear=True, top=False, bottom=True)
                    else:
                        heating_elements = HeatingElements(top=args.top, bottom=args.bottom, rear=args.rear)

                    stage_kwargs = {
                        'temperature': temp,
                        'mode': TemperatureMode.DRY,
                        'heating_elements': heating_elements,
                        'fan_speed': args.fan_speed,
                        'vent_open': False,
                        'rack_position': 3,
                    }

                    if args.duration:
                        stage_kwargs['timer'] = Timer(
                            initial=args.duration,
                            start_type=TimerStartType.IMMEDIATELY
                        )

                    stages = [CookStage(**stage_kwargs)]

                # Build command payload
                payload = oven.command_builder.build_start_command(
                    args.device, stages, device.oven_version
                )

                # Show payload if requested
                if args.show_payload or args.dry_run:
                    if not args.json:
                        print(f"\n{Colors.BOLD}Command Payload:{Colors.ENDC}")
                    print(json.dumps(payload, indent=2, default=str))

                # Dry run - don't actually send
                if args.dry_run:
                    if not args.json:
                        self._print_info("Dry run - command not sent")
                    return 0

                # Interactive mode - ask for confirmation
                if args.interactive and not args.json:
                    print()
                    response = input(f"{Colors.WARNING}Send command to oven? (y/N): {Colors.ENDC}")
                    if response.lower() != 'y':
                        self._print_info("Cook cancelled")
                        return 0

                # Send command
                await oven.start_cook(args.device, stages=stages, wait_for_response=args.wait_for_response)

                # Wait for response if requested
                if args.wait_for_response and not args.json:
                    self._print_info("\nWaiting for oven response...")
                    await asyncio.sleep(2)  # Give time for response

                    # Check device state
                    device = oven.get_device(args.device)
                    print(f"\n{Colors.BOLD}Oven Response:{Colors.ENDC}")
                    print(f"  Device State: {device.state.value}")

                    # Check if state changed from idle
                    if device.state.value != 'idle':
                        self._print_success(f"✓ Oven accepted command - now in '{device.state.value}' state")
                    else:
                        self._print_warning(f"⚠ Oven still in 'idle' state - command was rejected")
                        print(f"\n{Colors.WARNING}The oven sent an ERROR response.{Colors.ENDC}")
                        print(f"\n{Colors.BOLD}Common issues for oven_v1:{Colors.ENDC}")
                        print("  • Payload structure may have extra nesting")
                        print("  • Check if 'payload' contains another 'payload' object")
                        print("  • v1 ovens may need flatter structure")
                        print(f"\n{Colors.OKBLUE}Debug steps:{Colors.ENDC}")
                        print("  1. Check commands.py build_start_command() for v1 handling")
                        print("  2. Look for double-nested 'payload' in structure")
                        print("  3. Compare with working commands from Anova app")
                        print("  4. Check WebSocket logs for ERROR response details")

                    # Show current temperature if available
                    if device.nodes:
                        try:
                            if hasattr(device.nodes.temperature_bulbs, 'dry'):
                                temp_c = device.nodes.temperature_bulbs.dry.current.get('celsius', 0)
                                temp_f = temp_c * 9 / 5 + 32
                                print(f"  Current Temp: {temp_c}°C ({temp_f:.1f}°F)")
                        except (AttributeError, KeyError):
                            pass

                if args.json:
                    result = {"status": "success", "device": args.device}
                    if args.wait_for_response:
                        device = oven.get_device(args.device)
                        result["device_state"] = device.state.value
                        result["command_accepted"] = device.state.value != 'idle'
                    print(json.dumps(result))
                else:
                    self._print_success("Cook started successfully")

                # Monitor briefly if requested
                if args.monitor:
                    print()
                    self._print_info("Monitoring for 10 seconds...")
                    await asyncio.sleep(2)
                    device = oven.get_device(args.device)
                    print(f"  State: {device.state.value}")
                    await asyncio.sleep(8)

                return 0

        except AnovaError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": str(e)}))
            else:
                self._print_error(f"Cook failed: {e}")
            return 1

    async def cmd_stop(self, args: argparse.Namespace) -> int:
        """Stop cooking."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                devices = await oven.discover_devices(timeout=2.0)
                device_ids = [d.id for d in devices]

                if args.device not in device_ids:
                    self._print_error(f"Device '{args.device}' not found.")
                    print(f"Available devices: {', '.join(device_ids)}")
                    return 1

                device = oven.get_device(args.device)

                # Interactive confirmation
                if args.interactive and not args.json:
                    self._print_warning(f"Stop cook on {device.name}?")
                    response = input(f"{Colors.WARNING}Are you sure? (y/N): {Colors.ENDC}")
                    if response.lower() != 'y':
                        self._print_info("Stop cancelled")
                        return 0

                await oven.stop_cook(args.device)

                if args.json:
                    print(json.dumps({"status": "success", "device": args.device}))
                else:
                    self._print_success(f"Cook stopped on {device.name}")

                return 0

        except AnovaError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": str(e)}))
            else:
                self._print_error(f"Stop failed: {e}")
            return 1

    async def cmd_test(self, args: argparse.Namespace) -> int:
        """Run test sequence."""
        try:
            async with AnovaOven(environment=self.environment) as oven:
                self._print_header(f"TEST SEQUENCE: {args.test_type}")

                # Discover
                self._print_info("Step 1: Discovering devices...")
                devices = await oven.discover_devices(timeout=3.0)

                if args.device not in [d.id for d in devices]:
                    self._print_error(f"Device {args.device} not found")
                    return 1

                device = oven.get_device(args.device)
                self._print_success(f"Found device: {device.name}")

                if args.test_type == 'basic':
                    # Basic test: start and stop
                    self._print_info("\nStep 2: Starting simple cook (150°C for 60s)...")
                    await oven.start_cook(
                        args.device,
                        temperature=150,
                        temperature_unit='C',
                        duration=60
                    )
                    self._print_success("Cook started")

                    self._print_info("\nStep 3: Waiting 5 seconds...")
                    await asyncio.sleep(5)

                    self._print_info("\nStep 4: Checking status...")
                    device = oven.get_device(args.device)
                    print(f"  State: {device.state.value}")

                    self._print_info("\nStep 5: Stopping cook...")
                    await oven.stop_cook(args.device)
                    self._print_success("Cook stopped")

                    self._print_info("\nStep 6: Final status check...")
                    await asyncio.sleep(2)
                    device = oven.get_device(args.device)
                    print(f"  State: {device.state.value}")

                elif args.test_type == 'recipe':
                    # Recipe test
                    library = self._load_recipes()
                    recipes = library.list_recipes_with_info()

                    if not recipes:
                        self._print_error("No recipes found")
                        return 1

                    recipe_id = recipes[0]['id']
                    recipe = library.get_recipe(recipe_id)

                    self._print_info(f"\nStep 2: Testing recipe '{recipe.name}'...")
                    recipe.validate_for_oven(device.oven_version)
                    stages = recipe.to_cook_stages()

                    self._print_info(f"\nStep 3: Starting cook ({len(stages)} stages)...")
                    await oven.start_cook(args.device, stages=stages)
                    self._print_success("Recipe cook started")

                    self._print_info("\nStep 4: Monitoring for 10 seconds...")
                    for i in range(5):
                        await asyncio.sleep(2)
                        device = oven.get_device(args.device)
                        print(f"  [{i + 1}/5] State: {device.state.value}")

                    self._print_info("\nStep 5: Stopping cook...")
                    await oven.stop_cook(args.device)
                    self._print_success("Recipe cook stopped")

                elif args.test_type == 'payload':
                    # Payload validation test
                    self._print_info("\nStep 2: Building test payloads...")

                    # Test 1: Simple cook
                    from anova_oven_sdk.models import CookStage, Temperature, HeatingElements, TemperatureMode
                    stage = CookStage(
                        temperature=Temperature.from_celsius(200),
                        mode=TemperatureMode.DRY,
                        heating_elements=HeatingElements(),
                        fan_speed=100,
                    )
                    payload1 = oven.command_builder.build_start_command(
                        args.device, [stage], device.oven_version
                    )

                    print(f"\n{Colors.BOLD}Test Payload 1 (Simple):{Colors.ENDC}")
                    print(json.dumps(payload1, indent=2, default=str))

                    # Test 2: With timer
                    from anova_oven_sdk.models import Timer, TimerStartType
                    stage2 = CookStage(
                        temperature=Temperature.from_fahrenheit(350),
                        mode=TemperatureMode.DRY,
                        heating_elements=HeatingElements(),
                        fan_speed=75,
                        timer=Timer(initial=1800, start_type=TimerStartType.IMMEDIATELY)
                    )
                    payload2 = oven.command_builder.build_start_command(
                        args.device, [stage2], device.oven_version
                    )

                    print(f"\n{Colors.BOLD}Test Payload 2 (With Timer):{Colors.ENDC}")
                    print(json.dumps(payload2, indent=2, default=str))

                    self._print_success("Payload validation complete")

                print()
                self._print_success("Test sequence complete!")
                return 0

        except AnovaError as e:
            self._print_error(f"Test failed: {e}")
            return 1

    async def cmd_recipes_list(self, args: argparse.Namespace) -> int:
        """List available recipes."""
        try:
            library = self._load_recipes()

            if not library.recipes:
                self._print_warning("No recipes found.")
                return 1

            if args.json:
                output = library.list_recipes_with_info()
                print(json.dumps(output, indent=2))
            else:
                self._print_header(f"RECIPES FROM {self.recipe_file}")
                for info in library.list_recipes_with_info():
                    print(f"{Colors.BOLD}{info['id']}{Colors.ENDC}")
                    print(f"  Name:         {info['name']}")
                    print(f"  Description:  {info['description']}")
                    print(f"  Stages:       {info['stages']}")
                    print(f"  Oven Version: {info['oven_version']}")
                    print()

            return 0

        except Exception as e:
            self._print_error(f"Recipe list failed: {e}")
            return 1

    async def cmd_recipes_show(self, args: argparse.Namespace) -> int:
        """Show recipe details."""
        try:
            library = self._load_recipes()
            recipe = library.get_recipe(args.recipe_id)

            if args.json:
                print(json.dumps(recipe.to_dict(), indent=2))
            else:
                self._print_header(f"RECIPE: {recipe.name}")
                print(f"ID:          {recipe.recipe_id}")
                print(f"Description: {recipe.description}")
                print(f"Oven:        {recipe.oven_version.value if recipe.oven_version else 'any'}")
                print(f"\n{Colors.BOLD}Stages ({len(recipe.stages)}):{Colors.ENDC}\n")

                for i, stage in enumerate(recipe.stages, 1):
                    print(f"{Colors.BOLD}Stage {i}: {stage.name}{Colors.ENDC}")
                    temp_config = stage.temperature
                    temp_val = temp_config['value']
                    unit = temp_config.get('temperature_unit', 'C')

                    if unit == 'C':
                        temp_f = temp_val * 9 / 5 + 32
                        print(f"  Temperature: {temp_val}°C ({temp_f:.1f}°F)")
                    else:
                        temp_c = (temp_val - 32) * 5 / 9
                        print(f"  Temperature: {temp_val}°F ({temp_c:.1f}°C)")

                    print(f"  Mode:        {temp_config.get('mode', 'DRY')}")

                    if stage.timer:
                        mins = stage.timer['seconds'] // 60
                        secs = stage.timer['seconds'] % 60
                        print(f"  Timer:       {mins}m {secs}s")

                    elements = []
                    if stage.heating_elements.get('top'):
                        elements.append('top')
                    if stage.heating_elements.get('bottom'):
                        elements.append('bottom')
                    if stage.heating_elements.get('rear'):
                        elements.append('rear')
                    print(f"  Heating:     {', '.join(elements)}")
                    print(f"  Fan Speed:   {stage.fan_speed}%")

                    if stage.steam:
                        steam_parts = []
                        if 'relative_humidity' in stage.steam:
                            steam_parts.append(f"{stage.steam['relative_humidity']}% RH")
                        if 'steam_percentage' in stage.steam:
                            steam_parts.append(f"{stage.steam['steam_percentage']}% steam")

                        if steam_parts:
                            print(f"  Steam:       {', '.join(steam_parts)}")
                    print()

            return 0

        except ValueError as e:
            self._print_error(f"Recipe show failed: {e}")
            return 1


def create_parser() -> argparse.ArgumentParser:
    """Create enhanced argument parser."""
    parser = argparse.ArgumentParser(
        description="Anova Oven CLI - Enhanced testing interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--recipe-file',
        type=str,
        help='Path to recipes YAML file'
    )

    parser.add_argument(
        '--env',
        '--environment',
        type=str,
        choices=['dev', 'staging', 'production'],
        help='Environment'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # Discover
    discover_parser = subparsers.add_parser('discover', help='Discover devices')
    discover_parser.add_argument('--timeout', type=float, default=5.0, help='Timeout (default: 5.0)')
    discover_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    discover_parser.add_argument('--json', action='store_true', help='JSON output')

    # Status
    status_parser = subparsers.add_parser('status', help='Check device status')
    status_parser.add_argument('--device', type=str, required=True, help='Device ID')
    status_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    status_parser.add_argument('--json', action='store_true', help='JSON output')

    # Monitor
    monitor_parser = subparsers.add_parser('monitor', help='Monitor device in real-time')
    monitor_parser.add_argument('--device', type=str, required=True, help='Device ID')
    monitor_parser.add_argument('--interval', type=float, default=2.0, help='Update interval (default: 2.0)')

    # Cook
    cook_parser = subparsers.add_parser('cook', help='Start cooking')
    cook_parser.add_argument('--device', type=str, required=True, help='Device ID')
    cook_parser.add_argument('--recipe', type=str, help='Recipe ID')
    cook_parser.add_argument('--temp', '--temperature', type=float, help='Temperature')
    cook_parser.add_argument('--unit', type=str, choices=['C', 'F'], default='C', help='Unit (default: C)')
    cook_parser.add_argument('--duration', type=int, help='Duration (seconds)')
    cook_parser.add_argument('--fan-speed', type=int, default=75, help='Fan speed (default: 75)')
    cook_parser.add_argument('--top', action='store_true', help='Enable top heating element')
    cook_parser.add_argument('--bottom', action='store_true', help='Enable bottom heating element')
    cook_parser.add_argument('--rear', action='store_true', help='Enable rear heating element')
    cook_parser.add_argument('--show-payload', action='store_true', help='Show command payload')
    cook_parser.add_argument('--dry-run', action='store_true', help='Build payload but do not send')
    cook_parser.add_argument('--interactive', '-i', action='store_true', help='Interactive confirmation')
    cook_parser.add_argument('--monitor', action='store_true', help='Monitor after starting')
    cook_parser.add_argument('--no-wait', dest='wait_for_response', action='store_false',
                             help='Do not wait for oven response (default: wait)')
    cook_parser.set_defaults(wait_for_response=True)
    cook_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    cook_parser.add_argument('--json', action='store_true', help='JSON output')

    # Stop
    stop_parser = subparsers.add_parser('stop', help='Stop cooking')
    stop_parser.add_argument('--device', type=str, required=True, help='Device ID')
    stop_parser.add_argument('--interactive', '-i', action='store_true', help='Interactive confirmation')
    stop_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    stop_parser.add_argument('--json', action='store_true', help='JSON output')

    # Test
    test_parser = subparsers.add_parser('test', help='Run test sequence')
    test_parser.add_argument('--device', type=str, required=True, help='Device ID')
    test_parser.add_argument(
        '--test-type',
        type=str,
        choices=['basic', 'recipe', 'payload'],
        default='basic',
        help='Test type (default: basic)'
    )
    test_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    test_parser.add_argument('--json', action='store_true', help='JSON output')

    # Recipes
    recipes_parser = subparsers.add_parser('recipes', help='Manage recipes')
    recipes_subparsers = recipes_parser.add_subparsers(dest='recipes_command')

    recipes_list_parser = recipes_subparsers.add_parser('list', help='List recipes')
    recipes_list_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    recipes_list_parser.add_argument('--json', action='store_true', help='JSON output')

    recipes_show_parser = recipes_subparsers.add_parser('show', help='Show recipe')
    recipes_show_parser.add_argument('recipe_id', type=str, help='Recipe ID')
    recipes_show_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    recipes_show_parser.add_argument('--json', action='store_true', help='JSON output')

    return parser


async def async_main() -> int:
    """Async main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Get verbose from args if available, otherwise default to False
    verbose = getattr(args, 'verbose', False)

    cli = AnovaOvenCLI(
        recipe_file=getattr(args, 'recipe_file', None),
        environment=getattr(args, 'env', None),
        verbose=verbose
    )

    # Route commands
    if args.command == 'discover':
        return await cli.cmd_discover(args)
    elif args.command == 'status':
        return await cli.cmd_status(args)
    elif args.command == 'monitor':
        return await cli.cmd_monitor(args)
    elif args.command == 'cook':
        return await cli.cmd_cook(args)
    elif args.command == 'stop':
        return await cli.cmd_stop(args)
    elif args.command == 'test':
        return await cli.cmd_test(args)
    elif args.command == 'recipes':
        if args.recipes_command == 'list':
            return await cli.cmd_recipes_list(args)
        elif args.recipes_command == 'show':
            return await cli.cmd_recipes_show(args)
        else:
            parser.parse_args(['recipes', '--help'])
            return 1
    else:
        parser.print_help()
        return 1


def main() -> int:
    """Main entry point."""
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
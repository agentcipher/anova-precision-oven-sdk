"""
Anova Precision Oven Python SDK - CLI

DISCLAIMER:
This software is provided "as is" without warranty of any kind, express or implied. The authors and contributors are not liable for any damages, losses, or issues arising from the use of this software, including but not limited to:

- Device malfunction or damage
- Property damage
- Food safety issues
- Data loss
- Service interruptions

Use at your own risk. Always supervise cooking operations and follow manufacturer guidelines for your Anova Precision Oven. This is unofficial software not endorsed by Anova Culinary.

Installation:
    pip install websockets pydantic dynaconf

Project Structure:
    anova_oven_sdk/
    ├── settings.yaml          # Main configuration
    ├── .secrets.yaml          # Secrets (gitignored)
    ├── .env                   # Environment variables
    └── anova_oven_sdk.py      # SDK files

settings.yaml example:
    default:
      ws_url: "wss://devices.anovaculinary.io"
      supported_accessories:
        - APO
      connection_timeout: 30.0
      log_level: INFO

    development:
      log_level: DEBUG
      log_file: "anova_dev.log"

    production:
      log_level: WARNING
      max_retries: 5

.secrets.yaml example:
    default:
      token: "anova-your-token-here"

Usage:
    # Discover devices
    python anova_oven_cli.py discover

    # Start cooking
    python anova_oven_cli.py cook --device DEVICE_ID --temp 200 --duration 30

    # Run examples
    python anova_oven_cli.py example basic
    python anova_oven_cli.py example advanced
"""

import os
import sys
import asyncio
import argparse
import logging
from typing import Optional, List
from enum import Enum

# Import SDK components
try:
    from anova_oven_sdk import (
        AnovaOven,
        CookStage,
        SteamSettings,
        SteamMode,
        Temperature,
        TimerStartType,
        Timer,
        HeatingElements,
        TemperatureMode,
        ConfigurationError,
        CookingPresets,
        DeviceNotFoundError,
        CommandError,
    )
except ImportError as e:
    print(f"❌ Failed to import anova_oven_sdk: {e}")
    print("\nPlease ensure the SDK is installed:")
    print("  pip install anova-oven-sdk")
    sys.exit(1)


# ============================================================================
# CLI Configuration
# ============================================================================

class ExitCode(Enum):
    """Standard exit codes for better error handling"""
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    DEVICE_ERROR = 3
    COMMAND_ERROR = 4
    KEYBOARD_INTERRUPT = 130


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY output"""
        for attr in dir(cls):
            if not attr.startswith('_') and attr != 'disable':
                setattr(cls, attr, '')


# Disable colors if not in a TTY
if not sys.stdout.isatty():
    Colors.disable()


def print_header(text: str) -> None:
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}", file=sys.stderr)


def print_warning(text: str) -> None:
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


# ============================================================================
# CLI Commands
# ============================================================================

async def cli_discover(args: argparse.Namespace) -> int:
    """
    CLI: Discover devices.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    try:
        async with AnovaOven() as oven:
            print_info(f"Discovering devices (timeout: {args.timeout}s)...")
            devices = await oven.discover_devices(timeout=args.timeout)

            if not devices:
                print_warning("No devices found")
                print_info("Ensure your oven is connected to WiFi and paired with your account")
                return ExitCode.DEVICE_ERROR.value

            print_success(f"Found {len(devices)} device(s):\n")

            for i, device in enumerate(devices, 1):
                print(f"{Colors.BOLD}{i}. {device.name}{Colors.RESET}")
                print(f"   {Colors.CYAN}ID:{Colors.RESET} {device.cooker_id}")
                print(f"   {Colors.CYAN}Type:{Colors.RESET} {device.oven_version.value}")
                print(f"   {Colors.CYAN}Paired:{Colors.RESET} {device.paired_at}")
                print(f"   {Colors.CYAN}State:{Colors.RESET} {device.state.value}")
                if device.current_temperature:
                    print(f"   {Colors.CYAN}Current Temp:{Colors.RESET} {device.current_temperature}°C")
                print()

            if args.json:
                import json
                devices_data = [
                    {
                        "id": d.cooker_id,
                        "name": d.name,
                        "type": d.oven_version.value,
                        "state": d.state.value,
                        "paired_at": d.paired_at,
                    }
                    for d in devices
                ]
                print(json.dumps(devices_data, indent=2))

            return ExitCode.SUCCESS.value

    except Exception as e:
        print_error(f"Discovery failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def cli_cook(args: argparse.Namespace) -> int:
    """
    CLI: Start cooking.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    if not args.device:
        print_error("--device is required for cook command")
        return ExitCode.COMMAND_ERROR.value

    try:
        async with AnovaOven() as oven:
            print_info("Discovering devices...")
            await oven.discover_devices()

            # Validate device exists
            try:
                device = oven.get_device(args.device)
                print_info(f"Using device: {device.name}")
            except DeviceNotFoundError:
                print_error(f"Device not found: {args.device}")
                print_info("Run 'discover' command to see available devices")
                return ExitCode.DEVICE_ERROR.value

            # Start cooking
            print_info(f"Starting cook: {args.temp}°{args.unit} for {args.duration} minutes")

            await oven.start_cook(
                device_id=args.device,
                temperature=args.temp,
                temperature_unit=args.unit,
                duration=args.duration * 60,
                fan_speed=args.fan_speed,
                vent_open=args.vent_open,
            )

            print_success(
                f"Cook started: {args.temp}°{args.unit} for {args.duration} minutes"
            )

            if args.wait:
                print_info(f"Cook will run for {args.duration} minutes...")
                print_info("Press Ctrl+C to stop early")
                try:
                    await asyncio.sleep(args.duration * 60)
                    print_success("Cook completed!")
                except KeyboardInterrupt:
                    print_warning("\nStopping cook early...")
                    await oven.stop_cook(args.device)
                    print_success("Cook stopped")

            return ExitCode.SUCCESS.value

    except ValueError as e:
        print_error(f"Invalid parameter: {e}")
        return ExitCode.COMMAND_ERROR.value
    except CommandError as e:
        print_error(f"Command failed: {e}")
        return ExitCode.COMMAND_ERROR.value
    except Exception as e:
        print_error(f"Cook failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def cli_stop(args: argparse.Namespace) -> int:
    """
    CLI: Stop cooking.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    if not args.device:
        print_error("--device is required for stop command")
        return ExitCode.COMMAND_ERROR.value

    try:
        async with AnovaOven() as oven:
            print_info("Discovering devices...")
            await oven.discover_devices()

            try:
                device = oven.get_device(args.device)
                print_info(f"Stopping cook on: {device.name}")
            except DeviceNotFoundError:
                print_error(f"Device not found: {args.device}")
                return ExitCode.DEVICE_ERROR.value

            await oven.stop_cook(args.device)
            print_success("Cook stopped")

            return ExitCode.SUCCESS.value

    except CommandError as e:
        print_error(f"Stop command failed: {e}")
        return ExitCode.COMMAND_ERROR.value
    except Exception as e:
        print_error(f"Stop failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def cli_probe(args: argparse.Namespace) -> int:
    """
    CLI: Set probe temperature.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    if not args.device:
        print_error("--device is required for probe command")
        return ExitCode.COMMAND_ERROR.value

    try:
        async with AnovaOven() as oven:
            print_info("Discovering devices...")
            await oven.discover_devices()

            device = oven.get_device(args.device)
            print_info(f"Setting probe on: {device.name}")

            await oven.set_probe(
                args.device,
                target=args.temp,
                temperature_unit=args.unit
            )

            print_success(f"Probe set to {args.temp}°{args.unit}")
            return ExitCode.SUCCESS.value

    except DeviceNotFoundError:
        print_error(f"Device not found: {args.device}")
        return ExitCode.DEVICE_ERROR.value
    except ValueError as e:
        print_error(f"Invalid temperature: {e}")
        return ExitCode.COMMAND_ERROR.value
    except Exception as e:
        print_error(f"Probe command failed: {e}")
        return ExitCode.GENERAL_ERROR.value


# ============================================================================
# Example Commands
# ============================================================================

async def example_basic(args: argparse.Namespace) -> int:
    """Basic usage example"""
    print_header("Basic Usage Example")

    try:
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()

            if not devices:
                print_warning("No devices found")
                return ExitCode.DEVICE_ERROR.value

            device = devices[0]
            print_info(f"Using: {device.name}\n")

            # Example 1: Celsius
            print(f"{Colors.BOLD}Example 1: Cooking with Celsius{Colors.RESET}")
            print_info("Starting cook at 200°C for 60 seconds...")
            await oven.start_cook(device.id, temperature=200, duration=60)
            await asyncio.sleep(2)
            await oven.stop_cook(device.id)
            print_success("Example 1 completed\n")

            # Example 2: Fahrenheit
            print(f"{Colors.BOLD}Example 2: Cooking with Fahrenheit{Colors.RESET}")
            print_info("Starting cook at 350°F for 60 seconds...")
            await oven.start_cook(
                device.id,
                temperature=350,
                temperature_unit="F",
                duration=60
            )
            await asyncio.sleep(2)
            await oven.stop_cook(device.id)
            print_success("Example 2 completed\n")

            print_success("All basic examples completed!")
            return ExitCode.SUCCESS.value

    except Exception as e:
        print_error(f"Example failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def example_advanced(args: argparse.Namespace) -> int:
    """Advanced multi-stage example"""
    print_header("Advanced Multi-Stage Example")

    try:
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()

            if not devices:
                print_warning("No devices found")
                return ExitCode.DEVICE_ERROR.value

            device_id = devices[0].id
            print_info(f"Using: {devices[0].name}\n")

            # Multi-stage: sous vide then sear
            stages = [
                CookStage(
                    temperature=Temperature.from_fahrenheit(131),  # 55°C
                    mode=TemperatureMode.WET,
                    timer=Timer(initial=3600),
                    steam=SteamSettings(
                        mode=SteamMode.STEAM_PERCENTAGE,
                        steam_percentage=100
                    ),
                    title="Sous Vide",
                    description="Low temperature cooking with steam"
                ),
                CookStage(
                    temperature=Temperature.from_celsius(250),  # 482°F
                    mode=TemperatureMode.DRY,
                    timer=Timer(
                        initial=300,
                        start_type=TimerStartType.WHEN_PREHEATED
                    ),
                    heating_elements=HeatingElements(
                        top=True,
                        bottom=True,
                        rear=False
                    ),
                    fan_speed=0,
                    title="Sear",
                    description="High heat searing"
                )
            ]

            print(f"{Colors.BOLD}Multi-stage cook plan:{Colors.RESET}")
            for i, stage in enumerate(stages, 1):
                print(f"  {Colors.CYAN}Stage {i}{Colors.RESET} ({stage.title}): "
                      f"{stage.temperature.celsius:.1f}°C / "
                      f"{stage.temperature.fahrenheit:.1f}°F")
                print(f"    Duration: {stage.timer.initial}s")
                print(f"    Mode: {stage.mode.value}")

            if not args.dry_run:
                print_info("\nStarting multi-stage cook...")
                await oven.start_cook(device_id, stages=stages)
                print_success("Multi-stage cook started!")
                print_info("This is a demonstration - stopping after 5 seconds...")
                await asyncio.sleep(5)
                await oven.stop_cook(device_id)
                print_success("Cook stopped")
            else:
                print_info("Dry run - not actually starting cook")

            return ExitCode.SUCCESS.value

    except Exception as e:
        print_error(f"Advanced example failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def example_presets(args: argparse.Namespace) -> int:
    """Using presets with different units"""
    print_header("Cooking Presets Example")

    try:
        async with AnovaOven() as oven:
            devices = await oven.discover_devices()

            if not devices:
                print_warning("No devices found")
                return ExitCode.DEVICE_ERROR.value

            device_id = devices[0].id
            print_info(f"Using: {devices[0].name}\n")

            # Celsius preset
            print(f"{Colors.BOLD}1. Roasting (Celsius){Colors.RESET}")
            print_info("Roasting at 200°C for 1 minute...")
            await CookingPresets.roast(
                oven, device_id,
                temperature=200,
                duration_minutes=1
            )
            await asyncio.sleep(2)
            await oven.stop_cook(device_id)
            print_success("Roast completed\n")

            # Fahrenheit preset
            print(f"{Colors.BOLD}2. Roasting (Fahrenheit){Colors.RESET}")
            print_info("Roasting at 392°F for 1 minute...")
            await CookingPresets.roast(
                oven, device_id,
                temperature=392,
                temperature_unit="F",
                duration_minutes=1
            )
            await asyncio.sleep(2)
            await oven.stop_cook(device_id)
            print_success("Roast completed\n")

            print_success("All preset examples completed!")
            return ExitCode.SUCCESS.value

    except Exception as e:
        print_error(f"Preset example failed: {e}")
        return ExitCode.GENERAL_ERROR.value


async def example_validation(args: argparse.Namespace) -> int:
    """Demonstrate Pydantic validation"""
    print_header("Validation Examples")

    print(f"{Colors.BOLD}1. Temperature Validation{Colors.RESET}")
    try:
        temp = Temperature(celsius=-300)
        print_error("Should have failed!")
    except ValueError as e:
        print_success(f"Correctly caught invalid temperature: {e}\n")

    print(f"{Colors.BOLD}2. Heating Elements Validation{Colors.RESET}")
    try:
        heating = HeatingElements(top=True, bottom=True, rear=True)
        print_error("Should have failed!")
    except ValueError as e:
        print_success(f"Correctly caught invalid elements: {e}\n")

    print(f"{Colors.BOLD}3. Valid Configuration{Colors.RESET}")
    try:
        stage = CookStage(
            temperature=Temperature.from_celsius(200),
            timer=Timer(initial=1800),
            fan_speed=75,
            rack_position=3,
            title="Test Stage"
        )
        print_success(f"Valid stage created: {stage.title} at {stage.temperature}")
    except ValueError as e:
        print_error(f"Unexpected validation error: {e}")
        return ExitCode.GENERAL_ERROR.value

    return ExitCode.SUCCESS.value


# ============================================================================
# Main Entry Point
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        description="Anova Precision Oven SDK Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s discover
  %(prog)s cook --device abc123 --temp 200 --duration 30
  %(prog)s cook --device abc123 --temp 350 --unit F --duration 45
  %(prog)s stop --device abc123
  %(prog)s probe --device abc123 --temp 65
  %(prog)s example basic
  %(prog)s example advanced --dry-run

For more information, visit: https://github.com/agentcipher/anova-oven-sdk
        """
    )

    # Global arguments
    parser.add_argument(
        '--env',
        choices=['development', 'staging', 'production'],
        help='Environment override'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    subparsers.required = True

    # Discover command
    discover_parser = subparsers.add_parser(
        'discover',
        help='Discover connected devices'
    )
    discover_parser.add_argument(
        '--timeout',
        type=float,
        default=5.0,
        help='Discovery timeout in seconds (default: 5.0)'
    )
    discover_parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )

    # Cook command
    cook_parser = subparsers.add_parser(
        'cook',
        help='Start cooking'
    )
    cook_parser.add_argument(
        '--device',
        required=True,
        help='Device ID'
    )
    cook_parser.add_argument(
        '--temp',
        type=float,
        default=200,
        help='Temperature (default: 200)'
    )
    cook_parser.add_argument(
        '--unit',
        choices=['C', 'F'],
        default='C',
        help='Temperature unit (default: C)'
    )
    cook_parser.add_argument(
        '--duration',
        type=int,
        default=30,
        help='Duration in minutes (default: 30)'
    )
    cook_parser.add_argument(
        '--fan-speed',
        type=int,
        default=100,
        choices=range(0, 101),
        metavar='0-100',
        help='Fan speed percentage (default: 100)'
    )
    cook_parser.add_argument(
        '--vent-open',
        action='store_true',
        help='Open vent during cooking'
    )
    cook_parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait for cook to complete'
    )

    # Stop command
    stop_parser = subparsers.add_parser(
        'stop',
        help='Stop cooking'
    )
    stop_parser.add_argument(
        '--device',
        required=True,
        help='Device ID'
    )

    # Probe command
    probe_parser = subparsers.add_parser(
        'probe',
        help='Set probe temperature'
    )
    probe_parser.add_argument(
        '--device',
        required=True,
        help='Device ID'
    )
    probe_parser.add_argument(
        '--temp',
        type=float,
        required=True,
        help='Probe target temperature'
    )
    probe_parser.add_argument(
        '--unit',
        choices=['C', 'F'],
        default='C',
        help='Temperature unit (default: C)'
    )

    # Example command
    example_parser = subparsers.add_parser(
        'example',
        help='Run examples'
    )
    example_subparsers = example_parser.add_subparsers(
        dest='example_type',
        help='Example type'
    )
    example_subparsers.required = True

    example_subparsers.add_parser('basic', help='Run basic examples')

    advanced_parser = example_subparsers.add_parser(
        'advanced',
        help='Run advanced multi-stage example'
    )
    advanced_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show plan without executing'
    )

    example_subparsers.add_parser('presets', help='Run preset examples')
    example_subparsers.add_parser('validation', help='Run validation examples')

    return parser


async def main_async(args: argparse.Namespace) -> int:
    """
    Main async entry point.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code
    """
    # Set environment if specified
    if args.env:
        os.environ['ANOVA_ENV'] = args.env
        print_info(f"Environment set to: {args.env}")

    # Set logging level
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Dispatch to appropriate command handler
    try:
        if args.command == 'discover':
            return await cli_discover(args)
        elif args.command == 'cook':
            return await cli_cook(args)
        elif args.command == 'stop':
            return await cli_stop(args)
        elif args.command == 'probe':
            return await cli_probe(args)
        elif args.command == 'example':
            if args.example_type == 'basic':
                return await example_basic(args)
            elif args.example_type == 'advanced':
                return await example_advanced(args)
            elif args.example_type == 'presets':
                return await example_presets(args)
            elif args.example_type == 'validation':
                return await example_validation(args)

        print_error(f"Unknown command: {args.command}")
        return ExitCode.COMMAND_ERROR.value

    except ConfigurationError as e:
        print_error(f"Configuration Error: {e}")
        print_info("\nMake sure you have:")
        print("  1. settings.yaml with configuration")
        print("  2. .secrets.yaml with your token")
        print("  3. Or ANOVA_TOKEN environment variable set")
        return ExitCode.CONFIG_ERROR.value

    except DeviceNotFoundError as e:
        print_error(f"Device Error: {e}")
        print_info("Run 'discover' command to see available devices")
        return ExitCode.DEVICE_ERROR.value

    except KeyboardInterrupt:
        print_warning("\n\nInterrupted by user")
        return ExitCode.KEYBOARD_INTERRUPT.value

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return ExitCode.GENERAL_ERROR.value


def main() -> None:
    """Main entry point"""
    print_header("Anova Precision Oven SDK CLI")

    parser = create_parser()

    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        Colors.disable()

    # Run async main and exit with return code
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
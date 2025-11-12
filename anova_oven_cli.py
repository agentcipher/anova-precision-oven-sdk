#!/usr/bin/env python3
# ============================================================================
# Command Line Interface
# ============================================================================
"""
Anova Oven CLI - Command-line interface for controlling Anova Precision Ovens.

Usage:
    # Discover devices
    python anova_oven_cli.py discover

    # List available recipes
    python anova_oven_cli.py recipes list

    # Show recipe details
    python anova_oven_cli.py recipes show perfect_toast_v1

    # Start cooking with a recipe
    python anova_oven_cli.py cook --device <device_id> --recipe perfect_toast_v1

    # Start simple cook
    python anova_oven_cli.py cook --device <device_id> --temp 200 --duration 1800

    # Stop cooking
    python anova_oven_cli.py stop --device <device_id>
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional
import json

from anova_oven_sdk.oven import AnovaOven
from anova_oven_sdk.models import RecipeLibrary
from anova_oven_sdk.settings import settings
from anova_oven_sdk.exceptions import AnovaError


class AnovaOvenCLI:
    """Command-line interface for Anova Oven SDK."""

    def __init__(self, recipe_file: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize CLI.

        Args:
            recipe_file: Path to recipes YAML file
            environment: Environment name (dev/staging/production)
        """
        self.recipe_file = recipe_file or self._find_recipe_file()
        self.environment = environment
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
                print(f"Warning: Recipe file not found: {self.recipe_file}")
                self.library = RecipeLibrary()
        return self.library

    async def cmd_discover(self, args: argparse.Namespace) -> int:
        """
        Discover connected devices.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        try:
            async with AnovaOven(environment=self.environment) as oven:
                if not args.json:
                    print("Discovering devices...")

                devices = await oven.discover_devices(timeout=args.timeout)

                if not devices:
                    if not args.json:
                        print("No devices found.")
                    return 1

                if args.json:
                    # JSON output only - clean, parseable
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
                    # Human-readable output
                    print(f"\nFound {len(devices)} device(s):\n")
                    for device in devices:
                        print(f"  Name:    {device.name}")
                        print(f"  ID:      {device.id}")
                        print(f"  Type:    {device.oven_version.value}")
                        print(f"  State:   {device.state.value}")
                        if device.current_temperature:
                            print(f"  Temp:    {device.current_temperature}°C")
                        print()

                return 0

        except AnovaError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    async def cmd_recipes_list(self, args: argparse.Namespace) -> int:
        """
        List available recipes.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        try:
            library = self._load_recipes()

            if not library.recipes:
                print("No recipes found.")
                return 1

            if args.json:
                output = library.list_recipes_with_info()
                print(json.dumps(output, indent=2))
            else:
                print(f"Available recipes from {self.recipe_file}:\n")
                for info in library.list_recipes_with_info():
                    print(f"  {info['id']}")
                    print(f"    Name:         {info['name']}")
                    print(f"    Description:  {info['description']}")
                    print(f"    Stages:       {info['stages']}")
                    print(f"    Oven Version: {info['oven_version']}")
                    print()

            return 0

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    async def cmd_recipes_show(self, args: argparse.Namespace) -> int:
        """
        Show recipe details.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        try:
            library = self._load_recipes()
            recipe = library.get_recipe(args.recipe_id)

            if args.json:
                print(json.dumps(recipe.to_dict(), indent=2))
            else:
                print(f"Recipe: {recipe.name}")
                print(f"ID: {recipe.recipe_id}")
                print(f"Description: {recipe.description}")
                print(f"Oven Version: {recipe.oven_version.value if recipe.oven_version else 'any'}")
                print(f"\nStages ({len(recipe.stages)}):\n")

                for i, stage in enumerate(recipe.stages, 1):
                    print(f"  Stage {i}: {stage.name}")
                    temp_config = stage.temperature
                    print(f"    Temperature: {temp_config['value']}°{temp_config.get('temperature_unit', 'C')}")
                    print(f"    Mode: {temp_config.get('mode', 'DRY')}")

                    if stage.timer:
                        mins = stage.timer['seconds'] // 60
                        secs = stage.timer['seconds'] % 60
                        print(f"    Timer: {mins}m {secs}s")

                    elements = []
                    if stage.heating_elements.get('top'):
                        elements.append('top')
                    if stage.heating_elements.get('bottom'):
                        elements.append('bottom')
                    if stage.heating_elements.get('rear'):
                        elements.append('rear')
                    print(f"    Heating: {', '.join(elements)}")
                    print(f"    Fan Speed: {stage.fan_speed}%")

                    if stage.steam:
                        # Format steam settings in a user-friendly way
                        steam_parts = []

                        if 'relative_humidity' in stage.steam:
                            steam_parts.append(f"{stage.steam['relative_humidity']}% relative humidity")

                        if 'steam_percentage' in stage.steam:
                            steam_parts.append(f"{stage.steam['steam_percentage']}% steam")

                        if steam_parts:
                            print(f"    Steam: {', '.join(steam_parts)}")
                        else:
                            print(f"    Steam: enabled")

                    print()

            return 0

        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    async def cmd_cook(self, args: argparse.Namespace) -> int:
        """
        Start cooking.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        try:
            async with AnovaOven(environment=self.environment) as oven:
                # Discover devices to validate device_id
                devices = await oven.discover_devices(timeout=2.0)
                device_ids = [d.id for d in devices]

                if args.device not in device_ids:
                    print(f"Error: Device '{args.device}' not found.", file=sys.stderr)
                    print(f"Available devices: {', '.join(device_ids)}")
                    return 1

                if args.recipe:
                    # Cook with recipe
                    library = self._load_recipes()
                    recipe = library.get_recipe(args.recipe)

                    print(f"Starting recipe: {recipe.name}")
                    print(f"Device: {args.device}")
                    print(f"Stages: {len(recipe.stages)}")

                    # Validate recipe for device
                    device = oven.get_device(args.device)
                    recipe.validate_for_oven(device.oven_version)

                    # Convert to cook stages
                    stages = recipe.to_cook_stages()

                    # Start cook
                    await oven.start_cook(args.device, stages=stages)

                    print("✓ Cook started successfully")

                elif args.temp is not None:
                    # Simple cook
                    print(f"Starting simple cook:")
                    print(f"  Device: {args.device}")
                    print(f"  Temperature: {args.temp}°{args.unit}")
                    if args.duration:
                        mins = args.duration // 60
                        secs = args.duration % 60
                        print(f"  Duration: {mins}m {secs}s")

                    await oven.start_cook(
                        device_id=args.device,
                        temperature=args.temp,
                        temperature_unit=args.unit,
                        duration=args.duration,
                        fan_speed=args.fan_speed
                    )

                    print("✓ Cook started successfully")

                else:
                    print("Error: Provide either --recipe or --temp", file=sys.stderr)
                    return 1

                return 0

        except AnovaError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    async def cmd_stop(self, args: argparse.Namespace) -> int:
        """
        Stop cooking.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        try:
            async with AnovaOven(environment=self.environment) as oven:
                # Discover devices to validate device_id
                devices = await oven.discover_devices(timeout=2.0)
                device_ids = [d.id for d in devices]

                if args.device not in device_ids:
                    print(f"Error: Device '{args.device}' not found.", file=sys.stderr)
                    print(f"Available devices: {', '.join(device_ids)}")
                    return 1

                print(f"Stopping cook on device: {args.device}")
                await oven.stop_cook(args.device)

                print("✓ Cook stopped successfully")
                return 0

        except AnovaError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Anova Oven CLI - Control your Anova Precision Oven",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--recipe-file',
        type=str,
        help='Path to recipes YAML file (default: auto-discover)'
    )

    parser.add_argument(
        '--env',
        '--environment',
        type=str,
        choices=['dev', 'staging', 'production'],
        help='Environment (dev/staging/production)'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover connected devices')
    discover_parser.add_argument(
        '--timeout',
        type=float,
        default=5.0,
        help='Discovery timeout in seconds (default: 5.0)'
    )
    discover_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Recipes command
    recipes_parser = subparsers.add_parser('recipes', help='Manage recipes')
    recipes_subparsers = recipes_parser.add_subparsers(dest='recipes_command')

    # Recipes list
    recipes_list_parser = recipes_subparsers.add_parser('list', help='List available recipes')
    recipes_list_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Recipes show
    recipes_show_parser = recipes_subparsers.add_parser('show', help='Show recipe details')
    recipes_show_parser.add_argument(
        'recipe_id',
        type=str,
        help='Recipe ID to show'
    )
    recipes_show_parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    # Cook command
    cook_parser = subparsers.add_parser('cook', help='Start cooking')
    cook_parser.add_argument(
        '--device',
        type=str,
        required=True,
        help='Device ID'
    )
    cook_parser.add_argument(
        '--recipe',
        type=str,
        help='Recipe ID to cook'
    )
    cook_parser.add_argument(
        '--temp',
        '--temperature',
        type=float,
        help='Temperature for simple cook'
    )
    cook_parser.add_argument(
        '--unit',
        type=str,
        choices=['C', 'F'],
        default='C',
        help='Temperature unit (default: C)'
    )
    cook_parser.add_argument(
        '--duration',
        type=int,
        help='Duration in seconds'
    )
    cook_parser.add_argument(
        '--fan-speed',
        type=int,
        default=100,
        help='Fan speed percentage (default: 100)'
    )

    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop cooking')
    stop_parser.add_argument(
        '--device',
        type=str,
        required=True,
        help='Device ID'
    )

    return parser


async def async_main() -> int:
    """Async main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = AnovaOvenCLI(
        recipe_file=args.recipe_file,
        environment=args.env
    )

    # Route to appropriate command
    if args.command == 'discover':
        return await cli.cmd_discover(args)

    elif args.command == 'recipes':
        if args.recipes_command == 'list':
            return await cli.cmd_recipes_list(args)
        elif args.recipes_command == 'show':
            return await cli.cmd_recipes_show(args)
        else:
            parser.parse_args(['recipes', '--help'])
            return 1

    elif args.command == 'cook':
        return await cli.cmd_cook(args)

    elif args.command == 'stop':
        return await cli.cmd_stop(args)

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
        return 1


if __name__ == '__main__':
    sys.exit(main())
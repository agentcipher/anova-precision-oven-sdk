# Changelog

## [2026.06.0]
- Added `current`/`setpoint` temperature readings to `ProbeState` for the temperature probe
- Added `start_type` (timer start trigger) to `TimerState`
- Added `CookData`/`CookStageInfo` models exposing active cook session info (cook ID, origin source, stages, rack position)
- Exposed active cook session data via `Device.cook` and `Device.rack_position`
- Added `setpoint` to `SteamGeneratorState`, fixing dropped `relativeHumidity.setpoint` data
- Added `steam_percentage` (`steamPercentage`) to `SteamGenerators`, previously silently dropped
- Added `step_type` (`stepType`) to `CookStageInfo`
- Exposed the active cook session's current stage via `Device.current_stage` (first entry in `stages`)

## [2025.11.0] - 2025-11-03
- Initial release
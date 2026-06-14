# Changelog

## [2026.06.2]
- Fixed `Device.cook` never being populated for V1 ovens
- For V1 ovens, `Device.current_stage`, `Device.current_stage_index`, and `Device.total_stage_count` are now derived directly from `cook.active_stage_index` and `cook.stages` -- `register_cook_plan`/`stages[0]`-based resolution remains as a fallback for V2 ovens, where this nested `cook` shape is unconfirmed

## [2026.06.1]
- Added `Device.total_stage_count` and `Device.current_stage_index` for "stage X of Y" cook progress. For cooks started via `AnovaOven.start_cook()`, these are resolved by matching the live `current_stage.id` against the ordered stage plan recorded at `CMD_APO_START` time (`Device.register_cook_plan`); they return `None` for cooks started outside this SDK instance (e.g. the Anova app)
- Added debug logging of cook session stage counts and unrecognized (`model_extra`) fields on `EVENT_APO_STATE` updates, to help verify `cook.stages` semantics (full plan vs. shrinking remainder) against a real multi-stage cook

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
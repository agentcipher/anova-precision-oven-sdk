import pytest
from pydantic import ValidationError
from anova_oven_sdk.response_models import (
    SteamGenerators, ApoStateResponse, SteamGeneratorState,
    ProbeState, TimerState, CookData, Nodes,
)

class TestSteamGenerators:
    """Test SteamGenerators model validation."""

    def test_steam_percentage_mode_missing_relative_humidity(self):
        """Test steam-percentage mode allows missing relativeHumidity."""
        data = {
            "mode": "steam-percentage",
            "evaporator": {"watts": 0, "failed": False, "overheated": False},
            "boiler": {"watts": 0, "failed": False, "overheated": False},
            "steamPercentage": {"setpoint": 100}
        }
        # Should not raise
        model = SteamGenerators.model_validate(data)
        assert model.mode == "steam-percentage"
        assert model.relative_humidity is None

    def test_steam_percentage_setpoint_and_current(self):
        """steamPercentage setpoint/current are exposed, not silently dropped."""
        data = {
            "mode": "steam-percentage",
            "evaporator": {"watts": 0, "failed": False, "overheated": False},
            "boiler": {"watts": 0, "failed": False, "overheated": False},
            "steamPercentage": {"setpoint": 100.0, "current": 0.0}
        }
        model = SteamGenerators.model_validate(data)
        assert model.steam_percentage.setpoint == 100.0
        assert model.steam_percentage.current == 0.0

    def test_relative_humidity_mode_valid(self):
        """Test relative-humidity mode with valid data."""
        data = {
            "mode": "relative-humidity",
            "relativeHumidity": {"setpoint": 50, "current": 45},
            "evaporator": {"watts": 0, "failed": False, "overheated": False},
            "boiler": {"watts": 0, "failed": False, "overheated": False}
        }
        model = SteamGenerators.model_validate(data)
        assert model.mode == "relative-humidity"
        assert model.relative_humidity is not None
        assert model.relative_humidity.setpoint == 50
        assert model.relative_humidity.current == 45

    def test_relative_humidity_mode_missing_field(self):
        """Test relative-humidity mode raises error if field missing."""
        data = {
            "mode": "relative-humidity",
            # Missing relativeHumidity
            "evaporator": {"watts": 0, "failed": False, "overheated": False},
            "boiler": {"watts": 0, "failed": False, "overheated": False}
        }
        with pytest.raises(ValueError, match="relativeHumidity is required"):
            SteamGenerators.model_validate(data)

class TestProbeState:
    """Test ProbeState model validation."""

    def test_disconnected_probe_without_readings(self):
        """A disconnected probe may report only 'connected'."""
        probe = ProbeState.model_validate({"connected": False})
        assert probe.connected is False
        assert probe.current is None
        assert probe.setpoint is None

    def test_connected_probe_with_current_and_setpoint(self):
        """A connected probe reports current and setpoint temperatures."""
        probe = ProbeState.model_validate({
            "connected": True,
            "current": {"celsius": 55.0, "fahrenheit": 131.0},
            "setpoint": {"celsius": 60.0, "fahrenheit": 140.0},
        })
        assert probe.current["celsius"] == 55.0
        assert probe.setpoint["fahrenheit"] == 140.0


class TestTimerState:
    """Test TimerState model validation."""

    def test_timer_without_start_type(self):
        """Older payloads may not include startType."""
        timer = TimerState.model_validate({"mode": "idle", "initial": 0, "current": 0})
        assert timer.start_type is None

    def test_timer_with_start_type(self):
        """Timer reports its configured start type."""
        timer = TimerState.model_validate({
            "mode": "running", "initial": 600, "current": 599, "startType": "when-preheated"
        })
        assert timer.start_type == "when-preheated"


class TestCookData:
    """Test CookData / CookStageInfo model validation."""

    def test_cook_data_with_stages(self):
        """Cook session data exposes cook ID, origin, and stage rack position."""
        cook = CookData.model_validate({
            "cookId": "cook-1",
            "originSource": "app",
            "type": "v1",
            "stages": [
                {"id": "stage-1", "stepType": "stage", "type": "cook", "title": "Roast", "rackPosition": 4, "userActionRequired": False}
            ],
        })
        assert cook.cook_id == "cook-1"
        assert cook.origin_source == "app"
        assert cook.stages[0].rack_position == 4
        assert cook.stages[0].step_type == "stage"

    def test_cook_data_optional(self):
        """Cook data is optional when no cook session is active."""
        cook = CookData.model_validate({})
        assert cook.cook_id is None
        assert cook.stages is None

    def test_cook_data_preserves_unrecognized_fields(self):
        """
        extra='allow' surfaces fields the typed models don't recognize yet via
        model_extra. This matters for the open question of whether the API
        sends an explicit stage index/count (e.g. currentStageIndex,
        totalStages) anywhere in the cook payload - if it does, it will show
        up here rather than being silently dropped.
        """
        cook = CookData.model_validate({
            "cookId": "cook-1",
            "stages": [
                {"id": "stage-1", "title": "Roast", "currentStageIndex": 1, "totalStages": 3}
            ],
            "currentStageIndex": 1,
            "totalStages": 3,
        })
        assert cook.model_extra == {"currentStageIndex": 1, "totalStages": 3}
        assert cook.stages[0].model_extra == {"currentStageIndex": 1, "totalStages": 3}


class TestApoStateResponse:
    """Test ApoStateResponse with raw payloads."""

    def test_v1_payload_regression(self):
        """Test the payload that caused the regression."""
        payload = {
            'command': 'EVENT_APO_STATE',
            'payload': {
                'cookerId': '01239de9c81b16c301',
                'type': 'oven_v1',
                'state': {
                    'nodes': {
                        'temperatureBulbs': {
                            'dry': {'current': {'fahrenheit': 155.52, 'celsius': 68.62}, 'setpoint': {'fahrenheit': 482, 'celsius': 250}},
                            'dryBottom': {'overheated': False, 'current': {'celsius': 64.02, 'fahrenheit': 147.24}},
                            'wet': {'current': {'celsius': 48.6, 'fahrenheit': 119.49}, 'doseFailed': False, 'dosed': False},
                            'dryTop': {'current': {'celsius': 68.62, 'fahrenheit': 155.52}, 'overheated': False},
                            'mode': 'dry'
                        },
                        'temperatureProbe': {'connected': False},
                        'steamGenerators': {
                            'boiler': {'watts': 0, 'descaleRequired': False, 'overheated': False, 'failed': False, 'celsius': 22.95, 'dosed': False},
                            'steamPercentage': {'setpoint': 100},
                            'evaporator': {'watts': 0, 'overheated': False, 'failed': False, 'celsius': 22.63},
                            'mode': 'steam-percentage'
                        },
                        'door': {'closed': True},
                        'lamp': {'preference': 'on', 'on': True, 'failed': False},
                        'userInterfaceCircuit': {'communicationFailed': False},
                        'timer': {'current': 239, 'initial': 240, 'mode': 'running'},
                        'heatingElements': {
                            'bottom': {'failed': False, 'watts': 0, 'on': False},
                            'rear': {'watts': 0, 'on': True, 'failed': False},
                            'top': {'failed': False, 'on': False, 'watts': 1600}
                        },
                        'waterTank': {'empty': False},
                        'vent': {'open': False},
                        'fan': {'failed': False, 'speed': 100}
                    }
                }
            }
        }
        
        # Simulate V1 nested validation
        nested_state = payload['payload']['state']
        constructed_payload = {'command': 'EVENT_APO_STATE', 'payload': nested_state}
        
        # Should pass validation
        response = ApoStateResponse.model_validate(constructed_payload)
        assert response.payload.nodes.steam_generators.mode == "steam-percentage"

    def test_v1_payload_with_cook_and_probe_data(self):
        """V1 nested payload with an active cook session and a connected probe."""
        nested_state = {
            'cookId': 'cook-123',
            'originSource': 'app',
            'type': 'v1',
            'stages': [
                {'id': 'stage-1', 'type': 'cook', 'title': 'Roast', 'rackPosition': 4}
            ],
            'nodes': {
                'temperatureBulbs': {
                    'dry': {'current': {'celsius': 68.62, 'fahrenheit': 155.52}},
                    'dryBottom': {'current': {'celsius': 64.02, 'fahrenheit': 147.24}},
                    'wet': {'current': {'celsius': 48.6, 'fahrenheit': 119.49}},
                    'dryTop': {'current': {'celsius': 68.62, 'fahrenheit': 155.52}},
                    'mode': 'dry'
                },
                'temperatureProbe': {
                    'connected': True,
                    'current': {'celsius': 55.0, 'fahrenheit': 131.0},
                    'setpoint': {'celsius': 60.0, 'fahrenheit': 140.0},
                },
                'steamGenerators': {'mode': 'idle', 'evaporator': {}, 'boiler': {}},
                'door': {'closed': True},
                'lamp': {'preference': 'on', 'on': True, 'failed': False},
                'userInterfaceCircuit': {'communicationFailed': False},
                'timer': {'current': 599, 'initial': 600, 'mode': 'running', 'startType': 'when-preheated'},
                'heatingElements': {
                    'bottom': {'failed': False, 'watts': 0, 'on': False},
                    'rear': {'watts': 0, 'on': True, 'failed': False},
                    'top': {'failed': False, 'on': False, 'watts': 1600}
                },
                'waterTank': {'empty': False},
                'vent': {'open': False},
                'fan': {'failed': False, 'speed': 100}
            }
        }

        constructed_payload = {'command': 'EVENT_APO_STATE', 'payload': nested_state}
        response = ApoStateResponse.model_validate(constructed_payload)

        payload = response.payload
        assert payload.cook_id == 'cook-123'
        assert payload.stages[0].rack_position == 4
        assert payload.nodes.temperature_probe.current['celsius'] == 55.0
        assert payload.nodes.timer.start_type == 'when-preheated'

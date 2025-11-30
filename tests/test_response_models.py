import pytest
from pydantic import ValidationError
from anova_oven_sdk.response_models import SteamGenerators, ApoStateResponse, SteamGeneratorState

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

"""Unit tests for new API endpoints (Official Home Assistant REST API)."""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient


class TestEntityStateEndpoints:
    """Tests for entity state API endpoints."""

    @pytest.mark.asyncio
    async def test_get_states_without_entity_id(self):
        """Test get_states returns all entities when no entity_id specified."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/states",
                status=200,
                body='[{"entity_id": "light.living_room", "state": "on"}, {"entity_id": "sensor.temperature", "state": "22.5"}]',
            )

            result = await client.get_states()

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["entity_id"] == "light.living_room"
            assert result[1]["entity_id"] == "sensor.temperature"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_states_with_entity_id(self):
        """Test get_states returns specific entity when entity_id specified."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/states/light.living_room",
                status=200,
                body='{"entity_id": "light.living_room", "state": "on", "attributes": {"brightness": 255}}',
            )

            result = await client.get_states("light.living_room")

            assert isinstance(result, dict)
            assert result["entity_id"] == "light.living_room"
            assert result["state"] == "on"
            assert result["attributes"]["brightness"] == 255

        await client.close()


class TestServiceCallEndpoints:
    """Tests for service call API endpoints."""

    @pytest.mark.asyncio
    async def test_call_service_without_service_data(self):
        """Test call_service works without service_data parameter."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/services/light/turn_off",
                status=200,
                body='[{"entity_id": "light.living_room", "state": "off"}]',
            )

            result = await client.call_service("light", "turn_off")

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["entity_id"] == "light.living_room"
            assert result[0]["state"] == "off"

        await client.close()

    @pytest.mark.asyncio
    async def test_call_service_with_service_data(self):
        """Test call_service works with service_data parameter."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/services/light/turn_on",
                status=200,
                body='[{"entity_id": "light.living_room", "state": "on", "attributes": {"brightness": 128}}]',
            )

            result = await client.call_service(
                "light",
                "turn_on",
                service_data={"entity_id": "light.living_room", "brightness": 128},
            )

            assert isinstance(result, list)
            assert result[0]["attributes"]["brightness"] == 128

        await client.close()

    @pytest.mark.asyncio
    async def test_call_service_with_empty_service_data(self):
        """Test call_service works with empty service_data dict."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/services/automation/trigger",
                status=200,
                body="[]",
            )

            result = await client.call_service("automation", "trigger", service_data={})

            assert isinstance(result, list)

        await client.close()


class TestTemplateEndpoints:
    """Tests for template rendering API endpoints."""

    @pytest.mark.asyncio
    async def test_render_template_with_valid_template(self):
        """Test render_template with valid Jinja2 template."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post("http://ha.local:8123/api/template", status=200, body="22.5")

            result = await client.render_template('{{ states("sensor.temperature") }}')

            assert result == "22.5"

        await client.close()

    @pytest.mark.asyncio
    async def test_render_template_with_complex_template(self):
        """Test render_template with complex template logic."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/template",
                status=200,
                body="The temperature is 22.5°C",
            )

            result = await client.render_template(
                'The temperature is {{ states("sensor.temperature") }}°C'
            )

            assert "22.5" in result

        await client.close()


class TestHistoryEndpoints:
    """Tests for history API endpoints."""

    @pytest.mark.asyncio
    async def test_get_history_with_various_parameter_combinations(self):
        """Test get_history with different parameter combinations."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        # Test 1: No parameters
        with aioresponses() as m:
            m.get("http://ha.local:8123/api/history/period", status=200, body="[[]]")

            result = await client.get_history()
            assert isinstance(result, list)

        # Test 2: With entity_ids only
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/history/period?filter_entity_id=sensor.temperature",
                status=200,
                body='[[{"entity_id": "sensor.temperature", "state": "22.5"}]]',
            )

            result = await client.get_history(entity_ids=["sensor.temperature"])
            assert isinstance(result, list)
            assert len(result) > 0

        # Test 3: With start_time and entity_ids
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/history/period/2024-01-15T10:00:00?filter_entity_id=sensor.temperature",
                status=200,
                body='[[{"entity_id": "sensor.temperature", "state": "22.5"}]]',
            )

            result = await client.get_history(
                start_time="2024-01-15T10:00:00", entity_ids=["sensor.temperature"]
            )
            assert isinstance(result, list)

        await client.close()


class TestConfigEndpoints:
    """Tests for configuration API endpoints."""

    @pytest.mark.asyncio
    async def test_get_config_returns_expected_fields(self):
        """Test get_config returns expected configuration fields."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/config",
                status=200,
                body="""{
                    "version": "2024.1.0",
                    "location_name": "Home",
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "time_zone": "America/Los_Angeles",
                    "unit_system": {"length": "km", "mass": "g", "temperature": "°C"},
                    "components": ["automation", "light", "sensor"]
                }""",
            )

            result = await client.get_config()

            assert "version" in result
            assert "location_name" in result
            assert "time_zone" in result
            assert "unit_system" in result
            assert "components" in result
            assert result["version"] == "2024.1.0"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_config_handles_missing_optional_fields(self):
        """Test get_config handles cases where optional fields may be missing."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Minimal config response
            m.get(
                "http://ha.local:8123/api/config",
                status=200,
                body='{"version": "2024.1.0"}',
            )

            result = await client.get_config()

            assert "version" in result
            # Should not raise error if optional fields are missing

        await client.close()


class TestEventEndpoints:
    """Tests for event listing API endpoints."""

    @pytest.mark.asyncio
    async def test_list_events_with_empty_list(self):
        """Test list_events handles empty event list."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get("http://ha.local:8123/api/events", status=200, body="[]")

            result = await client.list_events()

            assert isinstance(result, list)
            assert len(result) == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_list_events_with_populated_list(self):
        """Test list_events with populated event list."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/events",
                status=200,
                body='[{"event": "state_changed", "listener_count": 5}, {"event": "service_registered", "listener_count": 2}]',
            )

            result = await client.list_events()

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["event"] == "state_changed"
            assert result[0]["listener_count"] == 5

        await client.close()


class TestServiceListEndpoints:
    """Tests for service listing API endpoints."""

    @pytest.mark.asyncio
    async def test_list_services_returns_proper_structure(self):
        """Test list_services returns services organized by domain."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/services",
                status=200,
                body="""{
                    "light": {
                        "turn_on": {"name": "Turn on", "description": "Turn on lights"},
                        "turn_off": {"name": "Turn off", "description": "Turn off lights"}
                    },
                    "switch": {
                        "toggle": {"name": "Toggle", "description": "Toggle switch"}
                    }
                }""",
            )

            result = await client.list_services()

            assert isinstance(result, dict)
            assert "light" in result
            assert "switch" in result
            assert "turn_on" in result["light"]
            assert "turn_off" in result["light"]

        await client.close()

    @pytest.mark.asyncio
    async def test_list_services_includes_field_information(self):
        """Test list_services includes service field information when available."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/services",
                status=200,
                body="""{
                    "light": {
                        "turn_on": {
                            "name": "Turn on",
                            "description": "Turn on lights",
                            "fields": {
                                "entity_id": {"description": "Entity ID", "example": "light.living_room"},
                                "brightness": {"description": "Brightness (0-255)", "example": 255}
                            }
                        }
                    }
                }""",
            )

            result = await client.list_services()

            assert "fields" in result["light"]["turn_on"]
            assert "entity_id" in result["light"]["turn_on"]["fields"]
            assert "brightness" in result["light"]["turn_on"]["fields"]

        await client.close()


class TestConfigCheckEndpoints:
    """Tests for configuration validation API endpoints."""

    @pytest.mark.asyncio
    async def test_check_config_with_valid_response(self):
        """Test check_config with valid configuration response."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/config/core/check_config",
                status=200,
                body='{"result": "valid", "errors": null}',
            )

            result = await client.check_config()

            assert isinstance(result, dict)
            assert result["result"] == "valid"

        await client.close()

    @pytest.mark.asyncio
    async def test_check_config_with_invalid_response(self):
        """Test check_config with invalid configuration response."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/config/core/check_config",
                status=200,
                body='{"result": "invalid", "errors": "Invalid config for [automation]: required key not provided"}',
            )

            result = await client.check_config()

            assert isinstance(result, dict)
            assert result["result"] == "invalid"
            assert "errors" in result
            assert "automation" in result["errors"]

        await client.close()

    @pytest.mark.asyncio
    async def test_check_config_handles_unavailable(self):
        """Test check_config handles cases where config checking is unavailable."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Config check might return 404 if not available
            m.post(
                "http://ha.local:8123/api/config/core/check_config",
                status=404,
                body='{"message": "Config check not available"}',
            )

            from ha_dev_tools.connection.api import HAAPIError

            with pytest.raises(HAAPIError):
                await client.check_config()

        await client.close()

"""Unit tests for validate_entities method in HAAPIClient.

These tests verify entity validation functionality with specific examples and edge cases.
"""

import asyncio

import pytest
from aioresponses import aioresponses

from ha_config_manager.connection.api import HAAPIClient, HAAPIError


# Disable Home Assistant test framework for these tests
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skip_ha_fixtures
]


class TestValidateEntities:
    """Unit tests for HAAPIClient.validate_entities method."""
    
    async def test_all_entities_exist(self):
        """Test validation when all entities exist in HA."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Entity IDs to validate
        entity_ids = ['sensor.temperature', 'light.living_room', 'switch.bedroom']
        
        # Mock /api/states response with all entities
        mock_states = [
            {'entity_id': 'sensor.temperature', 'state': 'on', 'attributes': {}},
            {'entity_id': 'light.living_room', 'state': 'on', 'attributes': {}},
            {'entity_id': 'switch.bedroom', 'state': 'off', 'attributes': {}},
            {'entity_id': 'sensor.humidity', 'state': '50', 'attributes': {}}  # Extra entity
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities(entity_ids)
            
            # All entities should be in existing list
            assert set(existing) == set(entity_ids)
            assert missing == []
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_all_entities_missing(self):
        """Test validation when all entities are missing from HA."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Entity IDs to validate
        entity_ids = ['sensor.nonexistent', 'light.invalid', 'switch.missing']
        
        # Mock /api/states response with different entities
        mock_states = [
            {'entity_id': 'sensor.temperature', 'state': 'on', 'attributes': {}},
            {'entity_id': 'light.living_room', 'state': 'on', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities(entity_ids)
            
            # All entities should be in missing list
            assert existing == []
            assert set(missing) == set(entity_ids)
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_mixed_existing_missing(self):
        """Test validation with mixed existing and missing entities."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Entity IDs to validate
        entity_ids = [
            'sensor.temperature',  # exists
            'light.invalid',       # missing
            'switch.bedroom',      # exists
            'sensor.nonexistent'   # missing
        ]
        
        # Mock /api/states response
        mock_states = [
            {'entity_id': 'sensor.temperature', 'state': '22.5', 'attributes': {}},
            {'entity_id': 'switch.bedroom', 'state': 'on', 'attributes': {}},
            {'entity_id': 'light.living_room', 'state': 'off', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities(entity_ids)
            
            # Check correct partitioning
            assert set(existing) == {'sensor.temperature', 'switch.bedroom'}
            assert set(missing) == {'light.invalid', 'sensor.nonexistent'}
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_empty_entity_list(self):
        """Test validation with empty entity list."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Mock /api/states response
        mock_states = [
            {'entity_id': 'sensor.temperature', 'state': '22.5', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities([])
            
            # Both lists should be empty
            assert existing == []
            assert missing == []
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_api_error_response(self):
        """Test validation when API returns an error."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        entity_ids = ['sensor.temperature']
        
        # Mock API error response
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=500,
                body="Internal Server Error"
            )
            
            # Should raise HAAPIError
            with pytest.raises(HAAPIError) as exc_info:
                await client.validate_entities(entity_ids)
            
            error = exc_info.value
            assert error.status_code == 500
            assert error.error_code == "SERVER_ERROR"
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_api_error_404(self):
        """Test validation when API returns 404 Not Found."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        entity_ids = ['sensor.temperature']
        
        # Mock 404 error response
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=404,
                body="Not Found"
            )
            
            # Should raise HAAPIError
            with pytest.raises(HAAPIError) as exc_info:
                await client.validate_entities(entity_ids)
            
            error = exc_info.value
            assert error.status_code == 404
            assert error.error_code == "RESOURCE_NOT_FOUND"
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_malformed_api_response(self):
        """Test validation when API returns malformed JSON."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        entity_ids = ['sensor.temperature']
        
        # Mock malformed response (invalid JSON)
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                body="This is not valid JSON"
            )
            
            # Should raise HAAPIError due to JSON parsing failure
            with pytest.raises(HAAPIError) as exc_info:
                await client.validate_entities(entity_ids)
            
            error = exc_info.value
            assert "JSON" in str(error) or "parse" in str(error).lower()
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_malformed_state_objects(self):
        """Test validation when API returns states without entity_id field."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        entity_ids = ['sensor.temperature']
        
        # Mock response with malformed state objects (missing entity_id)
        mock_states = [
            {'state': 'on', 'attributes': {}},  # Missing entity_id
            {'entity_id': 'sensor.temperature', 'state': '22.5', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            # Should raise HAAPIError or KeyError due to missing entity_id
            with pytest.raises((HAAPIError, KeyError)):
                await client.validate_entities(entity_ids)
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_order_preservation(self):
        """Test that entity order is preserved in results."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Entity IDs in specific order
        entity_ids = [
            'sensor.a',
            'sensor.b',
            'sensor.c',
            'sensor.d',
            'sensor.e'
        ]
        
        # Mock states with only some entities (in different order)
        mock_states = [
            {'entity_id': 'sensor.e', 'state': 'on', 'attributes': {}},
            {'entity_id': 'sensor.b', 'state': 'on', 'attributes': {}},
            {'entity_id': 'sensor.a', 'state': 'on', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities(entity_ids)
            
            # Check order is preserved from input
            assert existing == ['sensor.a', 'sensor.b', 'sensor.e']
            assert missing == ['sensor.c', 'sensor.d']
            
        await client.close()
        await asyncio.sleep(0.1)
    
    async def test_duplicate_entity_ids(self):
        """Test validation with duplicate entity IDs in input."""
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)
        
        # Entity IDs with duplicates
        entity_ids = [
            'sensor.temperature',
            'sensor.temperature',  # duplicate
            'light.living_room'
        ]
        
        # Mock states
        mock_states = [
            {'entity_id': 'sensor.temperature', 'state': '22.5', 'attributes': {}},
            {'entity_id': 'light.living_room', 'state': 'on', 'attributes': {}}
        ]
        
        with aioresponses() as mock:
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=mock_states
            )
            
            existing, missing = await client.validate_entities(entity_ids)
            
            # Duplicates should be preserved in output
            assert existing == ['sensor.temperature', 'sensor.temperature', 'light.living_room']
            assert missing == []
            
        await client.close()
        await asyncio.sleep(0.1)

"""Unit tests for enhanced render_template method."""

import pytest
from aioresponses import aioresponses

from ha_config_manager.connection.api import HAAPIClient, HAAPIError


@pytest.mark.asyncio
async def test_render_template_backward_compatibility():
    """Test rendering with validate_entities=False (backward compatibility)."""
    template = "{{ states('sensor.temperature') }}"
    rendered_output = "22.5"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/template endpoint
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template without validation (default behavior)
            result = await client.render_template(template)
            
            # Should return plain string (backward compatible)
            assert isinstance(result, str)
            assert result == rendered_output
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_with_validation_all_entities_exist():
    """Test rendering with validate_entities=True and all entities exist."""
    template = "{{ states('sensor.temperature') }}"
    rendered_output = "22.5"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint (entity exists)
            m.get(
                "http://localhost:8123/api/states",
                payload=[
                    {'entity_id': 'sensor.temperature', 'state': '22.5'}
                ],
                status=200
            )
            
            # Mock /api/template endpoint
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Should return plain string when no warnings
            assert isinstance(result, str)
            assert result == rendered_output
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_with_validation_missing_entities():
    """Test rendering with validate_entities=True and missing entities."""
    template = "{{ states('sensor.invalid') }}"
    rendered_output = "unknown"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint (entity does not exist)
            m.get(
                "http://localhost:8123/api/states",
                payload=[
                    {'entity_id': 'sensor.temperature', 'state': '22.5'}
                ],
                status=200
            )
            
            # Mock /api/template endpoint (renders successfully despite missing entity)
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Should return dict with result and warnings
            assert isinstance(result, dict)
            assert 'result' in result
            assert 'warnings' in result
            assert result['result'] == rendered_output
            assert 'sensor.invalid' in result['warnings']
            assert 'does not exist' in result['warnings']
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_with_validation_no_entities():
    """Test rendering with validate_entities=True and no entities in template."""
    template = "{{ 1 + 1 }}"
    rendered_output = "2"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/template endpoint (no entity validation needed)
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Should return plain string (no entities to validate)
            assert isinstance(result, str)
            assert result == rendered_output
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_error_response():
    """Test error responses with structured error format."""
    template = "{{ invalid syntax"
    error_message = "unexpected end of template"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/template endpoint with error
            m.post(
                "http://localhost:8123/api/template",
                payload={'message': error_message},
                status=400
            )
            
            # Call render_template and expect error
            with pytest.raises(HAAPIError) as exc_info:
                await client.render_template(template)
            
            # Verify error information is preserved
            assert exc_info.value.status_code == 400
            assert error_message in exc_info.value.message or 'message' in exc_info.value.message.lower()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_network_error():
    """Test network errors and timeouts."""
    template = "{{ states('sensor.temperature') }}"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/template endpoint with connection error
            m.post(
                "http://localhost:8123/api/template",
                exception=ConnectionError("Network error")
            )
            
            # Call render_template and expect error
            with pytest.raises(HAAPIError) as exc_info:
                await client.render_template(template)
            
            # Verify error is wrapped in HAAPIError
            assert 'network' in exc_info.value.message.lower() or 'connection' in exc_info.value.message.lower()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_malformed_ha_response():
    """Test malformed HA API responses."""
    template = "{{ states('sensor.temperature') }}"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states with malformed response
            m.get(
                "http://localhost:8123/api/states",
                payload="not a list",  # Invalid response format
                status=200
            )
            
            # Mock /api/template endpoint
            m.post(
                "http://localhost:8123/api/template",
                body="22.5",
                status=200
            )
            
            # Call render_template with validation enabled
            # Should handle malformed response gracefully
            with pytest.raises(Exception):  # Could be HAAPIError or other exception
                await client.render_template(template, validate_entities=True)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_multiple_missing_entities():
    """Test rendering with multiple missing entities."""
    template = "{{ states('sensor.invalid1') }} {{ states('sensor.invalid2') }}"
    rendered_output = "unknown unknown"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint (entities do not exist)
            m.get(
                "http://localhost:8123/api/states",
                payload=[
                    {'entity_id': 'sensor.temperature', 'state': '22.5'}
                ],
                status=200
            )
            
            # Mock /api/template endpoint
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Should return dict with warnings for both entities
            assert isinstance(result, dict)
            assert 'warnings' in result
            assert 'sensor.invalid1' in result['warnings']
            assert 'sensor.invalid2' in result['warnings']
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_render_template_mixed_existing_missing_entities():
    """Test rendering with mix of existing and missing entities."""
    template = "{{ states('sensor.temperature') }} {{ states('sensor.invalid') }}"
    rendered_output = "22.5 unknown"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint (one exists, one doesn't)
            m.get(
                "http://localhost:8123/api/states",
                payload=[
                    {'entity_id': 'sensor.temperature', 'state': '22.5'}
                ],
                status=200
            )
            
            # Mock /api/template endpoint
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Should return dict with warnings only for missing entity
            assert isinstance(result, dict)
            assert 'warnings' in result
            assert 'sensor.invalid' in result['warnings']
            assert 'sensor.temperature' not in result['warnings']
    finally:
        await client.close()

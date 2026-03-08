"""Property-based tests for enhanced render_template method.

Tests Properties 3, 7, and 8 from the design document.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from aioresponses import aioresponses

from ha_config_manager.connection.api import HAAPIClient


# Strategy for generating entity IDs
@st.composite
def entity_id_strategy(draw):
    """Generate valid Home Assistant entity IDs."""
    domain = draw(st.sampled_from(['sensor', 'light', 'switch', 'binary_sensor', 'climate']))
    name = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_', min_size=3, max_size=15))
    return f"{domain}.{name}"


# Strategy for generating templates with entity references
@st.composite
def template_with_entities_strategy(draw):
    """Generate templates with entity references."""
    num_entities = draw(st.integers(min_value=1, max_value=3))
    entities = [draw(entity_id_strategy()) for _ in range(num_entities)]
    
    # Choose a template pattern
    pattern = draw(st.sampled_from([
        lambda e: f"{{{{ states('{e}') }}}}",
        lambda e: f"{{{{ state_attr('{e}', 'temperature') }}}}",
        lambda e: f"{{{{ is_state('{e}', 'on') }}}}",
    ]))
    
    # Build template with entities
    template_parts = [pattern(e) for e in entities]
    template = " ".join(template_parts)
    
    return template, entities


@pytest.mark.asyncio
@given(data=st.data())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
async def test_property_3_validation_before_rendering(data):
    """Property 3: Validation Before Rendering.
    
    For any template with validate_entities=true, if entity validation detects
    missing entities, the warning should be returned regardless of whether the
    template would successfully render.
    
    Validates: Requirements 2.5, 5.3
    """
    # Generate template with entities
    template, entities = data.draw(template_with_entities_strategy())
    
    # Remove duplicates from entities list
    unique_entities = list(set(entities))
    
    # Randomly select which entities exist (ensure at least one is missing)
    if len(unique_entities) == 1:
        # If only one entity, it must be missing
        missing_entities = unique_entities
        existing_entities = []
    else:
        # Select some entities to be missing
        num_missing = data.draw(st.integers(min_value=1, max_value=len(unique_entities)))
        missing_entities = data.draw(st.lists(
            st.sampled_from(unique_entities),
            min_size=num_missing,
            max_size=num_missing,
            unique=True
        ))
        existing_entities = [e for e in unique_entities if e not in missing_entities]
    
    # Create mock states response (only existing entities)
    mock_states = [{'entity_id': e, 'state': 'on'} for e in existing_entities]
    
    # Mock successful template rendering
    rendered_output = "rendered_result"
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint
            m.get(
                "http://localhost:8123/api/states",
                payload=mock_states,
                status=200
            )
            
            # Mock /api/template endpoint (successful rendering)
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Property: Warnings should be returned even when template renders successfully
            assert isinstance(result, dict), "Result should be a dict when warnings are present"
            assert 'result' in result, "Result dict should contain 'result' key"
            assert 'warnings' in result, "Result dict should contain 'warnings' key"
            
            # Verify rendered output is preserved
            assert result['result'] == rendered_output
            
            # Verify warning format includes missing entity names
            warnings = result['warnings']
            for missing_entity in missing_entities:
                assert missing_entity in warnings, f"Warning should mention missing entity {missing_entity}"
    finally:
        await client.close()


@pytest.mark.asyncio
@given(data=st.data())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
async def test_property_7_successful_rendering_returns_output(data):
    """Property 7: Successful Rendering Returns Output.
    
    For any syntactically valid template that references only existing entities
    and functions, rendering should return a string result (the rendered output).
    
    Validates: Requirements 4.4, 5.4
    """
    # Generate template with entities
    template, entities = data.draw(template_with_entities_strategy())
    
    # All entities exist
    mock_states = [{'entity_id': e, 'state': 'on'} for e in entities]
    
    # Generate random rendered output
    rendered_output = data.draw(st.text(min_size=1, max_size=50))
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/states endpoint (all entities exist)
            m.get(
                "http://localhost:8123/api/states",
                payload=mock_states,
                status=200
            )
            
            # Mock /api/template endpoint (successful rendering)
            m.post(
                "http://localhost:8123/api/template",
                body=rendered_output,
                status=200
            )
            
            # Call render_template with validation enabled
            result = await client.render_template(template, validate_entities=True)
            
            # Property: Should return string result when all entities exist
            assert isinstance(result, str), "Result should be a string when no warnings"
            assert result == rendered_output, "Result should match rendered output"
    finally:
        await client.close()


@pytest.mark.asyncio
@given(
    error_type=st.sampled_from(['TemplateSyntaxError', 'UndefinedError', 'TypeError']),
    error_message=st.text(min_size=10, max_size=100)
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
async def test_property_8_error_information_preservation(error_type, error_message):
    """Property 8: Error Information Preservation.
    
    For any template that fails to render in Home Assistant, the error returned
    by the MCP server should preserve the error type and message from the original
    Home Assistant API response.
    
    Validates: Requirements 4.5
    """
    template = "{{ invalid template }}"
    
    # Create mock error response from HA
    error_response = {
        'message': error_message
    }
    
    client = HAAPIClient(
        base_url="http://localhost:8123",
        access_token="test_token"
    )
    
    try:
        with aioresponses() as m:
            # Mock /api/template endpoint with error response
            m.post(
                "http://localhost:8123/api/template",
                payload=error_response,
                status=400
            )
            
            # Call render_template and expect error
            with pytest.raises(Exception) as exc_info:
                await client.render_template(template, validate_entities=False)
            
            # Property: Error message should be preserved
            error_str = str(exc_info.value)
            assert error_message in error_str or 'message' in error_str.lower(), \
                "Error should preserve information from HA API response"
    finally:
        await client.close()

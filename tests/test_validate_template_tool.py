"""Unit tests for validate_template MCP tool.

Tests the validate_template tool handler in the MCP server, including:
- Valid template syntax validation
- Syntax error detection
- Entity validation integration
- Error handling for malformed requests
"""

import pytest
from aioresponses import aioresponses

from ha_dev_tools.connection.api import HAAPIClient

# Disable Home Assistant test framework for these tests
pytestmark = [pytest.mark.asyncio, pytest.mark.skip_ha_fixtures]


class TestValidateTemplateTool:
    """Unit tests for validate_template tool functionality."""

    async def test_valid_single_line_template(self):
        """Test validation of a valid single-line template.

        Validates: Requirements 7.1, 7.2, 7.3
        """
        # Valid single-line template
        template = "{{ states('sensor.temperature') }}"

        # Import here to avoid circular imports
        from ha_dev_tools.template_validator import validate_template_syntax

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Assertions
        assert is_valid is True, "Valid template should pass syntax validation"
        assert error_dict is None, "Valid template should not return error dict"

    async def test_valid_multi_line_template(self):
        """Test validation of a valid multi-line template.

        Validates: Requirements 7.1, 7.2, 7.3, 8.1
        """
        # Valid multi-line template
        template = """
{% set temp = states('sensor.temperature') %}
{% if temp | float > 20 %}
  Temperature is high: {{ temp }}
{% else %}
  Temperature is normal: {{ temp }}
{% endif %}
"""

        from ha_dev_tools.template_validator import validate_template_syntax

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Assertions
        assert is_valid is True, "Valid multi-line template should pass"
        assert error_dict is None, "Valid template should not return error"

    async def test_syntax_error_unclosed_tag(self):
        """Test detection of unclosed Jinja2 tag.

        Validates: Requirements 7.2, 7.4
        """
        # Template with unclosed tag
        template = "{{ states('sensor.temp') "

        from ha_dev_tools.template_validator import validate_template_syntax

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Assertions
        assert is_valid is False, "Template with unclosed tag should fail"
        assert error_dict is not None, "Should return error dict"
        assert "error_type" in error_dict, "Error dict should have error_type"
        assert "message" in error_dict, "Error dict should have message"

    async def test_syntax_error_invalid_expression(self):
        """Test detection of invalid Jinja2 expression.

        Validates: Requirements 7.2, 7.4
        """
        # Template with invalid expression
        template = "{{ states('sensor.temp' }}"

        from ha_dev_tools.template_validator import validate_template_syntax

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Assertions
        assert is_valid is False, "Template with invalid expression should fail"
        assert error_dict is not None, "Should return error dict"
        assert "error_type" in error_dict
        assert "message" in error_dict

    async def test_validate_entities_false_default(self):
        """Test that validate_entities defaults to False.

        Validates: Requirements 7.5
        """
        # Create API client
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)

        template = "{{ states('sensor.temperature') }}"

        # Mock only the template endpoint (not states endpoint)
        with aioresponses() as mock:
            mock.post(f"{url}/api/template", status=200, body="25.5")

            # Render without validate_entities (should not call /api/states)
            result = await client.render_template(template)

            # Should succeed without entity validation
            assert result == "25.5"

    async def test_validate_entities_true_all_exist(self):
        """Test validation when all entities exist.

        Validates: Requirements 7.5, 2.2, 2.3
        """
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)

        template = "{{ states('sensor.temperature') }}"

        with aioresponses() as mock:
            # Mock /api/states to return the entity
            mock.get(
                f"{url}/api/states",
                status=200,
                payload=[
                    {
                        "entity_id": "sensor.temperature",
                        "state": "25.5",
                        "attributes": {},
                        "last_changed": "2024-01-15T10:00:00",
                        "last_updated": "2024-01-15T10:00:00",
                    }
                ],
            )

            # Mock /api/template
            mock.post(f"{url}/api/template", status=200, body="25.5")

            # Render with validate_entities=True
            result = await client.render_template(template, validate_entities=True)

            # Should succeed with no warnings
            assert result == "25.5", "Should return rendered result"

    async def test_validate_entities_true_missing_entities(self):
        """Test validation when entities are missing.

        Validates: Requirements 7.5, 2.3, 2.4, 5.3
        """
        url = "http://homeassistant.local:8123"
        token = "test_token"
        client = HAAPIClient(url, token)

        template = "{{ states('sensor.missing') }}"

        with aioresponses() as mock:
            # Mock /api/states to return empty list (no entities)
            mock.get(f"{url}/api/states", status=200, payload=[])

            # Mock /api/template to succeed anyway
            mock.post(f"{url}/api/template", status=200, body="unknown")

            # Render with validate_entities=True
            result = await client.render_template(template, validate_entities=True)

            # Should return dict with result and warnings
            assert isinstance(result, dict), "Should return dict with warnings"
            assert "result" in result, "Should have result field"
            assert "warnings" in result, "Should have warnings field"
            assert (
                "sensor.missing" in result["warnings"]
            ), "Warning should mention missing entity"

    async def test_validate_template_syntax_only(self):
        """Test syntax validation without entity validation.

        Validates: Requirements 7.1, 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Valid template with entity reference
        template = "{{ states('sensor.nonexistent') }}"

        # Validate syntax only (should pass even though entity doesn't exist)
        is_valid, error_dict = validate_template_syntax(template)

        assert is_valid is True, "Syntax validation should pass"
        assert error_dict is None, "Should not return error for valid syntax"

    async def test_error_handling_malformed_request(self):
        """Test error handling for malformed requests.

        Validates: Requirements 7.4
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Test with None (should handle gracefully)
        try:
            is_valid, error_dict = validate_template_syntax(None)
            # Should either raise or return error
            if not is_valid:
                assert error_dict is not None
        except (TypeError, AttributeError):
            # Expected - None is not a valid template
            pass

    async def test_validate_template_with_undefined_variable(self):
        """Test that syntax validation passes for undefined variables.

        Note: Undefined variables are only detected at render time, not during
        syntax validation.

        Validates: Requirements 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Template with undefined variable (valid syntax)
        template = "{{ undefined_variable }}"

        # Syntax validation should pass
        is_valid, error_dict = validate_template_syntax(template)

        assert is_valid is True, "Syntax validation should pass for undefined variables"
        assert error_dict is None, "Should not return error for valid syntax"

    async def test_validate_template_with_undefined_filter(self):
        """Test that syntax validation passes for undefined filters.

        Note: Undefined filters are only detected at render time, not during
        syntax validation.

        Validates: Requirements 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Template with undefined filter (valid syntax)
        template = "{{ 'value' | undefined_filter }}"

        # Syntax validation should pass
        is_valid, error_dict = validate_template_syntax(template)

        assert is_valid is True, "Syntax validation should pass for undefined filters"
        assert error_dict is None, "Should not return error for valid syntax"

    async def test_complex_template_with_multiple_entities(self):
        """Test validation of complex template with multiple entity references.

        Validates: Requirements 7.1, 7.2, 2.1
        """
        from ha_dev_tools.template_validator import (
            validate_template_syntax,
            extract_entity_references,
        )

        # Complex template with multiple entities
        template = """
{% set temp = states('sensor.temperature') | float %}
{% set humidity = states('sensor.humidity') | float %}
{% if temp > 20 and humidity > 60 %}
  Hot and humid
{% else %}
  Comfortable
{% endif %}
"""

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)
        assert is_valid is True, "Complex template should pass syntax validation"

        # Extract entities
        entities = extract_entity_references(template)
        assert "sensor.temperature" in entities, "Should extract temperature sensor"
        assert "sensor.humidity" in entities, "Should extract humidity sensor"

    async def test_template_with_comments(self):
        """Test validation of template with Jinja2 comments.

        Validates: Requirements 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Template with comments
        template = """
{# This is a comment #}
{{ states('sensor.temperature') }}
{# Another comment #}
"""

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        assert is_valid is True, "Template with comments should pass"
        assert error_dict is None

    async def test_empty_template(self):
        """Test validation of empty template.

        Validates: Requirements 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Empty template
        template = ""

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Empty template is valid Jinja2
        assert is_valid is True, "Empty template should be valid"
        assert error_dict is None

    async def test_template_with_whitespace_only(self):
        """Test validation of template with only whitespace.

        Validates: Requirements 7.2
        """
        from ha_dev_tools.template_validator import validate_template_syntax

        # Whitespace-only template
        template = "   \n\t  \n  "

        # Validate syntax
        is_valid, error_dict = validate_template_syntax(template)

        # Whitespace-only template is valid
        assert is_valid is True, "Whitespace-only template should be valid"
        assert error_dict is None

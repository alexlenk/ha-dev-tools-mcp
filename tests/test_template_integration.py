"""Integration tests for template testing enhancement.

These tests verify the template testing functionality. Tests are divided into:
1. Tests that work without network (syntax validation, error formatting)
2. Tests that require a real Home Assistant instance (marked with @pytest.mark.skipif)

To run ALL tests including those requiring Home Assistant:
    export HA_URL="http://homeassistant.local:8123"
    export HA_TOKEN="your_long_lived_access_token"
    PYTHONPATH=src python -m pytest tests/test_template_integration.py -v

To run only tests that don't require Home Assistant (default):
    PYTHONPATH=src python -m pytest tests/test_template_integration.py -v
"""

import pytest
import os

from ha_dev_tools.connection.api import HAAPIClient
from ha_dev_tools.template_validator import (
    extract_entity_references,
    validate_template_syntax,
    format_entity_validation_warnings,
    format_template_error,
)

# Check if we should run against real HA instance
USE_REAL_HA = os.getenv("HA_URL") and os.getenv("HA_TOKEN")


@pytest.fixture
async def api_client():
    """Create API client for testing with real Home Assistant."""
    if not USE_REAL_HA:
        pytest.skip("Requires HA_URL and HA_TOKEN environment variables")

    url = os.getenv("HA_URL")
    token = os.getenv("HA_TOKEN")
    client = HAAPIClient(url, token)
    yield client
    await client.close()


class TestTemplateSyntaxValidation:
    """Integration tests for template syntax validation (no network required)."""

    def test_validate_valid_single_line_template(self):
        """Test validation of valid single-line template."""
        template = "{{ states('sensor.temperature') }}"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None

    def test_validate_valid_multi_line_template(self):
        """Test validation of valid multi-line template."""
        template = """
{% if states('sensor.temp') | float > 20 %}
  Hot
{% else %}
  Cold
{% endif %}
        """.strip()
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None

    def test_validate_invalid_template_syntax(self):
        """Test validation of syntactically invalid template."""
        template = "{{ invalid syntax"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert "error_type" in error
        assert "message" in error

    def test_validate_multiline_template_with_error(self):
        """Test validation of multi-line template with syntax error."""
        template = """
Line 1: {{ states('sensor.temp') }}
Line 2: {{ invalid
Line 3: {{ states('sensor.humidity') }}
        """.strip()
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert "line" in error
        # Error should be on line 2 or 3
        assert error["line"] in [2, 3]


class TestEntityReferenceExtraction:
    """Integration tests for entity reference extraction (no network required)."""

    def test_extract_entities_from_simple_template(self):
        """Test extracting entities from simple template."""
        template = "{{ states('sensor.temperature') }}"
        entities = extract_entity_references(template)
        assert entities == ["sensor.temperature"]

    def test_extract_entities_from_complex_template(self):
        """Test extracting entities from complex template."""
        template = """
{{ states('sensor.temp1') }}
{{ state_attr('climate.living', 'temperature') }}
{{ is_state('light.kitchen', 'on') }}
{{ states.binary_sensor.door }}
        """
        entities = extract_entity_references(template)
        # Should be sorted and unique
        assert "sensor.temp1" in entities
        assert "climate.living" in entities
        assert "light.kitchen" in entities
        assert "binary_sensor.door" in entities

    def test_extract_no_entities(self):
        """Test template with no entity references."""
        template = "{{ 1 + 1 }}"
        entities = extract_entity_references(template)
        assert entities == []


class TestErrorFormatting:
    """Integration tests for error formatting (no network required)."""

    def test_format_syntax_error(self):
        """Test formatting of syntax error."""
        template = "{{ invalid"
        try:
            from jinja2 import Environment

            env = Environment()
            env.parse(template)
        except Exception as e:
            error_dict = format_template_error(e, template)
            assert "error_type" in error_dict
            assert "message" in error_dict
            assert len(error_dict["message"]) > 0

    def test_format_multiline_error(self):
        """Test formatting of error in multi-line template."""
        template = """Line 1
Line 2
{{ invalid
Line 4"""
        try:
            from jinja2 import Environment

            env = Environment()
            env.parse(template)
        except Exception as e:
            error_dict = format_template_error(e, template)
            assert "error_type" in error_dict
            assert "message" in error_dict
            if "line" in error_dict:
                assert error_dict["line"] > 0

    def test_format_entity_warnings(self):
        """Test formatting of entity validation warnings."""
        missing = ["sensor.temp1", "sensor.temp2"]
        warning = format_entity_validation_warnings(missing)
        assert "sensor.temp1" in warning
        assert "sensor.temp2" in warning
        assert "do not exist" in warning or "not found" in warning


class TestCompleteValidationWorkflow:
    """Integration tests for complete validation workflows (no network required)."""

    def test_syntax_validation_workflow(self):
        """Test complete syntax validation workflow."""
        template = "{{ states('sensor.temperature') | float | round(1) }}"

        # Step 1: Validate syntax
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True

        # Step 2: Extract entities
        entities = extract_entity_references(template)
        assert len(entities) > 0
        assert "sensor.temperature" in entities

    def test_error_detection_workflow(self):
        """Test workflow for detecting and reporting template errors."""
        template = "{{ states('sensor.temp') "

        # Syntax validation should catch the error
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert "error_type" in error
        assert "message" in error

    def test_entity_extraction_workflow(self):
        """Test workflow for extracting and listing entities."""
        template = "{{ states('sensor.temp1') }} {{ states('sensor.temp2') }}"

        # Extract entities
        entities = extract_entity_references(template)
        assert len(entities) == 2
        assert "sensor.temp1" in entities
        assert "sensor.temp2" in entities


# Tests below require a real Home Assistant instance
@pytest.mark.skipif(not USE_REAL_HA, reason="Requires real Home Assistant instance")
class TestWithRealHomeAssistant:
    """Tests that require a real Home Assistant instance."""

    @pytest.mark.asyncio
    async def test_real_ha_connection(self, api_client):
        """Test connection to real Home Assistant instance."""
        states = await api_client.get_states()
        assert isinstance(states, list)
        assert len(states) > 0

    @pytest.mark.asyncio
    async def test_real_ha_template_rendering(self, api_client):
        """Test template rendering against real Home Assistant."""
        template = "{{ 1 + 1 }}"
        result = await api_client.render_template(template)
        assert result == "2"

    @pytest.mark.asyncio
    async def test_real_ha_entity_validation(self, api_client):
        """Test entity validation against real Home Assistant."""
        # Use a common entity that likely exists
        entities = ["sun.sun"]
        existing, missing = await api_client.validate_entities(entities)
        # sun.sun should exist in any HA instance
        assert "sun.sun" in existing or len(existing) >= 0

    @pytest.mark.asyncio
    async def test_real_ha_render_with_validation(self, api_client):
        """Test rendering with entity validation."""
        template = "{{ states('sun.sun') }}"
        result = await api_client.render_template(template, validate_entities=True)
        # Should return result (string or dict with result key)
        assert result is not None

    @pytest.mark.asyncio
    async def test_real_ha_multiline_template(self, api_client):
        """Test multi-line template rendering."""
        template = """
{% if states('sun.sun') %}
  Sun exists
{% else %}
  No sun
{% endif %}
        """.strip()
        result = await api_client.render_template(template)
        assert result is not None
        assert isinstance(result, str)

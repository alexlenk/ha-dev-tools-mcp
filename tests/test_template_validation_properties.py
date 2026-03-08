"""Property-based tests for template validation functionality.

These tests validate universal properties of entity validation and template processing.
"""

import asyncio
from typing import List

import pytest
from aioresponses import aioresponses
from hypothesis import given, strategies as st, settings, HealthCheck
from jinja2 import Environment

from ha_dev_tools.connection.api import HAAPIClient, HAAPIError
from ha_dev_tools.template_validator import (
    extract_entity_references,
    validate_template_syntax,
)

# Disable Home Assistant test framework for these tests
# These are pure API client tests that don't need HA fixtures
pytestmark = [pytest.mark.asyncio, pytest.mark.skip_ha_fixtures]


# Hypothesis strategies for generating test data
@st.composite
def entity_id(draw):
    """Generate valid entity IDs in format domain.entity_name.

    Home Assistant entity IDs must be ASCII-only with lowercase letters,
    numbers, and underscores.
    """
    domains = ["sensor", "light", "switch", "binary_sensor", "climate", "cover", "fan"]
    domain = draw(st.sampled_from(domains))

    # Entity name: ASCII lowercase letters, numbers, underscores only
    # Use string.ascii_lowercase + string.digits + '_' to ensure ASCII-only
    entity_name = draw(
        st.text(
            min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_"
        )
    )

    return f"{domain}.{entity_name}"


@st.composite
def entity_id_list(draw):
    """Generate a list of entity IDs."""
    return draw(st.lists(entity_id(), min_size=0, max_size=20, unique=True))


@st.composite
def entity_state(draw, entity_id_val: str):
    """Generate a valid entity state object."""
    return {
        "entity_id": entity_id_val,
        "state": draw(st.sampled_from(["on", "off", "unknown", "unavailable"])),
        "attributes": draw(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(
                    st.text(max_size=50),
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                ),
                max_size=5,
            )
        ),
        "last_changed": "2024-01-15T10:30:00",
        "last_updated": "2024-01-15T10:30:00",
    }


class TestTemplateValidationProperties:
    """Property-based tests for template validation functionality."""

    @given(entity_id_list())
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100
    )
    def test_property_1_entity_reference_extraction_completeness(
        self, entity_ids: List[str]
    ):
        """
        **Property 1: Entity Reference Extraction Completeness**

        For any template string containing entity references in supported patterns
        (states(), state_attr(), is_state(), states.domain.entity), the
        extract_entity_references() function should return all unique entity IDs
        present in the template.

        **Validates: Requirements 2.1**
        """
        if not entity_ids:
            # Test with empty template
            template = "{{ 'no entities here' }}"
            result = extract_entity_references(template)
            assert result == [], "Empty template should return empty list"
            return

        # Generate a template with all supported patterns
        template_parts = []

        # Pattern 1: states('entity.id')
        if len(entity_ids) > 0:
            template_parts.append(f"{{{{ states('{entity_ids[0]}') }}}}")

        # Pattern 2: state_attr('entity.id', 'attr')
        if len(entity_ids) > 1:
            template_parts.append(
                f"{{{{ state_attr('{entity_ids[1]}', 'temperature') }}}}"
            )

        # Pattern 3: is_state('entity.id', 'value')
        if len(entity_ids) > 2:
            template_parts.append(f"{{{{ is_state('{entity_ids[2]}', 'on') }}}}")

        # Pattern 4: states.domain.entity
        if len(entity_ids) > 3:
            template_parts.append(f"{{{{ states.{entity_ids[3].replace('.', '.')} }}}}")

        # Add remaining entities with mixed patterns
        for i, eid in enumerate(entity_ids[4:], start=4):
            pattern_choice = i % 4
            if pattern_choice == 0:
                template_parts.append(f"{{{{ states('{eid}') }}}}")
            elif pattern_choice == 1:
                template_parts.append(f"{{{{ state_attr('{eid}', 'attr') }}}}")
            elif pattern_choice == 2:
                template_parts.append(f"{{{{ is_state('{eid}', 'value') }}}}")
            else:
                # Direct access pattern
                template_parts.append(f"{{{{ states.{eid.replace('.', '.')} }}}}")

        # Join template parts
        template = " ".join(template_parts)

        # Extract entity references
        result = extract_entity_references(template)

        # Property 1: All entities should be extracted
        expected_entities = sorted(set(entity_ids))
        assert (
            result == expected_entities
        ), f"All entities should be extracted. Expected: {expected_entities}, Got: {result}"

        # Property 2: No duplicates in result
        assert len(result) == len(
            set(result)
        ), f"Result should not contain duplicates: {result}"

        # Property 3: Result should be sorted
        assert result == sorted(result), f"Result should be sorted: {result}"

        # Property 4: All returned entities should be valid entity IDs
        for eid in result:
            assert "." in eid, f"Entity ID should contain a dot: {eid}"
            domain, entity_name = eid.split(".", 1)
            assert domain, f"Domain should not be empty: {eid}"
            assert entity_name, f"Entity name should not be empty: {eid}"

    def test_property_1_mixed_patterns_single_entity(self):
        """
        **Property 1 (Edge Case): Same Entity in Multiple Patterns**

        When the same entity appears multiple times in different patterns,
        extract_entity_references() should return it only once.

        **Validates: Requirements 2.1**
        """
        entity_id = "sensor.temperature"

        # Template with same entity in all patterns
        template = f"""
        {{{{ states('{entity_id}') }}}}
        {{{{ state_attr('{entity_id}', 'unit') }}}}
        {{{{ is_state('{entity_id}', 'on') }}}}
        {{{{ states.{entity_id.replace('.', '.')} }}}}
        """

        result = extract_entity_references(template)

        # Property: Entity should appear only once
        assert result == [entity_id], f"Entity should appear only once. Got: {result}"

    def test_property_1_no_entities(self):
        """
        **Property 1 (Edge Case): Template Without Entities**

        When a template contains no entity references, extract_entity_references()
        should return an empty list.

        **Validates: Requirements 2.1**
        """
        templates = [
            "{{ 'hello world' }}",
            "{{ 1 + 2 }}",
            "{{ now() }}",
            "{% if true %}yes{% endif %}",
            "Plain text without any Jinja2",
            "",
        ]

        for template in templates:
            result = extract_entity_references(template)
            assert (
                result == []
            ), f"Template without entities should return empty list. Template: {template}, Got: {result}"

    def test_property_1_double_quotes(self):
        """
        **Property 1 (Edge Case): Double Quotes in Entity References**

        Entity references can use either single or double quotes.
        extract_entity_references() should handle both.

        **Validates: Requirements 2.1**
        """
        entity_id = "sensor.temperature"

        # Test with double quotes
        template_double = f'{{{{ states("{entity_id}") }}}}'
        result_double = extract_entity_references(template_double)
        assert result_double == [
            entity_id
        ], f"Should extract entity with double quotes. Got: {result_double}"

        # Test with single quotes
        template_single = f"{{{{ states('{entity_id}') }}}}"
        result_single = extract_entity_references(template_single)
        assert result_single == [
            entity_id
        ], f"Should extract entity with single quotes. Got: {result_single}"

        # Test mixed quotes in same template
        template_mixed = (
            f"{{{{ states(\"{entity_id}\") }}}} {{{{ states('{entity_id}') }}}}"
        )
        result_mixed = extract_entity_references(template_mixed)
        assert result_mixed == [
            entity_id
        ], f"Should extract entity once with mixed quotes. Got: {result_mixed}"

    @given(entity_id_list())
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100
    )
    async def test_property_2_entity_validation_correctness(
        self, entity_ids: List[str]
    ):
        """
        **Property 2: Entity Validation Correctness**

        For any list of entity IDs, when validated against Home Assistant's current state,
        the validate_entities() function should correctly partition them into existing and
        missing entities, with no entity appearing in both lists and all entities appearing
        in exactly one list.

        **Validates: Requirements 2.2, 2.3, 2.4**
        """
        # Use fixed URL and token for testing
        url = "http://homeassistant.local:8123"
        token = "test_token_12345"

        # Create client
        client = HAAPIClient(url, token)

        # Generate a random subset of entities that "exist" in HA
        # Use a deterministic split based on hash to ensure consistency
        existing_in_ha = [eid for eid in entity_ids if hash(eid) % 2 == 0]

        # Create mock entity states for existing entities
        mock_states = []
        for eid in existing_in_ha:
            mock_states.append(
                {
                    "entity_id": eid,
                    "state": "on",
                    "attributes": {},
                    "last_changed": "2024-01-15T10:30:00",
                    "last_updated": "2024-01-15T10:30:00",
                }
            )

        # Mock the /api/states endpoint
        with aioresponses() as mock:
            mock.get(f"{url}/api/states", status=200, payload=mock_states, repeat=True)

            try:
                # Call validate_entities
                existing, missing = await client.validate_entities(entity_ids)

                # Property 1: No entity appears in both lists
                overlap = set(existing) & set(missing)
                assert (
                    len(overlap) == 0
                ), f"Entities should not appear in both lists: {overlap}"

                # Property 2: All entities appear in exactly one list
                all_returned = set(existing) | set(missing)
                all_input = set(entity_ids)
                assert (
                    all_returned == all_input
                ), f"All entities must appear in exactly one list. Missing: {all_input - all_returned}, Extra: {all_returned - all_input}"

                # Property 3: Correct partitioning based on mock data
                expected_existing = set(existing_in_ha)
                expected_missing = set(entity_ids) - expected_existing

                assert (
                    set(existing) == expected_existing
                ), f"Existing entities mismatch. Expected: {expected_existing}, Got: {set(existing)}"
                assert (
                    set(missing) == expected_missing
                ), f"Missing entities mismatch. Expected: {expected_missing}, Got: {set(missing)}"

                # Property 4: Return types are lists
                assert isinstance(existing, list), "Existing entities should be a list"
                assert isinstance(missing, list), "Missing entities should be a list"

                # Property 5: Order preservation (entities should maintain input order)
                # Check that the order of entities in each list matches their order in input
                existing_order = [eid for eid in entity_ids if eid in existing]
                missing_order = [eid for eid in entity_ids if eid in missing]
                assert (
                    existing == existing_order
                ), "Existing entities should maintain input order"
                assert (
                    missing == missing_order
                ), "Missing entities should maintain input order"

            except HAAPIError as e:
                pytest.fail(
                    f"Entity validation should not raise HAAPIError for valid API response: {e}"
                )
            except Exception as e:
                pytest.fail(f"Entity validation failed unexpectedly: {e}")
            finally:
                await client.close()
                await asyncio.sleep(0.1)

    async def test_property_2_empty_entity_list(self):
        """
        **Property 2 (Edge Case): Empty Entity List**

        When validating an empty list of entity IDs, validate_entities() should return
        two empty lists without making unnecessary API calls.

        **Validates: Requirements 2.2, 2.3, 2.4**
        """
        url = "http://homeassistant.local:8123"
        token = "test_token_12345"
        client = HAAPIClient(url, token)

        # Mock the /api/states endpoint (should be called even for empty list)
        with aioresponses() as mock:
            mock.get(f"{url}/api/states", status=200, payload=[], repeat=True)

            try:
                existing, missing = await client.validate_entities([])

                # Property: Both lists should be empty
                assert existing == [], "Existing entities should be empty list"
                assert missing == [], "Missing entities should be empty list"
                assert isinstance(existing, list), "Should return list type"
                assert isinstance(missing, list), "Should return list type"

            except Exception as e:
                pytest.fail(f"Empty entity list validation failed: {e}")
            finally:
                await client.close()
                await asyncio.sleep(0.1)

    @given(entity_id_list())
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50
    )
    async def test_property_2_all_entities_exist(self, entity_ids: List[str]):
        """
        **Property 2 (Edge Case): All Entities Exist**

        When all entity IDs exist in Home Assistant, validate_entities() should return
        all entities in the existing list and an empty missing list.

        **Validates: Requirements 2.2, 2.3, 2.4**
        """
        if not entity_ids:
            # Skip if no entities generated
            return

        url = "http://homeassistant.local:8123"
        token = "test_token_12345"
        client = HAAPIClient(url, token)

        # Create mock states for ALL entities
        mock_states = []
        for eid in entity_ids:
            mock_states.append(
                {
                    "entity_id": eid,
                    "state": "on",
                    "attributes": {},
                    "last_changed": "2024-01-15T10:30:00",
                    "last_updated": "2024-01-15T10:30:00",
                }
            )

        with aioresponses() as mock:
            mock.get(f"{url}/api/states", status=200, payload=mock_states, repeat=True)

            try:
                existing, missing = await client.validate_entities(entity_ids)

                # Property: All entities should be in existing list
                assert set(existing) == set(
                    entity_ids
                ), "All entities should be in existing list"
                assert missing == [], "Missing list should be empty"

            except Exception as e:
                pytest.fail(f"All entities exist validation failed: {e}")
            finally:
                await client.close()
                await asyncio.sleep(0.1)

    @given(entity_id_list())
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50
    )
    async def test_property_2_no_entities_exist(self, entity_ids: List[str]):
        """
        **Property 2 (Edge Case): No Entities Exist**

        When no entity IDs exist in Home Assistant, validate_entities() should return
        an empty existing list and all entities in the missing list.

        **Validates: Requirements 2.2, 2.3, 2.4**
        """
        if not entity_ids:
            # Skip if no entities generated
            return

        url = "http://homeassistant.local:8123"
        token = "test_token_12345"
        client = HAAPIClient(url, token)

        # Mock empty states (no entities exist)
        with aioresponses() as mock:
            mock.get(f"{url}/api/states", status=200, payload=[], repeat=True)

            try:
                existing, missing = await client.validate_entities(entity_ids)

                # Property: All entities should be in missing list
                assert existing == [], "Existing list should be empty"
                assert set(missing) == set(
                    entity_ids
                ), "All entities should be in missing list"

            except Exception as e:
                pytest.fail(f"No entities exist validation failed: {e}")
            finally:
                await client.close()
                await asyncio.sleep(0.1)

    @given(st.text(min_size=1, max_size=200))
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100
    )
    def test_property_4_syntax_validation_without_execution(
        self, template_content: str
    ):
        """
        **Property 4: Syntax Validation Without Execution**

        For any template that would have side effects (like calling services),
        validating the template with validate_template_syntax() should not execute
        those side effects while still detecting syntax errors.

        This test verifies that:
        1. validate_template_syntax() only parses without executing
        2. Syntax errors are detected correctly
        3. Valid templates pass validation without execution

        **Validates: Requirements 7.2**
        """
        # Create templates with potential side effects
        # These should NOT be executed during validation

        # Test 1: Template with service call (should not execute)
        service_template = (
            f"{{{{ states('sensor.test') }}}} {{{{ {template_content} }}}}"
        )

        # Validate the template - this should only parse, not execute
        is_valid, error = validate_template_syntax(service_template)

        # Property 1: Function returns a tuple
        assert isinstance(is_valid, bool), "First return value should be boolean"
        assert error is None or isinstance(
            error, dict
        ), "Second return value should be None or dict"

        # Property 2: If valid, error should be None
        if is_valid:
            assert error is None, "Valid template should have no error"

        # Property 3: If invalid, error should be a dict with required fields
        if not is_valid:
            assert error is not None, "Invalid template should have error dict"
            assert "error_type" in error, "Error dict should have error_type"
            assert "message" in error, "Error dict should have message"
            assert isinstance(error["error_type"], str), "error_type should be string"
            assert isinstance(error["message"], str), "message should be string"

        # Test 2: Known valid syntax should pass
        valid_templates = [
            "{{ states('sensor.temperature') }}",
            "{{ 1 + 2 }}",
            "{{ 'hello' }}",
            "{% if true %}yes{% endif %}",
            "{{ states.sensor.temperature }}",
            "{{ state_attr('sensor.temp', 'unit') }}",
        ]

        for valid_template in valid_templates:
            is_valid, error = validate_template_syntax(valid_template)
            assert is_valid is True, f"Valid template should pass: {valid_template}"
            assert (
                error is None
            ), f"Valid template should have no error: {valid_template}"

        # Test 3: Known invalid syntax should fail
        invalid_templates = [
            "{{ unclosed",
            "{% if %}",
            "{{ }}",
            "{% for %}",
            "{{ states('sensor.temp' }}",  # Missing closing paren
            "{{ states 'sensor.temp') }}",  # Missing opening paren
            "{% if true %} no endif",
            "{{ 1 + }}",  # Incomplete expression
        ]

        for invalid_template in invalid_templates:
            is_valid, error = validate_template_syntax(invalid_template)
            assert (
                is_valid is False
            ), f"Invalid template should fail: {invalid_template}"
            assert (
                error is not None
            ), f"Invalid template should have error: {invalid_template}"
            assert (
                "error_type" in error
            ), f"Error should have error_type: {invalid_template}"
            assert "message" in error, f"Error should have message: {invalid_template}"

    def test_property_4_no_execution_side_effects(self):
        """
        **Property 4 (Edge Case): No Execution Side Effects**

        Validate that validate_template_syntax() does not execute templates,
        even if they contain function calls or expressions that would have
        side effects in a real Home Assistant environment.

        **Validates: Requirements 7.2**
        """
        # Templates that would have side effects if executed
        side_effect_templates = [
            # Service calls (would trigger actions in HA)
            "{{ states('sensor.test') }}",
            "{{ state_attr('light.living_room', 'brightness') }}",
            "{{ is_state('switch.test', 'on') }}",
            # Time-based functions (would use current time)
            "{{ now() }}",
            "{{ utcnow() }}",
            # State access (would query HA state)
            "{{ states.sensor.temperature }}",
            "{{ states.light.living_room.state }}",
            # Complex expressions
            "{{ states('sensor.temp') | float + 10 }}",
            "{% if states('sensor.motion') == 'on' %}Motion detected{% endif %}",
        ]

        for template in side_effect_templates:
            # Validate syntax only - should not execute
            is_valid, error = validate_template_syntax(template)

            # Property: All these templates have valid syntax
            assert (
                is_valid is True
            ), f"Template with side effects should have valid syntax: {template}"
            assert error is None, f"Valid template should have no error: {template}"

            # Note: We cannot directly verify that side effects didn't occur,
            # but the fact that validation succeeds without a HA connection
            # proves that no execution happened

    def test_property_4_syntax_error_detection(self):
        """
        **Property 4 (Edge Case): Syntax Error Detection**

        Validate that validate_template_syntax() correctly detects various
        types of Jinja2 syntax errors without attempting to execute the template.

        **Validates: Requirements 7.2**
        """
        # Test cases: (template, expected_error_type_substring)
        syntax_error_cases = [
            ("{{ unclosed", "TemplateSyntaxError"),
            ("{% if %}", "TemplateSyntaxError"),
            ("{{ }}", "TemplateSyntaxError"),
            ("{% for %}", "TemplateSyntaxError"),
            ("{{ states('sensor.temp' }}", "TemplateSyntaxError"),
            ("{% if true %} no endif", "TemplateSyntaxError"),
            ("{{ 1 + }}", "TemplateSyntaxError"),
            ("{{ | filter }}", "TemplateSyntaxError"),
            ("{% endif %}", "TemplateSyntaxError"),  # endif without if
            ("{{ 'unclosed string }", "TemplateSyntaxError"),
        ]

        for template, expected_error_type in syntax_error_cases:
            is_valid, error = validate_template_syntax(template)

            # Property 1: Should detect as invalid
            assert is_valid is False, f"Syntax error should be detected: {template}"

            # Property 2: Should return error dict
            assert error is not None, f"Error dict should be returned: {template}"

            # Property 3: Error should have required fields
            assert "error_type" in error, f"Error should have error_type: {template}"
            assert "message" in error, f"Error should have message: {template}"

            # Property 4: Error type should match expected
            assert (
                expected_error_type in error["error_type"]
            ), f"Error type should be {expected_error_type}: {template}, got {error['error_type']}"

            # Property 5: Message should be non-empty
            assert (
                len(error["message"]) > 0
            ), f"Error message should be non-empty: {template}"

    def test_property_4_valid_multiline_templates(self):
        """
        **Property 4 (Edge Case): Valid Multi-line Templates**

        Validate that validate_template_syntax() correctly handles multi-line
        templates without executing them.

        **Validates: Requirements 7.2**
        """
        multiline_templates = [
            """
            {{ states('sensor.temperature') }}
            {{ states('sensor.humidity') }}
            """,
            """
            {% if states('sensor.motion') == 'on' %}
              Motion detected
            {% else %}
              No motion
            {% endif %}
            """,
            """
            {% for entity in ['sensor.temp', 'sensor.humidity'] %}
              {{ entity }}
            {% endfor %}
            """,
            """
            {# This is a comment #}
            {{ states('sensor.test') }}
            """,
        ]

        for template in multiline_templates:
            is_valid, error = validate_template_syntax(template)

            # Property: Multi-line templates with valid syntax should pass
            assert (
                is_valid is True
            ), f"Valid multi-line template should pass: {template}"
            assert (
                error is None
            ), f"Valid multi-line template should have no error: {template}"

    def test_property_4_invalid_multiline_templates(self):
        """
        **Property 4 (Edge Case): Invalid Multi-line Templates**

        Validate that validate_template_syntax() correctly detects syntax errors
        in multi-line templates and reports line numbers when available.

        **Validates: Requirements 7.2**
        """
        # Templates with errors on specific lines
        invalid_multiline_templates = [
            """
            {{ states('sensor.temperature') }}
            {{ unclosed
            """,
            """
            {% if states('sensor.motion') == 'on' %}
              Motion detected
            {# Missing endif #}
            """,
            """
            {{ states('sensor.temp') }}
            {{ }}
            {{ states('sensor.humidity') }}
            """,
        ]

        for template in invalid_multiline_templates:
            is_valid, error = validate_template_syntax(template)

            # Property 1: Should detect as invalid
            assert (
                is_valid is False
            ), f"Invalid multi-line template should fail: {template}"

            # Property 2: Should return error dict
            assert error is not None, f"Error dict should be returned: {template}"

            # Property 3: Error should have required fields
            assert "error_type" in error, f"Error should have error_type: {template}"
            assert "message" in error, f"Error should have message: {template}"

            # Property 4: Line number may be present (optional but useful)
            # If line number is present, it should be positive
            if "line" in error and error["line"] is not None:
                assert error["line"] > 0, f"Line number should be positive: {template}"

    @given(st.text(min_size=1, max_size=200))
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100
    )
    def test_property_5_error_structure_completeness(self, template_content: str):
        """
        **Property 5: Error Structure Completeness**

        For any template error (syntax or runtime), the error response should be valid JSON
        containing at minimum an error_type field and a message field, and should include
        line, column, and context fields when that information is available from the
        underlying Jinja2 exception.

        This test verifies that format_template_error() produces complete and correct
        error structures that match the TemplateError dataclass specification.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from jinja2 import TemplateSyntaxError
        from ha_dev_tools.template_validator import format_template_error, TemplateError

        # Generate templates with various types of syntax errors
        invalid_templates = [
            "{{ unclosed",
            "{% if %}",
            "{{ }}",
            "{% for %}",
            f"{{{{ {template_content}",  # Unclosed with random content
            "{{ states('sensor.temp' }}",  # Missing closing paren
            "{% if true %} no endif",
            "{{ 1 + }}",  # Incomplete expression
        ]

        for template in invalid_templates:
            # Try to parse the template to generate an error
            try:
                env = Environment()
                env.parse(template)
                # If parsing succeeds, skip this template
                continue
            except TemplateSyntaxError as e:
                # Format the error using format_template_error
                error_dict = format_template_error(e, template)

                # Property 1: Error dict must be a dictionary
                assert isinstance(
                    error_dict, dict
                ), f"Error should be a dict, got {type(error_dict)}"

                # Property 2: Required fields must be present
                assert (
                    "error_type" in error_dict
                ), f"Error must have error_type field: {error_dict}"
                assert (
                    "message" in error_dict
                ), f"Error must have message field: {error_dict}"

                # Property 3: Required fields must be strings
                assert isinstance(
                    error_dict["error_type"], str
                ), f"error_type must be string: {error_dict['error_type']}"
                assert isinstance(
                    error_dict["message"], str
                ), f"message must be string: {error_dict['message']}"

                # Property 4: Required fields must be non-empty
                assert (
                    len(error_dict["error_type"]) > 0
                ), f"error_type must be non-empty: {error_dict}"
                assert (
                    len(error_dict["message"]) > 0
                ), f"message must be non-empty: {error_dict}"

                # Property 5: Optional fields, when present, must have correct types
                if "line" in error_dict and error_dict["line"] is not None:
                    assert isinstance(
                        error_dict["line"], int
                    ), f"line must be int when present: {error_dict['line']}"
                    assert (
                        error_dict["line"] > 0
                    ), f"line must be positive: {error_dict['line']}"

                if "column" in error_dict and error_dict["column"] is not None:
                    assert isinstance(
                        error_dict["column"], int
                    ), f"column must be int when present: {error_dict['column']}"
                    assert (
                        error_dict["column"] >= 0
                    ), f"column must be non-negative: {error_dict['column']}"

                if "context" in error_dict and error_dict["context"] is not None:
                    assert isinstance(
                        error_dict["context"], str
                    ), f"context must be string when present: {error_dict['context']}"

                if (
                    "template_excerpt" in error_dict
                    and error_dict["template_excerpt"] is not None
                ):
                    assert isinstance(
                        error_dict["template_excerpt"], list
                    ), f"template_excerpt must be list when present: {error_dict['template_excerpt']}"
                    # All items in template_excerpt must be strings
                    for item in error_dict["template_excerpt"]:
                        assert isinstance(
                            item, str
                        ), f"template_excerpt items must be strings: {item}"

                # Property 6: Error dict should be serializable to TemplateError
                try:
                    template_error = TemplateError(
                        error_type=error_dict["error_type"],
                        message=error_dict["message"],
                        line=error_dict.get("line"),
                        column=error_dict.get("column"),
                        context=error_dict.get("context"),
                        template_excerpt=error_dict.get("template_excerpt"),
                    )

                    # Property 7: TemplateError.to_dict() should produce equivalent dict
                    reconstructed = template_error.to_dict()
                    assert (
                        "error_type" in reconstructed
                    ), "Reconstructed dict must have error_type"
                    assert (
                        "message" in reconstructed
                    ), "Reconstructed dict must have message"
                    assert (
                        reconstructed["error_type"] == error_dict["error_type"]
                    ), "error_type must match"
                    assert (
                        reconstructed["message"] == error_dict["message"]
                    ), "message must match"

                except Exception as e:
                    pytest.fail(
                        f"Error dict should be convertible to TemplateError: {e}"
                    )

            except Exception as e:
                # Other exceptions are also valid for testing
                error_dict = format_template_error(e, template)

                # Same properties apply for all error types
                assert isinstance(
                    error_dict, dict
                ), f"Error should be a dict, got {type(error_dict)}"
                assert (
                    "error_type" in error_dict
                ), f"Error must have error_type field: {error_dict}"
                assert (
                    "message" in error_dict
                ), f"Error must have message field: {error_dict}"

    def test_property_5_error_with_line_info(self):
        """
        **Property 5 (Edge Case): Error With Line Information**

        When a Jinja2 exception includes line number information, format_template_error()
        should include line, context, and template_excerpt fields in the error response.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from jinja2 import TemplateSyntaxError
        from ha_dev_tools.template_validator import format_template_error

        # Multi-line template with error on line 3
        template = """{{ states('sensor.temp') }}
{{ states('sensor.humidity') }}
{{ unclosed
{{ states('sensor.pressure') }}"""

        try:
            env = Environment()
            env.parse(template)
            pytest.fail("Template should have syntax error")
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)

            # Property 1: Required fields present
            assert "error_type" in error_dict, "Must have error_type"
            assert "message" in error_dict, "Must have message"

            # Property 2: Line information should be present
            assert "line" in error_dict, "Should have line field"
            assert error_dict["line"] is not None, "Line should not be None"
            assert error_dict["line"] > 0, "Line should be positive"

            # Property 3: Context should be present (the error line)
            assert "context" in error_dict, "Should have context field"
            assert error_dict["context"] is not None, "Context should not be None"
            assert isinstance(error_dict["context"], str), "Context should be string"

            # Property 4: Template excerpt should be present for multi-line templates
            assert (
                "template_excerpt" in error_dict
            ), "Should have template_excerpt field"
            assert (
                error_dict["template_excerpt"] is not None
            ), "template_excerpt should not be None"
            assert isinstance(
                error_dict["template_excerpt"], list
            ), "template_excerpt should be list"
            assert (
                len(error_dict["template_excerpt"]) > 0
            ), "template_excerpt should not be empty"

            # Property 5: Template excerpt should contain error marker
            has_error_marker = any(
                "<-- ERROR" in line for line in error_dict["template_excerpt"]
            )
            assert has_error_marker, "template_excerpt should mark error line"

    def test_property_5_error_without_line_info(self):
        """
        **Property 5 (Edge Case): Error Without Line Information**

        When a Jinja2 exception does not include line number information,
        format_template_error() should still return a valid error dict with
        error_type and message, but may omit line, context, and template_excerpt.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from ha_dev_tools.template_validator import format_template_error

        # Create a generic exception without line info
        template = "{{ some template }}"
        error = Exception("Generic error without line information")

        error_dict = format_template_error(error, template)

        # Property 1: Required fields must be present
        assert "error_type" in error_dict, "Must have error_type"
        assert "message" in error_dict, "Must have message"

        # Property 2: Required fields must be valid
        assert error_dict["error_type"] == "Exception", "error_type should be Exception"
        assert (
            error_dict["message"] == "Generic error without line information"
        ), "message should match exception message"

        # Property 3: Optional fields may be absent or None
        # This is acceptable - the error dict is still valid
        if "line" in error_dict:
            assert error_dict["line"] is None or isinstance(
                error_dict["line"], int
            ), "line should be None or int"

        if "context" in error_dict:
            assert error_dict["context"] is None or isinstance(
                error_dict["context"], str
            ), "context should be None or string"

    def test_property_5_single_line_template_error(self):
        """
        **Property 5 (Edge Case): Single Line Template Error**

        For single-line templates with errors, format_template_error() should include
        line and context but may omit template_excerpt (since there's no surrounding context).

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from jinja2 import TemplateSyntaxError
        from ha_dev_tools.template_validator import format_template_error

        # Single-line template with error
        template = "{{ unclosed"

        try:
            env = Environment()
            env.parse(template)
            pytest.fail("Template should have syntax error")
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)

            # Property 1: Required fields present
            assert "error_type" in error_dict, "Must have error_type"
            assert "message" in error_dict, "Must have message"

            # Property 2: Line should be present (line 1)
            assert "line" in error_dict, "Should have line field"
            assert error_dict["line"] == 1, "Single line template should report line 1"

            # Property 3: Context should be present
            assert "context" in error_dict, "Should have context field"
            assert (
                error_dict["context"] == template
            ), "Context should be the template line"

            # Property 4: Template excerpt may be omitted for single-line templates
            # (This is implementation-dependent, but if present, should be valid)
            if (
                "template_excerpt" in error_dict
                and error_dict["template_excerpt"] is not None
            ):
                assert isinstance(
                    error_dict["template_excerpt"], list
                ), "template_excerpt should be list if present"

    def test_property_5_multiline_template_error(self):
        """
        **Property 5 (Edge Case): Multi-line Template Error**

        For multi-line templates with errors, format_template_error() should include
        line, context, and template_excerpt with surrounding lines for context.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from jinja2 import TemplateSyntaxError
        from ha_dev_tools.template_validator import format_template_error

        # Multi-line template with error on line 3
        template = """Line 1: {{ states('sensor.temp') }}
Line 2: {{ states('sensor.humidity') }}
Line 3: {{ unclosed
Line 4: {{ states('sensor.pressure') }}
Line 5: {{ states('sensor.motion') }}"""

        try:
            env = Environment()
            env.parse(template)
            pytest.fail("Template should have syntax error")
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)

            # Property 1: Required fields present
            assert "error_type" in error_dict, "Must have error_type"
            assert "message" in error_dict, "Must have message"

            # Property 2: Line information present
            assert "line" in error_dict, "Should have line field"
            assert error_dict["line"] is not None, "Line should not be None"

            # Property 3: Context present
            assert "context" in error_dict, "Should have context field"
            assert error_dict["context"] is not None, "Context should not be None"

            # Property 4: Template excerpt present for multi-line templates
            assert (
                "template_excerpt" in error_dict
            ), "Should have template_excerpt field"
            assert (
                error_dict["template_excerpt"] is not None
            ), "template_excerpt should not be None"
            assert isinstance(
                error_dict["template_excerpt"], list
            ), "template_excerpt should be list"

            # Property 5: Template excerpt should include surrounding lines
            # Should have at least 3 lines (error line + some context)
            assert (
                len(error_dict["template_excerpt"]) >= 3
            ), "template_excerpt should include surrounding lines"

            # Property 6: Template excerpt should mark error line
            has_error_marker = any(
                "<-- ERROR" in line for line in error_dict["template_excerpt"]
            )
            assert (
                has_error_marker
            ), "template_excerpt should mark error line with '<-- ERROR'"

            # Property 7: Template excerpt lines should have line numbers
            for excerpt_line in error_dict["template_excerpt"]:
                assert excerpt_line.startswith(
                    "Line "
                ), f"Excerpt line should start with 'Line ': {excerpt_line}"

    def test_property_5_error_dict_to_template_error_conversion(self):
        """
        **Property 5 (Edge Case): Error Dict to TemplateError Conversion**

        Any error dict produced by format_template_error() should be convertible
        to a TemplateError dataclass and back to dict without loss of information.

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
        """
        from jinja2 import TemplateSyntaxError
        from ha_dev_tools.template_validator import format_template_error, TemplateError

        # Test with various templates
        test_cases = [
            "{{ unclosed",  # Single line error
            "{{ states('sensor.temp') }}\n{{ unclosed\n{{ states('sensor.humidity') }}",  # Multi-line
            "{% if %}",  # Different error type
        ]

        for template in test_cases:
            try:
                env = Environment()
                env.parse(template)
                continue  # Skip if no error
            except TemplateSyntaxError as e:
                # Format error
                error_dict = format_template_error(e, template)

                # Convert to TemplateError
                template_error = TemplateError(
                    error_type=error_dict["error_type"],
                    message=error_dict["message"],
                    line=error_dict.get("line"),
                    column=error_dict.get("column"),
                    context=error_dict.get("context"),
                    template_excerpt=error_dict.get("template_excerpt"),
                )

                # Convert back to dict
                reconstructed_dict = template_error.to_dict()

                # Property 1: Required fields must match
                assert (
                    reconstructed_dict["error_type"] == error_dict["error_type"]
                ), "error_type must be preserved"
                assert (
                    reconstructed_dict["message"] == error_dict["message"]
                ), "message must be preserved"

                # Property 2: Optional fields must match when present
                for field in ["line", "column", "context", "template_excerpt"]:
                    if field in error_dict and error_dict[field] is not None:
                        assert (
                            field in reconstructed_dict
                        ), f"{field} should be in reconstructed dict"
                        assert (
                            reconstructed_dict[field] == error_dict[field]
                        ), f"{field} must be preserved"

                # Property 3: Reconstructed dict should not have None values for optional fields
                # (TemplateError.to_dict() only includes fields that are not None)
                for field in ["line", "column", "context", "template_excerpt"]:
                    if field in reconstructed_dict:
                        assert (
                            reconstructed_dict[field] is not None
                        ), f"{field} should not be None in reconstructed dict"

    @given(
        st.sampled_from(
            [
                # Undefined variables
                "{{ undefined_var }}",
                "{{ some_undefined_variable }}",
                "{{ missing_value }}",
                # Undefined functions
                "{{ undefined_func() }}",
                "{{ missing_function(123) }}",
                "{{ nonexistent_helper('test') }}",
                # Undefined filters
                "{{ 'value' | undefined_filter }}",
                "{{ 42 | missing_filter }}",
                "{{ 'test' | nonexistent_pipe }}",
                # Mixed undefined references
                "{{ undefined_var | some_filter }}",
                "{{ missing_func() | another_filter }}",
            ]
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100
    )
    def test_property_6_undefined_reference_error_reporting(self, template: str):
        """
        **Property 6: Undefined Reference Error Reporting**

        For any template that references an undefined variable, function, or filter,
        the error message should contain the name of the undefined reference.

        This property validates that when templates fail due to undefined references,
        the error reporting is clear and identifies what is missing.

        **Validates: Requirements 1.5, 3.3, 3.4**
        """
        # Create API client
        url = "http://homeassistant.local:8123"
        token = "test_token_12345"
        client = HAAPIClient(url, token)

        # Mock the /api/template endpoint to return an UndefinedError
        # Home Assistant will detect undefined references during rendering
        with aioresponses() as mock:
            # Extract the undefined reference name from the template
            # This is what we expect to see in the error message
            import re

            # Try to extract the undefined name from various patterns
            undefined_name = None

            # Pattern 1: {{ undefined_var }}
            var_match = re.search(r"\{\{\s*(\w+)\s*\}\}", template)
            if var_match:
                undefined_name = var_match.group(1)

            # Pattern 2: {{ undefined_func() }}
            func_match = re.search(r"\{\{\s*(\w+)\s*\(", template)
            if func_match:
                undefined_name = func_match.group(1)

            # Pattern 3: {{ value | undefined_filter }}
            filter_match = re.search(r"\|\s*(\w+)", template)
            if filter_match:
                undefined_name = filter_match.group(1)

            # Mock HA API to return an undefined error
            error_message = f"UndefinedError: '{undefined_name}' is undefined"
            mock.post(f"{client.base_url}/api/template", status=400, body=error_message)

            # Attempt to render the template (run async in sync test)
            try:
                asyncio.run(client.render_template(template))
                pytest.fail("Expected HAAPIError for undefined reference")
            except HAAPIError as e:
                # Property 1: Error should be raised
                assert (
                    e.error_code == "INVALID_REQUEST"
                ), "Error code should be 'INVALID_REQUEST' for template errors"

                # Property 2: Error message should contain the undefined reference name
                if undefined_name:
                    assert (
                        undefined_name in e.message
                    ), f"Error message should contain undefined reference name '{undefined_name}'"

                # Property 3: Error message should indicate it's an undefined reference
                assert (
                    "undefined" in e.message.lower()
                    or "not defined" in e.message.lower()
                ), "Error message should indicate undefined reference"

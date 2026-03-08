"""Unit tests for template_validator module."""

import pytest
from jinja2 import TemplateSyntaxError, UndefinedError

from ha_dev_tools.template_validator import (
    extract_entity_references,
    validate_template_syntax,
    format_template_error,
    format_entity_validation_warnings,
    _extract_template_excerpt,
    _extract_error_line,
    TemplateError,
    ValidationResult,
)


class TestExtractEntityReferences:
    """Tests for extract_entity_references function."""
    
    def test_states_function_single_quotes(self):
        """Test extraction of entity from states() with single quotes."""
        template = "{{ states('sensor.temperature') }}"
        result = extract_entity_references(template)
        assert result == ['sensor.temperature']
    
    def test_states_function_double_quotes(self):
        """Test extraction of entity from states() with double quotes."""
        template = '{{ states("sensor.humidity") }}'
        result = extract_entity_references(template)
        assert result == ['sensor.humidity']
    
    def test_state_attr_function(self):
        """Test extraction of entity from state_attr()."""
        template = "{{ state_attr('climate.living_room', 'temperature') }}"
        result = extract_entity_references(template)
        assert result == ['climate.living_room']
    
    def test_is_state_function(self):
        """Test extraction of entity from is_state()."""
        template = "{{ is_state('light.kitchen', 'on') }}"
        result = extract_entity_references(template)
        assert result == ['light.kitchen']
    
    def test_is_state_attr_function(self):
        """Test extraction of entity from is_state_attr()."""
        template = "{{ is_state_attr('sensor.temp', 'unit', 'C') }}"
        result = extract_entity_references(template)
        assert result == ['sensor.temp']
    
    def test_direct_state_access(self):
        """Test extraction of entity from states.domain.entity pattern."""
        template = "{{ states.sensor.temperature }}"
        result = extract_entity_references(template)
        assert result == ['sensor.temperature']
    
    def test_no_entities(self):
        """Test template with no entity references."""
        template = "{{ 'Hello World' }}"
        result = extract_entity_references(template)
        assert result == []
    
    def test_empty_template(self):
        """Test empty template."""
        template = ""
        result = extract_entity_references(template)
        assert result == []
    
    def test_mixed_patterns(self):
        """Test template with multiple entity reference patterns."""
        template = """
        {{ states('sensor.temp') }}
        {{ state_attr('climate.living', 'temp') }}
        {{ is_state('light.kitchen', 'on') }}
        {{ states.binary_sensor.door }}
        """
        result = extract_entity_references(template)
        # Should be sorted and unique
        assert result == [
            'binary_sensor.door',
            'climate.living',
            'light.kitchen',
            'sensor.temp'
        ]
    
    def test_duplicate_entities(self):
        """Test that duplicate entities are deduplicated."""
        template = """
        {{ states('sensor.temp') }}
        {{ states('sensor.temp') }}
        {{ states.sensor.temp }}
        """
        result = extract_entity_references(template)
        assert result == ['sensor.temp']
    
    def test_entity_with_numbers(self):
        """Test entity IDs containing numbers."""
        template = "{{ states('sensor.temp_1') }}"
        result = extract_entity_references(template)
        assert result == ['sensor.temp_1']
    
    def test_entity_with_underscores(self):
        """Test entity IDs with underscores in domain and name."""
        template = "{{ states('binary_sensor.motion_sensor_1') }}"
        result = extract_entity_references(template)
        assert result == ['binary_sensor.motion_sensor_1']
    
    def test_whitespace_in_function_call(self):
        """Test entity extraction with whitespace in function call."""
        template = "{{ states(  'sensor.temp'  ) }}"
        result = extract_entity_references(template)
        assert result == ['sensor.temp']


class TestValidateTemplateSyntax:
    """Tests for validate_template_syntax function."""
    
    def test_valid_single_line_template(self):
        """Test validation of valid single-line template."""
        template = "{{ states('sensor.temperature') }}"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None
    
    def test_valid_multi_line_template(self):
        """Test validation of valid multi-line template."""
        template = """
        {% if states('sensor.temp') | float > 20 %}
          Hot
        {% else %}
          Cold
        {% endif %}
        """
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None
    
    def test_valid_template_with_filters(self):
        """Test validation of template with filters."""
        template = "{{ states('sensor.temp') | float | round(1) }}"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None
    
    def test_valid_template_with_logic(self):
        """Test validation of template with conditional logic."""
        template = "{{ 'on' if is_state('light.kitchen', 'on') else 'off' }}"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is True
        assert error is None
    
    def test_syntax_error_unclosed_tag(self):
        """Test detection of unclosed tag syntax error."""
        template = "{{ states('sensor.temp') "
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert error['error_type'] == 'TemplateSyntaxError'
        assert 'message' in error
    
    def test_syntax_error_invalid_expression(self):
        """Test detection of invalid expression syntax error."""
        template = "{{ states('sensor.temp' }}"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert error['error_type'] == 'TemplateSyntaxError'
    
    def test_syntax_error_unclosed_block(self):
        """Test detection of unclosed block syntax error."""
        template = "{% if true %} test"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert error['error_type'] == 'TemplateSyntaxError'
    
    def test_syntax_error_with_line_number(self):
        """Test that syntax error includes line number."""
        template = """
        {{ states('sensor.temp') }}
        {{ invalid syntax
        """
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        assert 'line' in error
        assert error['line'] is not None
    
    def test_syntax_error_with_context(self):
        """Test that syntax error includes context line."""
        template = "{{ invalid syntax"
        is_valid, error = validate_template_syntax(template)
        assert is_valid is False
        assert error is not None
        if error.get('line'):
            assert 'context' in error


class TestFormatTemplateError:
    """Tests for format_template_error function."""
    
    def test_format_template_syntax_error_with_line(self):
        """Test formatting TemplateSyntaxError with line number."""
        template = "{{ invalid syntax"
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            assert error_dict['error_type'] == 'TemplateSyntaxError'
            assert 'message' in error_dict
            assert 'line' in error_dict
            assert error_dict['line'] == 1
            assert 'context' in error_dict
            assert error_dict['context'] == template
    
    def test_format_template_syntax_error_multi_line(self):
        """Test formatting TemplateSyntaxError in multi-line template."""
        template = """Line 1
Line 2
{{ invalid
Line 4"""
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            assert error_dict['error_type'] == 'TemplateSyntaxError'
            assert 'line' in error_dict
            # Line number reported by Jinja2 may vary, just verify it's present and reasonable
            assert error_dict['line'] in [3, 4]  # Could be line 3 or 4 depending on Jinja2 version
            assert 'context' in error_dict
            assert 'template_excerpt' in error_dict
            assert isinstance(error_dict['template_excerpt'], list)
            # Should include surrounding lines
            assert any('ERROR' in line for line in error_dict['template_excerpt'])
    
    def test_format_undefined_error(self):
        """Test formatting UndefinedError."""
        template = "{{ undefined_var }}"
        # Create a mock UndefinedError
        error = UndefinedError("'undefined_var' is undefined")
        error_dict = format_template_error(error, template)
        assert error_dict['error_type'] == 'UndefinedError'
        assert 'undefined_var' in error_dict['message']
    
    def test_format_error_without_line_info(self):
        """Test formatting exception without line number information."""
        template = "{{ test }}"
        error = ValueError("Some error")
        error_dict = format_template_error(error, template)
        assert error_dict['error_type'] == 'ValueError'
        assert error_dict['message'] == 'Some error'
        assert 'line' not in error_dict
        assert 'context' not in error_dict
    
    def test_format_error_with_column(self):
        """Test formatting error with column number."""
        template = "{{ test }}"
        # Create error with column info
        error = TemplateSyntaxError("test error", 1)
        error.colno = 5
        error_dict = format_template_error(error, template)
        assert 'column' in error_dict
        assert error_dict['column'] == 5
    
    def test_format_error_single_line_no_excerpt(self):
        """Test that single-line templates don't include excerpt."""
        template = "{{ invalid"
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            # Single line template should not have excerpt
            assert 'template_excerpt' not in error_dict or error_dict['template_excerpt'] is None


class TestExtractTemplateExcerpt:
    """Tests for _extract_template_excerpt function."""
    
    def test_extract_excerpt_middle_line(self):
        """Test extracting excerpt with error in middle of template."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
        error_line = 3
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        assert len(excerpt) == 5  # 2 before + error + 2 after
        assert "Line 1:" in excerpt[0]
        assert "Line 3:" in excerpt[2]
        assert "<-- ERROR" in excerpt[2]
        assert "Line 5:" in excerpt[4]
    
    def test_extract_excerpt_first_line(self):
        """Test extracting excerpt with error at first line."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        error_line = 1
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        # Should only include lines 1-3 (no lines before line 1)
        assert len(excerpt) == 3
        assert "Line 1:" in excerpt[0]
        assert "<-- ERROR" in excerpt[0]
        assert "Line 3:" in excerpt[2]
    
    def test_extract_excerpt_last_line(self):
        """Test extracting excerpt with error at last line."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        error_line = 4
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        # Should only include lines 2-4 (no lines after line 4)
        assert len(excerpt) == 3
        assert "Line 2:" in excerpt[0]
        assert "Line 4:" in excerpt[2]
        assert "<-- ERROR" in excerpt[2]
    
    def test_extract_excerpt_custom_context(self):
        """Test extracting excerpt with custom context lines."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5", "Line 6", "Line 7"]
        error_line = 4
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=1)
        
        # Should include 1 before + error + 1 after = 3 lines
        assert len(excerpt) == 3
        assert "Line 3:" in excerpt[0]
        assert "Line 4:" in excerpt[1]
        assert "<-- ERROR" in excerpt[1]
        assert "Line 5:" in excerpt[2]
    
    def test_extract_excerpt_error_marker(self):
        """Test that error line is properly marked."""
        lines = ["Line 1", "Line 2", "Line 3"]
        error_line = 2
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=1)
        
        # Find the error line
        error_lines = [line for line in excerpt if "<-- ERROR" in line]
        assert len(error_lines) == 1
        assert "Line 2:" in error_lines[0]


class TestExtractErrorLine:
    """Tests for _extract_error_line function."""
    
    def test_extract_valid_line(self):
        """Test extracting a valid line from template."""
        template = "Line 1\nLine 2\nLine 3"
        line = _extract_error_line(template, 2)
        assert line == "Line 2"
    
    def test_extract_first_line(self):
        """Test extracting first line."""
        template = "Line 1\nLine 2\nLine 3"
        line = _extract_error_line(template, 1)
        assert line == "Line 1"
    
    def test_extract_last_line(self):
        """Test extracting last line."""
        template = "Line 1\nLine 2\nLine 3"
        line = _extract_error_line(template, 3)
        assert line == "Line 3"
    
    def test_extract_line_out_of_range_high(self):
        """Test extracting line number beyond template length."""
        template = "Line 1\nLine 2"
        line = _extract_error_line(template, 5)
        assert line is None
    
    def test_extract_line_out_of_range_low(self):
        """Test extracting line number less than 1."""
        template = "Line 1\nLine 2"
        line = _extract_error_line(template, 0)
        assert line is None
    
    def test_extract_line_single_line_template(self):
        """Test extracting from single-line template."""
        template = "Single line"
        line = _extract_error_line(template, 1)
        assert line == "Single line"


class TestFormatEntityValidationWarnings:
    """Tests for format_entity_validation_warnings function."""
    
    def test_format_single_missing_entity(self):
        """Test formatting warning for single missing entity."""
        missing = ['sensor.temperature']
        warning = format_entity_validation_warnings(missing)
        assert 'sensor.temperature' in warning
        assert 'does not exist' in warning
        assert 'entity' in warning.lower()
    
    def test_format_multiple_missing_entities(self):
        """Test formatting warning for multiple missing entities."""
        missing = ['sensor.temp', 'light.kitchen', 'climate.living']
        warning = format_entity_validation_warnings(missing)
        assert 'sensor.temp' in warning
        assert 'light.kitchen' in warning
        assert 'climate.living' in warning
        assert 'entities' in warning.lower()
        assert 'do not exist' in warning
    
    def test_format_empty_list(self):
        """Test formatting warning with empty list."""
        missing = []
        warning = format_entity_validation_warnings(missing)
        assert warning == ""
    
    def test_format_warning_structure(self):
        """Test that warning has proper structure."""
        missing = ['sensor.test']
        warning = format_entity_validation_warnings(missing)
        assert warning.startswith('Warning:')


class TestTemplateError:
    """Tests for TemplateError dataclass."""
    
    def test_to_dict_minimal(self):
        """Test to_dict with minimal fields."""
        error = TemplateError(
            error_type="TemplateSyntaxError",
            message="Test error"
        )
        result = error.to_dict()
        assert result['error_type'] == "TemplateSyntaxError"
        assert result['message'] == "Test error"
        assert 'line' not in result
        assert 'column' not in result
    
    def test_to_dict_complete(self):
        """Test to_dict with all fields."""
        error = TemplateError(
            error_type="TemplateSyntaxError",
            message="Test error",
            line=5,
            column=10,
            context="{{ invalid }}",
            template_excerpt=["Line 4", "Line 5  <-- ERROR", "Line 6"]
        )
        result = error.to_dict()
        assert result['error_type'] == "TemplateSyntaxError"
        assert result['message'] == "Test error"
        assert result['line'] == 5
        assert result['column'] == 10
        assert result['context'] == "{{ invalid }}"
        assert result['template_excerpt'] == ["Line 4", "Line 5  <-- ERROR", "Line 6"]


class TestValidationResult:
    """Tests for ValidationResult dataclass."""
    
    def test_to_dict_valid(self):
        """Test to_dict for valid result."""
        result = ValidationResult(valid=True)
        result_dict = result.to_dict()
        assert result_dict['valid'] is True
        assert 'error' not in result_dict
        assert 'warnings' not in result_dict
    
    def test_to_dict_with_error(self):
        """Test to_dict with error."""
        error = TemplateError(
            error_type="TemplateSyntaxError",
            message="Test error"
        )
        result = ValidationResult(valid=False, error=error)
        result_dict = result.to_dict()
        assert result_dict['valid'] is False
        assert 'error' in result_dict
        assert result_dict['error']['error_type'] == "TemplateSyntaxError"
    
    def test_to_dict_with_warnings(self):
        """Test to_dict with warnings."""
        result = ValidationResult(
            valid=True,
            warnings=["Warning 1", "Warning 2"]
        )
        result_dict = result.to_dict()
        assert result_dict['valid'] is True
        assert 'warnings' in result_dict
        assert result_dict['warnings'] == ["Warning 1", "Warning 2"]

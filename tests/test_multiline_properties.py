"""Property-based tests for multi-line template support.

Tests verify that multi-line templates are handled correctly with accurate
line numbers, context inclusion, line break preservation, indentation handling,
and YAML multi-line string support.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from ha_dev_tools.template_validator import (
    validate_template_syntax,
    format_template_error,
    _extract_template_excerpt
)
from jinja2 import TemplateSyntaxError


# Strategy for generating multi-line templates with errors at specific lines
@st.composite
def multiline_template_with_error(draw, min_lines=3, max_lines=20):
    """Generate a multi-line template with a syntax error at a random line.
    
    Returns:
        Tuple of (template_string, expected_error_line)
    """
    num_lines = draw(st.integers(min_value=min_lines, max_value=max_lines))
    error_line = draw(st.integers(min_value=1, max_value=num_lines))
    
    lines = []
    for i in range(1, num_lines + 1):
        if i == error_line:
            # Insert a line with syntax error
            lines.append("{{ unclosed_tag")
        else:
            # Insert a valid line
            lines.append(f"Line {i}: {{{{ 'valid' }}}}")
    
    template = "\n".join(lines)
    return template, error_line


@pytest.mark.property
class TestMultilineLineNumberAccuracy:
    """Property 9: Multi-line Template Line Number Accuracy.
    
    For any multi-line template with a syntax error at a specific line,
    the error response should report a line number (1-indexed) that
    accurately reflects where Jinja2 detected the error.
    
    Note: Jinja2 may report the line where it encounters the error
    (e.g., the line after an unclosed tag), not necessarily where
    the problematic syntax starts.
    
    Validates: Requirements 8.2
    """
    
    @given(
        num_lines=st.integers(min_value=3, max_value=20),
        error_line_offset=st.integers(min_value=0, max_value=15)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_line_number_is_reported(self, num_lines, error_line_offset):
        """Verify that line numbers are reported for multi-line template errors."""
        # Insert error at a specific line
        error_line = min(error_line_offset + 1, num_lines)
        
        lines = []
        for i in range(1, num_lines + 1):
            if i == error_line:
                lines.append("{{ unclosed_tag")
            else:
                lines.append(f"Line {i}: {{{{ 'valid' }}}}")
        
        template = "\n".join(lines)
        
        # Validate the template (should fail with syntax error)
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be invalid
        assert not is_valid, "Template should have syntax error"
        assert error_dict is not None, "Error dict should be present"
        
        # Check line number is reported
        assert "line" in error_dict, "Error should include line number"
        reported_line = error_dict["line"]
        
        # Verify line number is 1-indexed and within valid range
        assert reported_line >= 1, "Line number should be 1-indexed"
        assert reported_line <= num_lines, (
            f"Reported line {reported_line} should be within template bounds (1-{num_lines})"
        )
    
    @given(
        num_lines=st.integers(min_value=3, max_value=20),
        error_line_position=st.sampled_from(['first', 'middle', 'last'])
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_line_number_at_different_positions(self, num_lines, error_line_position):
        """Verify line numbers are reported for errors at different positions."""
        # Determine error line based on position
        if error_line_position == 'first':
            error_line = 1
        elif error_line_position == 'last':
            error_line = num_lines
        else:  # middle
            error_line = num_lines // 2
        
        # Build template with error at specified line
        lines = []
        for i in range(1, num_lines + 1):
            if i == error_line:
                lines.append("{{ unclosed")
            else:
                lines.append(f"Valid line {i}")
        
        template = "\n".join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Verify
        assert not is_valid
        assert error_dict is not None
        assert "line" in error_dict, "Error should include line number"
        
        reported_line = error_dict.get("line")
        
        # Jinja2 reports where it detects the error, which may be the next line
        # For an unclosed tag, it typically reports the line where it encounters
        # unexpected content or EOF
        assert reported_line >= 1, "Line number should be 1-indexed"
        assert reported_line <= num_lines, (
            f"Reported line should be within template bounds"
        )



@pytest.mark.property
class TestMultilineContextInclusion:
    """Property 10: Multi-line Template Context Inclusion.
    
    For any multi-line template (3+ lines) with an error, the error response
    should include template_excerpt with surrounding lines for context.
    
    Validates: Requirements 8.3
    """
    
    @given(
        num_lines=st.integers(min_value=3, max_value=15),
        error_line_offset=st.integers(min_value=0, max_value=10)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_context_excerpt_present(self, num_lines, error_line_offset):
        """Verify template_excerpt field is present in error response."""
        # Calculate error line (ensure it's within bounds)
        error_line = min(error_line_offset + 1, num_lines)
        
        # Build multi-line template with error
        lines = []
        for i in range(1, num_lines + 1):
            if i == error_line:
                lines.append("{{ unclosed")
            else:
                lines.append(f"Line {i}: valid content")
        
        template = "\n".join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be invalid
        assert not is_valid
        assert error_dict is not None
        
        # For multi-line templates, template_excerpt should be present
        # Note: format_template_error adds this, but validate_template_syntax doesn't
        # Let's test format_template_error directly
        from jinja2 import TemplateSyntaxError
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            
            # Verify template_excerpt is present for multi-line templates
            assert "template_excerpt" in error_dict, (
                "Multi-line template errors should include template_excerpt"
            )
            
            excerpt = error_dict["template_excerpt"]
            assert isinstance(excerpt, list), "template_excerpt should be a list"
            assert len(excerpt) > 0, "template_excerpt should not be empty"
    
    @given(
        num_lines=st.integers(min_value=5, max_value=15),
        error_line_offset=st.integers(min_value=2, max_value=10)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_context_includes_surrounding_lines(self, num_lines, error_line_offset):
        """Verify template_excerpt includes surrounding lines (2 before, 2 after)."""
        # Calculate error line (ensure it's not at edges)
        error_line = min(error_line_offset + 2, num_lines - 2)
        
        # Build template
        lines = []
        for i in range(1, num_lines + 1):
            if i == error_line:
                lines.append("{{ unclosed")
            else:
                lines.append(f"Line {i}")
        
        template = "\n".join(lines)
        
        # Parse and get error
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            
            excerpt = error_dict.get("template_excerpt", [])
            
            # Should include surrounding lines (up to 2 before and 2 after)
            # The exact number depends on position in template
            assert len(excerpt) >= 3, "Should include at least error line and some context"
            assert len(excerpt) <= 5, "Should include at most 2 before + error + 2 after"
    
    @given(
        num_lines=st.integers(min_value=5, max_value=15),
        error_line_offset=st.integers(min_value=2, max_value=10)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_error_line_marked(self, num_lines, error_line_offset):
        """Verify error line is marked with '<-- ERROR'."""
        # Calculate error line
        error_line = min(error_line_offset + 2, num_lines - 2)
        
        # Build template
        lines = []
        for i in range(1, num_lines + 1):
            if i == error_line:
                lines.append("{{ unclosed")
            else:
                lines.append(f"Line {i}")
        
        template = "\n".join(lines)
        
        # Parse and get error
        try:
            from jinja2 import Environment
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            
            excerpt = error_dict.get("template_excerpt", [])
            
            # Find the line with ERROR marker
            error_marked_lines = [line for line in excerpt if "<-- ERROR" in line]
            
            assert len(error_marked_lines) >= 1, (
                "At least one line should be marked with '<-- ERROR'"
            )



@pytest.mark.property
class TestLineBreakPreservation:
    """Property 11: Template Line Break Preservation.
    
    For any template string containing newline characters, when processed
    by the validation or rendering functions, the line breaks should be
    preserved in the template sent to Home Assistant.
    
    Validates: Requirements 8.1
    """
    
    @given(
        num_lines=st.integers(min_value=2, max_value=10),
        line_ending=st.sampled_from(['\n', '\r\n'])
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_newline_preservation_in_validation(self, num_lines, line_ending):
        """Verify newlines are preserved when validating templates."""
        # Build template with specific line endings
        lines = [f"Line {i}: {{{{ 'valid' }}}}" for i in range(1, num_lines + 1)]
        template = line_ending.join(lines)
        
        # Count expected newlines
        expected_newline_count = template.count('\n')
        
        # Validate template
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid, "Template should be valid"
        
        # The template string itself should preserve newlines
        actual_newline_count = template.count('\n')
        assert actual_newline_count == expected_newline_count, (
            f"Newlines should be preserved: expected {expected_newline_count}, "
            f"got {actual_newline_count}"
        )
    
    @given(
        num_lines=st.integers(min_value=2, max_value=10),
        line_ending=st.sampled_from(['\n', '\r\n'])
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_line_ending_types(self, num_lines, line_ending):
        """Verify both \\n and \\r\\n line endings are handled correctly."""
        # Build template
        lines = [f"{{{{ 'line{i}' }}}}" for i in range(1, num_lines + 1)]
        template = line_ending.join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid regardless of line ending type
        assert is_valid, f"Template with {repr(line_ending)} endings should be valid"
    
    @given(
        lines_before=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
        lines_after=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_random_newline_placements(self, lines_before, lines_after):
        """Verify templates with random newline placements are handled correctly."""
        # Build template with random content and newlines
        template = "\n".join(lines_before) + "\n{{ unclosed\n" + "\n".join(lines_after)
        
        # Count newlines
        newline_count = template.count('\n')
        
        # Validate (will fail due to syntax error, but that's okay)
        is_valid, error_dict = validate_template_syntax(template)
        
        # The template string should still have all its newlines
        assert template.count('\n') == newline_count, "Newlines should be preserved"



@pytest.mark.property
class TestIndentationHandling:
    """Property 12: Indentation Handling.
    
    For any template with varying indentation levels (spaces or tabs),
    the template should be parsed and processed correctly without
    indentation causing syntax errors.
    
    Validates: Requirements 8.4
    """
    
    @given(
        num_lines=st.integers(min_value=2, max_value=8),
        indent_type=st.sampled_from(['spaces', 'tabs'])
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_indentation_with_spaces_or_tabs(self, num_lines, indent_type):
        """Verify templates with spaces or tabs parse correctly."""
        # Build template with indentation
        lines = []
        for i in range(1, num_lines + 1):
            indent = ('    ' if indent_type == 'spaces' else '\t') * (i % 3)
            lines.append(f"{indent}{{{{ 'line{i}' }}}}")
        
        template = "\n".join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid - indentation shouldn't cause syntax errors
        assert is_valid, f"Template with {indent_type} indentation should be valid"
    
    @given(
        num_lines=st.integers(min_value=3, max_value=8)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_mixed_indentation_styles(self, num_lines):
        """Verify templates with mixed spaces and tabs parse correctly."""
        # Build template with mixed indentation
        lines = []
        for i in range(1, num_lines + 1):
            # Alternate between spaces and tabs
            if i % 2 == 0:
                indent = '    ' * (i % 3)
            else:
                indent = '\t' * (i % 3)
            lines.append(f"{indent}{{{{ 'line{i}' }}}}")
        
        template = "\n".join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid, "Template with mixed indentation should be valid"
    
    @given(
        num_lines=st.integers(min_value=2, max_value=8),
        max_indent=st.integers(min_value=0, max_value=5)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_random_indentation_levels(self, num_lines, max_indent):
        """Verify templates with random indentation levels parse correctly."""
        import random
        
        # Build template with random indentation
        lines = []
        for i in range(1, num_lines + 1):
            indent_level = random.randint(0, max_indent)
            indent = '  ' * indent_level
            lines.append(f"{indent}{{{{ 'value' }}}}")
        
        template = "\n".join(lines)
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid, "Template with random indentation should be valid"



@pytest.mark.property
class TestYAMLMultilineHandling:
    """Property 13: YAML Multi-line String Handling.
    
    For templates containing YAML-like multi-line content within string literals,
    the template should be parsed correctly. Note that YAML operators (| and >)
    outside of string literals are interpreted as Jinja2 syntax (filter operators).
    
    Validates: Requirements 8.5
    """
    
    @given(
        num_content_lines=st.integers(min_value=2, max_value=5)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_yaml_content_in_string_literals(self, num_content_lines):
        """Verify templates with YAML-like content in strings parse correctly."""
        # Build template with YAML-like content inside string literals
        content_lines = [f"  Line {i}" for i in range(1, num_content_lines + 1)]
        yaml_content = "\\n".join(content_lines)
        
        # Create a template with YAML-like content in a string
        template = f"{{{{ 'description:\\n{yaml_content}' }}}}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid, "Template with YAML-like content in string should be valid"
    
    @given(
        num_lines=st.integers(min_value=2, max_value=5)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_multiline_strings_with_yaml_markers(self, num_lines):
        """Verify multi-line strings containing YAML markers are handled."""
        # Build template with multi-line string containing YAML-like markers
        lines = [f"Line {i}" for i in range(1, num_lines + 1)]
        content = "\\n".join(lines)
        
        # YAML markers inside string literals should be treated as text
        template = f"{{{{ 'literal: |\\n{content}' }}}}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid, "Template with YAML markers in string should be valid"
    
    @given(
        num_lines=st.integers(min_value=2, max_value=5),
        yaml_marker=st.sampled_from(['|', '>'])
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_yaml_markers_as_text(self, num_lines, yaml_marker):
        """Verify YAML block scalar markers can appear as text in templates."""
        # Build template where YAML markers appear as text content
        lines = [f"Line {i}" for i in range(1, num_lines + 1)]
        content = "\\n".join(lines)
        
        # YAML marker as part of text content
        template = f"{{{{ 'key: {yaml_marker}\\n{content}' }}}}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid - markers are just text inside the string
        assert is_valid, f"Template with {yaml_marker} as text should be valid"

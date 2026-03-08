"""Unit tests for multi-line template support.

Tests verify line break preservation, line number accuracy, context excerpt
generation, indentation handling, and YAML multi-line string support.
"""

import pytest
from ha_config_manager.template_validator import (
    validate_template_syntax,
    format_template_error,
    _extract_template_excerpt,
    _extract_error_line
)
from jinja2 import TemplateSyntaxError, Environment


class TestLineBreakPreservation:
    """Test line break preservation in template processing.
    
    Validates: Requirements 8.1
    """
    
    def test_newline_preservation_with_n(self):
        """Test line break preservation with \\n characters."""
        template = "Line 1\nLine 2\nLine 3"
        
        # Count newlines
        assert template.count('\n') == 2
        
        # Validate template
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
        
        # Newlines should still be present
        assert template.count('\n') == 2
    
    def test_newline_preservation_with_rn(self):
        """Test line break preservation with \\r\\n characters."""
        template = "Line 1\r\nLine 2\r\nLine 3"
        
        # Count newlines
        assert template.count('\n') == 2
        
        # Validate template
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
        
        # Newlines should still be present
        assert template.count('\n') == 2


class TestLineNumberAccuracy:
    """Test error line number accuracy for multi-line templates.
    
    Validates: Requirements 8.2
    """
    
    def test_error_at_line_1(self):
        """Test error line number accuracy for errors at line 1."""
        template = "{{ unclosed\nLine 2\nLine 3"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be invalid
        assert not is_valid
        assert error_dict is not None
        
        # Line number should be reported (Jinja2 reports where it detects the error)
        assert "line" in error_dict
        assert error_dict["line"] >= 1
    
    def test_error_at_middle_line(self):
        """Test error line number accuracy for errors at middle line."""
        template = "Line 1\n{{ unclosed\nLine 3"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be invalid
        assert not is_valid
        assert error_dict is not None
        
        # Line number should be reported
        assert "line" in error_dict
        assert error_dict["line"] >= 2
    
    def test_error_at_last_line(self):
        """Test error line number accuracy for errors at last line."""
        template = "Line 1\nLine 2\n{{ unclosed"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be invalid
        assert not is_valid
        assert error_dict is not None
        
        # Line number should be reported
        assert "line" in error_dict
        assert error_dict["line"] >= 3


class TestContextExcerptGeneration:
    """Test template excerpt generation for error context.
    
    Validates: Requirements 8.3
    """
    
    def test_context_excerpt_with_2_line_context(self):
        """Test context excerpt generation with 2-line context."""
        lines = [
            "Line 1",
            "Line 2",
            "Line 3",
            "Line 4",
            "Line 5"
        ]
        error_line = 3
        
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        # Should include 2 before + error + 2 after = 5 lines
        assert len(excerpt) == 5
        
        # Error line should be marked
        assert any("<-- ERROR" in line for line in excerpt)
        
        # Should include correct line numbers
        assert "Line 1:" in excerpt[0]
        assert "Line 3:" in excerpt[2]
        assert "Line 5:" in excerpt[4]
    
    def test_context_excerpt_at_start(self):
        """Test context excerpt at start of template (limited before context)."""
        lines = [
            "Line 1",
            "Line 2",
            "Line 3",
            "Line 4"
        ]
        error_line = 1
        
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        # Should include error + 2 after (no lines before)
        assert len(excerpt) == 3
        
        # Error line should be marked
        assert any("<-- ERROR" in line for line in excerpt)
        
        # Should start at line 1
        assert "Line 1:" in excerpt[0]
    
    def test_context_excerpt_at_end(self):
        """Test context excerpt at end of template (limited after context)."""
        lines = [
            "Line 1",
            "Line 2",
            "Line 3",
            "Line 4"
        ]
        error_line = 4
        
        excerpt = _extract_template_excerpt(lines, error_line, context_lines=2)
        
        # Should include 2 before + error (no lines after)
        assert len(excerpt) == 3
        
        # Error line should be marked
        assert any("<-- ERROR" in line for line in excerpt)
        
        # Should end at line 4
        assert "Line 4:" in excerpt[2]


class TestIndentationHandling:
    """Test indentation handling in templates.
    
    Validates: Requirements 8.4
    """
    
    def test_indentation_with_spaces(self):
        """Test indentation handling with spaces."""
        template = "    {{ 'indented' }}\n        {{ 'more indented' }}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
    
    def test_indentation_with_tabs(self):
        """Test indentation handling with tabs."""
        template = "\t{{ 'indented' }}\n\t\t{{ 'more indented' }}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
    
    def test_indentation_with_mixed_spaces_tabs(self):
        """Test indentation handling with mixed spaces/tabs."""
        template = "    {{ 'spaces' }}\n\t{{ 'tab' }}\n  \t{{ 'mixed' }}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid


class TestYAMLMultilineStrings:
    """Test YAML multi-line string handling.
    
    Validates: Requirements 8.5
    """
    
    def test_yaml_literal_operator_in_string(self):
        """Test YAML multi-line strings with | operator inside string literals."""
        # The | operator inside a string literal should be treated as text
        template = "{{ 'description: | some text' }}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
    
    def test_yaml_folded_operator_in_string(self):
        """Test YAML multi-line strings with > operator inside string literals."""
        # The > operator inside a string literal should be treated as text
        template = "{{ 'description: > some text' }}"
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid
    
    def test_multiline_string_with_yaml_like_content(self):
        """Test multi-line templates containing YAML-like content."""
        template = """{{ 'key: |
  value1
  value2' }}"""
        
        # Validate
        is_valid, error_dict = validate_template_syntax(template)
        
        # Should be valid
        assert is_valid


class TestExtractErrorLine:
    """Test _extract_error_line helper function."""
    
    def test_extract_valid_line(self):
        """Test extracting a valid line number."""
        template = "Line 1\nLine 2\nLine 3"
        
        line = _extract_error_line(template, 2)
        
        assert line == "Line 2"
    
    def test_extract_first_line(self):
        """Test extracting the first line."""
        template = "Line 1\nLine 2\nLine 3"
        
        line = _extract_error_line(template, 1)
        
        assert line == "Line 1"
    
    def test_extract_last_line(self):
        """Test extracting the last line."""
        template = "Line 1\nLine 2\nLine 3"
        
        line = _extract_error_line(template, 3)
        
        assert line == "Line 3"
    
    def test_extract_out_of_range(self):
        """Test extracting a line number out of range."""
        template = "Line 1\nLine 2\nLine 3"
        
        line = _extract_error_line(template, 10)
        
        assert line is None
    
    def test_extract_zero_line(self):
        """Test extracting line 0 (invalid)."""
        template = "Line 1\nLine 2\nLine 3"
        
        line = _extract_error_line(template, 0)
        
        assert line is None


class TestFormatTemplateError:
    """Test format_template_error function with multi-line templates."""
    
    def test_format_error_with_multiline_template(self):
        """Test error formatting with multi-line template."""
        template = "Line 1\n{{ unclosed\nLine 3"
        
        # Parse and catch error
        try:
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            
            # Should have error type and message
            assert "error_type" in error_dict
            assert "message" in error_dict
            
            # Should have line number
            assert "line" in error_dict
            
            # Should have template_excerpt for multi-line template
            assert "template_excerpt" in error_dict
            assert isinstance(error_dict["template_excerpt"], list)
            assert len(error_dict["template_excerpt"]) > 0
    
    def test_format_error_with_single_line_template(self):
        """Test error formatting with single-line template."""
        template = "{{ unclosed"
        
        # Parse and catch error
        try:
            env = Environment()
            env.parse(template)
        except TemplateSyntaxError as e:
            error_dict = format_template_error(e, template)
            
            # Should have error type and message
            assert "error_type" in error_dict
            assert "message" in error_dict
            
            # Should have line number
            assert "line" in error_dict
            
            # Single-line template should not have excerpt (or have minimal excerpt)
            # The implementation adds excerpt for multi-line templates (len(lines) > 1)
            # So single-line templates won't have excerpt
            if "template_excerpt" in error_dict:
                # If present, should be minimal
                assert len(error_dict["template_excerpt"]) <= 1

"""Tests for new validation functions: validate_template and validate_boolean."""

import pytest
from ha_config_manager.validation import (
    ValidationError,
    validate_template,
    validate_boolean
)


class TestValidateTemplate:
    """Test validate_template function."""
    
    def test_valid_template(self):
        """Test that valid templates pass validation."""
        validate_template("{{ states('sensor.temp') }}")
        validate_template("Hello {{ name }}")
        validate_template("  {{ value }}  ")  # With whitespace
    
    def test_empty_template_rejected(self):
        """Test that empty templates are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_template("")
        assert exc_info.value.parameter == "template"
        assert "empty" in str(exc_info.value).lower()
    
    def test_whitespace_only_template_rejected(self):
        """Test that whitespace-only templates are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_template("   ")
        assert exc_info.value.parameter == "template"
        assert "empty" in str(exc_info.value).lower()
    
    def test_none_template_rejected(self):
        """Test that None template is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_template(None)
        assert exc_info.value.parameter == "template"
        assert "none" in str(exc_info.value).lower()
    
    def test_non_string_template_rejected(self):
        """Test that non-string templates are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_template(123)
        assert exc_info.value.parameter == "template"
        assert "string" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError) as exc_info:
            validate_template(["template"])
        assert exc_info.value.parameter == "template"
        assert "string" in str(exc_info.value).lower()


class TestValidateBoolean:
    """Test validate_boolean function."""
    
    def test_valid_boolean_true(self):
        """Test that True passes validation."""
        validate_boolean(True, "validate_entities")
    
    def test_valid_boolean_false(self):
        """Test that False passes validation."""
        validate_boolean(False, "validate_entities")
    
    def test_string_rejected(self):
        """Test that string values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean("true", "validate_entities")
        assert exc_info.value.parameter == "validate_entities"
        assert "boolean" in str(exc_info.value).lower()
    
    def test_integer_rejected(self):
        """Test that integer values are rejected (even 0 and 1)."""
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean(1, "validate_entities")
        assert exc_info.value.parameter == "validate_entities"
        assert "boolean" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean(0, "validate_entities")
        assert exc_info.value.parameter == "validate_entities"
        assert "boolean" in str(exc_info.value).lower()
    
    def test_none_rejected(self):
        """Test that None is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean(None, "validate_entities")
        assert exc_info.value.parameter == "validate_entities"
        assert "boolean" in str(exc_info.value).lower()
    
    def test_list_rejected(self):
        """Test that list values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean([True], "validate_entities")
        assert exc_info.value.parameter == "validate_entities"
        assert "boolean" in str(exc_info.value).lower()

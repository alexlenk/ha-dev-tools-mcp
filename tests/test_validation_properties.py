"""Property-based tests for input validation.

This module contains property-based tests that validate the correctness
of input validation functions across a wide range of inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from ha_dev_tools.validation import (
    ValidationError,
    validate_file_path,
    validate_positive_integer,
    validate_log_source,
    validate_entity_id,
    validate_domain,
    validate_service,
    validate_required_parameter
)


# Property 10: Path Validation
# For any file_path parameter containing path traversal sequences (like "../")
# or absolute paths, the validation should reject it with an error.
# Validates: Requirements 9.2

@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_rejects_traversal(path):
    """Property: Paths containing '..' should be rejected."""
    if ".." in path:
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path(path)
        assert "path traversal" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "file_path"


@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_rejects_absolute_paths(path):
    """Property: Absolute paths (starting with /) should be rejected."""
    if path.startswith("/"):
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path(path)
        assert "absolute path" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "file_path"


@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_rejects_windows_absolute_paths(path):
    """Property: Windows-style absolute paths (C:, etc.) should be rejected."""
    import re
    # Only test Windows paths that don't have other validation issues
    if re.match(r'^[a-zA-Z]:', path) and "\x00" not in path and ".." not in path:
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path(path)
        assert "absolute path" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "file_path"


@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_rejects_null_bytes(path):
    """Property: Paths containing null bytes should be rejected."""
    if "\x00" in path:
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path(path)
        assert "null byte" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "file_path"


@given(st.text(min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_accepts_safe_paths(path):
    """Property: Safe relative paths should be accepted."""
    # Only test paths that don't contain dangerous patterns
    if (
        ".." not in path
        and not path.startswith("/")
        and "\x00" not in path
        and not path.startswith(tuple(f"{c}:" for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    ):
        # Should not raise an exception
        try:
            validate_file_path(path)
        except ValidationError:
            pytest.fail(f"Safe path '{path}' was incorrectly rejected")


@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_path_validation_empty_path_rejected(path):
    """Property: Empty paths should be rejected."""
    if not path:
        with pytest.raises(ValidationError) as exc_info:
            validate_file_path(path)
        assert "cannot be empty" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "file_path"


# Property 11: Numeric Parameter Validation
# For any numeric parameter (lines, offset, limit) in tool calls, if the value
# is not a positive integer, the validation should reject it with an error.
# Validates: Requirements 9.4

@given(st.integers())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_numeric_validation_rejects_negative_values(value):
    """Property: Negative integers should be rejected."""
    if value < 1:
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(value, "test_param", min_value=1)
        assert "at least 1" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "test_param"


@given(st.integers(min_value=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_numeric_validation_accepts_positive_values(value):
    """Property: Positive integers should be accepted."""
    # Should not raise an exception
    try:
        validate_positive_integer(value, "test_param", min_value=1)
    except ValidationError:
        pytest.fail(f"Positive integer {value} was incorrectly rejected")


@given(st.integers(min_value=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_numeric_validation_respects_max_value(value):
    """Property: Values exceeding max_value should be rejected."""
    max_val = 1000
    if value > max_val:
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(value, "test_param", min_value=1, max_value=max_val)
        assert f"at most {max_val}" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "test_param"


@given(st.integers(min_value=1, max_value=1000))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_numeric_validation_accepts_values_within_bounds(value):
    """Property: Values within min and max bounds should be accepted."""
    # Should not raise an exception
    try:
        validate_positive_integer(value, "test_param", min_value=1, max_value=1000)
    except ValidationError:
        pytest.fail(f"Value {value} within bounds was incorrectly rejected")


@given(st.one_of(st.text(), st.floats(), st.booleans(), st.none()))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_numeric_validation_rejects_non_integers(value):
    """Property: Non-integer values should be rejected."""
    if not isinstance(value, int) or isinstance(value, bool):
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(value, "test_param")
        assert "must be an integer" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "test_param"


# Additional validation property tests

@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_log_source_validation_rejects_unsupported(log_source):
    """Property: Unsupported log sources should be rejected."""
    if log_source not in ["core"]:
        with pytest.raises(ValidationError) as exc_info:
            validate_log_source(log_source)
        assert "must be one of" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "log_source"


def test_log_source_validation_accepts_core():
    """Property: 'core' log source should be accepted."""
    # Should not raise an exception
    try:
        validate_log_source("core")
    except ValidationError:
        pytest.fail("Valid log source 'core' was incorrectly rejected")


@given(st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_entity_id_validation_requires_dot(entity_id):
    """Property: Entity IDs without a dot should be rejected."""
    if entity_id and "." not in entity_id:
        with pytest.raises(ValidationError) as exc_info:
            validate_entity_id(entity_id)
        assert "domain.object_id" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "entity_id"


@given(st.text(min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_entity_id_validation_requires_both_parts(entity_id):
    """Property: Entity IDs with empty domain or object_id should be rejected."""
    if "." in entity_id:
        parts = entity_id.split(".", 1)
        if not parts[0] or not parts[1]:
            with pytest.raises(ValidationError) as exc_info:
                validate_entity_id(entity_id)
            assert "both domain and object_id" in exc_info.value.message.lower()
            assert exc_info.value.parameter == "entity_id"


@given(st.text(alphabet=st.characters(whitelist_categories=("Lu",)), min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_domain_validation_rejects_uppercase(domain):
    """Property: Domains with uppercase letters should be rejected."""
    if domain and any(c.isupper() for c in domain):
        with pytest.raises(ValidationError) as exc_info:
            validate_domain(domain)
        assert "lowercase" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "domain"


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_domain_validation_accepts_valid_format(domain):
    """Property: Domains with only lowercase, numbers, and underscores should be accepted."""
    # Should not raise an exception
    try:
        validate_domain(domain)
    except ValidationError:
        pytest.fail(f"Valid domain '{domain}' was incorrectly rejected")


@given(st.text(alphabet=st.characters(whitelist_categories=("Lu",)), min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_service_validation_rejects_uppercase(service):
    """Property: Services with uppercase letters should be rejected."""
    if service and any(c.isupper() for c in service):
        with pytest.raises(ValidationError) as exc_info:
            validate_service(service)
        assert "lowercase" in exc_info.value.message.lower()
        assert exc_info.value.parameter == "service"


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_service_validation_accepts_valid_format(service):
    """Property: Services with only lowercase, numbers, and underscores should be accepted."""
    # Should not raise an exception
    try:
        validate_service(service)
    except ValidationError:
        pytest.fail(f"Valid service '{service}' was incorrectly rejected")


def test_required_parameter_validation_rejects_none():
    """Property: None values for required parameters should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        validate_required_parameter(None, "test_param")
    assert "required parameter" in exc_info.value.message.lower()
    assert "missing" in exc_info.value.message.lower()
    assert exc_info.value.parameter == "test_param"


@given(st.one_of(st.text(), st.integers(), st.floats(), st.booleans(), st.lists(st.integers())))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_required_parameter_validation_accepts_non_none(value):
    """Property: Non-None values for required parameters should be accepted."""
    # Should not raise an exception
    try:
        validate_required_parameter(value, "test_param")
    except ValidationError:
        pytest.fail("Non-None value was incorrectly rejected")

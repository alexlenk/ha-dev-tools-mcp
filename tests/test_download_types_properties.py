"""Property-based tests for file save data model serialization.

Feature: file-download-capability
Property: Data models round-trip through JSON serialization
Validates: Requirements 1.3, 3.1
"""

import json

import pytest
from hypothesis import given, settings, strategies as st

from ha_dev_tools.types import (
    SaveResult,
    SaveConfig,
    SaveErrorCode,
    UploadResult,
    IntegrityError,
)

# Hypothesis strategies for generating test data


@st.composite
def save_result_strategy(draw):
    """Generate random SaveResult instances."""
    return SaveResult(
        local_path=draw(st.text(min_size=1, max_size=100)),
        file_size=draw(st.integers(min_value=0, max_value=1024 * 1024 * 100)),
        remote_path=draw(st.text(min_size=1, max_size=100)),
        checksum=draw(st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)),
    )


@st.composite
def save_config_strategy(draw):
    """Generate random SaveConfig instances."""
    max_size = draw(st.integers(min_value=1024 * 1024, max_value=100 * 1024 * 1024))
    return SaveConfig(
        max_file_size=max_size,
        max_file_size_limit=draw(
            st.integers(min_value=max_size, max_value=100 * 1024 * 1024)
        ),
    )


# Helper functions for serialization


def serialize_dataclass(obj):
    """Convert dataclass to JSON-serializable dict."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = value
        return result
    return obj


def deserialize_to_type(data, cls):
    """Deserialize dict back to dataclass type."""
    if not hasattr(cls, "__dataclass_fields__"):
        return data

    kwargs = {}
    for field_name in cls.__dataclass_fields__:
        if field_name in data:
            kwargs[field_name] = data[field_name]

    return cls(**kwargs)


# Property tests


@given(result=save_result_strategy())
@settings(max_examples=100)
def test_save_result_json_roundtrip(result):
    """
    Property: SaveResult round-trips through JSON serialization.

    For any SaveResult, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(result)
    json_str = json.dumps(serialized)

    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, SaveResult)

    # Verify all fields match
    assert reconstructed.local_path == result.local_path
    assert reconstructed.file_size == result.file_size
    assert reconstructed.remote_path == result.remote_path
    assert reconstructed.checksum == result.checksum


@given(config=save_config_strategy())
@settings(max_examples=100)
def test_save_config_json_roundtrip(config):
    """
    Property: SaveConfig round-trips through JSON serialization.

    For any SaveConfig, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(config)
    json_str = json.dumps(serialized)

    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, SaveConfig)

    # Verify all fields match
    assert reconstructed.max_file_size == config.max_file_size
    assert reconstructed.max_file_size_limit == config.max_file_size_limit


@given(result=save_result_strategy())
@settings(max_examples=100)
def test_save_result_has_required_fields(result):
    """
    Property: SaveResult has all required fields.

    For any SaveResult, it should have local_path, file_size, and remote_path.
    """
    assert hasattr(result, "local_path")
    assert hasattr(result, "file_size")
    assert hasattr(result, "remote_path")
    assert hasattr(result, "checksum")

    # Fields should have correct types
    assert isinstance(result.local_path, str)
    assert isinstance(result.file_size, int)
    assert isinstance(result.remote_path, str)
    assert isinstance(result.checksum, str)

    # File size should be non-negative
    assert result.file_size >= 0

    # Checksum should be 64-char hex string (SHA-256)
    assert len(result.checksum) == 64


@given(config=save_config_strategy())
@settings(max_examples=100)
def test_save_config_has_valid_limits(config):
    """
    Property: SaveConfig has valid size limits.

    For any SaveConfig, max_file_size should not exceed max_file_size_limit.
    """
    assert hasattr(config, "max_file_size")
    assert hasattr(config, "max_file_size_limit")

    # Both should be positive integers
    assert isinstance(config.max_file_size, int)
    assert isinstance(config.max_file_size_limit, int)
    assert config.max_file_size > 0
    assert config.max_file_size_limit > 0

    # max_file_size should not exceed limit
    assert config.max_file_size <= config.max_file_size_limit


def test_save_error_codes_exist():
    """
    Property: All required error codes exist.

    SaveErrorCode should have all the error codes specified in the design.
    """
    required_codes = [
        "MUTUALLY_EXCLUSIVE",
        "INVALID_PATH",
        "PATH_TRAVERSAL",
        "FILE_TOO_LARGE",
        "DISK_SPACE",
        "PERMISSION_DENIED",
        "WRITE_FAILED",
    ]

    for code in required_codes:
        assert hasattr(SaveErrorCode, code), f"Missing error code: {code}"

        # Verify it's a valid enum value
        error_code = getattr(SaveErrorCode, code)
        assert isinstance(error_code, SaveErrorCode)


@given(result=save_result_strategy())
@settings(max_examples=100)
def test_save_result_serialization_preserves_types(result):
    """
    Property: SaveResult serialization preserves field types.

    For any SaveResult, after JSON round-trip, all fields should maintain
    their original types.
    """
    # Serialize and deserialize
    serialized = serialize_dataclass(result)
    json_str = json.dumps(serialized)
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, SaveResult)

    # Check types are preserved
    assert isinstance(reconstructed.local_path, str) and isinstance(
        result.local_path, str
    )
    assert isinstance(reconstructed.file_size, int) and isinstance(
        result.file_size, int
    )
    assert isinstance(reconstructed.remote_path, str) and isinstance(
        result.remote_path, str
    )
    assert isinstance(reconstructed.checksum, str) and isinstance(
        result.checksum, str
    )


def test_save_config_default_values():
    """
    Property: SaveConfig can be created with default values.

    SaveConfig should have sensible defaults for max_file_size.
    """
    # Create with defaults
    default_config = SaveConfig()

    # Should have default max_file_size (10MB)
    assert default_config.max_file_size == 10 * 1024 * 1024

    # Should have default max_file_size_limit (100MB)
    assert default_config.max_file_size_limit == 100 * 1024 * 1024

    # Defaults should be valid
    assert default_config.max_file_size <= default_config.max_file_size_limit


# --- UploadResult and IntegrityError tests ---


@st.composite
def upload_result_strategy(draw):
    """Generate random UploadResult instances."""
    return UploadResult(
        local_path=draw(st.text(min_size=1, max_size=100)),
        remote_path=draw(st.text(min_size=1, max_size=100)),
        file_size=draw(st.integers(min_value=0, max_value=1024 * 1024 * 100)),
        checksum=draw(st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)),
        verified=draw(st.booleans()),
        write_result=draw(
            st.fixed_dictionaries({"status": st.text(min_size=1, max_size=20)})
        ),
    )


@given(result=upload_result_strategy())
@settings(max_examples=100)
def test_upload_result_json_roundtrip(result):
    """Property: UploadResult round-trips through JSON serialization."""
    serialized = serialize_dataclass(result)
    json_str = json.dumps(serialized)
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, UploadResult)

    assert reconstructed.local_path == result.local_path
    assert reconstructed.remote_path == result.remote_path
    assert reconstructed.file_size == result.file_size
    assert reconstructed.checksum == result.checksum
    assert reconstructed.verified == result.verified
    assert reconstructed.write_result == result.write_result


@given(result=upload_result_strategy())
@settings(max_examples=100)
def test_upload_result_has_required_fields(result):
    """Property: UploadResult has all required fields with correct types."""
    assert isinstance(result.local_path, str)
    assert isinstance(result.remote_path, str)
    assert isinstance(result.file_size, int)
    assert isinstance(result.checksum, str)
    assert isinstance(result.verified, bool)
    assert isinstance(result.write_result, dict)
    assert result.file_size >= 0
    assert len(result.checksum) == 64


def test_integrity_error_is_exception():
    """IntegrityError should be a proper Exception subclass."""
    err = IntegrityError("checksum mismatch")
    assert isinstance(err, Exception)
    assert str(err) == "checksum mismatch"

    # Should be raisable and catchable
    with pytest.raises(IntegrityError):
        raise IntegrityError("test")

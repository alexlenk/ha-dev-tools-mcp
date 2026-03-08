"""Property-based tests for download data model serialization.

Feature: file-download-capability
Property: Data models round-trip through JSON serialization
Validates: Requirements 8.2, 8.4
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ha_dev_tools.types import (
    DownloadResult,
    DownloadFailure,
    BatchDownloadResult,
    DownloadMetadata,
    CleanupResult,
    DownloadConfig,
    DownloadErrorCode,
)


# Hypothesis strategies for generating test data

@st.composite
def download_result_strategy(draw):
    """Generate random DownloadResult instances."""
    return DownloadResult(
        local_path=draw(st.text(min_size=1, max_size=100)),
        file_size=draw(st.integers(min_value=0, max_value=1024*1024*100)),
        content_hash=draw(st.text(min_size=64, max_size=64, alphabet="0123456789abcdef")),
        remote_path=draw(st.text(min_size=1, max_size=100)),
        compressed=draw(st.booleans()),
        compression_ratio=draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
        download_time=draw(st.floats(min_value=0.0, max_value=3600.0)),
        timestamp=datetime.now(timezone.utc),
    )


@st.composite
def download_failure_strategy(draw):
    """Generate random DownloadFailure instances."""
    error_codes = [code.value for code in DownloadErrorCode]
    return DownloadFailure(
        remote_path=draw(st.text(min_size=1, max_size=100)),
        error_code=draw(st.sampled_from(error_codes)),
        error_message=draw(st.text(min_size=1, max_size=200)),
    )


@st.composite
def batch_download_result_strategy(draw):
    """Generate random BatchDownloadResult instances."""
    successful = draw(st.lists(download_result_strategy(), max_size=20))
    failed = draw(st.lists(download_failure_strategy(), max_size=20))
    return BatchDownloadResult(
        successful=successful,
        failed=failed,
        total_size=draw(st.integers(min_value=0, max_value=1024*1024*1000)),
        total_time=draw(st.floats(min_value=0.0, max_value=7200.0)),
    )


@st.composite
def download_metadata_strategy(draw):
    """Generate random DownloadMetadata instances."""
    return DownloadMetadata(
        local_path=draw(st.text(min_size=1, max_size=100)),
        remote_path=draw(st.text(min_size=1, max_size=100)),
        file_size=draw(st.integers(min_value=0, max_value=1024*1024*100)),
        content_hash=draw(st.text(min_size=64, max_size=64, alphabet="0123456789abcdef")),
        timestamp=datetime.now(timezone.utc),
        compressed=draw(st.booleans()),
        compression_ratio=draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
        exists=draw(st.booleans()),
    )


@st.composite
def cleanup_result_strategy(draw):
    """Generate random CleanupResult instances."""
    return CleanupResult(
        removed_count=draw(st.integers(min_value=0, max_value=1000)),
        freed_bytes=draw(st.integers(min_value=0, max_value=1024*1024*1000)),
        errors=draw(st.lists(st.text(min_size=1, max_size=100), max_size=10)),
    )


@st.composite
def download_config_strategy(draw):
    """Generate random DownloadConfig instances."""
    download_dir = Path(draw(st.text(min_size=1, max_size=50)))
    return DownloadConfig(
        download_dir=download_dir,
        max_file_size=draw(st.integers(min_value=1024, max_value=1024*1024*500)),
        compression_threshold=draw(st.floats(min_value=0.0, max_value=1.0)),
        partial_download_ttl=draw(st.integers(min_value=1, max_value=24)),
        registry_path=None,  # Will be set by __post_init__
    )


# Helper functions for serialization

def serialize_dataclass(obj):
    """Convert dataclass to JSON-serializable dict."""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, Path):
                result[field_name] = str(value)
            elif isinstance(value, list):
                result[field_name] = [serialize_dataclass(item) for item in value]
            else:
                result[field_name] = value
        return result
    return obj


def deserialize_to_type(data, cls):
    """Deserialize dict back to dataclass type."""
    if not hasattr(cls, '__dataclass_fields__'):
        return data
    
    kwargs = {}
    for field_name, field_type in cls.__dataclass_fields__.items():
        if field_name not in data:
            continue
        
        value = data[field_name]
        field_type_hint = field_type.type
        type_str = str(field_type_hint)
        
        # Handle datetime
        if field_type_hint == datetime or 'datetime' in type_str:
            if isinstance(value, str):
                kwargs[field_name] = datetime.fromisoformat(value)
            else:
                kwargs[field_name] = value
        # Handle Path
        elif field_type_hint == Path or 'Path' in type_str:
            if isinstance(value, str):
                kwargs[field_name] = Path(value)
            else:
                kwargs[field_name] = value
        # Handle lists
        elif hasattr(field_type_hint, '__origin__') and field_type_hint.__origin__ == list:
            kwargs[field_name] = value
        else:
            kwargs[field_name] = value
    
    return cls(**kwargs)


# Property tests

@given(result=download_result_strategy())
@settings(max_examples=100)
def test_download_result_json_roundtrip(result):
    """
    Property: DownloadResult round-trips through JSON serialization.
    
    For any DownloadResult, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(result)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, DownloadResult)
    
    # Verify all fields match
    assert reconstructed.local_path == result.local_path
    assert reconstructed.file_size == result.file_size
    assert reconstructed.content_hash == result.content_hash
    assert reconstructed.remote_path == result.remote_path
    assert reconstructed.compressed == result.compressed
    assert reconstructed.compression_ratio == result.compression_ratio
    assert reconstructed.download_time == result.download_time
    # Timestamps may have microsecond differences, check they're close
    if result.timestamp:
        assert abs((reconstructed.timestamp - result.timestamp).total_seconds()) < 1


@given(failure=download_failure_strategy())
@settings(max_examples=100)
def test_download_failure_json_roundtrip(failure):
    """
    Property: DownloadFailure round-trips through JSON serialization.
    
    For any DownloadFailure, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(failure)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, DownloadFailure)
    
    # Verify all fields match
    assert reconstructed.remote_path == failure.remote_path
    assert reconstructed.error_code == failure.error_code
    assert reconstructed.error_message == failure.error_message


@given(metadata=download_metadata_strategy())
@settings(max_examples=100)
def test_download_metadata_json_roundtrip(metadata):
    """
    Property: DownloadMetadata round-trips through JSON serialization.
    
    For any DownloadMetadata, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(metadata)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, DownloadMetadata)
    
    # Verify all fields match
    assert reconstructed.local_path == metadata.local_path
    assert reconstructed.remote_path == metadata.remote_path
    assert reconstructed.file_size == metadata.file_size
    assert reconstructed.content_hash == metadata.content_hash
    assert reconstructed.compressed == metadata.compressed
    assert reconstructed.compression_ratio == metadata.compression_ratio
    assert reconstructed.exists == metadata.exists
    # Timestamps may have microsecond differences, check they're close
    if metadata.timestamp:
        assert abs((reconstructed.timestamp - metadata.timestamp).total_seconds()) < 1


@given(result=cleanup_result_strategy())
@settings(max_examples=100)
def test_cleanup_result_json_roundtrip(result):
    """
    Property: CleanupResult round-trips through JSON serialization.
    
    For any CleanupResult, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(result)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, CleanupResult)
    
    # Verify all fields match
    assert reconstructed.removed_count == result.removed_count
    assert reconstructed.freed_bytes == result.freed_bytes
    assert reconstructed.errors == result.errors


@given(config=download_config_strategy())
@settings(max_examples=100)
def test_download_config_json_roundtrip(config):
    """
    Property: DownloadConfig round-trips through JSON serialization.
    
    For any DownloadConfig, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(config)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    reconstructed = deserialize_to_type(deserialized_dict, DownloadConfig)
    
    # Verify all fields match
    assert str(reconstructed.download_dir) == str(config.download_dir)
    assert reconstructed.max_file_size == config.max_file_size
    assert reconstructed.compression_threshold == config.compression_threshold
    assert reconstructed.partial_download_ttl == config.partial_download_ttl
    # registry_path is set by __post_init__, verify it's set correctly
    assert reconstructed.registry_path == config.download_dir / ".download_registry.json"


@given(batch=batch_download_result_strategy())
@settings(max_examples=50)  # Fewer examples since this is more complex
def test_batch_download_result_json_roundtrip(batch):
    """
    Property: BatchDownloadResult round-trips through JSON serialization.
    
    For any BatchDownloadResult, serializing to JSON and deserializing back
    should produce an equivalent object.
    """
    # Serialize to JSON
    serialized = serialize_dataclass(batch)
    json_str = json.dumps(serialized)
    
    # Deserialize back
    deserialized_dict = json.loads(json_str)
    
    # Verify structure
    assert "successful" in deserialized_dict
    assert "failed" in deserialized_dict
    assert "total_size" in deserialized_dict
    assert "total_time" in deserialized_dict
    
    # Verify counts match
    assert len(deserialized_dict["successful"]) == len(batch.successful)
    assert len(deserialized_dict["failed"]) == len(batch.failed)
    assert deserialized_dict["total_size"] == batch.total_size
    assert deserialized_dict["total_time"] == batch.total_time

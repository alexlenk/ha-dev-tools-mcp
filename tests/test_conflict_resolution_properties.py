"""
Property-based tests for conflict resolution utilities.

Tests universal correctness properties for conflict detection and diff generation.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
import hashlib

from ha_config_manager.conflict_resolution import (
    FileMetadata,
    ConflictInfo,
    ConflictType,
    FileDiff,
    detect_conflict,
    generate_diff
)


# Strategies for generating test data

@st.composite
def file_metadata_strategy(draw, path=None, hash_value=None, timestamp=None):
    """Generate FileMetadata with optional fixed values."""
    if path is None:
        path = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='._-/'
        )))
    
    if hash_value is None:
        # Generate realistic SHA-256 hash
        content = draw(st.binary(min_size=0, max_size=1000))
        hash_value = hashlib.sha256(content).hexdigest()
    
    if timestamp is None:
        # Generate ISO 8601 timestamp
        base_time = datetime(2026, 1, 1)
        delta = draw(st.integers(min_value=0, max_value=365*24*60*60))
        timestamp = (base_time + timedelta(seconds=delta)).isoformat() + 'Z'
    
    size = draw(st.integers(min_value=0, max_value=1000000))
    
    return FileMetadata(
        path=path,
        content_hash=hash_value,
        modified_at=timestamp,
        size=size
    )


@st.composite
def yaml_content_strategy(draw):
    """Generate valid YAML-like content."""
    lines = draw(st.lists(
        st.text(min_size=0, max_size=80, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'P'),
            whitelist_characters=' \t'
        )),
        min_size=1,
        max_size=50
    ))
    return '\n'.join(lines)


# Property 5: Conflict Detection Accuracy
# For any file, if the remote hash differs from the local hash,
# a version conflict should be detected.

@given(
    local_meta=file_metadata_strategy(),
    remote_meta=file_metadata_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_conflict_detection_hash_difference(local_meta, remote_meta):
    """
    Property: If hashes differ, a conflict should be detected.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4
    """
    # Ensure same path for comparison
    remote_meta.path = local_meta.path
    
    conflict = detect_conflict(local_meta, remote_meta)
    
    if local_meta.content_hash == remote_meta.content_hash:
        # Same hash = no conflict
        assert conflict.conflict_type == ConflictType.NO_CONFLICT
        assert not conflict.has_conflict()
    else:
        # Different hash = conflict detected
        assert conflict.conflict_type != ConflictType.NO_CONFLICT
        assert conflict.has_conflict()


@given(
    path=st.text(min_size=1, max_size=50),
    hash_value=st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    timestamp=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_no_conflict_when_hashes_match(path, hash_value, timestamp):
    """
    Property: If hashes match, no conflict should be detected regardless of timestamps.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4
    """
    timestamp_str = timestamp.isoformat() + 'Z'
    
    local_meta = FileMetadata(
        path=path,
        content_hash=hash_value,
        modified_at=timestamp_str,
        size=1000
    )
    
    # Different timestamp but same hash
    remote_timestamp = (timestamp + timedelta(hours=1)).isoformat() + 'Z'
    remote_meta = FileMetadata(
        path=path,
        content_hash=hash_value,  # Same hash
        modified_at=remote_timestamp,
        size=1000
    )
    
    conflict = detect_conflict(local_meta, remote_meta)
    
    # No conflict when hashes match
    assert conflict.conflict_type == ConflictType.NO_CONFLICT
    assert not conflict.has_conflict()


@given(
    local_meta=file_metadata_strategy(),
    remote_meta=file_metadata_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_conflict_info_completeness(local_meta, remote_meta):
    """
    Property: ConflictInfo should always contain complete metadata from both versions.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4, 2.5
    """
    remote_meta.path = local_meta.path
    
    conflict = detect_conflict(local_meta, remote_meta)
    
    # All fields should be populated
    assert conflict.file_path == local_meta.path
    assert conflict.local_hash == local_meta.content_hash
    assert conflict.local_modified == local_meta.modified_at
    assert conflict.remote_hash == remote_meta.content_hash
    assert conflict.remote_modified == remote_meta.modified_at
    assert isinstance(conflict.conflict_type, ConflictType)


@given(
    path=st.text(min_size=1, max_size=50),
    base_time=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_remote_newer_detection(path, base_time):
    """
    Property: When remote timestamp is newer and hashes differ, conflict type is REMOTE_NEWER.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4
    """
    local_time = base_time.isoformat() + 'Z'
    remote_time = (base_time + timedelta(hours=1)).isoformat() + 'Z'
    
    local_meta = FileMetadata(
        path=path,
        content_hash='a' * 64,
        modified_at=local_time,
        size=1000
    )
    
    remote_meta = FileMetadata(
        path=path,
        content_hash='b' * 64,  # Different hash
        modified_at=remote_time,  # Newer timestamp
        size=1000
    )
    
    conflict = detect_conflict(local_meta, remote_meta)
    
    assert conflict.conflict_type == ConflictType.REMOTE_NEWER
    assert conflict.has_conflict()


@given(
    path=st.text(min_size=1, max_size=50),
    base_time=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_both_modified_detection(path, base_time):
    """
    Property: When local timestamp is newer/equal and hashes differ, conflict type is BOTH_MODIFIED.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4
    """
    remote_time = base_time.isoformat() + 'Z'
    local_time = (base_time + timedelta(hours=1)).isoformat() + 'Z'
    
    local_meta = FileMetadata(
        path=path,
        content_hash='a' * 64,
        modified_at=local_time,  # Newer timestamp
        size=1000
    )
    
    remote_meta = FileMetadata(
        path=path,
        content_hash='b' * 64,  # Different hash
        modified_at=remote_time,
        size=1000
    )
    
    conflict = detect_conflict(local_meta, remote_meta)
    
    assert conflict.conflict_type == ConflictType.BOTH_MODIFIED
    assert conflict.has_conflict()


# Property: Diff Generation Properties

@given(
    content=yaml_content_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_identical_content_no_diff(content):
    """
    Property: Identical content should produce empty diff with no conflict lines.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    diff = generate_diff(content, content, "test.yaml")
    
    # No conflict lines for identical content
    assert len(diff.conflict_lines) == 0
    assert not diff.has_differences()


@given(
    local_content=yaml_content_strategy(),
    remote_content=yaml_content_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_diff_completeness(local_content, remote_content):
    """
    Property: FileDiff should always contain all required fields.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    diff = generate_diff(local_content, remote_content, "test.yaml")
    
    # All fields should be populated
    assert diff.file_path == "test.yaml"
    assert diff.local_content == local_content
    assert diff.remote_content == remote_content
    assert isinstance(diff.unified_diff, str)
    assert isinstance(diff.conflict_lines, list)


@given(
    local_content=yaml_content_strategy(),
    remote_content=yaml_content_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_diff_symmetry(local_content, remote_content):
    """
    Property: Diff from A to B should be inverse of diff from B to A.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    diff_ab = generate_diff(local_content, remote_content, "test.yaml")
    diff_ba = generate_diff(remote_content, local_content, "test.yaml")
    
    # If content differs, both diffs should detect differences
    if local_content != remote_content:
        assert diff_ab.has_differences() == diff_ba.has_differences()
    else:
        # If content is same, neither should have differences
        assert not diff_ab.has_differences()
        assert not diff_ba.has_differences()


@given(
    base_content=yaml_content_strategy(),
    modification=st.text(min_size=1, max_size=50)
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_diff_detects_changes(base_content, modification):
    """
    Property: Any modification to content should be detected in diff.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    modified_content = base_content + "\n" + modification
    
    diff = generate_diff(base_content, modified_content, "test.yaml")
    
    # Modification should be detected
    if base_content != modified_content:
        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0


@given(
    content=yaml_content_strategy(),
    path=st.text(min_size=1, max_size=50)
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_diff_preserves_path(content, path):
    """
    Property: FileDiff should preserve the file path provided.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    diff = generate_diff(content, content, path)
    
    assert diff.file_path == path


# Edge case properties

@given(
    local_meta=file_metadata_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_conflict_with_self_is_no_conflict(local_meta):
    """
    Property: Comparing metadata with itself should never produce a conflict.
    
    Tag: Feature: improved-ha-development-workflow, Property 5: Conflict detection accuracy
    Validates: Requirements 2.4
    """
    conflict = detect_conflict(local_meta, local_meta)
    
    assert conflict.conflict_type == ConflictType.NO_CONFLICT
    assert not conflict.has_conflict()


@given(
    content=st.text(min_size=0, max_size=1000)
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_diff_with_self_has_no_differences(content):
    """
    Property: Comparing content with itself should produce no differences.
    
    Tag: Feature: improved-ha-development-workflow, Property: Diff generation
    Validates: Requirements 9.2
    """
    diff = generate_diff(content, content, "test.yaml")
    
    assert not diff.has_differences()
    assert len(diff.conflict_lines) == 0

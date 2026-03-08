"""Property-based tests for PathValidator.

Feature: file-download-capability
Property 17: Path traversal sequences are detected and sanitized
Validates: Requirements 6.2
"""

from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ha_dev_tools.path_validator import PathValidator


# Hypothesis strategies

@st.composite
def path_traversal_sequence(draw):
    """Generate path traversal sequences."""
    return draw(st.sampled_from(["../", "..\\", "../../", "..\\..\\", "../../../"]))


@st.composite
def valid_filename(draw):
    """Generate valid filename components."""
    return draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='-_.'
        ),
        min_size=1,
        max_size=20
    ))


@st.composite
def path_with_traversal(draw):
    """Generate paths containing traversal sequences."""
    # Generate a normal path
    components = draw(st.lists(valid_filename(), min_size=1, max_size=5))
    normal_path = "/".join(components)
    
    # Insert traversal sequence at random position
    traversal = draw(path_traversal_sequence())
    position = draw(st.integers(min_value=0, max_value=len(normal_path)))
    
    return normal_path[:position] + traversal + normal_path[position:]


@st.composite
def safe_path(draw):
    """Generate paths without traversal sequences."""
    components = draw(st.lists(valid_filename(), min_size=1, max_size=5))
    return "/".join(components)


@st.composite
def allowed_download_dir(draw):
    """Generate paths under allowed roots."""
    root = draw(st.sampled_from([Path.home(), Path("/tmp")]))
    subdir = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
        min_size=1,
        max_size=20
    ))
    return root / subdir


@st.composite
def disallowed_download_dir(draw):
    """Generate paths outside allowed roots."""
    # Generate paths that are definitely not under home or /tmp
    forbidden_roots = ["/etc", "/var", "/usr", "/opt", "/root"]
    root = draw(st.sampled_from(forbidden_roots))
    subdir = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
        min_size=1,
        max_size=20
    ))
    return Path(root) / subdir


# Property tests

@given(path=path_with_traversal())
@settings(max_examples=100)
def test_property_17_traversal_detected(path):
    """
    Property 17: Path traversal sequences are detected and sanitized.
    
    For any path containing traversal sequences (../, ..\\), the sanitize
    function should detect and remove them.
    """
    sanitized, was_modified = PathValidator.sanitize_remote_path(path)
    
    # Should be marked as modified
    assert was_modified, f"Path with traversal should be marked as modified: {path}"
    
    # Sanitized path should not contain traversal sequences
    assert "../" not in sanitized, f"Sanitized path still contains ../: {sanitized}"
    assert "..\\" not in sanitized, f"Sanitized path still contains ..\\: {sanitized}"


@given(path=safe_path())
@settings(max_examples=100)
def test_property_safe_paths_unchanged(path):
    """
    Property: Safe paths without traversal sequences are not modified.
    
    For any path without traversal sequences, sanitization should not
    modify the path.
    """
    # Skip if path accidentally contains traversal
    if "../" in path or "..\\" in path:
        return
    
    sanitized, was_modified = PathValidator.sanitize_remote_path(path)
    
    # Should not be marked as modified
    assert not was_modified, f"Safe path should not be modified: {path}"
    
    # Path should be unchanged (except leading slashes)
    assert sanitized == path.lstrip("/\\"), f"Safe path was changed: {path} -> {sanitized}"


@given(path=allowed_download_dir())
@settings(max_examples=50)
def test_property_allowed_dirs_accepted(path):
    """
    Property: Paths under allowed roots are accepted.
    
    For any path under user home or /tmp, validation should succeed.
    """
    is_valid, error_msg = PathValidator.validate_download_dir(path)
    
    # Should be valid
    assert is_valid, f"Allowed path rejected: {path}, error: {error_msg}"
    assert error_msg is None, f"Valid path should not have error message: {error_msg}"


@given(path=disallowed_download_dir())
@settings(max_examples=50)
def test_property_disallowed_dirs_rejected(path):
    """
    Property: Paths outside allowed roots are rejected.
    
    For any path not under user home or /tmp, validation should fail.
    """
    # Skip if path accidentally falls under allowed roots
    try:
        resolved = path.resolve()
        for allowed_root in [Path.home(), Path("/tmp")]:
            try:
                resolved.relative_to(allowed_root)
                # Path is actually under allowed root, skip
                return
            except ValueError:
                continue
    except (OSError, RuntimeError):
        # Can't resolve, will be rejected anyway
        pass
    
    is_valid, error_msg = PathValidator.validate_download_dir(path)
    
    # Should be invalid
    assert not is_valid, f"Disallowed path accepted: {path}"
    assert error_msg is not None, f"Invalid path should have error message"
    assert "must be under" in error_msg.lower(), f"Error message should mention allowed roots: {error_msg}"


@given(traversal=path_traversal_sequence(), filename=valid_filename())
@settings(max_examples=100)
def test_property_leading_traversal_removed(traversal, filename):
    """
    Property: Leading traversal sequences are removed.
    
    For any path starting with traversal sequences, sanitization should
    remove them completely.
    """
    path = traversal + filename
    sanitized, was_modified = PathValidator.sanitize_remote_path(path)
    
    # Should be modified
    assert was_modified, f"Path with leading traversal should be modified: {path}"
    
    # Should not start with traversal
    assert not sanitized.startswith("../"), f"Sanitized path starts with ../: {sanitized}"
    assert not sanitized.startswith("..\\"), f"Sanitized path starts with ..\\: {sanitized}"
    
    # Should contain the filename
    assert filename in sanitized, f"Filename lost during sanitization: {filename} not in {sanitized}"


@given(path=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_property_sanitize_always_returns_string(path):
    """
    Property: Sanitize always returns a string and boolean.
    
    For any input string, sanitize_remote_path should return a tuple
    of (string, boolean) without raising exceptions.
    """
    try:
        result = PathValidator.sanitize_remote_path(path)
        
        # Should return tuple
        assert isinstance(result, tuple), f"Should return tuple, got {type(result)}"
        assert len(result) == 2, f"Should return 2-tuple, got {len(result)}"
        
        sanitized, was_modified = result
        
        # Check types
        assert isinstance(sanitized, str), f"Sanitized should be string, got {type(sanitized)}"
        assert isinstance(was_modified, bool), f"was_modified should be bool, got {type(was_modified)}"
        
    except Exception as e:
        pytest.fail(f"sanitize_remote_path raised exception for input '{path}': {e}")


@given(path=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_property_multiple_sanitize_idempotent(path):
    """
    Property: Multiple sanitizations are idempotent.
    
    For any path, sanitizing multiple times should produce the same result
    as sanitizing once.
    """
    sanitized1, _ = PathValidator.sanitize_remote_path(path)
    sanitized2, was_modified2 = PathValidator.sanitize_remote_path(sanitized1)
    
    # Second sanitization should not modify
    assert not was_modified2, f"Second sanitization modified path: {sanitized1} -> {sanitized2}"
    assert sanitized1 == sanitized2, f"Multiple sanitizations not idempotent: {sanitized1} != {sanitized2}"

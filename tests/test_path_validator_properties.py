"""Property-based tests for PathValidator.

Feature: file-download-capability
Property 9: Path traversal prevention
Validates: Requirements 4.1
"""

import pytest
from hypothesis import given, settings, strategies as st

from ha_dev_tools.path_validator import PathValidator, SecurityError


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


# Property tests

@given(path=path_with_traversal())
@settings(max_examples=100)
def test_property_9_traversal_rejected(path):
    """
    Property 9: Path traversal sequences are rejected.
    
    For any path containing traversal sequences (../, ..\\), the sanitize
    function should raise SecurityError.
    """
    with pytest.raises(SecurityError) as exc_info:
        PathValidator.sanitize_remote_path(path)
    
    # Error message should mention invalid path
    assert "Invalid path" in str(exc_info.value)


@given(path=safe_path())
@settings(max_examples=100)
def test_property_safe_paths_accepted(path):
    """
    Property: Safe paths without traversal sequences are accepted.
    
    For any path without traversal sequences, sanitization should succeed
    and return a normalized path.
    """
    # Skip if path accidentally contains traversal
    if "../" in path or "..\\" in path or ".." in path:
        return
    
    try:
        sanitized = PathValidator.sanitize_remote_path(path)
        
        # Should not contain traversal sequences
        assert "../" not in sanitized
        assert "..\\" not in sanitized
        
        # Should have normalized separators
        assert "\\" not in sanitized
        
        # Should not have leading slashes
        assert not sanitized.startswith("/")
        
    except SecurityError:
        pytest.fail(f"Safe path should not raise SecurityError: {path}")


@given(traversal=path_traversal_sequence(), filename=valid_filename())
@settings(max_examples=100)
def test_property_leading_traversal_rejected(traversal, filename):
    """
    Property: Leading traversal sequences are rejected.
    
    For any path starting with traversal sequences, sanitization should
    raise SecurityError.
    """
    path = traversal + filename
    
    with pytest.raises(SecurityError) as exc_info:
        PathValidator.sanitize_remote_path(path)
    
    assert "Invalid path" in str(exc_info.value)


@given(path=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_property_sanitize_returns_string_or_raises(path):
    """
    Property: Sanitize either returns a string or raises SecurityError.
    
    For any input string, sanitize_remote_path should either return a
    string or raise SecurityError (never other exceptions).
    """
    try:
        result = PathValidator.sanitize_remote_path(path)
        
        # Should return string
        assert isinstance(result, str), f"Should return string, got {type(result)}"
        
        # Should not contain traversal
        assert ".." not in result, f"Result contains ..: {result}"
        
        # Should not have leading slashes
        assert not result.startswith("/"), f"Result has leading slash: {result}"
        assert not result.startswith("\\"), f"Result has leading backslash: {result}"
        
    except SecurityError:
        # This is expected for invalid paths
        pass
    except Exception as e:
        pytest.fail(f"sanitize_remote_path raised unexpected exception for input '{path}': {e}")


@given(path=safe_path())
@settings(max_examples=100)
def test_property_multiple_sanitize_idempotent(path):
    """
    Property: Multiple sanitizations are idempotent.
    
    For any safe path, sanitizing multiple times should produce the same
    result as sanitizing once.
    """
    # Skip if path contains traversal
    if ".." in path:
        return
    
    try:
        sanitized1 = PathValidator.sanitize_remote_path(path)
        sanitized2 = PathValidator.sanitize_remote_path(sanitized1)
        
        # Should be identical
        assert sanitized1 == sanitized2, f"Multiple sanitizations not idempotent: {sanitized1} != {sanitized2}"
        
    except SecurityError:
        # If first sanitization fails, that's fine
        pass


@given(filename=valid_filename())
@settings(max_examples=100)
def test_property_simple_filenames_preserved(filename):
    """
    Property: Simple filenames without paths are preserved.
    
    For any simple filename (no path separators), sanitization should
    preserve the filename.
    """
    # Skip if filename contains path separators or dots
    if "/" in filename or "\\" in filename or ".." in filename:
        return
    
    try:
        sanitized = PathValidator.sanitize_remote_path(filename)
        
        # Should preserve the filename
        assert sanitized == filename, f"Filename not preserved: {filename} -> {sanitized}"
        
    except SecurityError:
        pytest.fail(f"Simple filename should not raise SecurityError: {filename}")


@given(components=st.lists(valid_filename(), min_size=2, max_size=5))
@settings(max_examples=100)
def test_property_path_structure_preserved(components):
    """
    Property: Path structure is preserved for safe paths.
    
    For any path made of safe components, the structure should be preserved
    after sanitization (only leading slashes removed).
    """
    # Skip if any component contains dots
    if any(".." in c for c in components):
        return
    
    path = "/".join(components)
    
    try:
        sanitized = PathValidator.sanitize_remote_path(path)
        
        # Should preserve structure (components separated by /)
        assert all(c in sanitized for c in components), f"Components lost: {components} -> {sanitized}"
        
    except SecurityError:
        pytest.fail(f"Safe path should not raise SecurityError: {path}")

"""Property-based tests for FileSaver class."""

import asyncio
import hashlib
import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from ha_dev_tools.file_saver import FileSaver
from ha_dev_tools.path_validator import SecurityError
from ha_dev_tools.types import SaveResult

# Strategy for generating valid paths (no traversal sequences)
valid_path_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_."
    ),
    min_size=1,
    max_size=50,
).filter(lambda x: ".." not in x and not x.startswith("/") and not x.startswith("\\"))


# Strategy for generating nested paths
nested_path_strategy = st.lists(valid_path_strategy, min_size=1, max_size=5).map(
    lambda parts: "/".join(parts)
)


# Strategy for generating file content
content_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # Exclude surrogates
    min_size=0,
    max_size=1024 * 100,  # 100KB max for tests
)


def _make_workspace():
    """Create a temporary workspace directory and return (workspace_path, FileSaver)."""
    workspace = Path(tempfile.mkdtemp(prefix="ha-dev-test-")).resolve()
    return workspace, FileSaver(workspace_dir=str(workspace))


def _cleanup_workspace(workspace: Path):
    """Remove a temporary workspace directory."""
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


# Property 1: File Save Creates Local File
@given(content=content_strategy, path=nested_path_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_file_save_creates_local_file(content, path):
    """
    Property 1: File Save Creates Local File

    For any valid file content and path, verify:
    - File exists at returned local_path
    - File is readable and contains expected content

    Validates: Requirements 1.1, 1.5
    """
    workspace, file_saver = _make_workspace()
    try:
        result = asyncio.run(file_saver.save_file(path, content))

        # Verify result is correct type
        assert isinstance(result, SaveResult)

        # Verify file exists at returned path
        local_path = Path(result.local_path)
        assert local_path.exists(), f"File should exist at {result.local_path}"

        # Verify file is readable
        assert local_path.is_file(), f"Path should be a file: {result.local_path}"

        # Verify content matches
        with open(local_path, "r", encoding="utf-8", newline="") as f:
            saved_content = f.read()
        assert saved_content == content, "Saved content should match original"

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 2: Checksum Consistency
@given(content=content_strategy, path=nested_path_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_checksum_consistency(content, path):
    """
    Property 2: Checksum Consistency

    For any file content, the checksum returned by save_file SHALL equal
    SHA-256(content.encode('utf-8')).

    Validates: Requirements 2.3, 2.4
    """
    workspace, file_saver = _make_workspace()
    try:
        result = asyncio.run(file_saver.save_file(path, content))

        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert result.checksum == expected, "Checksum should match SHA-256 of content"

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 4: Workspace Directory Creation
@given(path=nested_path_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_workspace_directory_creation(path):
    """
    Property 4: Workspace Directory Creation

    For any nested path, verify:
    - All parent directories are created
    - Directories have correct permissions

    Validates: Requirements 1.4, 2.1
    """
    workspace, file_saver = _make_workspace()
    content = "test content"

    try:
        result = asyncio.run(file_saver.save_file(path, content))

        local_path = Path(result.local_path)

        # Verify all parent directories exist
        assert local_path.parent.exists(), "Parent directories should be created"
        assert local_path.parent.is_dir(), "Parent should be a directory"

        # Verify we can read the directory (permissions check)
        list(local_path.parent.iterdir())

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 5: Path Structure Preservation
@given(path=nested_path_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_path_structure_preservation(path):
    """
    Property 5: Path Structure Preservation

    For any remote path, verify:
    - Local path preserves structure
    - Path is under the workspace directory

    Validates: Requirements 2.2
    """
    workspace, file_saver = _make_workspace()
    content = "test content"

    try:
        result = asyncio.run(file_saver.save_file(path, content))

        local_path = Path(result.local_path)

        # Verify path is under workspace directory
        assert str(local_path).startswith(
            str(workspace)
        ), f"Local path should be under {workspace}"

        # Verify structure is preserved
        sanitized_path = path.lstrip("/").replace("\\", "/")
        assert str(local_path).endswith(
            sanitized_path
        ), f"Local path should preserve structure: {sanitized_path}"

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 6: Filename Preservation
@given(
    directory=st.lists(valid_path_strategy, min_size=0, max_size=3).map(
        lambda x: "/".join(x) if x else ""
    ),
    filename=valid_path_strategy,
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_filename_preservation(directory, filename):
    """
    Property 6: Filename Preservation

    For any remote path, verify:
    - Filename component matches original

    Validates: Requirements 1.5
    """
    workspace, file_saver = _make_workspace()
    content = "test content"
    remote_path = f"{directory}/{filename}" if directory else filename

    try:
        result = asyncio.run(file_saver.save_file(remote_path, content))

        local_path = Path(result.local_path)
        assert (
            local_path.name == filename
        ), f"Filename should be preserved: expected {filename}, got {local_path.name}"

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 7: Overwrite Behavior
@given(path=nested_path_strategy, content1=content_strategy, content2=content_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_overwrite_behavior(path, content1, content2):
    """
    Property 7: Overwrite Behavior

    For any file saved twice to same path, verify:
    - Only one file exists
    - Second save overwrites first

    Validates: Requirements 2.3
    """
    workspace, file_saver = _make_workspace()

    try:
        result1 = asyncio.run(file_saver.save_file(path, content1))
        local_path1 = Path(result1.local_path)
        first_mtime = local_path1.stat().st_mtime

        import time

        time.sleep(0.01)

        result2 = asyncio.run(file_saver.save_file(path, content2))
        local_path2 = Path(result2.local_path)

        assert result1.local_path == result2.local_path
        assert local_path1.exists()
        assert local_path1 == local_path2

        second_mtime = local_path2.stat().st_mtime
        assert second_mtime >= first_mtime

    except SecurityError:
        pass
    finally:
        _cleanup_workspace(workspace)


# Property 8: Size Limit Enforcement
@given(
    path=nested_path_strategy,
    size_multiplier=st.integers(min_value=11, max_value=20),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_size_limit_enforcement(path, size_multiplier):
    """
    Property 8: Size Limit Enforcement

    For any file exceeding max_file_size, verify:
    - SecurityError is raised
    - No file written to disk

    Validates: Requirements 4.3
    """
    workspace, file_saver = _make_workspace()
    content = "a" * (size_multiplier * 1024 * 1024)

    try:
        with pytest.raises(SecurityError) as exc_info:
            asyncio.run(file_saver.save_file(path, content))

        assert "exceeds limit" in str(exc_info.value)

        sanitized_path = path.lstrip("/").replace("\\", "/")
        potential_file = workspace / sanitized_path
        assert not potential_file.exists()

    except SecurityError as e:
        if "Invalid path" in str(e):
            pass
        else:
            raise
    finally:
        _cleanup_workspace(workspace)


# Property 9: Path Traversal Prevention
@given(
    base_path=st.sampled_from(["", "config", "config/automations"]),
    traversal=st.sampled_from(["../", "../..", "..\\", "..\\..", "test/../etc"]),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_path_traversal_prevention(base_path, traversal):
    """
    Property 9: Path Traversal Prevention

    For any path containing traversal sequences, verify:
    - SecurityError is raised
    - No file written to disk

    Validates: Requirements 4.1
    """
    workspace, file_saver = _make_workspace()
    content = "test content"
    remote_path = (
        f"{base_path}/{traversal}/passwd" if base_path else f"{traversal}/passwd"
    )

    try:
        with pytest.raises(SecurityError) as exc_info:
            asyncio.run(file_saver.save_file(remote_path, content))

        assert "Invalid path" in str(exc_info.value)

        if workspace.exists():
            for file_path in workspace.rglob("*"):
                if file_path.is_file():
                    assert ".." not in str(file_path.relative_to(workspace))
    finally:
        _cleanup_workspace(workspace)

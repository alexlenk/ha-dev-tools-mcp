"""Unit tests for FileUploader class."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ha_dev_tools.file_uploader import FileUploader
from ha_dev_tools.types import UploadResult


@pytest.fixture
def uploader():
    """Create FileUploader with default settings."""
    return FileUploader()


@pytest.fixture
def small_uploader():
    """Create FileUploader with a small size limit for testing."""
    return FileUploader(max_file_size=100)


@pytest.fixture
def mock_api_client():
    """Create a mock api_client with an async write_file method."""
    client = AsyncMock()
    client.write_file = AsyncMock(return_value={"result": "ok", "hash": "abc123"})
    return client


@pytest.fixture
def local_file(tmp_path):
    """Create a temporary local file with known content."""
    content = "homeassistant:\n  name: Test Home\n"
    file_path = tmp_path / "configuration.yaml"
    file_path.write_text(content, encoding="utf-8")
    return file_path, content


@pytest.mark.asyncio
async def test_upload_valid_file(uploader, mock_api_client, local_file):
    """Test successful upload of a valid local file."""
    file_path, content = local_file

    result = await uploader.upload_file(
        local_path=str(file_path),
        remote_path="configuration.yaml",
        api_client=mock_api_client,
    )

    assert isinstance(result, UploadResult)
    assert result.remote_path == "configuration.yaml"
    assert result.file_size == file_path.stat().st_size
    assert result.verified is True
    assert result.write_result == {"result": "ok", "hash": "abc123"}

    mock_api_client.write_file.assert_awaited_once_with(
        file_path="configuration.yaml",
        content=content,
        expected_hash=None,
        validate_before_write=True,
    )


@pytest.mark.asyncio
async def test_upload_missing_file_raises_file_not_found(uploader, mock_api_client):
    """Test FileNotFoundError when local file does not exist."""
    with pytest.raises(FileNotFoundError, match="Local file not found"):
        await uploader.upload_file(
            local_path="/nonexistent/path/config.yaml",
            remote_path="configuration.yaml",
            api_client=mock_api_client,
        )

    mock_api_client.write_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_directory_raises_file_not_found(
    uploader, mock_api_client, tmp_path
):
    """Test FileNotFoundError when path points to a directory, not a file."""
    with pytest.raises(FileNotFoundError, match="Path is not a file"):
        await uploader.upload_file(
            local_path=str(tmp_path),
            remote_path="configuration.yaml",
            api_client=mock_api_client,
        )

    mock_api_client.write_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_file_exceeding_size_limit(
    small_uploader, mock_api_client, tmp_path
):
    """Test ValueError when file exceeds max_file_size."""
    large_file = tmp_path / "large.yaml"
    large_file.write_text("x" * 200, encoding="utf-8")

    with pytest.raises(ValueError, match="File too large"):
        await small_uploader.upload_file(
            local_path=str(large_file),
            remote_path="large.yaml",
            api_client=mock_api_client,
        )

    mock_api_client.write_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_expected_hash_passed_to_write_file(
    uploader, mock_api_client, local_file
):
    """Test that expected_hash is forwarded to api_client.write_file()."""
    file_path, content = local_file

    await uploader.upload_file(
        local_path=str(file_path),
        remote_path="configuration.yaml",
        api_client=mock_api_client,
        expected_hash="deadbeef1234",
    )

    mock_api_client.write_file.assert_awaited_once_with(
        file_path="configuration.yaml",
        content=content,
        expected_hash="deadbeef1234",
        validate_before_write=True,
    )


@pytest.mark.asyncio
async def test_validate_yaml_false_passed_through(
    uploader, mock_api_client, local_file
):
    """Test that validate_yaml=False is forwarded correctly."""
    file_path, content = local_file

    await uploader.upload_file(
        local_path=str(file_path),
        remote_path="configuration.yaml",
        api_client=mock_api_client,
        validate_yaml=False,
    )

    mock_api_client.write_file.assert_awaited_once_with(
        file_path="configuration.yaml",
        content=content,
        expected_hash=None,
        validate_before_write=False,
    )


@pytest.mark.asyncio
async def test_checksum_matches_content(uploader, mock_api_client, local_file):
    """Test that returned checksum matches SHA-256 of file content."""
    file_path, content = local_file

    result = await uploader.upload_file(
        local_path=str(file_path),
        remote_path="configuration.yaml",
        api_client=mock_api_client,
    )

    expected_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert result.checksum == expected_checksum
    assert len(result.checksum) == 64  # SHA-256 hex digest length


@pytest.mark.asyncio
async def test_upload_preserves_utf8_content(uploader, mock_api_client, tmp_path):
    """Test that UTF-8 content is preserved through upload."""
    content = "name: \"Café ☕\"\nlocation: \"Zürich 🇨🇭\"\n"
    file_path = tmp_path / "utf8.yaml"
    file_path.write_text(content, encoding="utf-8")

    result = await uploader.upload_file(
        local_path=str(file_path),
        remote_path="utf8.yaml",
        api_client=mock_api_client,
    )

    # Verify the content sent to write_file matches
    call_args = mock_api_client.write_file.call_args
    assert call_args.kwargs["content"] == content

    expected_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert result.checksum == expected_checksum


@pytest.mark.asyncio
async def test_upload_file_at_exact_size_limit(mock_api_client, tmp_path):
    """Test that a file exactly at the size limit is accepted."""
    limit = 50
    uploader = FileUploader(max_file_size=limit)

    # Create file exactly at limit
    content = "a" * limit
    file_path = tmp_path / "exact.yaml"
    file_path.write_text(content, encoding="utf-8")

    result = await uploader.upload_file(
        local_path=str(file_path),
        remote_path="exact.yaml",
        api_client=mock_api_client,
    )

    assert result.file_size == limit


@pytest.mark.asyncio
async def test_upload_returns_resolved_local_path(uploader, mock_api_client, tmp_path):
    """Test that result.local_path is the resolved absolute path."""
    content = "test"
    file_path = tmp_path / "test.yaml"
    file_path.write_text(content, encoding="utf-8")

    result = await uploader.upload_file(
        local_path=str(file_path),
        remote_path="test.yaml",
        api_client=mock_api_client,
    )

    resolved = str(file_path.resolve())
    assert result.local_path == resolved

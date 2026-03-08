"""Unit tests for FileSaver class."""

import tempfile
from pathlib import Path

import pytest

from ha_dev_tools.file_saver import FileSaver
from ha_dev_tools.path_validator import SecurityError
from ha_dev_tools.types import SaveResult


@pytest.fixture
def file_saver():
    """Create FileSaver instance for testing."""
    return FileSaver()


@pytest.fixture
def cleanup_temp_dir():
    """Clean up temp directory after tests."""
    yield
    # Cleanup after test
    temp_dir = Path(tempfile.gettempdir()) / "ha-dev-tools"
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_save_small_file(file_saver, cleanup_temp_dir):
    """Test successful save of small file (1KB)."""
    content = "a" * 1024  # 1KB
    remote_path = "config/test.yaml"
    
    result = await file_saver.save_file(remote_path, content)
    
    assert isinstance(result, SaveResult)
    assert result.file_size == 1024
    assert result.remote_path == remote_path
    assert "ha-dev-tools" in result.local_path
    assert result.local_path.endswith("config/test.yaml")
    
    # Verify file exists and has correct content
    local_path = Path(result.local_path)
    assert local_path.exists()
    assert local_path.read_text(encoding='utf-8') == content


@pytest.mark.asyncio
async def test_save_large_file(file_saver, cleanup_temp_dir):
    """Test successful save of large file (5MB)."""
    content = "a" * (5 * 1024 * 1024)  # 5MB
    remote_path = "large_config.yaml"
    
    result = await file_saver.save_file(remote_path, content)
    
    assert isinstance(result, SaveResult)
    assert result.file_size == 5 * 1024 * 1024
    assert result.remote_path == remote_path
    
    # Verify file exists
    local_path = Path(result.local_path)
    assert local_path.exists()
    assert local_path.stat().st_size == 5 * 1024 * 1024


@pytest.mark.asyncio
async def test_reject_file_exceeding_size_limit(file_saver, cleanup_temp_dir):
    """Test rejection of file exceeding size limit."""
    # Create content larger than 10MB default limit
    content = "a" * (11 * 1024 * 1024)  # 11MB
    remote_path = "too_large.yaml"
    
    with pytest.raises(SecurityError) as exc_info:
        await file_saver.save_file(remote_path, content)
    
    assert "exceeds limit" in str(exc_info.value)
    
    # Verify no file was written
    temp_dir = Path(tempfile.gettempdir()) / "ha-dev-tools"
    if temp_dir.exists():
        assert not (temp_dir / "too_large.yaml").exists()


@pytest.mark.asyncio
async def test_reject_path_with_forward_traversal(file_saver, cleanup_temp_dir):
    """Test rejection of path with '../' traversal."""
    content = "test content"
    remote_path = "../etc/passwd"
    
    with pytest.raises(SecurityError) as exc_info:
        await file_saver.save_file(remote_path, content)
    
    assert "Invalid path" in str(exc_info.value)


@pytest.mark.asyncio
async def test_reject_path_with_backward_traversal(file_saver, cleanup_temp_dir):
    """Test rejection of path with '..\' traversal."""
    content = "test content"
    remote_path = "..\\windows\\system32\\config"
    
    with pytest.raises(SecurityError) as exc_info:
        await file_saver.save_file(remote_path, content)
    
    assert "Invalid path" in str(exc_info.value)


@pytest.mark.asyncio
async def test_directory_creation_for_nested_paths(file_saver, cleanup_temp_dir):
    """Test directory creation for nested paths."""
    content = "test content"
    remote_path = "config/automations/lights/bedroom.yaml"
    
    result = await file_saver.save_file(remote_path, content)
    
    # Verify all parent directories were created
    local_path = Path(result.local_path)
    assert local_path.exists()
    assert local_path.parent.exists()
    assert local_path.parent.name == "lights"
    assert local_path.parent.parent.name == "automations"


@pytest.mark.asyncio
async def test_overwrite_existing_file(file_saver, cleanup_temp_dir):
    """Test overwrite of existing file."""
    remote_path = "config/test.yaml"
    content1 = "first content"
    content2 = "second content"
    
    # Save first version
    result1 = await file_saver.save_file(remote_path, content1)
    local_path = Path(result1.local_path)
    assert local_path.read_text(encoding='utf-8') == content1
    
    # Save second version (overwrite)
    result2 = await file_saver.save_file(remote_path, content2)
    assert result2.local_path == result1.local_path
    
    # Verify only one file exists with second content
    assert local_path.read_text(encoding='utf-8') == content2


@pytest.mark.asyncio
async def test_special_characters_in_filenames(file_saver, cleanup_temp_dir):
    """Test special characters in filenames."""
    content = "test content"
    remote_path = "config/my-automation_v2.0.yaml"
    
    result = await file_saver.save_file(remote_path, content)
    
    local_path = Path(result.local_path)
    assert local_path.exists()
    assert local_path.name == "my-automation_v2.0.yaml"


@pytest.mark.asyncio
async def test_utf8_encoding_preservation(file_saver, cleanup_temp_dir):
    """Test UTF-8 encoding preservation."""
    # Content with various UTF-8 characters
    content = """
    # Configuration with UTF-8
    name: "Café ☕"
    location: "Zürich 🇨🇭"
    emoji: "🏠 🔥 💡"
    chinese: "你好世界"
    arabic: "مرحبا بالعالم"
    """
    remote_path = "config/utf8_test.yaml"
    
    result = await file_saver.save_file(remote_path, content)
    
    # Verify content is preserved exactly
    local_path = Path(result.local_path)
    saved_content = local_path.read_text(encoding='utf-8')
    assert saved_content == content
    assert "☕" in saved_content
    assert "🏠" in saved_content
    assert "你好世界" in saved_content

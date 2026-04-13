"""Unit tests for FileSaver integration with HAConfigurationManager."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from ha_dev_tools.manager import HAConfigurationManager
from ha_dev_tools.types import SaveResult
from ha_dev_tools.path_validator import SecurityError


@pytest.fixture
def manager():
    """Create HAConfigurationManager instance."""
    return HAConfigurationManager()


@pytest.fixture
def mock_connection():
    """Create mock HAConnection."""
    connection = Mock()
    connection.read_file = AsyncMock(return_value="test: content\nkey: value")
    return connection


@pytest.mark.asyncio
async def test_read_config_file_with_save_local_true(manager, mock_connection):
    """Test read_config_file with save_local=True returns save result."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    save_result = SaveResult(
        local_path="/tmp/ha-dev-tools/config.yaml",
        file_size=100,
        remote_path="config.yaml",
        checksum="a" * 64,
    )

    with patch.object(
        manager.file_saver, "save_file", new_callable=AsyncMock
    ) as mock_save:
        mock_save.return_value = save_result

        # Execute
        result = await manager.read_config_file(
            instance_id="test_instance", file_path="config.yaml", save_local=True
        )

        # Verify
        assert result["saved"] is True
        assert result["local_path"] == "/tmp/ha-dev-tools/config.yaml"
        assert result["file_size"] == 100
        assert result["remote_path"] == "config.yaml"
        assert "content" not in result

        # Verify file_saver was called
        mock_save.assert_called_once_with("config.yaml", "test: content\nkey: value")


@pytest.mark.asyncio
async def test_read_config_file_with_save_local_false(manager, mock_connection):
    """Test read_config_file with save_local=False returns content."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    # Execute
    result = await manager.read_config_file(
        instance_id="test_instance", file_path="config.yaml", save_local=False
    )

    # Verify
    assert result["saved"] is False
    assert result["content"] == "test: content\nkey: value"
    assert result["file_size"] == len("test: content\nkey: value".encode("utf-8"))
    assert result["file_path"] == "config.yaml"
    assert "local_path" not in result


@pytest.mark.asyncio
async def test_read_config_file_without_save_local(manager, mock_connection):
    """Test read_config_file without save_local returns content (backward compat)."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    # Execute
    result = await manager.read_config_file(
        instance_id="test_instance", file_path="config.yaml"
    )

    # Verify
    assert result["saved"] is False
    assert result["content"] == "test: content\nkey: value"
    assert result["file_size"] == len("test: content\nkey: value".encode("utf-8"))
    assert result["file_path"] == "config.yaml"
    assert "local_path" not in result


@pytest.mark.asyncio
async def test_error_when_save_local_and_offset(manager, mock_connection):
    """Test error when save_local=True and offset provided."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    # Execute & Verify
    with pytest.raises(ValueError) as exc_info:
        await manager.read_config_file(
            instance_id="test_instance",
            file_path="config.yaml",
            save_local=True,
            offset=100,
        )

    assert "mutually exclusive" in str(exc_info.value).lower()
    assert "save_local" in str(exc_info.value)
    assert "pagination" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_error_when_save_local_and_length(manager, mock_connection):
    """Test error when save_local=True and length provided."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    # Execute & Verify
    with pytest.raises(ValueError) as exc_info:
        await manager.read_config_file(
            instance_id="test_instance",
            file_path="config.yaml",
            save_local=True,
            length=500,
        )

    assert "mutually exclusive" in str(exc_info.value).lower()
    assert "save_local" in str(exc_info.value)
    assert "pagination" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_error_when_save_local_and_both_pagination_params(
    manager, mock_connection
):
    """Test error when save_local=True and both offset and length provided."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    # Execute & Verify
    with pytest.raises(ValueError) as exc_info:
        await manager.read_config_file(
            instance_id="test_instance",
            file_path="config.yaml",
            save_local=True,
            offset=100,
            length=500,
        )

    assert "mutually exclusive" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_pagination_works_without_save_local(manager, mock_connection):
    """Test pagination still works when save_local=False."""
    # Setup
    manager._connections["test_instance"] = mock_connection
    mock_connection.read_file = AsyncMock(return_value="0123456789")

    # Execute
    result = await manager.read_config_file(
        instance_id="test_instance",
        file_path="config.yaml",
        save_local=False,
        offset=2,
        length=5,
    )

    # Verify
    assert result["saved"] is False
    assert result["content"] == "23456"
    assert result["file_path"] == "config.yaml"


@pytest.mark.asyncio
async def test_security_error_handling(manager, mock_connection):
    """Test SecurityError is converted to ConfigError."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    with patch.object(
        manager.file_saver, "save_file", new_callable=AsyncMock
    ) as mock_save:
        mock_save.side_effect = SecurityError("Path traversal detected")

        # Execute & Verify
        with pytest.raises(Exception) as exc_info:
            await manager.read_config_file(
                instance_id="test_instance",
                file_path="../../../etc/passwd",
                save_local=True,
            )

        # Should be ConfigError with SECURITY_ERROR code
        assert (
            "Security error" in str(exc_info.value)
            or "security" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_io_error_handling(manager, mock_connection):
    """Test IOError is converted to ConfigError."""
    # Setup
    manager._connections["test_instance"] = mock_connection

    with patch.object(
        manager.file_saver, "save_file", new_callable=AsyncMock
    ) as mock_save:
        mock_save.side_effect = IOError("Disk full")

        # Execute & Verify
        with pytest.raises(Exception) as exc_info:
            await manager.read_config_file(
                instance_id="test_instance", file_path="config.yaml", save_local=True
            )

        # Should be ConfigError with FILE_SAVE_FAILED code
        assert (
            "Failed to save" in str(exc_info.value)
            or "save" in str(exc_info.value).lower()
        )

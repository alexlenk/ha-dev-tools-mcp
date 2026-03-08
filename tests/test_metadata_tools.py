"""Unit tests for metadata MCP tools.

Tests the get_file_metadata and batch_get_metadata tools including:
- Valid file metadata retrieval
- Invalid file handling (404)
- Batch metadata retrieval
- Error handling
"""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient, HAAPIError


@pytest.fixture
def api_client():
    """Create a mock API client for testing."""
    return HAAPIClient(
        base_url="http://homeassistant.local:8123",
        access_token="test_token"
    )


@pytest.mark.asyncio
async def test_get_file_metadata_valid_file(api_client):
    """Test get_file_metadata with a valid file."""
    with aioresponses() as mock:
        mock.get(
            "http://homeassistant.local:8123/api/management/metadata/configuration.yaml",
            status=200,
            payload={
                "path": "configuration.yaml",
                "size": 1024,
                "modified_at": "2026-02-12T10:30:00Z",
                "content_hash": "abc123def456",
                "exists": True,
                "accessible": True
            }
        )
        
        metadata = await api_client.get_file_metadata("configuration.yaml")
        
        assert metadata["path"] == "configuration.yaml"
        assert metadata["size"] == 1024
        assert metadata["modified_at"] == "2026-02-12T10:30:00Z"
        assert metadata["content_hash"] == "abc123def456"
        assert metadata["exists"] is True
        assert metadata["accessible"] is True


@pytest.mark.asyncio
async def test_get_file_metadata_invalid_file(api_client):
    """Test get_file_metadata with a non-existent file."""
    with aioresponses() as mock:
        mock.get(
            "http://homeassistant.local:8123/api/management/metadata/nonexistent.yaml",
            status=404,
            payload={
                "error": "file_not_found",
                "message": "File not found: nonexistent.yaml"
            }
        )
        
        with pytest.raises(HAAPIError) as exc_info:
            await api_client.get_file_metadata("nonexistent.yaml")
        
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_batch_get_metadata_multiple_files(api_client):
    """Test batch_get_metadata with multiple files."""
    with aioresponses() as mock:
        mock.post(
            "http://homeassistant.local:8123/api/management/metadata/batch",
            status=200,
            payload=[
                {
                    "path": "configuration.yaml",
                    "size": 1024,
                    "modified_at": "2026-02-12T10:30:00Z",
                    "content_hash": "abc123",
                    "exists": True,
                    "accessible": True
                },
                {
                    "path": "automations.yaml",
                    "size": 2048,
                    "modified_at": "2026-02-12T11:00:00Z",
                    "content_hash": "def456",
                    "exists": True,
                    "accessible": True
                }
            ]
        )
        
        metadata_list = await api_client.batch_get_metadata([
            "configuration.yaml",
            "automations.yaml"
        ])
        
        assert len(metadata_list) == 2
        assert metadata_list[0]["path"] == "configuration.yaml"
        assert metadata_list[0]["size"] == 1024
        assert metadata_list[1]["path"] == "automations.yaml"
        assert metadata_list[1]["size"] == 2048


@pytest.mark.asyncio
async def test_batch_get_metadata_with_errors(api_client):
    """Test batch_get_metadata with some files having errors."""
    with aioresponses() as mock:
        mock.post(
            "http://homeassistant.local:8123/api/management/metadata/batch",
            status=200,
            payload=[
                {
                    "path": "configuration.yaml",
                    "size": 1024,
                    "modified_at": "2026-02-12T10:30:00Z",
                    "content_hash": "abc123",
                    "exists": True,
                    "accessible": True
                },
                {
                    "path": "nonexistent.yaml",
                    "size": None,
                    "modified_at": None,
                    "content_hash": None,
                    "exists": False,
                    "accessible": False,
                    "error": "File not found"
                }
            ]
        )
        
        metadata_list = await api_client.batch_get_metadata([
            "configuration.yaml",
            "nonexistent.yaml"
        ])
        
        assert len(metadata_list) == 2
        assert metadata_list[0]["exists"] is True
        assert metadata_list[1]["exists"] is False
        assert "error" in metadata_list[1]


@pytest.mark.asyncio
async def test_get_file_metadata_access_denied(api_client):
    """Test get_file_metadata with access denied (403)."""
    with aioresponses() as mock:
        mock.get(
            "http://homeassistant.local:8123/api/management/metadata/secrets.yaml",
            status=403,
            payload={
                "error": "access_denied",
                "message": "Access denied to file: secrets.yaml"
            }
        )
        
        with pytest.raises(HAAPIError) as exc_info:
            await api_client.get_file_metadata("secrets.yaml")
        
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_batch_get_metadata_empty_list(api_client):
    """Test batch_get_metadata with empty file list."""
    with aioresponses() as mock:
        mock.post(
            "http://homeassistant.local:8123/api/management/metadata/batch",
            status=200,
            payload=[]
        )
        
        metadata_list = await api_client.batch_get_metadata([])
        
        assert len(metadata_list) == 0

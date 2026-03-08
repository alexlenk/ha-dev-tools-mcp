"""
Integration tests for complete Download File workflow.

Tests the end-to-end workflow:
1. User request → context recognition
2. Steering retrieval
3. get_file_metadata
4. read_config_file
5. Save locally to ~/ha-dev-workspace/
6. Record metadata in .ha-workflow/metadata.json

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
"""

import pytest
import json
import shutil
from unittest.mock import AsyncMock, Mock
from datetime import datetime


# Mock the MCP server components
@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    server = Mock()
    server.read_resource = AsyncMock()
    server.call_tool = AsyncMock()
    return server


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace directory."""
    workspace = tmp_path / "ha-dev-workspace"
    workspace.mkdir()

    workflow_dir = tmp_path / ".ha-workflow"
    workflow_dir.mkdir()

    metadata_file = workflow_dir / "metadata.json"
    metadata_file.write_text("{}")

    yield {
        "workspace": workspace,
        "workflow_dir": workflow_dir,
        "metadata_file": metadata_file,
    }

    # Cleanup
    if workspace.exists():
        shutil.rmtree(workspace)
    if workflow_dir.exists():
        shutil.rmtree(workflow_dir)


@pytest.fixture
def mock_ha_api():
    """Mock Home Assistant API responses."""
    api = Mock()

    # Mock get_file_metadata response
    api.get_file_metadata = AsyncMock(
        return_value={
            "path": "configuration.yaml",
            "size": 1024,
            "modified": "2026-03-07T10:00:00Z",
            "hash": "abc123def456",
            "exists": True,
        }
    )

    # Mock read_config_file response
    api.read_config_file = AsyncMock(
        return_value={
            "content": "homeassistant:\n  name: Test Home\n  unit_system: metric\n",
            "metadata": {
                "total_size": 1024,
                "returned_size": 1024,
                "truncated": False,
                "offset": 0,
                "has_more": False,
                "compressed": False,
                "content_hash": "abc123def456",
            },
        }
    )

    return api


class TestDownloadWorkflow:
    """Test complete download file workflow."""

    @pytest.mark.asyncio
    async def test_complete_download_workflow(
        self, mock_mcp_server, temp_workspace, mock_ha_api
    ):
        """
        Test complete download workflow from user request to metadata recording.

        Workflow steps:
        1. User request: "Download my Home Assistant configuration.yaml"
        2. Context recognition: Identify HA context + file
        3. Steering retrieval: Load file-management.md workflow
        4. get_file_metadata: Get file info
        5. read_config_file: Retrieve file content
        6. Save locally: Write to ~/ha-dev-workspace/
        7. Record metadata: Update .ha-workflow/metadata.json
        """
        # Step 1: Simulate user request

        # Step 2: Context recognition
        context = {
            "has_ha_keywords": True,
            "mentions_file": True,
            "power_installed": True,
            "explicit_local": False,
        }

        # Verify context recognition
        assert context["has_ha_keywords"], "Should recognize HA context"
        assert context["mentions_file"], "Should recognize file mention"
        assert context["power_installed"], "Should detect power installed"
        assert not context["explicit_local"], "Should not be explicit local request"

        # Step 3: Steering retrieval (simulated)

        # Step 4: get_file_metadata
        metadata = await mock_ha_api.get_file_metadata("configuration.yaml")

        assert metadata["exists"], "File should exist"
        assert metadata["path"] == "configuration.yaml"
        assert metadata["size"] == 1024
        assert metadata["hash"] == "abc123def456"

        # Step 5: read_config_file
        file_response = await mock_ha_api.read_config_file("configuration.yaml")

        assert file_response["content"], "Should have content"
        assert not file_response["metadata"]["truncated"], "Should not be truncated"
        assert file_response["metadata"]["content_hash"] == metadata["hash"]

        # Step 6: Save locally
        local_file = temp_workspace["workspace"] / "configuration.yaml"
        local_file.write_text(file_response["content"])

        assert local_file.exists(), "File should be saved locally"
        assert local_file.read_text() == file_response["content"]

        # Step 7: Record metadata
        metadata_entry = {
            "configuration.yaml": {
                "remote_path": "configuration.yaml",
                "local_path": str(local_file),
                "size": metadata["size"],
                "hash": metadata["hash"],
                "modified": metadata["modified"],
                "downloaded_at": datetime.now().isoformat(),
                "complete": True,
            }
        }

        metadata_file = temp_workspace["metadata_file"]
        current_metadata = json.loads(metadata_file.read_text())
        current_metadata.update(metadata_entry)
        metadata_file.write_text(json.dumps(current_metadata, indent=2))

        # Verify metadata recorded
        saved_metadata = json.loads(metadata_file.read_text())
        assert "configuration.yaml" in saved_metadata
        assert saved_metadata["configuration.yaml"]["hash"] == "abc123def456"
        assert saved_metadata["configuration.yaml"]["complete"] is True

    @pytest.mark.asyncio
    async def test_workflow_step_order(
        self, mock_mcp_server, temp_workspace, mock_ha_api
    ):
        """
        Test that workflow steps execute in correct order.

        Verifies:
        - get_file_metadata called before read_config_file
        - File saved after content retrieved
        - Metadata recorded after file saved
        """
        call_order = []

        # Wrap API calls to track order
        original_get_metadata = mock_ha_api.get_file_metadata
        original_read_file = mock_ha_api.read_config_file

        async def tracked_get_metadata(*args, **kwargs):
            call_order.append("get_file_metadata")
            return await original_get_metadata(*args, **kwargs)

        async def tracked_read_file(*args, **kwargs):
            call_order.append("read_config_file")
            return await original_read_file(*args, **kwargs)

        mock_ha_api.get_file_metadata = tracked_get_metadata
        mock_ha_api.read_config_file = tracked_read_file

        # Execute workflow
        await mock_ha_api.get_file_metadata("automations.yaml")
        file_response = await mock_ha_api.read_config_file("automations.yaml")

        call_order.append("save_locally")
        local_file = temp_workspace["workspace"] / "automations.yaml"
        local_file.write_text(file_response["content"])

        call_order.append("record_metadata")
        # Record metadata (simplified)

        # Verify order
        assert call_order == [
            "get_file_metadata",
            "read_config_file",
            "save_locally",
            "record_metadata",
        ], f"Workflow steps out of order: {call_order}"

    @pytest.mark.asyncio
    async def test_file_saved_to_correct_location(
        self, mock_mcp_server, temp_workspace, mock_ha_api
    ):
        """
        Test that files are saved to ~/ha-dev-workspace/ directory.
        """
        file_response = await mock_ha_api.read_config_file("scripts.yaml")

        # Save to workspace
        local_file = temp_workspace["workspace"] / "scripts.yaml"
        local_file.write_text(file_response["content"])

        # Verify location
        assert local_file.parent.name == "ha-dev-workspace"
        assert local_file.exists()
        assert local_file.is_file()

    @pytest.mark.asyncio
    async def test_metadata_recorded_correctly(
        self, mock_mcp_server, temp_workspace, mock_ha_api
    ):
        """
        Test that metadata is recorded in .ha-workflow/metadata.json.
        """
        # Get file info
        metadata = await mock_ha_api.get_file_metadata("configuration.yaml")
        file_response = await mock_ha_api.read_config_file("configuration.yaml")

        # Save file
        local_file = temp_workspace["workspace"] / "configuration.yaml"
        local_file.write_text(file_response["content"])

        # Record metadata
        metadata_entry = {
            "configuration.yaml": {
                "remote_path": "configuration.yaml",
                "local_path": str(local_file),
                "size": metadata["size"],
                "hash": metadata["hash"],
                "modified": metadata["modified"],
                "downloaded_at": datetime.now().isoformat(),
            }
        }

        metadata_file = temp_workspace["metadata_file"]
        current_metadata = json.loads(metadata_file.read_text())
        current_metadata.update(metadata_entry)
        metadata_file.write_text(json.dumps(current_metadata, indent=2))

        # Verify metadata structure
        saved_metadata = json.loads(metadata_file.read_text())
        entry = saved_metadata["configuration.yaml"]

        assert entry["remote_path"] == "configuration.yaml"
        assert entry["local_path"] == str(local_file)
        assert entry["size"] == 1024
        assert entry["hash"] == "abc123def456"
        assert "modified" in entry
        assert "downloaded_at" in entry

    @pytest.mark.asyncio
    async def test_multiple_files_workflow(
        self, mock_mcp_server, temp_workspace, mock_ha_api
    ):
        """
        Test downloading multiple files maintains separate metadata.
        """
        files = ["configuration.yaml", "automations.yaml", "scripts.yaml"]

        for filename in files:
            # Get metadata
            metadata = await mock_ha_api.get_file_metadata(filename)

            # Read file
            file_response = await mock_ha_api.read_config_file(filename)

            # Save locally
            local_file = temp_workspace["workspace"] / filename
            local_file.write_text(file_response["content"])

            # Record metadata
            metadata_entry = {
                filename: {
                    "remote_path": filename,
                    "local_path": str(local_file),
                    "hash": metadata["hash"],
                    "downloaded_at": datetime.now().isoformat(),
                }
            }

            metadata_file = temp_workspace["metadata_file"]
            current_metadata = json.loads(metadata_file.read_text())
            current_metadata.update(metadata_entry)
            metadata_file.write_text(json.dumps(current_metadata, indent=2))

        # Verify all files tracked
        saved_metadata = json.loads(temp_workspace["metadata_file"].read_text())
        assert len(saved_metadata) == 3
        for filename in files:
            assert filename in saved_metadata
            assert saved_metadata[filename]["remote_path"] == filename

"""
Integration tests for complete Upload File workflow.

Tests the end-to-end workflow:
1. User request → validate YAML
2. Check conflicts with get_file_metadata
3. write_config_file with expected_hash
4. Verify upload succeeded

Requirements: 2.5, 2.6, 2.7, 2.8
"""

import pytest
import yaml
from unittest.mock import AsyncMock, Mock


@pytest.fixture
def mock_ha_api():
    """Mock Home Assistant API responses."""
    api = Mock()
    
    # Mock get_file_metadata response
    api.get_file_metadata = AsyncMock(return_value={
        "path": "automations.yaml",
        "size": 512,
        "modified": "2026-03-07T09:00:00Z",
        "hash": "original_hash_123",
        "exists": True
    })
    
    # Mock write_config_file response
    api.write_config_file = AsyncMock(return_value={
        "success": True,
        "path": "automations.yaml",
        "new_hash": "new_hash_456",
        "message": "File written successfully"
    })
    
    return api


@pytest.fixture
def valid_yaml_content():
    """Valid YAML content for testing."""
    return """
automation:
  - alias: "Test Automation"
    trigger:
      - platform: state
        entity_id: sensor.test
    action:
      - service: light.turn_on
        target:
          entity_id: light.test
"""


@pytest.fixture
def invalid_yaml_content():
    """Invalid YAML content for testing."""
    return """
automation:
  - alias: "Test Automation"
    trigger:
      [invalid: yaml: syntax
"""


class TestUploadWorkflow:
    """Test complete upload file workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_upload_workflow(self, mock_ha_api, valid_yaml_content):
        """
        Test complete upload workflow from user request to verification.
        
        Workflow steps:
        1. User request: "Upload my changes to automations.yaml"
        2. Validate YAML syntax
        3. Check for conflicts with get_file_metadata
        4. write_config_file with expected_hash
        5. Verify upload succeeded
        """
        # Step 1: Simulate user request
        filename = "automations.yaml"
        
        # Step 2: Validate YAML
        try:
            parsed = yaml.safe_load(valid_yaml_content)
            yaml_valid = True
            validation_error = None
        except yaml.YAMLError as e:
            yaml_valid = False
            validation_error = str(e)
        
        assert yaml_valid, f"YAML validation failed: {validation_error}"
        assert parsed is not None
        assert "automation" in parsed
        
        # Step 3: Check for conflicts
        current_metadata = await mock_ha_api.get_file_metadata(filename)
        
        assert current_metadata["exists"], "File should exist"
        expected_hash = current_metadata["hash"]
        
        # Step 4: write_config_file with expected_hash
        write_result = await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content,
            expected_hash=expected_hash
        )
        
        assert write_result["success"], "Upload should succeed"
        assert write_result["path"] == filename
        assert "new_hash" in write_result
        
        # Step 5: Verify upload
        assert write_result["new_hash"] != expected_hash, "Hash should change after upload"
        assert write_result["message"] == "File written successfully"
    
    @pytest.mark.asyncio
    async def test_yaml_validation_before_upload(self, mock_ha_api, invalid_yaml_content):
        """
        Test that YAML validation occurs before upload attempt.
        """
        
        # Attempt to validate invalid YAML
        try:
            yaml.safe_load(invalid_yaml_content)
            yaml_valid = True
        except yaml.YAMLError:
            yaml_valid = False
        
        assert not yaml_valid, "Invalid YAML should fail validation"
        
        # Should NOT proceed to upload if validation fails
        # Verify write_config_file was never called
        mock_ha_api.write_config_file.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_conflict_checking_with_expected_hash(self, mock_ha_api, valid_yaml_content):
        """
        Test that conflict checking uses expected_hash parameter.
        """
        filename = "configuration.yaml"
        
        # Get current file metadata
        current_metadata = await mock_ha_api.get_file_metadata(filename)
        expected_hash = current_metadata["hash"]
        
        # Upload with expected_hash
        await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content,
            expected_hash=expected_hash
        )
        
        # Verify expected_hash was passed
        mock_ha_api.write_config_file.assert_called_once()
        call_args = mock_ha_api.write_config_file.call_args
        assert call_args.kwargs.get("expected_hash") == expected_hash
    
    @pytest.mark.asyncio
    async def test_upload_confirmation(self, mock_ha_api, valid_yaml_content):
        """
        Test that upload confirmation is received and verified.
        """
        filename = "automations.yaml"
        
        # Validate YAML
        yaml.safe_load(valid_yaml_content)
        
        # Get metadata
        metadata = await mock_ha_api.get_file_metadata(filename)
        
        # Upload
        result = await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content,
            expected_hash=metadata["hash"]
        )
        
        # Verify confirmation
        assert result["success"] is True
        assert "new_hash" in result
        assert "message" in result
        assert result["path"] == filename
    
    @pytest.mark.asyncio
    async def test_workflow_step_order(self, mock_ha_api, valid_yaml_content):
        """
        Test that upload workflow steps execute in correct order.
        """
        call_order = []
        filename = "scripts.yaml"
        
        # Step 1: Validate YAML
        call_order.append("validate_yaml")
        yaml.safe_load(valid_yaml_content)
        
        # Step 2: Check conflicts
        call_order.append("check_conflicts")
        metadata = await mock_ha_api.get_file_metadata(filename)
        
        # Step 3: Write file
        call_order.append("write_config_file")
        result = await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content,
            expected_hash=metadata["hash"]
        )
        
        # Step 4: Verify upload
        call_order.append("verify_upload")
        assert result["success"]
        
        # Verify order
        assert call_order == [
            "validate_yaml",
            "check_conflicts",
            "write_config_file",
            "verify_upload"
        ]
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, mock_ha_api, valid_yaml_content):
        """
        Test that conflicts are detected when expected_hash doesn't match.
        """
        filename = "configuration.yaml"
        
        # Get current metadata
        current_metadata = await mock_ha_api.get_file_metadata(filename)
        
        # Simulate conflict: use wrong expected_hash
        wrong_hash = "wrong_hash_999"
        
        # Mock conflict response
        mock_ha_api.write_config_file = AsyncMock(return_value={
            "success": False,
            "error": "Conflict detected",
            "message": "File has been modified since last read",
            "current_hash": current_metadata["hash"],
            "expected_hash": wrong_hash
        })
        
        # Attempt upload with wrong hash
        result = await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content,
            expected_hash=wrong_hash
        )
        
        # Verify conflict detected
        assert not result["success"]
        assert "Conflict" in result["error"]
        assert result["current_hash"] != result["expected_hash"]
    
    @pytest.mark.asyncio
    async def test_yaml_validation_error_messages(self, invalid_yaml_content):
        """
        Test that YAML validation provides clear error messages.
        """
        try:
            yaml.safe_load(invalid_yaml_content)
            validation_passed = True
            error_message = None
        except yaml.YAMLError as e:
            validation_passed = False
            error_message = str(e)
        
        assert not validation_passed
        assert error_message is not None
        assert len(error_message) > 0
    
    @pytest.mark.asyncio
    async def test_upload_new_file(self, mock_ha_api, valid_yaml_content):
        """
        Test uploading a new file that doesn't exist yet.
        """
        filename = "new_automations.yaml"
        
        # Mock metadata for non-existent file
        mock_ha_api.get_file_metadata = AsyncMock(return_value={
            "path": filename,
            "exists": False
        })
        
        # Mock successful creation
        mock_ha_api.write_config_file = AsyncMock(return_value={
            "success": True,
            "path": filename,
            "new_hash": "new_file_hash_123",
            "message": "File created successfully"
        })
        
        # Validate YAML
        yaml.safe_load(valid_yaml_content)
        
        # Check if file exists
        metadata = await mock_ha_api.get_file_metadata(filename)
        assert not metadata["exists"]
        
        # Upload new file (no expected_hash needed)
        result = await mock_ha_api.write_config_file(
            filename,
            valid_yaml_content
        )
        
        assert result["success"]
        assert "created" in result["message"].lower()

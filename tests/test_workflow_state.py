"""Unit tests for workflow state management.

Tests workflow creation, state persistence and loading, workflow resumption,
workflow completion and cleanup, and handling corrupted state.

Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime

from ha_config_manager.workflow_state import (
    WorkflowStateManager,
    WorkflowType,
    WorkflowStatus,
    FileStatus,
    WorkflowState,
    WorkflowFile
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_files():
    """Sample file data for testing."""
    return [
        {
            "local_path": "automations.yaml",
            "remote_path": "automations.yaml",
            "downloaded_at": "2026-03-06T10:00:00",
            "remote_hash": "a" * 64,
            "remote_modified": "2026-03-06T09:00:00",
            "status": FileStatus.CLEAN.value
        },
        {
            "local_path": "scripts.yaml",
            "remote_path": "scripts.yaml",
            "downloaded_at": "2026-03-06T10:01:00",
            "remote_hash": "b" * 64,
            "remote_modified": "2026-03-06T09:01:00",
            "status": FileStatus.CLEAN.value
        }
    ]


class TestWorkflowCreation:
    """Test workflow creation functionality."""
    
    def test_create_automation_workflow(self, temp_workspace, sample_files):
        """Test creating an automation workflow."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        assert workflow is not None
        assert workflow.workflow_type == WorkflowType.AUTOMATION
        assert workflow.current_step == 1
        assert workflow.total_steps == 9
        assert len(workflow.files) == 2
        assert workflow.status == WorkflowStatus.IN_PROGRESS
        assert workflow.workflow_id is not None
    
    def test_create_template_workflow(self, temp_workspace, sample_files):
        """Test creating a template workflow."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.TEMPLATE,
            files=sample_files[:1],
            total_steps=4
        )
        
        assert workflow.workflow_type == WorkflowType.TEMPLATE
        assert len(workflow.files) == 1
        assert workflow.total_steps == 4
    
    def test_create_package_workflow(self, temp_workspace, sample_files):
        """Test creating a package workflow."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.PACKAGE,
            files=sample_files,
            total_steps=7
        )
        
        assert workflow.workflow_type == WorkflowType.PACKAGE
        assert workflow.total_steps == 7
    
    def test_workflow_creates_directory(self, temp_workspace, sample_files):
        """Test that workflow creation creates .ha-workflow directory."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow_dir = Path(temp_workspace) / ".ha-workflow"
        assert not workflow_dir.exists()
        
        manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=5
        )
        
        assert workflow_dir.exists()
        assert workflow_dir.is_dir()
    
    def test_workflow_creates_state_file(self, temp_workspace, sample_files):
        """Test that workflow creation creates state.json file."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        state_file = Path(temp_workspace) / ".ha-workflow" / "state.json"
        assert not state_file.exists()
        
        manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=5
        )
        
        assert state_file.exists()
        assert state_file.is_file()


class TestStatePersistence:
    """Test state persistence and loading."""
    
    def test_save_and_load_workflow(self, temp_workspace, sample_files):
        """Test saving and loading workflow state."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        # Create workflow
        original = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Load in new manager instance
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        loaded = manager2.load_current_workflow()
        
        assert loaded is not None
        assert loaded.workflow_id == original.workflow_id
        assert loaded.workflow_type == original.workflow_type
        assert loaded.current_step == original.current_step
        assert loaded.total_steps == original.total_steps
        assert len(loaded.files) == len(original.files)
    
    def test_state_file_format(self, temp_workspace, sample_files):
        """Test that state file is valid JSON."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=5
        )
        
        state_file = Path(temp_workspace) / ".ha-workflow" / "state.json"
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        assert "workflow_id" in data
        assert "workflow_type" in data
        assert "files" in data
        assert "status" in data
    
    def test_load_nonexistent_workflow(self, temp_workspace):
        """Test loading when no workflow exists."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.load_current_workflow()
        
        assert workflow is None
    
    def test_multiple_save_updates(self, temp_workspace, sample_files):
        """Test that multiple saves update the state file."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Update step
        manager.update_step(workflow.workflow_id, 3)
        
        # Load and verify
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        loaded = manager2.load_current_workflow()
        
        assert loaded.current_step == 3


class TestWorkflowResumption:
    """Test workflow resumption after interruption."""
    
    def test_resume_in_progress_workflow(self, temp_workspace, sample_files):
        """Test resuming an in-progress workflow."""
        # Create workflow
        manager1 = WorkflowStateManager(workspace_path=temp_workspace)
        original = manager1.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Simulate interruption and resume
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        resumed = manager2.load_current_workflow()
        
        assert resumed is not None
        assert resumed.workflow_id == original.workflow_id
        assert resumed.status == WorkflowStatus.IN_PROGRESS
    
    def test_resume_preserves_file_status(self, temp_workspace, sample_files):
        """Test that resumption preserves file status."""
        manager1 = WorkflowStateManager(workspace_path=temp_workspace)
        workflow = manager1.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Mark file as modified
        manager1.mark_file_modified(workflow.workflow_id, "automations.yaml")
        
        # Resume
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        resumed = manager2.load_current_workflow()
        
        assert resumed.files[0].status == FileStatus.MODIFIED
    
    def test_resume_preserves_current_step(self, temp_workspace, sample_files):
        """Test that resumption preserves current step."""
        manager1 = WorkflowStateManager(workspace_path=temp_workspace)
        workflow = manager1.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Update step
        manager1.update_step(workflow.workflow_id, 5)
        
        # Resume
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        resumed = manager2.load_current_workflow()
        
        assert resumed.current_step == 5


class TestWorkflowCompletion:
    """Test workflow completion and cleanup."""
    
    def test_complete_workflow(self, temp_workspace, sample_files):
        """Test completing a workflow."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        manager.complete_workflow(workflow.workflow_id)
        
        # Load and verify status
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        loaded = manager2.load_current_workflow()
        
        assert loaded.status == WorkflowStatus.COMPLETED
    
    def test_complete_workflow_updates_timestamp(self, temp_workspace, sample_files):
        """Test that completion updates last_updated timestamp."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        original_timestamp = workflow.last_updated
        
        # Wait a moment to ensure timestamp changes
        import time
        time.sleep(0.01)
        
        manager.complete_workflow(workflow.workflow_id)
        
        # Load and verify
        manager2 = WorkflowStateManager(workspace_path=temp_workspace)
        loaded = manager2.load_current_workflow()
        
        assert loaded.last_updated != original_timestamp
    
    def test_complete_clears_current_workflow(self, temp_workspace, sample_files):
        """Test that completion clears current workflow reference."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        assert manager._current_workflow is not None
        
        manager.complete_workflow(workflow.workflow_id)
        
        assert manager._current_workflow is None


class TestCorruptedStateHandling:
    """Test handling of corrupted state files."""
    
    def test_handle_invalid_json(self, temp_workspace):
        """Test handling of invalid JSON in state file."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        # Create workflow directory and write invalid JSON
        manager._ensure_workflow_dir()
        with open(manager.state_file, 'w') as f:
            f.write("{ invalid json }")
        
        # Should return None and not crash
        workflow = manager.load_current_workflow()
        assert workflow is None
    
    def test_backup_corrupted_file(self, temp_workspace):
        """Test that corrupted file is backed up."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        # Create workflow directory and write invalid JSON
        manager._ensure_workflow_dir()
        with open(manager.state_file, 'w') as f:
            f.write("{ invalid json }")
        
        # Load (will fail and backup)
        manager.load_current_workflow()
        
        # Check backup exists
        backup_file = manager.state_file.with_suffix('.json.corrupted')
        assert backup_file.exists()
    
    def test_handle_missing_required_fields(self, temp_workspace):
        """Test handling of JSON with missing required fields."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        # Create workflow directory and write incomplete JSON
        manager._ensure_workflow_dir()
        with open(manager.state_file, 'w') as f:
            json.dump({"workflow_id": "test"}, f)
        
        # Should return None and not crash
        workflow = manager.load_current_workflow()
        assert workflow is None
    
    def test_handle_empty_file(self, temp_workspace):
        """Test handling of empty state file."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        # Create workflow directory and write empty file
        manager._ensure_workflow_dir()
        with open(manager.state_file, 'w') as f:
            f.write("")
        
        # Should return None and not crash
        workflow = manager.load_current_workflow()
        assert workflow is None


class TestWorkflowLifecycleMethods:
    """Test workflow lifecycle methods."""
    
    def test_update_step(self, temp_workspace, sample_files):
        """Test updating workflow step."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        assert workflow.current_step == 1
        
        manager.update_step(workflow.workflow_id, 5)
        
        # Verify in loaded state
        loaded = manager.load_current_workflow()
        assert loaded.current_step == 5
    
    def test_mark_file_modified(self, temp_workspace, sample_files):
        """Test marking a file as modified."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        assert workflow.files[0].status == FileStatus.CLEAN
        
        manager.mark_file_modified(workflow.workflow_id, "automations.yaml")
        
        # Verify in loaded state
        loaded = manager.load_current_workflow()
        assert loaded.files[0].status == FileStatus.MODIFIED
    
    def test_mark_file_modified_by_remote_path(self, temp_workspace, sample_files):
        """Test marking a file as modified using remote path."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        manager.mark_file_modified(workflow.workflow_id, sample_files[1]["remote_path"])
        
        # Verify in loaded state
        loaded = manager.load_current_workflow()
        assert loaded.files[1].status == FileStatus.MODIFIED
    
    def test_detect_conflicts_empty(self, temp_workspace, sample_files):
        """Test detecting conflicts when none exist."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        conflicts = manager.detect_conflicts(workflow.workflow_id)
        
        assert len(conflicts) == 0
    
    def test_detect_conflicts_with_conflict(self, temp_workspace, sample_files):
        """Test detecting conflicts when they exist."""
        manager = WorkflowStateManager(workspace_path=temp_workspace)
        
        workflow = manager.create_workflow(
            workflow_type=WorkflowType.AUTOMATION,
            files=sample_files,
            total_steps=9
        )
        
        # Manually set a file to conflict status
        workflow.files[0].status = FileStatus.CONFLICT
        manager._save_state(workflow)
        
        conflicts = manager.detect_conflicts(workflow.workflow_id)
        
        assert len(conflicts) == 1
        assert conflicts[0].local_path == "automations.yaml"


class TestWorkflowFileSerialization:
    """Test WorkflowFile serialization."""
    
    def test_workflow_file_to_dict(self):
        """Test converting WorkflowFile to dictionary."""
        file = WorkflowFile(
            local_path="test.yaml",
            remote_path="test.yaml",
            downloaded_at="2026-03-06T10:00:00",
            remote_hash="a" * 64,
            remote_modified="2026-03-06T09:00:00",
            status=FileStatus.CLEAN
        )
        
        data = file.to_dict()
        
        assert data["local_path"] == "test.yaml"
        assert data["status"] == "clean"
    
    def test_workflow_file_from_dict(self):
        """Test creating WorkflowFile from dictionary."""
        data = {
            "local_path": "test.yaml",
            "remote_path": "test.yaml",
            "downloaded_at": "2026-03-06T10:00:00",
            "remote_hash": "a" * 64,
            "remote_modified": "2026-03-06T09:00:00",
            "status": "modified"
        }
        
        file = WorkflowFile.from_dict(data)
        
        assert file.local_path == "test.yaml"
        assert file.status == FileStatus.MODIFIED


class TestWorkflowStateSerialization:
    """Test WorkflowState serialization."""
    
    def test_workflow_state_to_json(self, sample_files):
        """Test converting WorkflowState to JSON."""
        workflow = WorkflowState(
            workflow_id="test-123",
            workflow_type=WorkflowType.AUTOMATION,
            current_step=1,
            total_steps=9,
            files=[WorkflowFile.from_dict(f) for f in sample_files]
        )
        
        json_str = workflow.to_json()
        
        assert "test-123" in json_str
        assert "automation" in json_str
    
    def test_workflow_state_from_json(self, sample_files):
        """Test creating WorkflowState from JSON."""
        workflow = WorkflowState(
            workflow_id="test-123",
            workflow_type=WorkflowType.AUTOMATION,
            current_step=1,
            total_steps=9,
            files=[WorkflowFile.from_dict(f) for f in sample_files]
        )
        
        json_str = workflow.to_json()
        restored = WorkflowState.from_json(json_str)
        
        assert restored.workflow_id == workflow.workflow_id
        assert restored.workflow_type == workflow.workflow_type
        assert len(restored.files) == len(workflow.files)

"""Property-based tests for workflow state management.

Tests Property 11: Workflow State Persistence
Validates: Requirements 8.3
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from pathlib import Path
import tempfile
import shutil
import json

from ha_dev_tools.workflow_state import (
    WorkflowStateManager,
    WorkflowType,
    WorkflowStatus,
    FileStatus,
    WorkflowState,
    WorkflowFile
)


# Strategy for generating workflow types
workflow_type_strategy = st.sampled_from([
    WorkflowType.AUTOMATION,
    WorkflowType.TEMPLATE,
    WorkflowType.CONFIGURATION,
    WorkflowType.PACKAGE,
    WorkflowType.SCRIPT
])

# Strategy for generating file paths
file_path_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-./'),
    min_size=1,
    max_size=50
).filter(lambda x: x and not x.startswith('/') and '..' not in x)

# Strategy for generating workflow files
@st.composite
def workflow_file_strategy(draw):
    """Generate a valid WorkflowFile."""
    local_path = draw(file_path_strategy)
    remote_path = draw(file_path_strategy)
    
    return {
        "local_path": local_path,
        "remote_path": remote_path,
        "downloaded_at": "2026-03-06T10:00:00",
        "remote_hash": "a" * 64,  # Valid SHA-256 hash
        "remote_modified": "2026-03-06T09:00:00",
        "status": FileStatus.CLEAN.value
    }


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@given(
    workflow_type=workflow_type_strategy,
    files=st.lists(workflow_file_strategy(), min_size=1, max_size=5),
    total_steps=st.integers(min_value=1, max_value=20)
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=100
)
def test_workflow_state_persistence_property(temp_workspace, workflow_type, files, total_steps):
    """Property 11: Workflow State Persistence
    
    For any workflow, interrupting and resuming should preserve all workflow state
    including files, steps, and status.
    
    Tag: Feature: improved-ha-development-workflow, Property 11: Workflow state persistence
    """
    # Create workflow state manager
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create a workflow
    workflow = manager.create_workflow(
        workflow_type=workflow_type,
        files=files,
        total_steps=total_steps
    )
    
    original_id = workflow.workflow_id
    original_type = workflow.workflow_type
    original_files_count = len(workflow.files)
    original_total_steps = workflow.total_steps
    
    # Simulate interruption by creating a new manager instance
    manager2 = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Resume workflow
    resumed_workflow = manager2.load_current_workflow()
    
    # Verify workflow state is preserved
    assert resumed_workflow is not None, "Workflow should be loadable after interruption"
    assert resumed_workflow.workflow_id == original_id, "Workflow ID should be preserved"
    assert resumed_workflow.workflow_type == original_type, "Workflow type should be preserved"
    assert len(resumed_workflow.files) == original_files_count, "File count should be preserved"
    assert resumed_workflow.total_steps == original_total_steps, "Total steps should be preserved"
    assert resumed_workflow.status == WorkflowStatus.IN_PROGRESS, "Status should be preserved"
    
    # Verify file details are preserved
    for original_file, resumed_file in zip(workflow.files, resumed_workflow.files):
        assert resumed_file.local_path == original_file.local_path, "Local path should be preserved"
        assert resumed_file.remote_path == original_file.remote_path, "Remote path should be preserved"
        assert resumed_file.downloaded_at == original_file.downloaded_at, "Download timestamp should be preserved"
        assert resumed_file.remote_hash == original_file.remote_hash, "Remote hash should be preserved"
        assert resumed_file.status == original_file.status, "File status should be preserved"


@given(
    workflow_type=workflow_type_strategy,
    files=st.lists(workflow_file_strategy(), min_size=1, max_size=3),
    step=st.integers(min_value=1, max_value=10)
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50
)
def test_workflow_step_update_persistence(temp_workspace, workflow_type, files, step):
    """Test that step updates are persisted correctly."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create workflow
    workflow = manager.create_workflow(
        workflow_type=workflow_type,
        files=files,
        total_steps=max(step, 10)
    )
    
    # Update step
    manager.update_step(workflow.workflow_id, step)
    
    # Load in new manager instance
    manager2 = WorkflowStateManager(workspace_path=temp_workspace)
    resumed = manager2.load_current_workflow()
    
    assert resumed is not None
    assert resumed.current_step == step, "Step update should be persisted"


@given(
    workflow_type=workflow_type_strategy,
    files=st.lists(workflow_file_strategy(), min_size=1, max_size=3)
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50
)
def test_workflow_file_modification_persistence(temp_workspace, workflow_type, files):
    """Test that file modifications are persisted correctly."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create workflow
    workflow = manager.create_workflow(
        workflow_type=workflow_type,
        files=files,
        total_steps=5
    )
    
    # Mark first file as modified
    first_file_path = workflow.files[0].local_path
    manager.mark_file_modified(workflow.workflow_id, first_file_path)
    
    # Load in new manager instance
    manager2 = WorkflowStateManager(workspace_path=temp_workspace)
    resumed = manager2.load_current_workflow()
    
    assert resumed is not None
    assert resumed.files[0].status == FileStatus.MODIFIED, "File modification should be persisted"


@given(
    workflow_type=workflow_type_strategy,
    files=st.lists(workflow_file_strategy(), min_size=1, max_size=3)
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50
)
def test_workflow_completion_persistence(temp_workspace, workflow_type, files):
    """Test that workflow completion is persisted correctly."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create workflow
    workflow = manager.create_workflow(
        workflow_type=workflow_type,
        files=files,
        total_steps=5
    )
    
    # Complete workflow
    manager.complete_workflow(workflow.workflow_id)
    
    # Load in new manager instance
    manager2 = WorkflowStateManager(workspace_path=temp_workspace)
    resumed = manager2.load_current_workflow()
    
    assert resumed is not None
    assert resumed.status == WorkflowStatus.COMPLETED, "Workflow completion should be persisted"


def test_corrupted_state_file_handling(temp_workspace):
    """Test that corrupted state files are handled gracefully."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create workflow directory and write corrupted JSON
    manager._ensure_workflow_dir()
    with open(manager.state_file, 'w') as f:
        f.write("{ invalid json }")
    
    # Should handle gracefully and return None
    workflow = manager.load_current_workflow()
    assert workflow is None, "Should return None for corrupted state"
    
    # Should create backup of corrupted file
    backup_file = manager.state_file.with_suffix('.json.corrupted')
    assert backup_file.exists(), "Should create backup of corrupted file"


def test_missing_state_file_handling(temp_workspace):
    """Test that missing state files are handled gracefully."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Should handle gracefully and return None
    workflow = manager.load_current_workflow()
    assert workflow is None, "Should return None when no state file exists"


@given(
    workflow_type=workflow_type_strategy,
    files=st.lists(workflow_file_strategy(), min_size=1, max_size=3)
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50
)
def test_workflow_serialization_round_trip(temp_workspace, workflow_type, files):
    """Test that workflow serialization and deserialization preserves all data."""
    manager = WorkflowStateManager(workspace_path=temp_workspace)
    
    # Create workflow
    original = manager.create_workflow(
        workflow_type=workflow_type,
        files=files,
        total_steps=5
    )
    
    # Serialize to JSON
    json_str = original.to_json()
    
    # Deserialize from JSON
    restored = WorkflowState.from_json(json_str)
    
    # Verify all fields match
    assert restored.workflow_id == original.workflow_id
    assert restored.workflow_type == original.workflow_type
    assert restored.current_step == original.current_step
    assert restored.total_steps == original.total_steps
    assert restored.status == original.status
    assert len(restored.files) == len(original.files)
    
    for orig_file, rest_file in zip(original.files, restored.files):
        assert rest_file.local_path == orig_file.local_path
        assert rest_file.remote_path == orig_file.remote_path
        assert rest_file.status == orig_file.status

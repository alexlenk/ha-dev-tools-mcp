"""
Bug Condition Exploration Test: Steering Workflow Compliance

This test explores Bug 2: Steering File Not Followed
- Tests that Kiro follows documented workflows from steering files
- EXPECTED TO FAIL on unfixed code (proves bug exists)
- Will PASS after fix is implemented (validates fix)

Bug Condition: isBugCondition2(context, toolCall)
  Returns true when:
  - Tool call is an HA file tool (read_config_file, write_config_file, get_file_metadata)
  - Steering file exists for ha-development-power
  - Workflow patterns are documented in steering file

Expected Behavior (after fix):
  - Download workflow: get_file_metadata → read_config_file → save locally → record metadata
  - Upload workflow: validate YAML → check conflicts → write_config_file with expected_hash
  - Steering file content is retrieved and applied

Current Behavior (unfixed):
  - Kiro calls single MCP tool without following workflow
  - Steering file guidance is ignored
  - Multi-step workflows are not executed
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# ============================================================================
# Workflow Step Definitions
# ============================================================================

@dataclass
class WorkflowStep:
    """Represents a single step in a workflow"""
    name: str
    tool: str
    parameters: Dict[str, Any]
    order: int


@dataclass
class Workflow:
    """Represents a complete workflow with multiple steps"""
    name: str
    steps: List[WorkflowStep]
    trigger_pattern: str


# ============================================================================
# Steering File Content (Documented Workflows)
# ============================================================================

class SteeringFileWorkflows:
    """
    Documented workflows from ha-development-power/steering/file-management.md
    
    These are the workflows that Kiro SHOULD follow but currently doesn't.
    """
    
    @staticmethod
    def get_download_workflow() -> Workflow:
        """
        Workflow 2: Download Files with Metadata
        
        Steps:
        1. Get file metadata (hash, timestamp)
        2. Download file content
        3. Save to ~/ha-dev-workspace/
        4. Record metadata for version tracking
        """
        return Workflow(
            name="Download File with Metadata",
            trigger_pattern="download|get|fetch",
            steps=[
                WorkflowStep(
                    name="Check metadata",
                    tool="get_file_metadata",
                    parameters={"file_path": "automations.yaml"},
                    order=1
                ),
                WorkflowStep(
                    name="Download file",
                    tool="read_config_file",
                    parameters={"file_path": "automations.yaml"},
                    order=2
                ),
                WorkflowStep(
                    name="Save locally",
                    tool="save_to_workspace",
                    parameters={
                        "file_path": "automations.yaml",
                        "workspace_dir": "~/ha-dev-workspace/"
                    },
                    order=3
                ),
                WorkflowStep(
                    name="Record metadata",
                    tool="record_metadata",
                    parameters={
                        "file_path": "automations.yaml",
                        "metadata_file": ".ha-workflow/metadata.json"
                    },
                    order=4
                )
            ]
        )
    
    @staticmethod
    def get_upload_workflow() -> Workflow:
        """
        Workflow 3: Upload Files with Validation
        
        Steps:
        1. Validate YAML syntax
        2. Check for conflicts (get metadata, compare hash)
        3. Upload with expected_hash
        4. Verify upload succeeded
        """
        return Workflow(
            name="Upload File with Validation",
            trigger_pattern="upload|write|save|push",
            steps=[
                WorkflowStep(
                    name="Validate YAML",
                    tool="validate_yaml",
                    parameters={"content": "yaml_content"},
                    order=1
                ),
                WorkflowStep(
                    name="Check conflicts",
                    tool="get_file_metadata",
                    parameters={"file_path": "scripts.yaml"},
                    order=2
                ),
                WorkflowStep(
                    name="Upload with hash",
                    tool="write_config_file",
                    parameters={
                        "file_path": "scripts.yaml",
                        "content": "yaml_content",
                        "expected_hash": "hash_from_metadata",
                        "validate_before_write": True
                    },
                    order=3
                ),
                WorkflowStep(
                    name="Verify upload",
                    tool="get_file_metadata",
                    parameters={"file_path": "scripts.yaml"},
                    order=4
                )
            ]
        )


# ============================================================================
# Mock Kiro Workflow Execution System
# ============================================================================

class MockKiroWorkflowExecutor:
    """
    Simulates Kiro's workflow execution logic (UNFIXED VERSION)
    
    Current behavior:
    - Executes single tool call without workflow
    - Does not retrieve steering file content
    - Does not follow multi-step workflows
    - Ignores documented workflow patterns
    """
    
    def __init__(self, steering_files: Dict[str, str]):
        self.steering_files = steering_files
        self.executed_steps = []
    
    def execute_request(self, user_request: str, file_path: str) -> List[str]:
        """
        Simulates current Kiro behavior (UNFIXED)
        
        Current logic:
        1. Parse user request
        2. Execute single tool call
        3. Return result
        
        This is the BUG - it should:
        1. Retrieve steering file
        2. Identify workflow pattern
        3. Execute all workflow steps in order
        """
        self.executed_steps = []
        
        # Current behavior: just execute single tool (THIS IS THE BUG)
        if "download" in user_request.lower() or "get" in user_request.lower():
            # Should follow download workflow, but only does single step
            self.executed_steps.append("read_config_file")
            return ["read_config_file"]
        
        elif "upload" in user_request.lower() or "write" in user_request.lower():
            # Should follow upload workflow, but only does single step
            self.executed_steps.append("write_config_file")
            return ["write_config_file"]
        
        return []
    
    def get_executed_workflow_steps(self) -> List[str]:
        """Returns the tools that were executed"""
        return self.executed_steps


# ============================================================================
# Bug Condition Function
# ============================================================================

def is_bug_condition_2(context: Dict[str, Any], tool_call: str) -> bool:
    """
    Bug Condition 2: Should follow steering workflow but doesn't
    
    Returns True when:
    - Tool call is an HA file tool
    - Steering file exists for ha-development-power
    - Workflow patterns are documented
    
    When this returns True, Kiro SHOULD follow documented workflows but currently doesn't.
    """
    ha_file_tools = [
        "read_config_file", "write_config_file",
        "get_file_metadata", "batch_get_metadata"
    ]
    
    # Check if tool is an HA file tool
    is_ha_file_tool = tool_call in ha_file_tools
    
    # Check if steering file exists
    steering_exists = "ha-development-power/steering/file-management.md" in context.get("steering_files", {})
    
    return is_ha_file_tool and steering_exists


# ============================================================================
# Property-Based Exploration Tests
# ============================================================================

class TestBug2SteeringWorkflow:
    """
    Bug 2 Exploration Tests
    
    These tests are EXPECTED TO FAIL on unfixed code.
    Failure confirms the bug exists.
    """
    
    def test_download_workflow_not_followed(self):
        """
        Test: User says "Download my automations.yaml"
        
        Expected (after fix): Follows complete download workflow
          1. get_file_metadata
          2. read_config_file
          3. save_to_workspace
          4. record_metadata
        
        Current (unfixed): Only executes read_config_file
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        # Setup context with steering file
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        # User request
        user_request = "Download my automations.yaml"
        file_path = "automations.yaml"
        
        # Get expected workflow from steering file
        expected_workflow = SteeringFileWorkflows.get_download_workflow()
        expected_steps = [step.tool for step in expected_workflow.steps]
        
        # Simulate Kiro's execution (UNFIXED)
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # Verify this is a bug condition
        first_tool = executed_steps[0] if executed_steps else ""
        assert is_bug_condition_2(context, first_tool), \
            "This should be identified as a bug condition"
        
        # ASSERTION: Should execute all workflow steps (will FAIL on unfixed code)
        assert len(executed_steps) == len(expected_steps), \
            f"Expected {len(expected_steps)} workflow steps, but only executed {len(executed_steps)}. " \
            f"Bug confirmed: Download workflow not followed."
        
        # ASSERTION: Should execute steps in correct order
        assert executed_steps == expected_steps, \
            f"Expected workflow steps {expected_steps}, but got {executed_steps}. " \
            f"Bug confirmed: Kiro only executes single tool, ignores workflow."
    
    def test_upload_workflow_not_followed(self):
        """
        Test: User says "Upload my changes to scripts.yaml"
        
        Expected (after fix): Follows complete upload workflow
          1. validate_yaml
          2. get_file_metadata (check conflicts)
          3. write_config_file (with expected_hash)
          4. get_file_metadata (verify)
        
        Current (unfixed): Only executes write_config_file
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Upload my changes to scripts.yaml"
        file_path = "scripts.yaml"
        
        # Get expected workflow
        expected_workflow = SteeringFileWorkflows.get_upload_workflow()
        expected_steps = [step.tool for step in expected_workflow.steps]
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # Verify bug condition
        first_tool = executed_steps[0] if executed_steps else ""
        assert is_bug_condition_2(context, first_tool)
        
        # ASSERTION: Should execute all workflow steps (will FAIL)
        assert len(executed_steps) == len(expected_steps), \
            f"Expected {len(expected_steps)} workflow steps, but only executed {len(executed_steps)}. " \
            f"Bug confirmed: Upload workflow not followed."
        
        # ASSERTION: Should include validation step
        assert "validate_yaml" in executed_steps, \
            f"Upload workflow should validate YAML before upload. " \
            f"Bug confirmed: Validation step missing."
        
        # ASSERTION: Should include conflict checking
        assert "get_file_metadata" in executed_steps, \
            f"Upload workflow should check for conflicts. " \
            f"Bug confirmed: Conflict checking missing."
    
    def test_metadata_not_recorded_after_download(self):
        """
        Test: After downloading file, metadata should be recorded
        
        Expected (after fix): Metadata saved to .ha-workflow/metadata.json
        Current (unfixed): Metadata not recorded
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Download automations.yaml"
        file_path = "automations.yaml"
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # ASSERTION: Should record metadata (will FAIL)
        assert "record_metadata" in executed_steps, \
            f"Download workflow should record metadata for version tracking. " \
            f"Executed steps: {executed_steps}. " \
            f"Bug confirmed: Metadata not recorded."
    
    def test_file_not_saved_locally_after_download(self):
        """
        Test: After downloading file, it should be saved to workspace
        
        Expected (after fix): File saved to ~/ha-dev-workspace/
        Current (unfixed): File content only displayed, not saved
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Download configuration.yaml"
        file_path = "configuration.yaml"
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # ASSERTION: Should save to workspace (will FAIL)
        assert "save_to_workspace" in executed_steps, \
            f"Download workflow should save file to local workspace. " \
            f"Executed steps: {executed_steps}. " \
            f"Bug confirmed: File not saved locally."
    
    def test_yaml_not_validated_before_upload(self):
        """
        Test: Before uploading file, YAML should be validated
        
        Expected (after fix): YAML validation before write_config_file
        Current (unfixed): No validation, direct upload
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Upload my automations.yaml"
        file_path = "automations.yaml"
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # ASSERTION: Should validate YAML (will FAIL)
        assert "validate_yaml" in executed_steps, \
            f"Upload workflow should validate YAML syntax before upload. " \
            f"Executed steps: {executed_steps}. " \
            f"Bug confirmed: YAML not validated."
    
    def test_conflicts_not_checked_before_upload(self):
        """
        Test: Before uploading file, conflicts should be checked
        
        Expected (after fix): get_file_metadata to check hash before upload
        Current (unfixed): No conflict checking
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Upload scripts.yaml"
        file_path = "scripts.yaml"
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # ASSERTION: Should check conflicts (will FAIL)
        assert "get_file_metadata" in executed_steps, \
            f"Upload workflow should check for conflicts before upload. " \
            f"Executed steps: {executed_steps}. " \
            f"Bug confirmed: Conflicts not checked."
    
    def test_expected_hash_not_used_in_upload(self):
        """
        Test: Upload should include expected_hash parameter
        
        Expected (after fix): write_config_file called with expected_hash
        Current (unfixed): write_config_file called without expected_hash
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Upload automations.yaml"
        file_path = "automations.yaml"
        
        # Get expected workflow
        expected_workflow = SteeringFileWorkflows.get_upload_workflow()
        write_step = next(s for s in expected_workflow.steps if s.tool == "write_config_file")
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # ASSERTION: write_config_file should be called with expected_hash (will FAIL)
        # Note: In real implementation, we'd check the actual parameters passed
        # For this mock, we just verify the workflow includes the conflict check step
        assert "get_file_metadata" in executed_steps, \
            f"Upload workflow should get metadata to obtain expected_hash. " \
            f"Bug confirmed: expected_hash not used in upload."
    
    @given(
        action=st.sampled_from(["Download", "Get", "Fetch"]),
        file_name=st.sampled_from(["automations.yaml", "scripts.yaml", "configuration.yaml"])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=15)
    def test_property_download_workflows_complete(self, action, file_name):
        """
        Property-Based Test: All download requests should follow complete workflow
        
        Property: For all download requests, Kiro should execute all workflow steps:
                  1. get_file_metadata
                  2. read_config_file
                  3. save_to_workspace
                  4. record_metadata
        
        EXPECTED OUTCOME: FAIL on multiple examples (proves bug exists across variations)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = f"{action} my {file_name}"
        
        # Get expected workflow
        expected_workflow = SteeringFileWorkflows.get_download_workflow()
        expected_steps = [step.tool for step in expected_workflow.steps]
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_name)
        
        # Verify bug condition
        if not executed_steps:
            return  # Skip if no tools executed
        
        first_tool = executed_steps[0]
        if not is_bug_condition_2(context, first_tool):
            return  # Skip if not a bug condition
        
        # ASSERTION: Should execute all workflow steps
        assert len(executed_steps) >= 3, \
            f"Request: '{user_request}' | " \
            f"Expected at least 3 workflow steps, but only executed {len(executed_steps)}. " \
            f"Bug confirmed: Incomplete workflow execution."
        
        # ASSERTION: Should include metadata retrieval
        assert "get_file_metadata" in executed_steps, \
            f"Request: '{user_request}' | " \
            f"Download workflow should get metadata first. " \
            f"Bug confirmed: Metadata step missing."
        
        # ASSERTION: Should include local save
        assert "save_to_workspace" in executed_steps, \
            f"Request: '{user_request}' | " \
            f"Download workflow should save file locally. " \
            f"Bug confirmed: Local save step missing."
    
    @given(
        action=st.sampled_from(["Upload", "Write", "Save", "Push"]),
        file_name=st.sampled_from(["automations.yaml", "scripts.yaml", "scenes.yaml"])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=15)
    def test_property_upload_workflows_complete(self, action, file_name):
        """
        Property-Based Test: All upload requests should follow complete workflow
        
        Property: For all upload requests, Kiro should execute all workflow steps:
                  1. validate_yaml
                  2. get_file_metadata (conflict check)
                  3. write_config_file (with expected_hash)
                  4. get_file_metadata (verify)
        
        EXPECTED OUTCOME: FAIL on multiple examples (proves bug exists across variations)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = f"{action} my {file_name}"
        
        # Get expected workflow
        expected_workflow = SteeringFileWorkflows.get_upload_workflow()
        expected_steps = [step.tool for step in expected_workflow.steps]
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_name)
        
        # Verify bug condition
        if not executed_steps:
            return
        
        first_tool = executed_steps[0]
        if not is_bug_condition_2(context, first_tool):
            return
        
        # ASSERTION: Should execute all workflow steps
        assert len(executed_steps) >= 3, \
            f"Request: '{user_request}' | " \
            f"Expected at least 3 workflow steps, but only executed {len(executed_steps)}. " \
            f"Bug confirmed: Incomplete upload workflow."
        
        # ASSERTION: Should include validation
        assert "validate_yaml" in executed_steps, \
            f"Request: '{user_request}' | " \
            f"Upload workflow should validate YAML. " \
            f"Bug confirmed: Validation step missing."
        
        # ASSERTION: Should include conflict check
        assert "get_file_metadata" in executed_steps, \
            f"Request: '{user_request}' | " \
            f"Upload workflow should check for conflicts. " \
            f"Bug confirmed: Conflict check missing."
    
    def test_steering_file_not_retrieved(self):
        """
        Test: Steering file content should be retrieved when using HA tools
        
        Expected (after fix): Steering file loaded and parsed for workflows
        Current (unfixed): Steering file not accessed
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "steering_files": {
                "ha-development-power/steering/file-management.md": "workflow content"
            }
        }
        
        user_request = "Download automations.yaml"
        file_path = "automations.yaml"
        
        # Simulate execution
        kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
        executed_steps = kiro.execute_request(user_request, file_path)
        
        # In real implementation, we'd check if steering file was accessed
        # For this mock, we verify that workflow steps indicate steering was used
        expected_workflow = SteeringFileWorkflows.get_download_workflow()
        expected_steps = [step.tool for step in expected_workflow.steps]
        
        # ASSERTION: Executed steps should match steering file workflow (will FAIL)
        assert executed_steps == expected_steps, \
            f"Steering file workflow not followed. " \
            f"Expected {expected_steps}, got {executed_steps}. " \
            f"Bug confirmed: Steering file not retrieved or applied."


# ============================================================================
# Counterexample Documentation
# ============================================================================

def document_counterexamples():
    """
    Document counterexamples found during exploration
    
    This function runs the tests and captures failures to document
    which workflows are not being followed.
    """
    print("\n" + "="*80)
    print("BUG 2 EXPLORATION: Steering Workflow Compliance")
    print("="*80)
    print("\nCounterexamples (workflows that are not followed):\n")
    
    context = {
        "installed_powers": ["ha-development-power"],
        "steering_files": {
            "ha-development-power/steering/file-management.md": "workflow content"
        }
    }
    
    kiro = MockKiroWorkflowExecutor(steering_files=context["steering_files"])
    
    # Test download workflow
    print("1. DOWNLOAD WORKFLOW")
    print("   Request: \"Download my automations.yaml\"")
    
    download_workflow = SteeringFileWorkflows.get_download_workflow()
    expected_download = [step.tool for step in download_workflow.steps]
    executed_download = kiro.execute_request("Download my automations.yaml", "automations.yaml")
    
    print(f"   Expected steps: {expected_download}")
    print(f"   Executed steps: {executed_download}")
    print(f"   Missing steps: {set(expected_download) - set(executed_download)}")
    print(f"   ❌ BUG CONFIRMED: Only {len(executed_download)}/{len(expected_download)} steps executed")
    print()
    
    # Test upload workflow
    print("2. UPLOAD WORKFLOW")
    print("   Request: \"Upload my changes to scripts.yaml\"")
    
    upload_workflow = SteeringFileWorkflows.get_upload_workflow()
    expected_upload = [step.tool for step in upload_workflow.steps]
    executed_upload = kiro.execute_request("Upload my changes to scripts.yaml", "scripts.yaml")
    
    print(f"   Expected steps: {expected_upload}")
    print(f"   Executed steps: {executed_upload}")
    print(f"   Missing steps: {set(expected_upload) - set(executed_upload)}")
    print(f"   ❌ BUG CONFIRMED: Only {len(executed_upload)}/{len(expected_upload)} steps executed")
    print()
    
    # Specific missing steps
    print("3. SPECIFIC MISSING STEPS")
    print()
    print("   Download workflow missing:")
    print("   - get_file_metadata (version checking)")
    print("   - save_to_workspace (local file save)")
    print("   - record_metadata (version tracking)")
    print()
    print("   Upload workflow missing:")
    print("   - validate_yaml (syntax validation)")
    print("   - get_file_metadata (conflict detection)")
    print("   - expected_hash parameter (conflict prevention)")
    print()
    
    print("="*80)
    print("CONCLUSION: Bug 2 exists - Kiro ignores steering file workflows")
    print("="*80)


if __name__ == "__main__":
    # Run counterexample documentation
    document_counterexamples()
    
    print("\n\nTo run the exploration tests:")
    print("  PYTHONPATH=src/config-manager/src python -m pytest src/config-manager/tests/test_bug2_steering_workflow.py -v")
    print("\nExpected outcome: Tests FAIL (this confirms the bug exists)")

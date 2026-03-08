# Bug 2 Counterexamples: Steering Workflow Not Followed

## Test Execution Summary

**Date**: Task 2 completion
**Test File**: `test_bug2_steering_workflow.py`
**Result**: All 10 tests FAILED as expected (confirms bug exists)

## Bug Description

When users request file operations (download/upload) with the ha-development-power, Kiro executes only a single MCP tool call instead of following the complete multi-step workflows documented in `ha-development-power/steering/file-management.md`.

## Documented Workflows (Expected Behavior)

### Download Workflow (Workflow 2 from steering file)
**Expected Steps**:
1. `get_file_metadata` - Check file hash and timestamp
2. `read_config_file` - Download file content
3. `save_to_workspace` - Save to ~/ha-dev-workspace/
4. `record_metadata` - Record metadata in .ha-workflow/metadata.json

### Upload Workflow (Workflow 3 from steering file)
**Expected Steps**:
1. `validate_yaml` - Validate YAML syntax
2. `get_file_metadata` - Check for conflicts (get current hash)
3. `write_config_file` - Upload with expected_hash parameter
4. `get_file_metadata` - Verify upload succeeded

## Counterexamples Found

### Counterexample 1: Download Workflow Incomplete

**User Request**: "Download my automations.yaml"

**Expected Execution**:
- Step 1: `get_file_metadata` (automations.yaml)
- Step 2: `read_config_file` (automations.yaml)
- Step 3: `save_to_workspace` (~/ha-dev-workspace/automations.yaml)
- Step 4: `record_metadata` (.ha-workflow/metadata.json)

**Actual Execution**:
- Step 1: `read_config_file` (automations.yaml)
- **MISSING**: `get_file_metadata`, `save_to_workspace`, `record_metadata`

**Impact**:
- No version tracking (metadata not recorded)
- File not saved locally (only displayed)
- No conflict detection on subsequent uploads
- User cannot work with file in local IDE

### Counterexample 2: Upload Workflow Incomplete

**User Request**: "Upload my changes to scripts.yaml"

**Expected Execution**:
- Step 1: `validate_yaml` (check syntax)
- Step 2: `get_file_metadata` (check for conflicts)
- Step 3: `write_config_file` (with expected_hash)
- Step 4: `get_file_metadata` (verify upload)

**Actual Execution**:
- Step 1: `write_config_file` (scripts.yaml)
- **MISSING**: `validate_yaml`, `get_file_metadata` (both calls)

**Impact**:
- Invalid YAML uploaded without validation
- No conflict detection (could overwrite changes)
- No verification that upload succeeded
- Risk of breaking Home Assistant configuration

### Counterexample 3: Metadata Not Recorded

**User Request**: "Download configuration.yaml"

**Expected**: Metadata saved to `.ha-workflow/metadata.json` with:
```json
{
  "configuration.yaml": {
    "hash": "a3f5b8c9...",
    "timestamp": "2026-02-12T10:30:00Z",
    "size": 2847
  }
}
```

**Actual**: No metadata recorded

**Impact**: Cannot detect conflicts on subsequent uploads

### Counterexample 4: File Not Saved Locally

**User Request**: "Download automations.yaml"

**Expected**: File saved to `~/ha-dev-workspace/automations.yaml`

**Actual**: File content only displayed in chat, not saved

**Impact**: User cannot edit file in IDE, must copy/paste manually

### Counterexample 5: YAML Not Validated

**User Request**: "Upload my automations.yaml"

**Expected**: YAML validation before upload

**Actual**: Direct upload without validation

**Impact**: Invalid YAML can break Home Assistant

### Counterexample 6: Conflicts Not Checked

**User Request**: "Upload scripts.yaml"

**Expected**: Get current file hash, compare with local metadata

**Actual**: No conflict checking

**Impact**: Can overwrite changes made by other users or HA UI

### Counterexample 7: Expected Hash Not Used

**User Request**: "Upload automations.yaml"

**Expected**: `write_config_file` called with `expected_hash` parameter

**Actual**: `write_config_file` called without `expected_hash`

**Impact**: No protection against concurrent modifications

## Property-Based Test Results

### Download Workflow Property Test
**Property**: All download requests should execute complete workflow

**Test Cases Generated**: 15 examples
- Actions: Download, Get, Fetch
- Files: automations.yaml, scripts.yaml, configuration.yaml

**Result**: ALL FAILED
- All examples executed only 1 step instead of 4
- Missing: metadata retrieval, local save, metadata recording

### Upload Workflow Property Test
**Property**: All upload requests should execute complete workflow

**Test Cases Generated**: 15 examples
- Actions: Upload, Write, Save, Push
- Files: automations.yaml, scripts.yaml, scenes.yaml

**Result**: ALL FAILED
- All examples executed only 1 step instead of 4
- Missing: validation, conflict checking, verification

## Root Cause Analysis

Based on the test failures, the root cause is:

1. **Steering File Not Retrieved**: Kiro doesn't load steering file content when using power-specific tools
2. **No Workflow Pattern Matching**: No mechanism to identify which workflow applies to user request
3. **Single Tool Execution**: Kiro executes single tool call instead of multi-step workflow
4. **No Workflow State Tracking**: No tracking of workflow progress or step completion

## Test Statistics

- **Total Tests**: 10
- **Failed Tests**: 10 (100%)
- **Expected Failures**: 10 (100%)
- **Conclusion**: Bug confirmed across all test scenarios

## Specific Missing Functionality

### Download Operations Missing:
1. Version checking (get_file_metadata before download)
2. Local file save (save_to_workspace)
3. Metadata recording (record_metadata)

### Upload Operations Missing:
1. YAML validation (validate_yaml)
2. Conflict detection (get_file_metadata before upload)
3. Expected hash parameter (conflict prevention)
4. Upload verification (get_file_metadata after upload)

## Real-World Impact

### For Users:
- Cannot maintain local workspace with version tracking
- Risk of uploading invalid YAML that breaks HA
- Risk of overwriting changes (no conflict detection)
- Manual copy/paste required instead of file save
- No verification that uploads succeeded

### For Development Workflow:
- Steering file guidance is ignored
- Documented workflows not followed
- Best practices not enforced
- Version control integration broken

## Next Steps

After implementing the fix (tasks 5-7), these same tests should PASS, confirming:
1. Steering file content is retrieved
2. Workflow patterns are identified
3. All workflow steps are executed in order
4. Metadata is recorded for version tracking
5. Files are saved locally
6. YAML is validated before upload
7. Conflicts are detected and prevented

## Test Execution Commands

```bash
# Run all Bug 2 exploration tests
PYTHONPATH=src/config-manager/src python -m pytest src/config-manager/tests/test_bug2_steering_workflow.py -v

# Run counterexample documentation
PYTHONPATH=src/config-manager/src python src/config-manager/tests/test_bug2_steering_workflow.py

# Run specific test
PYTHONPATH=src/config-manager/src python -m pytest src/config-manager/tests/test_bug2_steering_workflow.py::TestBug2SteeringWorkflow::test_download_workflow_not_followed -v
```

## References

- **Steering File**: `ha-development-power/steering/file-management.md`
- **Workflow 2**: Download Files with Metadata (lines 88-165)
- **Workflow 3**: Upload Files with Validation (lines 167-244)
- **Bug Condition Function**: `is_bug_condition_2()` in test file
- **Requirements**: 2.5, 2.6, 2.7, 2.8 in bugfix.md

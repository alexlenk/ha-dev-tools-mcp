# Preservation Property Tests - Documentation

## Overview

This document describes the preservation property tests that verify existing functionality remains unchanged after bug fixes. These tests establish the baseline behavior that must be preserved.

## Test Philosophy

**Observation-First Methodology:**
1. Observe behavior on UNFIXED code for non-buggy inputs
2. Write property-based tests capturing observed behavior patterns
3. Run tests on UNFIXED code
4. **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)

## Property Categories

### Property 1: Local File Operations in Non-HA Contexts

**Invariant**: For all non-HA file requests, local tools are used

**Test Coverage**:
- Non-HA files (package.json, README.md, tsconfig.json, etc.)
- Non-HA directories (src, tests, docs, node_modules, etc.)
- Files without HA-related keywords in request

**Expected Behavior**:
- `readFile` tool used for file reading
- `fileSearch` tool used for file searching
- `listDirectory` tool used for directory listing
- No MCP tool invocation for non-HA contexts

**Test Cases**:
```python
# Example: Reading package.json
user_request = "Read the package.json file"
expected_tool = "readFile"  # NOT read_config_file

# Example: Listing src directory
user_request = "List files in src"
expected_tool = "listDirectory"  # NOT list_config_files
```

### Property 2: Explicit Local Requests

**Invariant**: For all explicit local requests, local tools are used even in HA context

**Test Coverage**:
- Requests with "local" keyword
- Requests with "locally" keyword
- Requests with "on my machine" phrase
- Requests with "in this directory" phrase

**Expected Behavior**:
- Explicit local keywords override HA context detection
- Local tools used even for HA file names (configuration.yaml)
- User intent respected over automatic detection

**Test Cases**:
```python
# Example: Explicit local override
user_request = "Read the local configuration.yaml"
expected_tool = "readFile"  # NOT read_config_file (despite HA file name)

# Example: Various phrasings
user_request = "Show me the local copy of automations.yaml"
expected_tool = "readFile"  # Local override respected
```

### Property 3: Small File Retrievals

**Invariant**: For all small files (<10KB), single response without chunking

**Test Coverage**:
- Files from 1 byte to 10KB
- Response metadata structure
- No chunking overhead

**Expected Behavior**:
- Single response for files under 10KB
- No truncation metadata
- No pagination information
- No compression overhead
- `truncated: false` in metadata
- `has_more: false` in metadata

**Test Cases**:
```python
# Example: Small file response
file_size = 5000  # 5KB
expected_response = {
    "content": "file content",
    "metadata": {
        "size": 5000,
        "truncated": False,
        "has_more": False
    }
}
```

### Property 4: Non-File MCP Tools

**Invariant**: For all HA API tools, behavior unchanged

**Test Coverage**:
- `get_states` tool
- `render_template` tool
- `call_service` tool
- `get_logs` tool
- `validate_config` tool

**Expected Behavior**:
- Non-file tools work unchanged
- No impact from file handling bug fixes
- API operations continue normally
- Response formats unchanged

**Test Cases**:
```python
# Example: get_states tool
tool_name = "get_states"
assert not is_file_tool(tool_name)
assert tool_behavior_preserved(tool_name)

# Example: render_template tool
tool_name = "render_template"
assert not is_file_tool(tool_name)
assert tool_behavior_preserved(tool_name)
```

### Property 5: Error Handling

**Invariant**: For all error scenarios, clear error messages provided

**Test Coverage**:
- Network failures
- Authentication errors
- File not found errors
- Permission denied errors
- Invalid YAML errors
- Timeout errors

**Expected Behavior**:
- Clear, descriptive error messages
- Troubleshooting suggestions included
- No cryptic error codes
- Actionable guidance provided

**Test Cases**:
```python
# Example: Network failure
error_type = "network_failure"
error_message = "Network connection failed. Check your network connection and HA_URL."
assert is_clear_error_message(error_message)
assert includes_troubleshooting(error_message)

# Example: Authentication error
error_type = "authentication_error"
error_message = "Authentication failed. Verify HA_TOKEN is correct."
assert contains_suggestion(error_message, "Verify HA_TOKEN")
```

### Property 6: Power Installation Fallback

**Invariant**: When ha-development-power is not installed, local tools are used

**Test Coverage**:
- Power not installed scenarios
- Power installed but not configured scenarios
- Fallback to local tools

**Expected Behavior**:
- Local tools used when power not installed
- Local tools used when HA_URL/HA_TOKEN not configured
- Graceful degradation to local operations
- No errors when power unavailable

**Test Cases**:
```python
# Example: Power not installed
user_request = "Read configuration.yaml"
power_installed = False
expected_tool = "readFile"  # Fallback to local

# Example: Power not configured
user_request = "Read automations.yaml"
power_installed = True
ha_configured = False
expected_tool = "readFile"  # Fallback to local
```

## Running the Tests

### Prerequisites

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install pytest pytest-asyncio hypothesis
```

### Execute Tests

```bash
# Run all preservation property tests
PYTHONPATH=src python -m pytest tests/test_preservation_properties.py -v

# Run specific property test class
PYTHONPATH=src python -m pytest tests/test_preservation_properties.py::TestLocalFileOperationsPreservation -v

# Run with detailed output
PYTHONPATH=src python -m pytest tests/test_preservation_properties.py -v --tb=short
```

### Expected Results

**ALL TESTS SHOULD PASS on unfixed code**

This confirms the baseline behavior that must be preserved after bug fixes.

Example output:
```
tests/test_preservation_properties.py::TestLocalFileOperationsPreservation::test_non_ha_files_use_local_tools PASSED
tests/test_preservation_properties.py::TestLocalFileOperationsPreservation::test_non_ha_directories_use_local_tools PASSED
tests/test_preservation_properties.py::TestExplicitLocalRequestsPreservation::test_explicit_local_overrides_ha_context PASSED
tests/test_preservation_properties.py::TestExplicitLocalRequestsPreservation::test_various_explicit_local_phrasings PASSED
tests/test_preservation_properties.py::TestSmallFileRetrievalPreservation::test_small_files_single_response PASSED
tests/test_preservation_properties.py::TestSmallFileRetrievalPreservation::test_small_files_no_truncation_metadata PASSED
tests/test_preservation_properties.py::TestNonFileMCPToolsPreservation::test_non_file_tools_unchanged PASSED
tests/test_preservation_properties.py::TestNonFileMCPToolsPreservation::test_ha_api_operations_unchanged PASSED
tests/test_preservation_properties.py::TestErrorHandlingPreservation::test_error_messages_remain_clear PASSED
tests/test_preservation_properties.py::TestErrorHandlingPreservation::test_error_messages_include_suggestions PASSED
tests/test_preservation_properties.py::TestPowerInstallationFallback::test_fallback_to_local_when_power_not_installed PASSED
tests/test_preservation_properties.py::TestPowerInstallationFallback::test_fallback_to_local_when_not_configured PASSED
tests/test_preservation_properties.py::TestCombinedPreservationProperties::test_combined_preservation_scenarios PASSED

========================= 13 passed in 2.45s =========================
```

## Property-Based Testing Benefits

**Why use property-based testing for preservation?**

1. **Comprehensive Coverage**: Generates many test cases automatically across the input domain
2. **Edge Case Detection**: Catches edge cases that manual unit tests might miss
3. **Strong Guarantees**: Provides stronger guarantees that behavior is unchanged for all non-buggy inputs
4. **Regression Prevention**: Ensures fixes don't break existing functionality

**Hypothesis Configuration**:
- Default: 100 iterations per test
- Suppressed health checks: `function_scoped_fixture` (for pytest fixtures)
- Strategies: Sampled from realistic input values

## Validation Criteria

For each property test to be considered valid:

1. **Test passes on unfixed code** - Confirms baseline behavior
2. **Test covers realistic scenarios** - Uses actual file names, error types, etc.
3. **Test is deterministic** - Same inputs produce same results
4. **Test is independent** - No dependencies on other tests
5. **Test is clear** - Purpose and expected behavior documented

## Requirements Mapping

These tests validate the following requirements:

- **3.1**: Local file operations in non-HA contexts unchanged
- **3.2**: Explicit local requests honored
- **3.3**: Small file handling unchanged
- **3.4**: Error handling unchanged
- **3.5**: Non-file MCP tools unchanged
- **3.6**: HA API operations unchanged
- **3.7**: Steering guidance for non-file workflows unchanged
- **3.8**: Log pagination unchanged

## Next Steps

After these tests pass on unfixed code:

1. Implement bug fixes (Tasks 5-7)
2. Re-run preservation tests on fixed code
3. Verify all tests still pass (no regressions)
4. Document any intentional behavior changes

## Troubleshooting

### Tests Fail on Unfixed Code

**Problem**: Preservation tests should pass on unfixed code, but they're failing.

**Possible Causes**:
1. Test expectations don't match actual baseline behavior
2. Test logic has bugs
3. Environment setup issues

**Solutions**:
1. Review actual system behavior for the test scenario
2. Update test expectations to match observed behavior
3. Verify test environment is correct

### Hypothesis Errors

**Problem**: `FailedHealthCheck: function_scoped_fixture`

**Solution**: Add `@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])`

**Problem**: `InvalidArgument: Hypothesis doesn't know how to run async test functions`

**Solution**: Keep property tests synchronous, use `asyncio.run()` if needed

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Guide](https://increment.com/testing/in-praise-of-property-based-testing/)
- [Test Troubleshooting Guide](../../.kiro/steering/test-troubleshooting-guide.md)

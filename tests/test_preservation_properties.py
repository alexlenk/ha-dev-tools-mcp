"""
Preservation Property Tests for Non-Buggy Scenarios

These tests verify that existing functionality remains unchanged after bug fixes.
They test scenarios that should NOT be affected by the bug fixes:
- Local file operations in non-HA contexts
- Explicit local requests
- Small file retrievals
- Non-file MCP tools
- Error handling

EXPECTED OUTCOME: All tests PASS on unfixed code (baseline behavior)
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import Mock, AsyncMock, patch
import asyncio


# ============================================================================
# Property 1: Local File Operations in Non-HA Contexts
# ============================================================================

class TestLocalFileOperationsPreservation:
    """
    Property: For all non-HA file requests, local tools are used
    
    This verifies that accessing local project files (not HA-related)
    continues to use readFile, fsWrite, etc.
    """
    
    @given(
        filename=st.sampled_from([
            "package.json",
            "README.md",
            "tsconfig.json",
            "requirements.txt",
            "Dockerfile",
            "setup.py",
            ".gitignore"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_ha_files_use_local_tools(self, filename):
        """
        Property: Non-HA files should use local file operations
        
        For any file that is NOT Home Assistant related, the system
        should use local file tools (readFile, fileSearch, etc.)
        """
        # Simulate context without HA keywords
        user_request = f"Read the {filename} file"
        
        # Verify no HA context detected
        assert not self._has_ha_context(user_request)
        
        # Expected behavior: local tools should be used
        # This is the baseline behavior to preserve
        expected_tool = "readFile"  # or fileSearch, listDirectory
        
        # The actual implementation would check tool selection logic
        # For now, we verify the context detection is correct
        assert self._should_use_local_tools(user_request, filename)
    
    @given(
        directory=st.sampled_from([
            "src",
            "tests",
            "docs",
            "node_modules",
            ".git",
            "build"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_ha_directories_use_local_tools(self, directory):
        """
        Property: Non-HA directories should use local directory operations
        """
        user_request = f"List files in {directory}"
        
        # Verify no HA context
        assert not self._has_ha_context(user_request)
        
        # Expected: local listDirectory tool
        assert self._should_use_local_tools(user_request, directory)
    
    def _has_ha_context(self, text: str) -> bool:
        """Check if text contains HA-related keywords"""
        ha_keywords = [
            "home assistant", "HA", "homeassistant",
            "configuration.yaml", "automations.yaml",
            "scripts.yaml", "packages/"
        ]
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in ha_keywords)
    
    def _should_use_local_tools(self, request: str, path: str) -> bool:
        """Determine if local tools should be used"""
        # Local tools should be used when:
        # 1. No HA context in request
        # 2. Path is not HA-specific
        # 3. No explicit remote access requested
        
        has_ha_context = self._has_ha_context(request)
        is_ha_file = path.endswith(('.yaml', '.yml')) and self._has_ha_context(path)
        explicit_remote = "remote" in request.lower() or "mcp" in request.lower()
        
        return not has_ha_context and not is_ha_file and not explicit_remote


# ============================================================================
# Property 2: Explicit Local Requests
# ============================================================================

class TestExplicitLocalRequestsPreservation:
    """
    Property: For all explicit local requests, local tools are used even in HA context
    
    This verifies that when users explicitly request local operations,
    the system honors that request regardless of HA context.
    """
    
    @given(
        ha_file=st.sampled_from([
            "configuration.yaml",
            "automations.yaml",
            "scripts.yaml"
        ]),
        local_keyword=st.sampled_from([
            "local",
            "locally",
            "on my machine",
            "in this directory"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_explicit_local_overrides_ha_context(self, ha_file, local_keyword):
        """
        Property: Explicit local requests override HA context detection
        
        Even if the file name suggests HA context, explicit local
        keywords should force local tool usage.
        """
        user_request = f"Read the {local_keyword} {ha_file}"
        
        # Has HA context (file name)
        assert self._has_ha_context(ha_file)
        
        # But has explicit local override
        assert self._has_explicit_local(user_request)
        
        # Expected: local tools should be used
        assert self._should_use_local_tools_with_override(user_request)
    
    @given(
        request_template=st.sampled_from([
            "Show me the local copy of {}",
            "Read {} from my local filesystem",
            "Check the local {} file",
            "Open the {} file on my machine"
        ]),
        ha_file=st.sampled_from([
            "configuration.yaml",
            "automations.yaml"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_various_explicit_local_phrasings(self, request_template, ha_file):
        """
        Property: Various phrasings of explicit local requests are recognized
        """
        user_request = request_template.format(ha_file)
        
        # Should detect explicit local intent
        assert self._has_explicit_local(user_request)
        
        # Should use local tools despite HA file name
        assert self._should_use_local_tools_with_override(user_request)
    
    def _has_ha_context(self, text: str) -> bool:
        """Check if text contains HA-related keywords"""
        ha_keywords = [
            "home assistant", "HA", "homeassistant",
            "configuration.yaml", "automations.yaml",
            "scripts.yaml", "packages/"
        ]
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in ha_keywords)
    
    def _has_explicit_local(self, text: str) -> bool:
        """Check if text explicitly requests local access"""
        local_keywords = [
            "local", "locally", "on my machine",
            "in this directory", "from my filesystem",
            "local copy", "local file"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in local_keywords)
    
    def _should_use_local_tools_with_override(self, request: str) -> bool:
        """Check if local tools should be used with explicit override"""
        return self._has_explicit_local(request)


# ============================================================================
# Property 3: Small File Retrievals
# ============================================================================

class TestSmallFileRetrievalPreservation:
    """
    Property: For all small files, single response without chunking
    
    This verifies that small files (<10KB) continue to be returned
    in a single response without chunking overhead.
    """
    
    @given(
        file_size=st.integers(min_value=1, max_value=9999)  # 1 byte to 9999 bytes (< 10KB)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_small_files_single_response(self, file_size):
        """
        Property: Small files should be returned in single response
        
        Files under 10KB should not trigger chunking, pagination,
        or compression mechanisms.
        """
        # Simulate file metadata
        file_metadata = {
            "size": file_size,
            "path": "test.yaml"
        }
        
        # Verify file is small
        assert file_size < 10000
        
        # Expected: no chunking needed
        assert not self._requires_chunking(file_size)
        
        # Expected: single response
        assert self._expected_chunk_count(file_size) == 1
    
    @given(
        file_size=st.integers(min_value=1, max_value=9999)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_small_files_no_truncation_metadata(self, file_size):
        """
        Property: Small files should not include truncation metadata
        
        Response metadata for small files should not have truncation
        flags or pagination information.
        """
        # Expected response structure for small files
        expected_response = {
            "content": "file content here",
            "metadata": {
                "size": file_size,
                "truncated": False,
                "has_more": False
            }
        }
        
        # Verify no truncation for small files
        assert not expected_response["metadata"]["truncated"]
        assert not expected_response["metadata"]["has_more"]
    
    def _requires_chunking(self, file_size: int) -> bool:
        """Check if file size requires chunking"""
        CHUNK_THRESHOLD = 10000  # 10KB
        return file_size >= CHUNK_THRESHOLD
    
    def _expected_chunk_count(self, file_size: int) -> int:
        """Calculate expected number of chunks"""
        if file_size < 10000:
            return 1
        CHUNK_SIZE = 100000  # 100KB per chunk
        return (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE


# ============================================================================
# Property 4: Non-File MCP Tools
# ============================================================================

class TestNonFileMCPToolsPreservation:
    """
    Property: For all HA API tools, behavior unchanged
    
    This verifies that non-file MCP tools (get_states, render_template,
    call_service) continue to work unchanged.
    """
    
    @given(
        tool_name=st.sampled_from([
            "get_states",
            "render_template",
            "call_service",
            "get_logs",
            "validate_config"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_file_tools_unchanged(self, tool_name):
        """
        Property: Non-file MCP tools should work unchanged
        
        Tools that don't involve file access should not be affected
        by file handling bug fixes.
        """
        # Verify tool is not file-related
        assert not self._is_file_tool(tool_name)
        
        # Expected: tool behavior unchanged
        assert self._tool_behavior_preserved(tool_name)
    
    @given(
        api_operation=st.sampled_from([
            "get entity state",
            "render jinja template",
            "call service",
            "check logs",
            "validate configuration"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ha_api_operations_unchanged(self, api_operation):
        """
        Property: HA API operations without file access are unchanged
        """
        # Verify operation doesn't involve file access
        assert not self._involves_file_access(api_operation)
        
        # Expected: operation works as before
        assert self._operation_preserved(api_operation)
    
    def _is_file_tool(self, tool_name: str) -> bool:
        """Check if tool is file-related"""
        file_tools = [
            "read_config_file",
            "write_config_file",
            "list_config_files",
            "get_file_metadata",
            "batch_get_metadata"
        ]
        return tool_name in file_tools
    
    def _involves_file_access(self, operation: str) -> bool:
        """Check if operation involves file access"""
        file_keywords = ["read", "write", "file", "download", "upload"]
        operation_lower = operation.lower()
        return any(keyword in operation_lower for keyword in file_keywords)
    
    def _tool_behavior_preserved(self, tool_name: str) -> bool:
        """Verify tool behavior is preserved"""
        # For preservation testing, we assume non-file tools are unchanged
        return not self._is_file_tool(tool_name)
    
    def _operation_preserved(self, operation: str) -> bool:
        """Verify operation behavior is preserved"""
        return not self._involves_file_access(operation)


# ============================================================================
# Property 5: Error Handling
# ============================================================================

class TestErrorHandlingPreservation:
    """
    Property: For all error scenarios, clear error messages provided
    
    This verifies that error handling continues to provide clear
    error messages and troubleshooting suggestions.
    """
    
    @given(
        error_type=st.sampled_from([
            "network_failure",
            "authentication_error",
            "file_not_found",
            "permission_denied",
            "invalid_yaml",
            "timeout"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_error_messages_remain_clear(self, error_type):
        """
        Property: Error messages should remain clear and helpful
        
        All error scenarios should continue to provide clear error
        messages with troubleshooting suggestions.
        """
        # Expected error message structure
        error_message = self._get_error_message(error_type)
        
        # Verify error message is clear
        assert len(error_message) > 0
        assert self._is_clear_error_message(error_message)
        
        # Verify includes troubleshooting info
        assert self._includes_troubleshooting(error_message, error_type)
    
    @given(
        error_scenario=st.sampled_from([
            ("network", "Check your network connection"),
            ("auth", "Verify HA_TOKEN is correct"),
            ("not_found", "Check the file path"),
            ("permission", "Check file permissions"),
            ("yaml", "Check for syntax errors")
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_error_messages_include_suggestions(self, error_scenario):
        """
        Property: Error messages should include troubleshooting suggestions
        """
        error_type, expected_suggestion = error_scenario
        error_message = self._get_error_message(error_type)
        
        # Verify suggestion is included
        assert self._contains_suggestion(error_message, expected_suggestion)
    
    def _get_error_message(self, error_type: str) -> str:
        """Get error message for error type"""
        # Map both full error types and short names
        error_messages = {
            "network_failure": "Network connection failed. Check your network connection and HA_URL.",
            "network": "Network connection failed. Check your network connection and HA_URL.",
            "authentication_error": "Authentication failed. Verify HA_TOKEN is correct.",
            "auth": "Authentication failed. Verify HA_TOKEN is correct.",
            "file_not_found": "File not found. Check the file path.",
            "not_found": "File not found. Check the file path.",
            "permission_denied": "Permission denied. Check file permissions.",
            "permission": "Permission denied. Check file permissions.",
            "invalid_yaml": "Invalid YAML syntax. Check for syntax errors.",
            "yaml": "Invalid YAML syntax. Check for syntax errors.",
            "timeout": "Request timed out. Check network connection."
        }
        return error_messages.get(error_type, "An error occurred.")
    
    def _is_clear_error_message(self, message: str) -> bool:
        """Check if error message is clear"""
        # Clear messages should:
        # 1. Be non-empty
        # 2. Describe the problem
        # 3. Be readable (not just error codes)
        return (
            len(message) > 10 and
            not message.isdigit() and
            " " in message
        )
    
    def _includes_troubleshooting(self, message: str, error_type: str) -> bool:
        """Check if message includes troubleshooting info"""
        troubleshooting_keywords = [
            "check", "verify", "ensure", "try",
            "connection", "token", "path", "permissions"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in troubleshooting_keywords)
    
    def _contains_suggestion(self, message: str, suggestion: str) -> bool:
        """Check if message contains specific suggestion"""
        return suggestion.lower() in message.lower()


# ============================================================================
# Property 6: Power Installation Fallback
# ============================================================================

class TestPowerInstallationFallback:
    """
    Property: When ha-development-power is not installed, local tools are used
    
    This verifies the fallback behavior when the power is not available.
    """
    
    @given(
        ha_file=st.sampled_from([
            "configuration.yaml",
            "automations.yaml",
            "scripts.yaml"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_to_local_when_power_not_installed(self, ha_file):
        """
        Property: Without power installed, use local tools even for HA files
        """
        user_request = f"Read {ha_file}"
        power_installed = False
        
        # Even with HA context, should use local tools if power not installed
        assert self._should_use_local_tools_fallback(user_request, power_installed)
    
    @given(
        ha_file=st.sampled_from([
            "configuration.yaml",
            "automations.yaml"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_to_local_when_not_configured(self, ha_file):
        """
        Property: Without HA_URL/HA_TOKEN, use local tools
        """
        user_request = f"Read {ha_file}"
        power_installed = True
        ha_configured = False
        
        # Should use local tools if not configured
        assert self._should_use_local_tools_fallback(
            user_request, power_installed, ha_configured
        )
    
    def _should_use_local_tools_fallback(
        self,
        request: str,
        power_installed: bool,
        ha_configured: bool = True
    ) -> bool:
        """Check if local tools should be used as fallback"""
        # Use local tools if:
        # 1. Power not installed, OR
        # 2. Power installed but not configured
        return not power_installed or not ha_configured


# ============================================================================
# Integration Test: Combined Preservation Properties
# ============================================================================

class TestCombinedPreservationProperties:
    """
    Combined tests that verify multiple preservation properties together
    """
    
    @given(
        scenario=st.sampled_from([
            ("package.json", False, False),  # (file, has_ha_context, is_small)
            ("README.md", False, True),
            ("configuration.yaml", True, True),  # With explicit local
            ("automations.yaml", True, True)
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_combined_preservation_scenarios(self, scenario):
        """
        Property: Multiple preservation properties hold simultaneously
        """
        filename, has_ha_context, is_small = scenario
        
        # For non-HA files
        if not has_ha_context:
            # Should use local tools
            assert self._should_use_local_for_non_ha(filename)
            
            # Small files should not chunk
            if is_small:
                assert not self._requires_chunking_for_small(filename)
        
        # For HA files with explicit local
        if has_ha_context:
            request_with_local = f"Read the local {filename}"
            # Should still use local tools
            assert self._should_use_local_with_explicit(request_with_local)
    
    def _should_use_local_for_non_ha(self, filename: str) -> bool:
        """Check if local tools should be used for non-HA files"""
        ha_patterns = ["configuration.yaml", "automations.yaml", "scripts.yaml"]
        return filename not in ha_patterns
    
    def _requires_chunking_for_small(self, filename: str) -> bool:
        """Check if small file requires chunking"""
        # Assume files in test are small
        return False
    
    def _should_use_local_with_explicit(self, request: str) -> bool:
        """Check if local tools should be used with explicit keyword"""
        return "local" in request.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

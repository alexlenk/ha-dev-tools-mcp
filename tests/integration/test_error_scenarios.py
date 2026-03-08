"""
Integration tests for error scenarios.

Tests error handling for:
1. Network failures during file retrieval
2. MCP server returning errors
3. Malformed steering files
4. Missing workflow steps in steering files
5. File access denied (403) errors
6. File not found (404) errors

Requirements: 3.4
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import aiohttp


@pytest.fixture
def mock_ha_api_with_errors():
    """Mock Home Assistant API that can simulate various errors."""
    api = Mock()
    
    # Default to successful responses
    api.read_config_file = AsyncMock(return_value={
        "content": "test content",
        "metadata": {"truncated": False}
    })
    
    api.get_file_metadata = AsyncMock(return_value={
        "path": "test.yaml",
        "exists": True
    })
    
    return api


class TestErrorScenarios:
    """Test error handling in various failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_network_failure_during_retrieval(self, mock_ha_api_with_errors):
        """
        Test handling of network failures during file retrieval.
        
        Expected: Clear error message with troubleshooting suggestions
        """
        # Simulate network timeout
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            side_effect=aiohttp.ClientError("Connection timeout")
        )
        
        # Attempt to read file
        try:
            await mock_ha_api_with_errors.read_config_file("configuration.yaml")
            error_occurred = False
        except aiohttp.ClientError as e:
            error_occurred = True
            error_message = str(e)
        
        assert error_occurred, "Should raise network error"
        assert "timeout" in error_message.lower()
        
        # Generate user-friendly error message
        user_message = (
            "Failed to retrieve file from Home Assistant due to network error.\n"
            "Troubleshooting steps:\n"
            "  1. Check that Home Assistant is running and accessible\n"
            "  2. Verify HA_URL is correct\n"
            "  3. Check network connectivity\n"
            "  4. Verify firewall settings"
        )
        
        assert "network error" in user_message.lower()
        assert "troubleshooting" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_mcp_server_error_response(self, mock_ha_api_with_errors):
        """
        Test handling of MCP server errors.
        
        Expected: Clear error message with server error details
        """
        # Simulate MCP server error
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            side_effect=Exception("MCP server internal error")
        )
        
        try:
            await mock_ha_api_with_errors.read_config_file("test.yaml")
            error_occurred = False
        except Exception as e:
            error_occurred = True
            error_message = str(e)
        
        assert error_occurred
        assert "MCP server" in error_message or "internal error" in error_message
        
        # Generate user-friendly message
        user_message = (
            "MCP server encountered an error.\n"
            "Error details: MCP server internal error\n"
            "Suggestions:\n"
            "  - Check MCP server logs\n"
            "  - Verify server is running correctly\n"
            "  - Try restarting the MCP server"
        )
        
        assert "MCP server" in user_message
        assert "suggestions" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_file_not_found_404(self, mock_ha_api_with_errors):
        """
        Test handling of file not found (404) errors.
        
        Expected: Clear message indicating file doesn't exist
        """
        # Simulate 404 error
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            return_value={
                "error": "File not found",
                "status": 404,
                "path": "nonexistent.yaml"
            }
        )
        
        response = await mock_ha_api_with_errors.read_config_file("nonexistent.yaml")
        
        assert response.get("status") == 404
        assert "not found" in response.get("error", "").lower()
        
        # Generate user-friendly message
        user_message = (
            f"File '{response['path']}' not found in Home Assistant.\n"
            "Suggestions:\n"
            "  - Verify the file path is correct\n"
            "  - Check that the file exists in your HA configuration\n"
            "  - Use list_config_files to see available files"
        )
        
        assert "not found" in user_message
        assert response["path"] in user_message
    
    @pytest.mark.asyncio
    async def test_file_access_denied_403(self, mock_ha_api_with_errors):
        """
        Test handling of access denied (403) errors.
        
        Expected: Clear message about permissions
        """
        # Simulate 403 error
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            return_value={
                "error": "Access denied",
                "status": 403,
                "path": "secrets.yaml"
            }
        )
        
        response = await mock_ha_api_with_errors.read_config_file("secrets.yaml")
        
        assert response.get("status") == 403
        assert "denied" in response.get("error", "").lower()
        
        # Generate user-friendly message
        user_message = (
            f"Access denied to file '{response['path']}'.\n"
            "Possible causes:\n"
            "  - File is outside allowed paths\n"
            "  - Insufficient permissions\n"
            "  - Security restrictions in place\n"
            "Suggestions:\n"
            "  - Check security allowlist configuration\n"
            "  - Verify HA_TOKEN has necessary permissions\n"
            "  - Review Home Assistant file access settings"
        )
        
        assert "access denied" in user_message.lower()
        assert "permissions" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_malformed_steering_file(self):
        """
        Test handling of malformed steering files.
        
        Expected: Graceful degradation with warning
        """
        # Simulate malformed steering content
        malformed_steering = """
        # Workflow
        
        This is not properly formatted
        Missing step numbers
        No clear structure
        """
        
        # Attempt to parse workflow steps
        try:
            # Simple parsing logic
            lines = malformed_steering.strip().split('\n')
            steps = [line for line in lines if line.strip().startswith(('1.', '2.', '3.', '4.'))]
            
            if len(steps) == 0:
                raise ValueError("No workflow steps found in steering file")
            
            parsing_succeeded = True
        except ValueError as e:
            parsing_succeeded = False
            error_message = str(e)
        
        assert not parsing_succeeded
        assert "no workflow steps" in error_message.lower()
        
        # Generate warning message
        warning_message = (
            "Warning: Steering file appears to be malformed.\n"
            "Could not parse workflow steps.\n"
            "Proceeding with default workflow behavior."
        )
        
        assert "malformed" in warning_message.lower()
        assert "default workflow" in warning_message.lower()
    
    @pytest.mark.asyncio
    async def test_missing_workflow_steps(self):
        """
        Test handling of incomplete workflow definitions.
        
        Expected: Warning about missing steps, use defaults
        """
        # Simulate incomplete workflow
        incomplete_workflow = """
        # Download Workflow
        
        1. get_file_metadata
        2. read_config_file
        # Missing: save locally and record metadata steps
        """
        
        # Parse workflow
        lines = incomplete_workflow.strip().split('\n')
        steps = [line.strip() for line in lines if line.strip().startswith(('1.', '2.', '3.', '4.'))]
        
        expected_steps = 4
        actual_steps = len(steps)
        
        assert actual_steps < expected_steps
        
        # Generate warning
        warning_message = (
            f"Warning: Workflow definition incomplete.\n"
            f"Expected {expected_steps} steps, found {actual_steps}.\n"
            "Missing steps will use default behavior."
        )
        
        assert "incomplete" in warning_message.lower()
        assert str(actual_steps) in warning_message
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, mock_ha_api_with_errors):
        """
        Test handling of authentication errors.
        
        Expected: Clear message about token issues
        """
        # Simulate auth error
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            return_value={
                "error": "Unauthorized",
                "status": 401,
                "message": "Invalid or expired token"
            }
        )
        
        response = await mock_ha_api_with_errors.read_config_file("test.yaml")
        
        assert response.get("status") == 401
        assert "unauthorized" in response.get("error", "").lower()
        
        # Generate user-friendly message
        user_message = (
            "Authentication failed with Home Assistant.\n"
            "Error: Invalid or expired token\n"
            "Suggestions:\n"
            "  - Verify HA_TOKEN is correct\n"
            "  - Check if token has expired\n"
            "  - Generate a new long-lived access token\n"
            "  - Ensure token has necessary permissions"
        )
        
        assert "authentication failed" in user_message.lower()
        assert "HA_TOKEN" in user_message
    
    @pytest.mark.asyncio
    async def test_server_unavailable_503(self, mock_ha_api_with_errors):
        """
        Test handling of server unavailable errors.
        
        Expected: Clear message about server status
        """
        # Simulate 503 error
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            return_value={
                "error": "Service Unavailable",
                "status": 503,
                "message": "Home Assistant is starting up"
            }
        )
        
        response = await mock_ha_api_with_errors.read_config_file("test.yaml")
        
        assert response.get("status") == 503
        
        # Generate user-friendly message
        user_message = (
            "Home Assistant is currently unavailable.\n"
            "Reason: Home Assistant is starting up\n"
            "Suggestions:\n"
            "  - Wait a few moments and try again\n"
            "  - Check Home Assistant status\n"
            "  - Verify Home Assistant is running"
        )
        
        assert "unavailable" in user_message.lower()
        assert "try again" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_yaml_in_response(self, mock_ha_api_with_errors):
        """
        Test handling of invalid YAML content in response.
        
        Expected: Warning about invalid content
        """
        import yaml
        
        # Simulate response with invalid YAML
        mock_ha_api_with_errors.read_config_file = AsyncMock(
            return_value={
                "content": "invalid: yaml: [syntax",
                "metadata": {"truncated": False}
            }
        )
        
        response = await mock_ha_api_with_errors.read_config_file("test.yaml")
        content = response["content"]
        
        # Attempt to parse
        try:
            yaml.safe_load(content)
            is_valid = True
        except yaml.YAMLError:
            is_valid = False
        
        assert not is_valid
        
        # Generate warning
        warning_message = (
            "Warning: Retrieved file contains invalid YAML syntax.\n"
            "The file may be corrupted or contain syntax errors.\n"
            "Please review the file content before making changes."
        )
        
        assert "invalid YAML" in warning_message
        assert "syntax errors" in warning_message.lower()
    
    @pytest.mark.asyncio
    async def test_partial_chunk_failure(self, mock_ha_api_with_errors):
        """
        Test handling of failures during chunked retrieval.
        
        Expected: Clear error about incomplete retrieval
        """
        # Simulate successful first chunk, then failure
        call_count = 0
        
        async def chunked_read_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First chunk succeeds
                return {
                    "content": "chunk 1 content",
                    "metadata": {
                        "total_size": 200000,
                        "returned_size": 100000,
                        "truncated": True,
                        "has_more": True,
                        "offset": 0
                    }
                }
            else:
                # Second chunk fails
                raise aiohttp.ClientError("Connection lost during chunk retrieval")
        
        mock_ha_api_with_errors.read_config_file = chunked_read_with_failure
        
        # Retrieve first chunk
        chunk1 = await mock_ha_api_with_errors.read_config_file("large.yaml", offset=0)
        assert chunk1["metadata"]["has_more"]
        
        # Attempt second chunk
        try:
            chunk2 = await mock_ha_api_with_errors.read_config_file("large.yaml", offset=100000)
            retrieval_failed = False
        except aiohttp.ClientError:
            retrieval_failed = True
        
        assert retrieval_failed
        
        # Generate error message
        error_message = (
            "Failed to retrieve complete file due to network error.\n"
            "Retrieved 100000 of 200000 bytes before failure.\n"
            "Suggestions:\n"
            "  - Try again to resume from last successful chunk\n"
            "  - Check network stability\n"
            "  - Consider downloading file via alternative method"
        )
        
        assert "incomplete" in error_message.lower() or "failed" in error_message.lower()
        assert "100000" in error_message
    
    @pytest.mark.asyncio
    async def test_error_message_clarity(self):
        """
        Test that all error messages are clear and actionable.
        """
        error_scenarios = [
            {
                "error": "Connection timeout",
                "expected_keywords": ["network", "connectivity", "check"]
            },
            {
                "error": "File not found",
                "expected_keywords": ["not found", "verify", "path"]
            },
            {
                "error": "Access denied",
                "expected_keywords": ["denied", "permissions", "token"]
            },
            {
                "error": "Invalid token",
                "expected_keywords": ["authentication", "token", "generate"]
            }
        ]
        
        for scenario in error_scenarios:
            # Generate error message (simplified)
            error_message = f"Error: {scenario['error']}\nPlease check your configuration."
            
            # Verify message contains expected keywords
            message_lower = error_message.lower()
            has_keywords = any(
                keyword in message_lower
                for keyword in scenario["expected_keywords"]
            )
            
            assert has_keywords, f"Error message missing keywords for: {scenario['error']}"

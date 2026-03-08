"""Property-based tests for MCP Server logging behavior.

These tests validate universal properties that should hold for logging operations.
"""

import logging
import pytest
from hypothesis import given, strategies as st, settings
from aioresponses import aioresponses
from unittest.mock import Mock, patch
import json

from ha_config_manager.connection.api import HAAPIClient, HAAPIError


# Hypothesis strategies for generating test data
@st.composite
def tool_name_strategy(draw):
    """Generate valid tool names."""
    tools = [
        "list_config_files",
        "read_config_file",
        "get_logs",
        "get_states",
        "get_history",
        "call_service",
        "render_template",
        "get_config",
        "list_events",
        "list_services",
        "check_config"
    ]
    return draw(st.sampled_from(tools))


@st.composite
def access_token_strategy(draw):
    """Generate access tokens for testing."""
    # Generate various token formats
    return draw(st.text(min_size=10, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='.-_'
    )))


@st.composite
def error_status_code_strategy(draw):
    """Generate HTTP error status codes."""
    return draw(st.sampled_from([400, 401, 403, 404, 500, 502, 503, 504]))


class TestLoggingProperties:
    """Property-based tests for logging behavior."""
    
    @pytest.mark.asyncio
    @given(tool_name_strategy())
    @settings(max_examples=50, deadline=None)
    async def test_property_13_tool_call_logging(self, tool_name: str):
        """
        **Feature: ha-config-manager-mcp-server, Property 13: Tool Call Logging**
        
        For any tool call executed by the MCP server, a log entry should be created 
        containing the tool name.
        
        **Validates: Requirements 10.2**
        """
        # Import server module first
        import ha_config_manager.server as server_module
        
        # Create a mock logger to capture log calls
        with patch.object(server_module, 'logger') as mock_logger:
            # Set up mock API responses based on tool name
            with aioresponses() as mock:
                # Mock appropriate endpoint for each tool
                if tool_name == "list_config_files":
                    mock.get(
                        "http://test.local:8123/api/ha_config_manager/files",
                        status=200,
                        payload={"files": []}
                    )
                elif tool_name == "read_config_file":
                    mock.get(
                        "http://test.local:8123/api/ha_config_manager/files/test.yaml",
                        status=200,
                        body="test content"
                    )
                elif tool_name == "get_logs":
                    mock.get(
                        "http://test.local:8123/api/ha_config_manager/logs/core",
                        status=200,
                        payload={"logs": []}
                    )
                elif tool_name == "get_states":
                    mock.get(
                        "http://test.local:8123/api/states",
                        status=200,
                        payload=[]
                    )
                elif tool_name == "get_history":
                    mock.get(
                        "http://test.local:8123/api/history/period",
                        status=200,
                        payload=[]
                    )
                elif tool_name == "call_service":
                    mock.post(
                        "http://test.local:8123/api/services/test/service",
                        status=200,
                        payload=[]
                    )
                elif tool_name == "render_template":
                    mock.post(
                        "http://test.local:8123/api/template",
                        status=200,
                        body="rendered"
                    )
                elif tool_name == "get_config":
                    mock.get(
                        "http://test.local:8123/api/config",
                        status=200,
                        payload={"version": "2024.1.0"}
                    )
                elif tool_name == "list_events":
                    mock.get(
                        "http://test.local:8123/api/events",
                        status=200,
                        payload=[]
                    )
                elif tool_name == "list_services":
                    mock.get(
                        "http://test.local:8123/api/services",
                        status=200,
                        payload={}
                    )
                elif tool_name == "check_config":
                    mock.post(
                        "http://test.local:8123/api/config/core/check_config",
                        status=200,
                        payload={"result": "valid"}
                    )
                
                # Import and call the tool handler
                from ha_config_manager.server import handle_call_tool
                
                # Set up global api_client
                server_module.api_client = HAAPIClient("http://test.local:8123", "test_token")
                
                # Prepare arguments based on tool
                arguments = {}
                if tool_name == "read_config_file":
                    arguments = {"file_path": "test.yaml"}
                elif tool_name == "get_logs":
                    arguments = {"log_source": "core"}
                elif tool_name == "call_service":
                    arguments = {"domain": "test", "service": "service"}
                elif tool_name == "render_template":
                    arguments = {"template": "{{ 1 + 1 }}"}
                
                try:
                    # Call the tool
                    await handle_call_tool(tool_name, arguments)
                    
                    # Property: Logger should be called with INFO level containing tool name
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    
                    # Check that at least one log call contains the tool name
                    tool_logged = any(
                        tool_name in str(call) 
                        for call in info_calls
                    )
                    
                    assert tool_logged, f"Tool name '{tool_name}' should be logged"
                    
                except Exception:
                    # Even on error, tool should be logged
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    tool_logged = any(
                        tool_name in str(call) 
                        for call in info_calls
                    )
                    assert tool_logged, f"Tool name '{tool_name}' should be logged even on error"
                
                finally:
                    await server_module.api_client.close()
    
    @pytest.mark.asyncio
    @given(error_status_code_strategy())
    @settings(max_examples=50, deadline=None)
    async def test_property_14_error_logging(self, status_code: int):
        """
        **Feature: ha-config-manager-mcp-server, Property 14: Error Logging**
        
        For any API request that fails, a log entry should be created at ERROR level 
        containing error details but excluding sensitive data.
        
        **Validates: Requirements 10.3**
        """
        # Import server module first
        import ha_config_manager.server as server_module
        
        # Create a mock logger to capture log calls
        with patch.object(server_module, 'logger') as mock_logger:
            with aioresponses() as mock:
                # Mock error response
                mock.get(
                    "http://test.local:8123/api/ha_config_manager/files/test.yaml",
                    status=status_code,
                    body=json.dumps({"message": "Test error"})
                )
                
                # Import and call the tool handler
                from ha_config_manager.server import handle_call_tool
                
                # Set up global api_client
                server_module.api_client = HAAPIClient("http://test.local:8123", "test_token")
                
                try:
                    # Call the tool (should fail)
                    await handle_call_tool("read_config_file", {"file_path": "test.yaml"})
                except Exception:
                    pass  # Expected to fail
                
                # Property: Logger should be called with ERROR level
                error_calls = [call for call in mock_logger.error.call_args_list]
                
                assert len(error_calls) > 0, "Error should be logged at ERROR level"
                
                # Property: Error log should contain error details
                error_logged = any(
                    "error" in str(call).lower() or "API error" in str(call)
                    for call in error_calls
                )
                
                assert error_logged, "Error details should be logged"
                
                await server_module.api_client.close()
    
    @pytest.mark.asyncio
    @given(st.booleans())
    @settings(max_examples=50, deadline=None)
    async def test_property_15_log_level_usage(self, is_success: bool):
        """
        **Feature: ha-config-manager-mcp-server, Property 15: Log Level Usage**
        
        For any log entry created by the MCP server, it should use INFO level for 
        successful operations and ERROR level for failures.
        
        **Validates: Requirements 10.4**
        """
        # Import server module first
        import ha_config_manager.server as server_module
        
        # Create a mock logger to capture log calls
        with patch.object(server_module, 'logger') as mock_logger:
            with aioresponses() as mock:
                if is_success:
                    # Mock successful response
                    mock.get(
                        "http://test.local:8123/api/ha_config_manager/files",
                        status=200,
                        payload={"files": []}
                    )
                else:
                    # Mock error response
                    mock.get(
                        "http://test.local:8123/api/ha_config_manager/files",
                        status=500,
                        body=json.dumps({"message": "Server error"})
                    )
                
                # Import and call the tool handler
                from ha_config_manager.server import handle_call_tool
                
                # Set up global api_client
                server_module.api_client = HAAPIClient("http://test.local:8123", "test_token")
                
                try:
                    # Call the tool
                    await handle_call_tool("list_config_files", {})
                except Exception:
                    pass  # Expected to fail on error case
                
                if is_success:
                    # Property: Successful operations should use INFO level
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    assert len(info_calls) > 0, "Successful operations should log at INFO level"
                else:
                    # Property: Failed operations should use ERROR level
                    error_calls = [call for call in mock_logger.error.call_args_list]
                    assert len(error_calls) > 0, "Failed operations should log at ERROR level"
                
                await server_module.api_client.close()
    
    @pytest.mark.asyncio
    @given(access_token_strategy())
    @settings(max_examples=50, deadline=None)
    async def test_property_2_token_confidentiality(self, access_token: str):
        """
        **Feature: ha-config-manager-mcp-server, Property 2: Token Confidentiality**
        
        For any log message or error message produced by the MCP server, the access 
        token should not be present in the message text.
        
        **Validates: Requirements 6.4, 10.5**
        """
        # Import server module first
        import ha_config_manager.server as server_module
        
        # Create a mock logger to capture log calls
        with patch.object(server_module, 'logger') as mock_logger:
            with aioresponses() as mock:
                # Mock successful response
                mock.get(
                    "http://test.local:8123/api/ha_config_manager/files",
                    status=200,
                    payload={"files": []}
                )
                
                # Also mock error response for comprehensive testing
                mock.get(
                    "http://test.local:8123/api/ha_config_manager/files/error.yaml",
                    status=401,
                    body=json.dumps({"message": "Unauthorized"})
                )
                
                # Import and call the tool handler
                from ha_config_manager.server import handle_call_tool
                
                # Set up global api_client with the test token
                server_module.api_client = HAAPIClient("http://test.local:8123", access_token)
                
                # Test successful call
                try:
                    await handle_call_tool("list_config_files", {})
                except Exception:
                    pass
                
                # Test error call
                try:
                    await handle_call_tool("read_config_file", {"file_path": "error.yaml"})
                except Exception:
                    pass
                
                # Property: Token should NOT appear in any log messages
                all_log_calls = (
                    mock_logger.info.call_args_list +
                    mock_logger.error.call_args_list +
                    mock_logger.warning.call_args_list +
                    mock_logger.debug.call_args_list
                )
                
                for call in all_log_calls:
                    call_str = str(call)
                    assert access_token not in call_str, \
                        f"Access token should not appear in log messages: {call_str[:100]}"
                
                await server_module.api_client.close()

"""Property-based tests for MCP Server tool execution.

These tests validate universal properties that should hold for MCP tool calls.
"""

import json
import pytest
from hypothesis import given, strategies as st, settings
from aioresponses import aioresponses

from ha_dev_tools.connection.api import HAAPIClient


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
def file_content_strategy(draw):
    """Generate file content for testing passthrough."""
    # Generate various types of content including special characters
    return draw(st.text(min_size=0, max_size=1000))


@st.composite
def json_response_strategy(draw):
    """Generate valid JSON responses for list_files endpoint."""
    # Generate valid responses that list_files expects (dict with 'files' key)
    response_types = [
        {"files": []},
        {"files": [{"path": "test.yaml", "type": "file", "size": 100}]},
        {"files": [], "directory": ""},
        {"files": [{"path": "config.yaml"}], "directory": "packages"}
    ]
    return draw(st.sampled_from(response_types))


class TestToolExecutionProperties:
    """Property-based tests for MCP tool execution."""
    
    @pytest.mark.asyncio
    @given(file_content_strategy())
    @settings(max_examples=100)
    async def test_property_3_tool_execution_success(self, content: str):
        """
        **Feature: ha-config-manager-mcp-server, Property 3: Tool Execution Success**
        
        For any valid tool call with correct arguments, the MCP server should return 
        a result in valid MCP format (not an error).
        
        **Validates: Requirements 1.3**
        """
        # Test with read_config_file tool which returns plain text
        with aioresponses() as mock:
            # Mock successful API response
            mock.get(
                "http://test.local:8123/api/ha_dev_tools/files/test.yaml",
                status=200,
                body=content
            )
            
            client = HAAPIClient("http://test.local:8123", "test_token")
            
            # Property: Valid tool call should return result (not raise exception)
            result = await client.read_file("test.yaml")
            
            # Property: Result should be the content (successful execution)
            assert result == content, "Tool execution should return expected result"
            
            await client.close()
    
    @pytest.mark.asyncio
    @given(st.integers(min_value=400, max_value=599))
    @settings(max_examples=100)
    async def test_property_4_tool_execution_failure(self, status_code: int):
        """
        **Feature: ha-config-manager-mcp-server, Property 4: Tool Execution Failure**
        
        For any tool call that encounters an error, the MCP server should return 
        an error response in valid MCP error format with a descriptive message.
        
        **Validates: Requirements 1.4**
        """
        from ha_dev_tools.connection.api import HAAPIError
        
        with aioresponses() as mock:
            # Mock error response
            mock.get(
                "http://test.local:8123/api/ha_dev_tools/files/test.yaml",
                status=status_code,
                body=json.dumps({"message": "Test error"})
            )
            
            client = HAAPIClient("http://test.local:8123", "test_token")
            
            # Property: Error should be raised with proper error format
            with pytest.raises(HAAPIError) as exc_info:
                await client.read_file("test.yaml")
            
            # Property: Error should have descriptive message
            error = exc_info.value
            assert error.message, "Error should have a message"
            assert error.status_code == status_code, "Error should include status code"
            assert error.error_code, "Error should have an error code"
            
            await client.close()
    
    @pytest.mark.asyncio
    @given(json_response_strategy())
    @settings(max_examples=100)
    async def test_property_5_api_response_parsing(self, response_data: dict):
        """
        **Feature: ha-config-manager-mcp-server, Property 5: API Response Parsing**
        
        For any valid JSON response from the HA API containing file data, 
        the MCP server should successfully parse and return the data without errors.
        
        **Validates: Requirements 2.3**
        """
        with aioresponses() as mock:
            # Mock successful JSON response
            mock.get(
                "http://test.local:8123/api/ha_dev_tools/files",
                status=200,
                payload=response_data
            )
            
            client = HAAPIClient("http://test.local:8123", "test_token")
            
            # Property: Valid JSON should be parsed successfully
            result = await client.list_files()
            
            # Property: Result should match expected structure
            assert isinstance(result, list), "Parsed result should be a list"
            
            await client.close()
    
    @pytest.mark.asyncio
    @given(file_content_strategy())
    @settings(max_examples=100)
    async def test_property_7_file_content_passthrough(self, content: str):
        """
        **Feature: ha-config-manager-mcp-server, Property 7: File Content Passthrough**
        
        For any file content returned by the HA API, the MCP server should return 
        it unchanged (preserving whitespace, encoding, and formatting).
        
        **Validates: Requirements 3.3**
        """
        with aioresponses() as mock:
            # Mock file content response
            mock.get(
                "http://test.local:8123/api/ha_dev_tools/files/test.yaml",
                status=200,
                body=content
            )
            
            client = HAAPIClient("http://test.local:8123", "test_token")
            
            # Property: Content should be returned unchanged
            result = await client.read_file("test.yaml")
            assert result == content, "File content should be preserved exactly"
            
            await client.close()

"""Unit tests for MCP tool registration."""

import pytest
from ha_dev_tools.server import handle_list_tools


class TestToolRegistration:
    """Tests for tool registration functionality."""
    
    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        """Test that all 17 tools are registered."""
        tools = await handle_list_tools()
        
        # Should have exactly 17 tools
        assert len(tools) == 17
        
        # Verify all expected tool names are present
        tool_names = [tool.name for tool in tools]
        expected_tools = [
            # File Access (6 tools)
            "list_config_files",
            "read_config_file",
            "write_config_file",
            "get_file_metadata",
            "batch_get_metadata",
            "get_logs",
            # Entity & State (2 tools)
            "get_states",
            "get_history",
            # Service & Control (3 tools)
            "call_service",
            "render_template",
            "validate_template",
            # System Information (4 tools)
            "get_config",
            "list_events",
            "list_services",
            "get_logbook",
            # Configuration (1 tool)
            "check_config",
            # Diagnostics (1 tool)
            "get_error_log"
        ]
        
        assert set(tool_names) == set(expected_tools)
    
    @pytest.mark.asyncio
    async def test_tool_schemas_have_required_fields(self):
        """Test that all tool schemas have required fields (name, description, inputSchema)."""
        tools = await handle_list_tools()
        
        for tool in tools:
            # Each tool must have a name
            assert hasattr(tool, 'name')
            assert isinstance(tool.name, str)
            assert len(tool.name) > 0
            
            # Each tool must have a description
            assert hasattr(tool, 'description')
            assert isinstance(tool.description, str)
            assert len(tool.description) > 0
            
            # Each tool must have an inputSchema
            assert hasattr(tool, 'inputSchema')
            assert isinstance(tool.inputSchema, dict)
            
            # inputSchema must have type: object
            assert tool.inputSchema.get('type') == 'object'
            
            # inputSchema must have properties
            assert 'properties' in tool.inputSchema
            assert isinstance(tool.inputSchema['properties'], dict)
    
    @pytest.mark.asyncio
    async def test_file_access_tools_schemas(self):
        """Test schemas for file access tools."""
        tools = await handle_list_tools()
        tool_dict = {tool.name: tool for tool in tools}
        
        # list_config_files - optional directory parameter
        list_files = tool_dict['list_config_files']
        assert 'directory' in list_files.inputSchema['properties']
        assert 'required' not in list_files.inputSchema or 'directory' not in list_files.inputSchema.get('required', [])
        
        # read_config_file - required file_path parameter
        read_file = tool_dict['read_config_file']
        assert 'file_path' in read_file.inputSchema['properties']
        assert 'required' in read_file.inputSchema
        assert 'file_path' in read_file.inputSchema['required']
        
        # get_logs - required log_source parameter
        get_logs = tool_dict['get_logs']
        assert 'log_source' in get_logs.inputSchema['properties']
        assert 'required' in get_logs.inputSchema
        assert 'log_source' in get_logs.inputSchema['required']
    
    @pytest.mark.asyncio
    async def test_entity_state_tools_schemas(self):
        """Test schemas for entity and state tools."""
        tools = await handle_list_tools()
        tool_dict = {tool.name: tool for tool in tools}
        
        # get_states - optional entity_id parameter
        get_states = tool_dict['get_states']
        assert 'entity_id' in get_states.inputSchema['properties']
        assert 'required' not in get_states.inputSchema or 'entity_id' not in get_states.inputSchema.get('required', [])
        
        # get_history - all parameters optional
        get_history = tool_dict['get_history']
        assert 'start_time' in get_history.inputSchema['properties']
        assert 'end_time' in get_history.inputSchema['properties']
        assert 'entity_ids' in get_history.inputSchema['properties']
        assert 'required' not in get_history.inputSchema or len(get_history.inputSchema.get('required', [])) == 0
    
    @pytest.mark.asyncio
    async def test_service_control_tools_schemas(self):
        """Test schemas for service and control tools."""
        tools = await handle_list_tools()
        tool_dict = {tool.name: tool for tool in tools}
        
        # call_service - required domain and service parameters
        call_service = tool_dict['call_service']
        assert 'domain' in call_service.inputSchema['properties']
        assert 'service' in call_service.inputSchema['properties']
        assert 'service_data' in call_service.inputSchema['properties']
        assert 'required' in call_service.inputSchema
        assert 'domain' in call_service.inputSchema['required']
        assert 'service' in call_service.inputSchema['required']
        assert 'service_data' not in call_service.inputSchema['required']
        
        # render_template - required template parameter, optional validate_entities
        render_template = tool_dict['render_template']
        assert 'template' in render_template.inputSchema['properties']
        assert 'validate_entities' in render_template.inputSchema['properties']
        assert 'required' in render_template.inputSchema
        assert 'template' in render_template.inputSchema['required']
        assert 'validate_entities' not in render_template.inputSchema['required']
        # Verify validate_entities has default value
        assert not render_template.inputSchema['properties']['validate_entities'].get('default')
        
        # validate_template - required template parameter, optional validate_entities
        validate_template = tool_dict['validate_template']
        assert 'template' in validate_template.inputSchema['properties']
        assert 'validate_entities' in validate_template.inputSchema['properties']
        assert 'required' in validate_template.inputSchema
        assert 'template' in validate_template.inputSchema['required']
        assert 'validate_entities' not in validate_template.inputSchema['required']
        # Verify validate_entities has default value
        assert not validate_template.inputSchema['properties']['validate_entities'].get('default')
    
    @pytest.mark.asyncio
    async def test_system_info_tools_schemas(self):
        """Test schemas for system information tools."""
        tools = await handle_list_tools()
        tool_dict = {tool.name: tool for tool in tools}
        
        # get_config - no parameters
        get_config = tool_dict['get_config']
        assert len(get_config.inputSchema['properties']) == 0
        
        # list_events - no parameters
        list_events = tool_dict['list_events']
        assert len(list_events.inputSchema['properties']) == 0
        
        # list_services - no parameters
        list_services = tool_dict['list_services']
        assert len(list_services.inputSchema['properties']) == 0
    
    @pytest.mark.asyncio
    async def test_configuration_tools_schemas(self):
        """Test schemas for configuration tools."""
        tools = await handle_list_tools()
        tool_dict = {tool.name: tool for tool in tools}
        
        # check_config - no parameters
        check_config = tool_dict['check_config']
        assert len(check_config.inputSchema['properties']) == 0
    
    @pytest.mark.asyncio
    async def test_tool_names_are_unique(self):
        """Test that all tool names are unique."""
        tools = await handle_list_tools()
        tool_names = [tool.name for tool in tools]
        
        # No duplicates
        assert len(tool_names) == len(set(tool_names))
    
    @pytest.mark.asyncio
    async def test_tool_descriptions_are_meaningful(self):
        """Test that all tool descriptions are meaningful (not empty or too short)."""
        tools = await handle_list_tools()
        
        for tool in tools:
            # Description should be at least 20 characters
            assert len(tool.description) >= 20, f"Tool {tool.name} has too short description"
            
            # Description should contain the tool name or related keywords
            # (This is a heuristic check for meaningful descriptions)
            keywords = ['home', 'assistant', 'configuration', 'entity', 'service', 'log', 
                       'template', 'history', 'event', 'config', 'check', 'validate', 
                       'list', 'get', 'read', 'call', 'render', 'jinja']
            assert any(word in tool.description.lower() for word in keywords), \
                f"Tool {tool.name} description doesn't contain expected keywords: {tool.description}"

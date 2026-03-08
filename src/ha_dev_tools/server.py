"""MCP Server for Home Assistant Development Tools.

This module implements the Model Context Protocol (MCP) server that provides
comprehensive development tools for Home Assistant through REST API endpoints.

The server translates MCP tool calls into HTTP requests to:
1. HA Dev Tools Integration API: File access and log retrieval
2. Official Home Assistant API: Entity states, services, templates, history, and system configuration

Package: ha-dev-tools-mcp
Integration: ha_dev_tools
"""

import asyncio
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

from .config import load_config, ConfigError
from .connection.api import HAAPIClient, HAAPIError
from .validation import (
    ValidationError,
    validate_file_path,
    validate_positive_integer,
    validate_log_source,
    validate_entity_id,
    validate_domain,
    validate_service,
    validate_required_parameter,
    validate_template,
    validate_boolean
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCP Server instance
server = Server("ha-dev-tools")

# Global API client instance (initialized in main())
api_client: HAAPIClient = None


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available MCP tools.
    
    Returns all 17 tools organized into categories:
    - File Access (6 tools): list_config_files, read_config_file, write_config_file, get_file_metadata, batch_get_metadata, get_logs
    - Entity & State (2 tools): get_states, get_history
    - Service & Control (3 tools): call_service, render_template, validate_template
    - System Information (4 tools): get_config, list_events, list_services, get_logbook
    - Configuration (1 tool): check_config
    - Diagnostics (1 tool): get_error_log
    
    Returns:
        List[Tool]: List of Tool objects with names, descriptions, and input schemas
    """
    return [
        # File Access Tools (Custom Integration API)
        Tool(
            name="list_config_files",
            description="List configuration files in Home Assistant instance",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Optional directory to filter files (e.g., 'packages')"
                    }
                }
            }
        ),
        Tool(
            name="read_config_file",
            description=(
                "Read configuration file content from Home Assistant with support for large files. "
                "For files >50KB, use save_local=true to save to local temp directory instead of returning content. "
                "For smaller files or viewing specific sections, use pagination (offset/limit) or return content directly. "
                "Note: save_local and pagination (offset/limit) are mutually exclusive."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the configuration file (e.g., 'configuration.yaml')"
                    },
                    "save_local": {
                        "type": "boolean",
                        "description": (
                            "Save file to local temp directory instead of returning content (for large files >50KB). "
                            "Returns local file path, file size, and remote path. "
                            "Files are saved to system temp directory (e.g., /tmp/ha-dev-tools/ on Unix, %TEMP%\\ha-dev-tools\\ on Windows). "
                            "Cannot be used with offset or limit parameters."
                        )
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Byte offset to start reading from (default: 0, for chunking large files). Cannot be used with save_local.",
                        "minimum": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum bytes to return (optional, for chunking large files). Cannot be used with save_local.",
                        "minimum": 1
                    },
                    "compress": {
                        "type": "boolean",
                        "description": "Request gzip compression for large files (default: false)"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="write_config_file",
            description="Write content to a configuration file on Home Assistant instance. Validates YAML syntax before writing and supports conflict detection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the configuration file (e.g., 'configuration.yaml')"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write"
                    },
                    "expected_hash": {
                        "type": "string",
                        "description": "Expected current hash for conflict detection (optional). If provided, write will fail if file has been modified."
                    },
                    "validate_before_write": {
                        "type": "boolean",
                        "description": "Validate YAML syntax before writing (default: true)"
                    }
                },
                "required": ["file_path", "content"]
            }
        ),
        Tool(
            name="get_file_metadata",
            description="Get metadata for a configuration file without reading content. Returns path, size, modification timestamp, and content hash for version checking.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the configuration file (e.g., 'configuration.yaml')"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="batch_get_metadata",
            description="Get metadata for multiple configuration files in one request. Efficient for checking versions of multiple files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Array of file paths (e.g., ['configuration.yaml', 'automations.yaml'])"
                    }
                },
                "required": ["file_paths"]
            }
        ),
        Tool(
            name="get_logs",
            description="Retrieve Home Assistant logs with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "log_source": {
                        "type": "string",
                        "description": "Log source to retrieve (currently only 'core' is supported)",
                        "enum": ["core"]
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve (default: 100)",
                        "minimum": 1,
                        "maximum": 1000
                    },
                    "level": {
                        "type": "string",
                        "description": "Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
                    },
                    "search": {
                        "type": "string",
                        "description": "Search term to filter log messages"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination (default: 0)",
                        "minimum": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of entries to return (default: 100)",
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["log_source"]
            }
        ),
        
        # Entity and State Tools (Official HA API)
        Tool(
            name="get_states",
            description="Get entity states from Home Assistant. Returns all entities if no entity_id specified, or a specific entity's state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Optional entity ID to get specific entity state (e.g., 'light.living_room')"
                    }
                }
            }
        ),
        Tool(
            name="get_history",
            description="Get historical state data for entities over a time period",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format (e.g., '2024-01-15T10:00:00'). Defaults to 1 day ago."
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601 format. Defaults to now."
                    },
                    "entity_ids": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of entity IDs to get history for. If omitted, returns history for all entities."
                    }
                }
            }
        ),
        
        # Service and Control Tools (Official HA API)
        Tool(
            name="call_service",
            description="Call a Home Assistant service to control devices or trigger actions",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Service domain (e.g., 'light', 'switch', 'automation')"
                    },
                    "service": {
                        "type": "string",
                        "description": "Service name (e.g., 'turn_on', 'turn_off', 'toggle')"
                    },
                    "service_data": {
                        "type": "object",
                        "description": "Optional service data/parameters (e.g., {'entity_id': 'light.living_room', 'brightness': 255})"
                    }
                },
                "required": ["domain", "service"]
            }
        ),
        Tool(
            name="render_template",
            description="Render a Jinja2 template with Home Assistant context and enhanced error reporting. Optionally validate entity references before rendering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Jinja2 template string to render (e.g., '{{ states(\"sensor.temperature\") }}')"
                    },
                    "validate_entities": {
                        "type": "boolean",
                        "description": "If true, validate entity references before rendering (default: false)",
                        "default": False
                    }
                },
                "required": ["template"]
            }
        ),
        Tool(
            name="validate_template",
            description="Validate template syntax without executing the template. Optionally validate entity references.",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Jinja2 template string to validate"
                    },
                    "validate_entities": {
                        "type": "boolean",
                        "description": "If true, also validate entity references (default: false)",
                        "default": False
                    }
                },
                "required": ["template"]
            }
        ),
        
        # System Information Tools (Official HA API)
        Tool(
            name="get_config",
            description="Get Home Assistant configuration details including version, location, and components",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="list_events",
            description="List all available event types in Home Assistant",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="list_services",
            description="List all available services organized by domain with descriptions and schemas",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        
        # Configuration Tools (Official HA API)
        Tool(
            name="check_config",
            description="Validate Home Assistant configuration without restarting",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        
        # Diagnostics Tools (Official HA API)
        Tool(
            name="get_error_log",
            description="Retrieve all errors logged during the current Home Assistant session as plain text",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_logbook",
            description="Get logbook entries showing entity state changes and events over a time period",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format (e.g., '2024-01-15T00:00:00+00:00'). Defaults to 1 day ago."
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601 format. Defaults to now."
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Optional entity ID to filter logbook entries (e.g., 'light.living_room')"
                    }
                }
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool call requests.
    
    Routes tool calls to appropriate API client methods and returns results
    in MCP format. All 16 tools are handled here.
    
    Error handling:
    - HAAPIError: Translated to MCP error with user-friendly message
    - Validation errors: Returned as MCP errors with validation details
    - Unexpected errors: Returned as generic MCP error with error message
    - All errors are logged appropriately
    
    Args:
        name: Tool name to execute
        arguments: Tool arguments as a dictionary
    
    Returns:
        List[TextContent]: Tool execution results in MCP format
    
    Raises:
        Exception: If tool execution fails (caught and formatted by MCP SDK)
    """
    import json
    import time
    
    # Log tool call
    start_time = time.time()
    logger.info(f"Tool called: {name}")
    
    try:
        # File Access Tools (Custom Integration API)
        if name == "list_config_files":
            directory = arguments.get("directory", "")
            # No validation needed for optional directory parameter
            files = await api_client.list_files(directory)
            return [TextContent(
                type="text",
                text=json.dumps({"files": files}, indent=2)
            )]
        
        elif name == "read_config_file":
            # Validate required parameter
            file_path = arguments.get("file_path")
            validate_required_parameter(file_path, "file_path")
            
            # Validate file path format
            validate_file_path(file_path)
            
            # Get optional parameters
            save_local = arguments.get("save_local", False)
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit")
            compress = arguments.get("compress", False)
            
            # Call API client with all parameters (including save_local)
            result = await api_client.read_file(
                file_path=file_path,
                save_local=save_local,
                offset=offset,
                limit=limit,
                compress=compress
            )
            
            # Return structured response with content and metadata
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "write_config_file":
            # Validate required parameters
            file_path = arguments.get("file_path")
            content = arguments.get("content")
            validate_required_parameter(file_path, "file_path")
            validate_required_parameter(content, "content")
            
            # Validate file path format
            validate_file_path(file_path)
            
            # Get optional parameters
            expected_hash = arguments.get("expected_hash")
            validate_before_write = arguments.get("validate_before_write", True)
            
            # Validate boolean parameter if provided
            if validate_before_write is not True:  # Only validate if explicitly provided
                validate_boolean(validate_before_write, "validate_before_write")
            
            # Call API client write_file method
            result = await api_client.write_file(
                file_path=file_path,
                content=content,
                expected_hash=expected_hash,
                validate_before_write=validate_before_write
            )
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_file_metadata":
            # Validate required parameter
            file_path = arguments.get("file_path")
            validate_required_parameter(file_path, "file_path")
            
            # Validate file path format
            validate_file_path(file_path)
            
            metadata = await api_client.get_file_metadata(file_path)
            return [TextContent(
                type="text",
                text=json.dumps(metadata, indent=2)
            )]
        
        elif name == "batch_get_metadata":
            # Validate required parameter
            file_paths = arguments.get("file_paths")
            validate_required_parameter(file_paths, "file_paths")
            
            # Validate file_paths is a list
            if not isinstance(file_paths, list):
                raise ValidationError("file_paths must be a list", "file_paths")
            
            # Validate each file path
            for file_path in file_paths:
                validate_file_path(file_path)
            
            # Limit batch size to 20 files
            if len(file_paths) > 20:
                raise ValidationError("batch_get_metadata supports maximum 20 files", "file_paths")
            
            metadata_list = await api_client.batch_get_metadata(file_paths)
            return [TextContent(
                type="text",
                text=json.dumps({"metadata": metadata_list}, indent=2)
            )]
        
        elif name == "get_logs":
            # Validate required parameter
            log_source = arguments.get("log_source")
            validate_required_parameter(log_source, "log_source")
            
            # Validate log source is supported
            validate_log_source(log_source)
            
            # Get optional parameters with defaults
            lines = arguments.get("lines", 100)
            level = arguments.get("level")
            search = arguments.get("search")
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 100)
            
            # Validate numeric parameters
            if lines != 100:  # Only validate if explicitly provided
                validate_positive_integer(lines, "lines", min_value=1, max_value=1000)
            if offset != 0:  # Only validate if explicitly provided
                validate_positive_integer(offset, "offset", min_value=0)
            if limit != 100:  # Only validate if explicitly provided
                validate_positive_integer(limit, "limit", min_value=1, max_value=1000)
            
            logs = await api_client.get_logs(
                log_source=log_source,
                lines=lines,
                level=level,
                search=search,
                offset=offset,
                limit=limit
            )
            return [TextContent(
                type="text",
                text=json.dumps({"logs": logs}, indent=2)
            )]
        
        # Entity and State Tools (Official HA API)
        elif name == "get_states":
            entity_id = arguments.get("entity_id")
            
            # Validate entity_id format if provided
            if entity_id:
                validate_entity_id(entity_id)
            
            states = await api_client.get_states(entity_id)
            return [TextContent(
                type="text",
                text=json.dumps(states, indent=2)
            )]
        
        elif name == "get_history":
            start_time = arguments.get("start_time")
            end_time = arguments.get("end_time")
            entity_ids = arguments.get("entity_ids")
            
            # Validate entity_ids format if provided
            if entity_ids:
                if not isinstance(entity_ids, list):
                    raise ValidationError("entity_ids must be a list", "entity_ids")
                for entity_id in entity_ids:
                    validate_entity_id(entity_id)
            
            history = await api_client.get_history(
                start_time=start_time,
                end_time=end_time,
                entity_ids=entity_ids
            )
            return [TextContent(
                type="text",
                text=json.dumps(history, indent=2)
            )]
        
        # Service and Control Tools (Official HA API)
        elif name == "call_service":
            # Validate required parameters
            domain = arguments.get("domain")
            service = arguments.get("service")
            validate_required_parameter(domain, "domain")
            validate_required_parameter(service, "service")
            
            # Validate domain and service format
            validate_domain(domain)
            validate_service(service)
            
            service_data = arguments.get("service_data")
            
            result = await api_client.call_service(
                domain=domain,
                service=service,
                service_data=service_data
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "render_template":
            # Validate required parameter
            template = arguments.get("template")
            validate_required_parameter(template, "template")
            validate_template(template)
            
            # Get optional validate_entities parameter
            validate_entities = arguments.get("validate_entities", False)
            if validate_entities is not False:  # Only validate if explicitly provided
                validate_boolean(validate_entities, "validate_entities")
            
            result = await api_client.render_template(template, validate_entities=validate_entities)
            
            # Handle result that may be a string or dict with warnings
            if isinstance(result, dict):
                # Result with warnings
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            else:
                # Plain string result
                return [TextContent(
                    type="text",
                    text=result
                )]
        
        elif name == "validate_template":
            from .template_validator import (
                validate_template_syntax,
                extract_entity_references,
                format_entity_validation_warnings
            )
            
            # Validate required parameter
            template = arguments.get("template")
            validate_required_parameter(template, "template")
            validate_template(template)
            
            # Get optional validate_entities parameter
            validate_entities = arguments.get("validate_entities", False)
            if validate_entities is not False:  # Only validate if explicitly provided
                validate_boolean(validate_entities, "validate_entities")
            
            # Validate template syntax
            is_valid, error_dict = validate_template_syntax(template)
            
            if not is_valid:
                # Return error response with structured error
                return [TextContent(
                    type="text",
                    text=json.dumps(error_dict, indent=2)
                )]
            
            # If syntax is valid and entity validation is requested
            warnings = []
            if validate_entities:
                # Extract entity references from template
                entity_ids = extract_entity_references(template)
                
                if entity_ids:
                    # Validate entities exist in Home Assistant
                    existing, missing = await api_client.validate_entities(entity_ids)
                    
                    if missing:
                        # Format warning message
                        warning = format_entity_validation_warnings(missing)
                        warnings.append(warning)
            
            # Return success response
            response = {
                "valid": True,
                "message": "Template syntax is valid"
            }
            
            if warnings:
                response["warnings"] = warnings
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2)
            )]
        
        # System Information Tools (Official HA API)
        elif name == "get_config":
            config = await api_client.get_config()
            return [TextContent(
                type="text",
                text=json.dumps(config, indent=2)
            )]
        
        elif name == "list_events":
            events = await api_client.list_events()
            return [TextContent(
                type="text",
                text=json.dumps(events, indent=2)
            )]
        
        elif name == "list_services":
            services = await api_client.list_services()
            return [TextContent(
                type="text",
                text=json.dumps(services, indent=2)
            )]
        
        # Configuration Tools (Official HA API)
        elif name == "check_config":
            result = await api_client.check_config()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Diagnostics Tools (Official HA API)
        elif name == "get_error_log":
            error_log = await api_client.get_error_log()
            return [TextContent(
                type="text",
                text=error_log
            )]
        
        elif name == "get_logbook":
            start_time = arguments.get("start_time")
            end_time = arguments.get("end_time")
            entity_id = arguments.get("entity_id")
            
            logbook = await api_client.get_logbook(
                start_time=start_time,
                end_time=end_time,
                entity_id=entity_id
            )
            return [TextContent(
                type="text",
                text=json.dumps(logbook, indent=2)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except HAAPIError as e:
        # Log API errors (excluding sensitive data)
        logger.error(f"API error in tool {name}: {e.error_code} - {e.message}")
        # Re-raise to be formatted by MCP SDK
        raise
    
    except ValidationError as e:
        # Log validation errors
        logger.error(f"Validation error in tool {name}: {e.message}")
        # Re-raise as ValueError to be formatted by MCP SDK
        raise ValueError(e.message)
    
    except KeyError as e:
        # Missing required parameter
        error_msg = f"Missing required parameter: {e}"
        logger.error(f"Validation error in tool {name}: {error_msg}")
        raise ValueError(error_msg)
    
    except (TypeError, ValueError) as e:
        # Validation errors (invalid parameter types or values)
        error_msg = f"Invalid parameter: {e}"
        logger.error(f"Validation error in tool {name}: {error_msg}")
        raise ValueError(error_msg)
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error in tool {name}: {e}", exc_info=True)
        # Re-raise to be formatted by MCP SDK
        raise
    
    finally:
        # Log execution time
        execution_time = time.time() - start_time
        logger.info(f"Tool {name} completed in {execution_time:.2f}s")


async def main():
    """Initialize and run the MCP server.
    
    This function:
    1. Loads configuration from environment variables (HA_URL, HA_TOKEN)
    2. Creates HAAPIClient instance
    3. Sets up stdio_server context for MCP communication
    4. Runs the MCP server with stdio transport
    5. Handles shutdown and cleanup
    
    Raises:
        ConfigError: If configuration is missing or invalid
    """
    global api_client
    
    try:
        # Load configuration from environment variables
        logger.info("Loading configuration...")
        config = load_config()
        
        # Log successful startup (without token for security)
        logger.info(f"Starting MCP server for Home Assistant at {config.ha_url}")
        
        # Create HAAPIClient instance
        api_client = HAAPIClient(
            base_url=config.ha_url,
            access_token=config.ha_token,
            timeout=config.request_timeout
        )
        
        # Set up stdio_server context and run MCP server
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server started successfully")
            
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ha-config-manager",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    
    except ConfigError as e:
        # Configuration errors should be logged and re-raised
        logger.error(f"Configuration error: {e}")
        raise
    
    except Exception as e:
        # Unexpected errors during startup
        logger.error(f"Failed to start MCP server: {e}", exc_info=True)
        raise
    
    finally:
        # Ensure cleanup happens on server shutdown
        if api_client:
            logger.info("Shutting down server, cleaning up connections...")
            await api_client.close()
            logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

# Home Assistant Configuration Manager MCP Server

A Model Context Protocol (MCP) server for managing Home Assistant configuration files with validation, backup, and multi-instance support.

## Features

- **Configuration File Management**: Discover, read, and write HA configuration files
- **YAML Validation**: Syntax and structure validation before writing changes
- **Automatic Backups**: Create backups before modifying configuration files
- **Multi-Instance Support**: Manage multiple HA instances with context isolation
- **Local Connection**: Direct filesystem access for local HA instances

## Installation

```bash
pip install -e .
```

## Dependencies

- Python 3.12+
- pydantic
- pyyaml
- aiofiles
- mcp (Model Context Protocol SDK)

## Usage

### As MCP Server

```bash
python -m ha_config_manager.server
```

### Programmatic Usage

```python
from ha_config_manager.manager import HAConfigurationManager
from ha_config_manager.types import HAInstance, ConnectionType

# Create manager
manager = HAConfigurationManager()

# Add HA instance
instance = HAInstance(
    id="local_ha",
    name="Local Home Assistant",
    connection_type=ConnectionType.LOCAL,
    connection_config=ConnectionConfig(url="/path/to/ha"),
    # ... other config
)

await manager.add_instance(instance)
await manager.switch_instance("local_ha")

# List configuration files
files = await manager.list_config_files("local_ha")

# Read configuration
content = await manager.read_config_file("local_ha", "configuration.yaml")

# Validate YAML
result = await manager.validate_yaml(content)

# Create backup and write changes
backup_path = await manager.create_backup("local_ha", "configuration.yaml")
await manager.write_config_file("local_ha", "configuration.yaml", new_content)
```

## Testing

Run unit tests:
```bash
pytest tests/test_config_manager.py -v
```

Run property-based tests:
```bash
pytest tests/test_properties.py -v
```

## Architecture

- **Manager**: Core configuration management logic
- **Connection Layer**: Abstraction for different HA connection types
- **Types**: Pydantic models for type safety and validation
- **MCP Server**: Protocol server for integration with MCP clients

## Property-Based Testing

The project includes property-based tests that validate universal correctness properties:

1. **Configuration File Discovery and Access**: Files can be discovered and read completely
2. **Configuration Backup Creation**: Backups preserve exact original content
3. **YAML Validation Consistency**: Valid YAML is accepted, invalid YAML is rejected

## Requirements Validation

This implementation validates the following requirements:
- 1.1, 1.2: Configuration file discovery and access
- 1.3: YAML validation before writing
- 1.4: Automatic backup creation
- 1.5: Multi-instance support with context isolation
- 6.1, 6.2: YAML syntax and structure validation
- 8.1, 8.4: MCP server integration support
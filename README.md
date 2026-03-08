# HA Dev Tools MCP Server

A Model Context Protocol (MCP) server providing comprehensive development tools for Home Assistant. This server enables file management, template testing, entity/state management, service calls, log access, and system information retrieval through the MCP protocol.

## Features

### File Management
- **Configuration File Discovery**: Automatically discover all configuration files in your HA instance
- **Read/Write Operations**: Read and modify configuration files with validation
- **YAML Validation**: Syntax and structure validation before writing changes
- **Automatic Backups**: Create backups before modifying configuration files
- **File Metadata**: Get file size, modification time, and other metadata
- **Content Pagination**: Handle large files with efficient pagination support
- **Local File Save**: Save large files to local temp directory to avoid context window overflow

### Template Testing
- **Template Rendering**: Test Jinja2 templates with real Home Assistant context
- **Template Validation**: Validate template syntax and entity references
- **Entity Validation**: Verify that entities referenced in templates exist
- **Multi-line Template Support**: Handle complex multi-line templates correctly

### Entity & State Management
- **Entity Discovery**: List all entities in your Home Assistant instance
- **State Retrieval**: Get current state and attributes of any entity
- **Service Calls**: Execute Home Assistant services programmatically

### System Information
- **Log Access**: Read and search Home Assistant logs
- **System Info**: Get Home Assistant version, configuration, and system details

### Multi-Instance Support
- **Multiple HA Instances**: Manage multiple Home Assistant instances simultaneously
- **Context Isolation**: Each instance maintains separate state and configuration
- **Instance Switching**: Easily switch between different HA instances

## Installation

### Via pip (Recommended)

```bash
pip install ha-dev-tools-mcp
```

### Via uvx (For Kiro Users)

```bash
uvx --from ha-dev-tools-mcp ha-dev-tools-mcp
```

### From Source

```bash
git clone https://github.com/username/ha-dev-tools-mcp.git
cd ha-dev-tools-mcp
pip install -e .
```

## Quick Start

### Running the MCP Server

```bash
# Start the server
ha-dev-tools-mcp

# Or with Python module syntax
python -m ha_dev_tools.server
```

### Configuration

The server connects to Home Assistant via the [HA Dev Tools integration](https://github.com/username/ha-dev-tools). Install the integration first:

1. Install via HACS (recommended) or manually
2. Configure the integration in Home Assistant
3. Note the API URL and authentication token
4. Configure the MCP server to connect to your HA instance

### Using with Kiro

Install the [HA Development Power](https://github.com/username/ha-development-power) for seamless integration with Kiro:

1. Open Kiro Powers UI
2. Search for "Home Assistant Development"
3. Install the power
4. The MCP server will be automatically configured

## Usage Examples

### File Management

```python
from ha_dev_tools import HADevTools

# Initialize client
client = HADevTools(ha_url="http://localhost:8123", token="your_token")

# List configuration files
files = await client.list_config_files()
print(f"Found {len(files)} configuration files")

# Read a configuration file (returns content directly)
content = await client.read_config_file("configuration.yaml")
print(content)

# Read a large file and save locally (recommended for files >50KB)
result = await client.read_config_file("configuration.yaml", save_local=True)
print(f"File saved to: {result['local_path']}")
print(f"File size: {result['file_size']} bytes")
# File is now available at the local path for direct access

# Read with pagination for viewing specific sections
partial = await client.read_config_file(
    "configuration.yaml",
    offset=0,
    length=1000
)
print(f"First 1000 bytes: {partial['content']}")

# Validate YAML before writing
is_valid = await client.validate_yaml(new_content)
if is_valid:
    # Create backup and write changes
    backup_path = await client.create_backup("configuration.yaml")
    await client.write_config_file("configuration.yaml", new_content)
```

#### Working with Large Files

The `save_local` parameter is designed for handling large configuration files that would overflow the AI model's context window:

**When to use `save_local=True`:**
- Files larger than 50KB
- When you need to process the entire file locally
- When working with large `configuration.yaml` files

**When to use pagination (`offset`/`length`):**
- Files smaller than 50KB
- When you only need to view specific sections
- For quick inspection of file contents

**Response format with `save_local=True`:**
```python
{
    "saved": True,
    "local_path": "/tmp/ha-dev-tools/configuration.yaml",  # Unix/Linux/macOS
    # or "C:\\Users\\Username\\AppData\\Local\\Temp\\ha-dev-tools\\configuration.yaml"  # Windows
    "file_size": 125000,
    "remote_path": "configuration.yaml"
}
```

**Response format with `save_local=False` (default):**
```python
{
    "saved": False,
    "content": "homeassistant:\n  name: Home\n  ...",
    "file_size": 1024,
    "file_path": "configuration.yaml"
}
```

**Important notes:**
- `save_local` and pagination parameters (`offset`, `length`) are mutually exclusive
- Files are saved to the system temporary directory with preserved directory structure
- Saved files overwrite previous versions (latest version wins)
- Maximum file size is configurable (default 10MB, max 100MB)

### Template Testing

```python
# Render a template with HA context
template = "The temperature is {{ states('sensor.temperature') }}°C"
result = await client.render_template(template)
print(result)

# Validate template syntax
is_valid = await client.validate_template(template)

# Validate entity references
entities = ["sensor.temperature", "sensor.humidity"]
validation = await client.validate_entities(entities)
```

### Entity & State Management

```python
# List all entities
entities = await client.list_entities()

# Get entity state
state = await client.get_entity_state("sensor.temperature")
print(f"Temperature: {state['state']}°C")

# Call a service
await client.call_service("light", "turn_on", {
    "entity_id": "light.living_room",
    "brightness": 255
})
```

### Log Access

```python
# Read recent logs
logs = await client.get_logs(lines=100)

# Search logs for errors
errors = await client.search_logs("ERROR")
```

## MCP Tools

The server exposes the following MCP tools:

### File Operations
- `list_config_files` - List all configuration files
- `read_config_file` - Read a configuration file with optional local save or pagination
  - Parameters:
    - `instance_id` (required): Home Assistant instance identifier
    - `file_path` (required): Path to configuration file
    - `save_local` (optional): Save to local temp directory instead of returning content (for large files >50KB)
    - `offset` (optional): Starting byte offset for partial read (mutually exclusive with save_local)
    - `length` (optional): Number of bytes to read (mutually exclusive with save_local)
- `write_config_file` - Write to a configuration file
- `create_backup` - Create a backup of a file
- `get_file_metadata` - Get file metadata (size, mtime, etc.)

### Template Operations
- `render_template` - Render a Jinja2 template
- `validate_template` - Validate template syntax
- `validate_entities` - Validate entity references

### Entity Operations
- `list_entities` - List all entities
- `get_entity_state` - Get entity state and attributes
- `call_service` - Execute a Home Assistant service

### System Operations
- `get_logs` - Read Home Assistant logs
- `get_system_info` - Get system information

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client (Kiro)                       │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   HA Dev Tools MCP Server                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ File Manager │  │   Template   │  │    Entity    │      │
│  │              │  │   Validator  │  │   Manager    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Log Manager  │  │   Workflow   │  │   Conflict   │      │
│  │              │  │     State    │  │  Resolution  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  HA Dev Tools Integration                    │
│                    (Home Assistant)                          │
└─────────────────────────────────────────────────────────────┘
```

## Development

### Prerequisites

- Python 3.12 or later
- Home Assistant 2024.1.0 or later
- HA Dev Tools integration installed

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/username/ha-dev-tools-mcp.git
cd ha-dev-tools-mcp

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/test_*.py -v

# Run property-based tests
pytest tests/test_*_properties.py -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=ha_dev_tools --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Property-Based Testing

This project uses property-based testing with Hypothesis to validate correctness properties:

### File Operations Properties
- **Preservation**: Reading a file returns its complete content
- **Backup Integrity**: Backups preserve exact original content
- **Write Consistency**: Written content can be read back unchanged

### Template Properties
- **Validation Consistency**: Valid templates are accepted, invalid rejected
- **Entity Validation**: Entity references are correctly validated
- **Rendering Determinism**: Same template + state = same result

### Workflow Properties
- **State Transitions**: Workflow states transition correctly
- **Conflict Detection**: Conflicts are detected and resolved properly
- **Idempotency**: Operations can be safely retried

See [tests/PRESERVATION_PROPERTIES.md](tests/PRESERVATION_PROPERTIES.md) for detailed property specifications.

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to Home Assistant
```
Error: Connection refused to http://localhost:8123
```

**Solution**: 
1. Verify HA Dev Tools integration is installed and configured
2. Check the API URL is correct
3. Verify the authentication token is valid
4. Ensure Home Assistant is running

### Template Rendering Errors

**Problem**: Template fails to render
```
Error: TemplateError: entity 'sensor.unknown' not found
```

**Solution**:
1. Validate entity references with `validate_entities` first
2. Check entity IDs are correct (case-sensitive)
3. Ensure entities exist in your HA instance

### File Write Failures

**Problem**: Cannot write to configuration file
```
Error: Permission denied
```

**Solution**:
1. Check file permissions in Home Assistant
2. Verify the integration has write access configured
3. Check security allowlist in integration settings

### Large File Handling

**Problem**: Timeout when reading large files
```
Error: Request timeout
```

**Solution**:
1. Use `save_local=True` for files larger than 50KB
2. Use pagination with `offset` and `length` parameters for viewing specific sections
3. Increase timeout settings in client configuration
4. Consider splitting large files into smaller ones

### File Save Issues

**Problem**: Cannot save file locally
```
Error: PERMISSION_DENIED - Permission denied writing to temp directory
```

**Solution**:
1. Check write permissions for system temp directory:
   - Unix/Linux/macOS: `/tmp/ha-dev-tools/`
   - Windows: `%TEMP%\ha-dev-tools\`
2. Ensure sufficient disk space is available
3. Check that the temp directory is not read-only

**Problem**: File too large to save
```
Error: FILE_TOO_LARGE - File size exceeds limit
```

**Solution**:
1. Default limit is 10MB, maximum is 100MB
2. Configure `max_file_size` in server settings if needed
3. Consider using pagination to work with specific sections instead
4. Split large configuration files into smaller includes

**Problem**: Mutually exclusive parameters error
```
Error: MUTUALLY_EXCLUSIVE_PARAMETERS - save_local and pagination are mutually exclusive
```

**Solution**:
1. Choose either `save_local=True` OR pagination (`offset`/`length`), not both
2. Use `save_local` for large files (>50KB) that need full processing
3. Use pagination for viewing specific sections of any file

### Temporary File Location

Saved files are stored in the system temporary directory:

- **Unix/Linux/macOS**: `/tmp/ha-dev-tools/`
- **Windows**: `%TEMP%\ha-dev-tools\` (typically `C:\Users\Username\AppData\Local\Temp\ha-dev-tools\`)

Files are organized to mirror the remote directory structure:
```
/tmp/ha-dev-tools/
├── configuration.yaml
├── automations.yaml
├── scripts.yaml
└── packages/
    ├── lights.yaml
    └── sensors.yaml
```

The operating system automatically cleans up temp files periodically. Files are overwritten on subsequent saves (latest version wins).

## Related Projects

- **[HA Dev Tools Integration](https://github.com/username/ha-dev-tools)** - Home Assistant custom integration providing the API backend
- **[HA Development Power](https://github.com/username/ha-development-power)** - Kiro Power for seamless integration with Kiro IDE

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/username/ha-dev-tools-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/username/ha-dev-tools-mcp/discussions)
- **Documentation**: [Full Documentation](https://github.com/username/ha-dev-tools-mcp/wiki)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

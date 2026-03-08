# MCP Server Testing Guide

This guide covers different ways to test the Home Assistant Configuration Manager MCP Server.

## Prerequisites

1. **Home Assistant Instance**: You need a running Home Assistant instance with:
   - The HA Config Manager custom integration installed
   - A long-lived access token generated

2. **Python Environment**: Python 3.12+ with dependencies installed:
   ```bash
   source .venv/bin/activate
   cd src/config-manager
   pip install -e .
   ```

3. **Environment Variables**:
   ```bash
   export HA_URL="http://homeassistant.local:8123"
   export HA_TOKEN="your_long_lived_access_token_here"
   ```

## Testing Methods

### 1. Automated Test Suite (Recommended for Development)

Run the complete test suite with mocked Home Assistant responses:

```bash
# From project root
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/ -v

# Run specific test categories
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_api_client_properties.py -v
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_tool_registration.py -v
```

**What this tests**: All functionality with mocked HTTP responses. Fast and doesn't require a real HA instance.

### 2. MCP Inspector (Recommended for Interactive Testing)

The MCP Inspector is the official tool for testing MCP servers interactively.

#### Install MCP Inspector
```bash
npm install -g @modelcontextprotocol/inspector
```

#### Run the Inspector
```bash
# Set environment variables first
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"

# Start the inspector
mcp-inspector python -m ha_config_manager.server
```

This will:
- Start the MCP server
- Open a web interface (usually at http://localhost:5173)
- Let you interactively call tools and see responses

#### Using the Inspector
1. Open the web interface
2. Click "Connect" to connect to the server
3. Browse available tools in the left sidebar
4. Click a tool to see its schema
5. Fill in parameters and click "Call Tool"
6. View the response in real-time

**What this tests**: Real MCP protocol communication with your actual Home Assistant instance.

### 3. Direct Python Testing

Create a simple Python script to test specific functionality:

```python
# test_mcp_server.py
import asyncio
import os
from ha_config_manager.connection.api import HAAPIClient

async def test_connection():
    """Test basic connection to Home Assistant."""
    url = os.getenv("HA_URL")
    token = os.getenv("HA_TOKEN")
    
    if not url or not token:
        print("Error: HA_URL and HA_TOKEN must be set")
        return
    
    client = HAAPIClient(url, token)
    
    try:
        # Test listing files
        print("Testing list_files...")
        files = await client.list_files()
        print(f"✓ Found {len(files)} files")
        
        # Test getting states
        print("\nTesting get_states...")
        states = await client.get_states()
        print(f"✓ Found {len(states)} entities")
        
        # Test listing services
        print("\nTesting list_services...")
        services = await client.list_services()
        print(f"✓ Found {len(services)} service domains")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
```

Run it:
```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"
PYTHONPATH=src/config-manager/src .venv/bin/python test_mcp_server.py
```

**What this tests**: Direct API client functionality against your real Home Assistant instance.

### 4. Testing with Kiro (End-to-End)

The ultimate test is using the MCP server with Kiro itself.

#### Configure Kiro to Use the Server

Edit your MCP configuration file (`~/.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "ha-config-manager": {
      "command": "python",
      "args": ["-m", "ha_config_manager.server"],
      "env": {
        "HA_URL": "http://homeassistant.local:8123",
        "HA_TOKEN": "your_long_lived_access_token_here",
        "PYTHONPATH": "/path/to/kiro-power-homeassistant/src/config-manager/src"
      },
      "disabled": false
    }
  }
}
```

#### Test in Kiro

1. Restart Kiro to load the new MCP server
2. In a chat, ask Kiro to use the Home Assistant tools:
   - "List my Home Assistant configuration files"
   - "Show me the state of all my lights"
   - "What services are available in Home Assistant?"
   - "Read my configuration.yaml file"

**What this tests**: Complete end-to-end integration with Kiro as the MCP client.

### 5. Manual stdio Testing (Advanced)

Test the MCP server's stdio protocol directly:

```bash
# Set environment variables
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"

# Start the server (it reads from stdin and writes to stdout)
PYTHONPATH=src/config-manager/src python -m ha_config_manager.server
```

Then send JSON-RPC messages via stdin:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
```

**What this tests**: Raw MCP protocol implementation. Very low-level.

## Common Test Scenarios

### Test 1: Verify Server Starts
```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="test_token"
PYTHONPATH=src/config-manager/src python -c "from ha_config_manager.server import main; print('Server imports successfully')"
```

### Test 2: Verify Configuration Loading
```bash
# Should fail with clear error
unset HA_URL
PYTHONPATH=src/config-manager/src python -m ha_config_manager.server
# Expected: "HA_URL environment variable is required"

# Should succeed
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="test_token"
# Server should start without errors
```

### Test 3: Test Individual Tools
Using MCP Inspector or Python script, test each tool:

1. **list_config_files** - Should return list of files
2. **read_config_file** - Should return file content
3. **get_logs** - Should return log entries
4. **get_states** - Should return entity states
5. **call_service** - Should execute service (be careful!)
6. **render_template** - Should render Jinja2 template
7. **get_history** - Should return historical data
8. **get_config** - Should return HA configuration
9. **list_events** - Should return event types
10. **list_services** - Should return service list
11. **check_config** - Should validate configuration

### Test 4: Error Handling
Test that errors are handled gracefully:

```python
# Test with invalid token
client = HAAPIClient("http://homeassistant.local:8123", "invalid_token")
try:
    await client.get_states()
except HAAPIError as e:
    print(f"✓ Correctly caught error: {e.message}")
```

## Troubleshooting

### Server Won't Start

**Check environment variables**:
```bash
echo $HA_URL
echo $HA_TOKEN
```

**Check Python path**:
```bash
PYTHONPATH=src/config-manager/src python -c "import ha_config_manager; print('OK')"
```

### Connection Errors

**Test Home Assistant is reachable**:
```bash
curl -H "Authorization: Bearer $HA_TOKEN" $HA_URL/api/
```

**Check integration is installed**:
```bash
curl -H "Authorization: Bearer $HA_TOKEN" $HA_URL/api/ha_config_manager/files
```

### MCP Inspector Issues

**Check server is running**:
```bash
ps aux | grep ha_config_manager
```

**Check logs**:
The server logs to stderr, so you can see errors in the inspector terminal.

## Best Practices

1. **Start with automated tests** - Run the test suite first to verify basic functionality
2. **Use MCP Inspector for development** - Great for interactive testing and debugging
3. **Test with real HA instance** - Verify against your actual Home Assistant setup
4. **Test error cases** - Try invalid tokens, missing files, etc.
5. **Monitor logs** - Watch server logs for errors and warnings
6. **Test in Kiro last** - Once everything else works, test the full integration

## Quick Start Testing Workflow

```bash
# 1. Run automated tests
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/ -v

# 2. Set up environment
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"

# 3. Test with MCP Inspector
mcp-inspector python -m ha_config_manager.server

# 4. Configure in Kiro and test end-to-end
# Edit ~/.kiro/settings/mcp.json and restart Kiro
```

## Template Testing

The MCP server includes enhanced template testing capabilities with detailed error reporting, entity validation, and syntax checking.

### Template Testing Features

1. **Enhanced Error Reporting**: Line numbers, character positions, and code context for template errors
2. **Entity Validation**: Verify entity references exist before template execution
3. **Syntax Validation**: Check template syntax without executing potentially dangerous templates
4. **Multi-line Support**: Proper error reporting for multi-line templates with context

### Running Template Tests

#### Unit Tests

Test individual template validation functions:

```bash
# Run all template validator unit tests
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_validator.py -v

# Run specific test class
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_validator.py::TestExtractEntityReferences -v
```

#### Property-Based Tests

Test template functionality across randomized inputs:

```bash
# Run template validation property tests
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_validation_properties.py -v

# Run render_template property tests
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_render_template_properties.py -v

# Run multi-line template property tests
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_multiline_properties.py -v
```

Property-based tests use Hypothesis to generate random test cases and verify correctness properties hold across all inputs. Each test runs a minimum of 100 iterations.

#### Integration Tests

Test complete template workflows with mocked or real Home Assistant:

```bash
# Run with mocked Home Assistant (default)
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_integration.py -v

# Run against real Home Assistant instance
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_access_token"
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_integration.py -v
```

Integration tests verify:
- Complete validation workflows (syntax → entities → rendering)
- Error detection and reporting
- Entity validation with real/mocked HA API
- Multi-line template handling
- Error message quality and helpfulness

### Template Testing Workflows

#### Workflow 1: Validate Template Syntax Only

Check template syntax without executing it:

```python
from ha_config_manager.template_validator import validate_template_syntax

template = "{{ states('sensor.temperature') }}"
is_valid, error = validate_template_syntax(template)

if is_valid:
    print("Template syntax is valid")
else:
    print(f"Syntax error: {error['message']}")
    if 'line' in error:
        print(f"Line {error['line']}: {error['context']}")
```

#### Workflow 2: Validate Entities Before Rendering

Check that entity references exist:

```python
from ha_config_manager.template_validator import extract_entity_references
from ha_config_manager.connection.api import HAAPIClient

template = "{{ states('sensor.temperature') }}"

# Extract entity references
entities = extract_entity_references(template)
print(f"Found entities: {entities}")

# Validate entities exist in HA
client = HAAPIClient(url, token)
existing, missing = await client.validate_entities(entities)

if missing:
    print(f"Warning: Missing entities: {missing}")
```

#### Workflow 3: Complete Validation and Rendering

Full workflow with all validation steps:

```python
from ha_config_manager.connection.api import HAAPIClient

template = "{{ states('sensor.temperature') | float | round(1) }}"

client = HAAPIClient(url, token)

# Render with entity validation
result = await client.render_template(template, validate_entities=True)

if isinstance(result, dict):
    print(f"Result: {result['result']}")
    if 'warnings' in result:
        print(f"Warnings: {result['warnings']}")
else:
    print(f"Result: {result}")
```

#### Workflow 4: Handle Template Errors

Detect and report template errors with context:

```python
from ha_config_manager.template_validator import validate_template_syntax

template = """
{{ states('sensor.temp1') }}
{{ invalid syntax
{{ states('sensor.temp2') }}
"""

is_valid, error = validate_template_syntax(template)

if not is_valid:
    print(f"Error Type: {error['error_type']}")
    print(f"Message: {error['message']}")
    if 'line' in error:
        print(f"Line {error['line']}")
    if 'template_excerpt' in error:
        print("Context:")
        for line in error['template_excerpt']:
            print(f"  {line}")
```

### Testing with MCP Inspector

Test template tools interactively:

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"
mcp-inspector python -m ha_config_manager.server
```

In the inspector:

1. **Test render_template**:
   - Tool: `render_template`
   - Parameters: `{"template": "{{ states('sensor.temperature') }}", "validate_entities": true}`
   - Verify: Result includes rendered output and warnings if entities missing

2. **Test validate_template**:
   - Tool: `validate_template`
   - Parameters: `{"template": "{{ invalid syntax", "validate_entities": false}`
   - Verify: Error response includes line number and context

3. **Test entity validation**:
   - Tool: `render_template`
   - Parameters: `{"template": "{{ states('sensor.nonexistent') }}", "validate_entities": true}`
   - Verify: Warning about missing entity

### Property-Based Test Execution

Property-based tests verify correctness properties across randomized inputs:

```bash
# Run all property tests with verbose output
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_*_properties.py -v

# Run specific property test
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_validation_properties.py::test_entity_extraction_completeness -v

# Run with more iterations (default is 100)
PYTHONPATH=src/config-manager/src .venv/bin/python -m pytest src/config-manager/tests/test_template_validation_properties.py --hypothesis-iterations=1000 -v
```

Property tests verify:
- **Property 1**: Entity reference extraction completeness
- **Property 2**: Entity validation correctness
- **Property 3**: Validation before rendering
- **Property 4**: Syntax validation without execution
- **Property 5**: Error structure completeness
- **Property 6**: Undefined reference error reporting
- **Property 7**: Successful rendering returns output
- **Property 8**: Error information preservation
- **Property 9**: Multi-line line number accuracy
- **Property 10**: Multi-line context inclusion
- **Property 11**: Line break preservation
- **Property 12**: Indentation handling
- **Property 13**: YAML multi-line string handling

### Template Testing Examples

#### Example 1: Test Valid Template

```python
# test_valid_template.py
import asyncio
from ha_config_manager.connection.api import HAAPIClient

async def test_valid_template():
    client = HAAPIClient("http://homeassistant.local:8123", "your_token")
    
    template = "{{ states('sensor.temperature') | float | round(1) }}"
    result = await client.render_template(template, validate_entities=True)
    
    print(f"Result: {result}")
    await client.close()

asyncio.run(test_valid_template())
```

#### Example 2: Test Template with Syntax Error

```python
# test_syntax_error.py
from ha_config_manager.template_validator import validate_template_syntax

template = "{{ states('sensor.temp') | unknown_filter }}"
is_valid, error = validate_template_syntax(template)

if not is_valid:
    print(f"Syntax Error Detected:")
    print(f"  Type: {error['error_type']}")
    print(f"  Message: {error['message']}")
```

#### Example 3: Test Missing Entities

```python
# test_missing_entities.py
import asyncio
from ha_config_manager.connection.api import HAAPIClient
from ha_config_manager.template_validator import extract_entity_references

async def test_missing_entities():
    client = HAAPIClient("http://homeassistant.local:8123", "your_token")
    
    template = "{{ states('sensor.nonexistent') }}"
    entities = extract_entity_references(template)
    
    existing, missing = await client.validate_entities(entities)
    
    print(f"Existing: {existing}")
    print(f"Missing: {missing}")
    
    await client.close()

asyncio.run(test_missing_entities())
```

### Troubleshooting Template Tests

#### Issue: Property tests fail with "function_scoped_fixture" error

**Solution**: Add health check suppression:
```python
from hypothesis import given, settings, HealthCheck

@given(data=st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property(mock_fixture, data):
    # test code
```

#### Issue: Integration tests fail with connection errors

**Solution**: Verify Home Assistant is accessible:
```bash
curl -H "Authorization: Bearer $HA_TOKEN" $HA_URL/api/
```

#### Issue: Template rendering returns "unknown" for entities

**Cause**: Entity doesn't exist in Home Assistant

**Solution**: Check entity exists:
```bash
curl -H "Authorization: Bearer $HA_TOKEN" $HA_URL/api/states/sensor.temperature
```

## Additional Resources

- [MCP Inspector Documentation](https://github.com/modelcontextprotocol/inspector)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Home Assistant REST API Documentation](https://developers.home-assistant.io/docs/api/rest/)
- [Home Assistant Template Documentation](https://www.home-assistant.io/docs/configuration/templating/)
- [Jinja2 Template Documentation](https://jinja.palletsprojects.com/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)

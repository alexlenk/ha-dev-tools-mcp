# MCP Server Tests

This directory contains tests for the Home Assistant Configuration Manager MCP Server.

## Test Organization

- `test_config.py` - Configuration loading tests
- `test_api_client_basic.py` - Basic API client tests
- `test_api_client_properties.py` - Property-based tests for API client
- `test_api_methods.py` - API method tests
- `test_manager_cleanup.py` - Cleanup and resource management tests

## Running Tests

### All Tests

```bash
cd src/config-manager
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```

### API Client Property Tests

The API client property tests use aiohttp, which creates background threads for SSL/DNS resolution. These threads conflict with the Home Assistant test framework's strict cleanup requirements.

To run these tests, use the special pytest configuration that disables the HA plugin:

```bash
cd src/config-manager
PYTHONPATH=src .venv/bin/python -m pytest -c pytest-api.ini tests/test_api_client_properties.py -v
```

### Other Tests

All other tests can be run normally:

```bash
cd src/config-manager
PYTHONPATH=src .venv/bin/python -m pytest tests/test_config.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/test_api_client_basic.py -v
```

## Test Configuration Files

- `pyproject.toml` - Main pytest configuration for all tests
- `pytest-api.ini` - Special configuration for API client property tests (disables HA plugin)
- `conftest.py` - Pytest fixtures and configuration

## Why Two Configurations?

The Home Assistant test framework (`pytest-homeassistant-custom-component`) includes a `verify_cleanup` fixture that checks for lingering threads after each test. This is useful for HA integration tests but conflicts with aiohttp's background threads, which are properly managed but not immediately cleaned up.

The `pytest-api.ini` configuration disables the HA plugin for API client property tests, allowing them to run without cleanup conflicts.

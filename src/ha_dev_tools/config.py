"""Configuration management for Home Assistant Configuration Manager MCP Server."""

import os
from dataclasses import dataclass


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


@dataclass
class ServerConfig:
    """MCP server configuration.

    Attributes:
        ha_url: Home Assistant instance URL (must start with http:// or https://)
        ha_token: Home Assistant long-lived access token for authentication
        request_timeout: Timeout in seconds for HTTP requests (default: 30)
        max_file_size: Maximum file size in bytes for file save operations (default: 10MB)
    """
    ha_url: str
    ha_token: str
    request_timeout: int = 30
    max_file_size: int = 10 * 1024 * 1024  # 10MB default


def load_config() -> ServerConfig:
    """Load and validate configuration from environment variables.

    Reads configuration from:
    - HA_URL: Home Assistant instance URL
    - HA_TOKEN: Home Assistant long-lived access token
    - MAX_FILE_SIZE: Maximum file size in bytes (optional, default: 10MB)

    Returns:
        ServerConfig: Validated configuration object

    Raises:
        ConfigError: If required environment variables are missing or invalid

    Examples:
        >>> os.environ["HA_URL"] = "http://homeassistant.local:8123"
        >>> os.environ["HA_TOKEN"] = "eyJ0eXAiOiJKV1QiLCJhbGc..."
        >>> config = load_config()
        >>> config.ha_url
        'http://homeassistant.local:8123'
    """
    ha_url = os.getenv("HA_URL")
    ha_token = os.getenv("HA_TOKEN")
    max_file_size_str = os.getenv("MAX_FILE_SIZE")

    # Validate required environment variables
    if not ha_url:
        raise ConfigError(
            "HA_URL environment variable is required. "
            "Please set it to your Home Assistant instance URL "
            "(e.g., http://homeassistant.local:8123)"
        )

    if not ha_token:
        raise ConfigError(
            "HA_TOKEN environment variable is required. "
            "Please set it to a Home Assistant long-lived access token. "
            "You can create one in Home Assistant under Profile > Security > Long-Lived Access Tokens"
        )

    # Validate URL format
    if not ha_url.startswith(("http://", "https://")):
        raise ConfigError(
            f"HA_URL must start with http:// or https://. Got: {ha_url}"
        )

    # Parse and validate max_file_size
    max_file_size = 10 * 1024 * 1024  # 10MB default
    if max_file_size_str:
        try:
            max_file_size = int(max_file_size_str)
        except ValueError:
            raise ConfigError(
                f"MAX_FILE_SIZE must be a valid integer. Got: {max_file_size_str}"
            )

        # Validate size limits: 1MB to 100MB
        min_size = 1 * 1024 * 1024  # 1MB
        max_size = 100 * 1024 * 1024  # 100MB

        if max_file_size < min_size:
            raise ConfigError(
                f"MAX_FILE_SIZE must be at least {min_size} bytes (1MB). Got: {max_file_size}"
            )

        if max_file_size > max_size:
            raise ConfigError(
                f"MAX_FILE_SIZE must not exceed {max_size} bytes (100MB). Got: {max_file_size}"
            )

    return ServerConfig(ha_url=ha_url, ha_token=ha_token, max_file_size=max_file_size)

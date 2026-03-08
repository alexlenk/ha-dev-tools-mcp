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
    """
    ha_url: str
    ha_token: str
    request_timeout: int = 30


def load_config() -> ServerConfig:
    """Load and validate configuration from environment variables.
    
    Reads configuration from:
    - HA_URL: Home Assistant instance URL
    - HA_TOKEN: Home Assistant long-lived access token
    
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
    
    return ServerConfig(ha_url=ha_url, ha_token=ha_token)

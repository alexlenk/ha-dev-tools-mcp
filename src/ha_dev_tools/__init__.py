"""Home Assistant Configuration Manager MCP Server."""

from .config import ConfigError, ServerConfig, load_config

__version__ = "1.0.0"
__all__ = ["ConfigError", "ServerConfig", "load_config"]
"""Input validation for MCP tool parameters.

This module provides validation functions for all tool parameters to ensure
they meet security and format requirements before being processed.

Package: ha-dev-tools-mcp
"""

import re
from typing import Any, Optional


class ValidationError(Exception):
    """Exception raised when parameter validation fails.
    
    Attributes:
        message: Human-readable error message describing the validation failure
        parameter: Name of the parameter that failed validation
    """
    
    def __init__(self, message: str, parameter: str):
        super().__init__(message)
        self.message = message
        self.parameter = parameter


def validate_file_path(file_path: str) -> None:
    """Validate file_path parameter format.
    
    Ensures the file path:
    - Does not contain path traversal sequences (../)
    - Is not an absolute path (does not start with /)
    - Does not contain null bytes or other dangerous characters
    
    Args:
        file_path: The file path to validate
    
    Raises:
        ValidationError: If the file path is invalid
    
    Examples:
        >>> validate_file_path("configuration.yaml")  # OK
        >>> validate_file_path("packages/lights.yaml")  # OK
        >>> validate_file_path("../etc/passwd")  # Raises ValidationError
        >>> validate_file_path("/etc/passwd")  # Raises ValidationError
    """
    if not file_path:
        raise ValidationError("file_path cannot be empty", "file_path")
    
    # Check for path traversal sequences
    if ".." in file_path:
        raise ValidationError(
            "file_path cannot contain path traversal sequences (..)",
            "file_path"
        )
    
    # Check for absolute paths
    if file_path.startswith("/"):
        raise ValidationError(
            "file_path cannot be an absolute path",
            "file_path"
        )
    
    # Check for null bytes and other dangerous characters
    if "\x00" in file_path:
        raise ValidationError(
            "file_path cannot contain null bytes",
            "file_path"
        )
    
    # Check for Windows-style absolute paths (C:\, etc.)
    if re.match(r'^[a-zA-Z]:', file_path):
        raise ValidationError(
            "file_path cannot be an absolute path",
            "file_path"
        )


def validate_positive_integer(value: Any, parameter_name: str, min_value: int = 1, max_value: Optional[int] = None) -> None:
    """Validate that a parameter is a positive integer within bounds.
    
    Args:
        value: The value to validate
        parameter_name: Name of the parameter (for error messages)
        min_value: Minimum allowed value (default: 1)
        max_value: Maximum allowed value (optional)
    
    Raises:
        ValidationError: If the value is not a positive integer or out of bounds
    
    Examples:
        >>> validate_positive_integer(100, "lines")  # OK
        >>> validate_positive_integer(0, "lines")  # Raises ValidationError
        >>> validate_positive_integer(-5, "lines")  # Raises ValidationError
        >>> validate_positive_integer("abc", "lines")  # Raises ValidationError
        >>> validate_positive_integer(2000, "lines", max_value=1000)  # Raises ValidationError
    """
    # Check if value is a boolean (bool is a subclass of int in Python)
    if isinstance(value, bool):
        raise ValidationError(
            f"{parameter_name} must be an integer, got bool",
            parameter_name
        )
    
    # Check if value is an integer
    if not isinstance(value, int):
        raise ValidationError(
            f"{parameter_name} must be an integer, got {type(value).__name__}",
            parameter_name
        )
    
    # Check if value is within bounds
    if value < min_value:
        raise ValidationError(
            f"{parameter_name} must be at least {min_value}, got {value}",
            parameter_name
        )
    
    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{parameter_name} must be at most {max_value}, got {value}",
            parameter_name
        )


def validate_log_source(log_source: str) -> None:
    """Validate log_source parameter.
    
    Ensures the log source is one of the supported values.
    
    Args:
        log_source: The log source to validate
    
    Raises:
        ValidationError: If the log source is not supported
    
    Examples:
        >>> validate_log_source("core")  # OK
        >>> validate_log_source("invalid")  # Raises ValidationError
    """
    supported_sources = ["core"]
    
    if log_source not in supported_sources:
        raise ValidationError(
            f"log_source must be one of {supported_sources}, got '{log_source}'",
            "log_source"
        )


def validate_entity_id(entity_id: str) -> None:
    """Validate entity_id parameter format.
    
    Ensures the entity_id follows the Home Assistant format: domain.object_id
    
    Args:
        entity_id: The entity ID to validate
    
    Raises:
        ValidationError: If the entity_id format is invalid
    
    Examples:
        >>> validate_entity_id("light.living_room")  # OK
        >>> validate_entity_id("sensor.temperature")  # OK
        >>> validate_entity_id("invalid")  # Raises ValidationError
        >>> validate_entity_id("light.")  # Raises ValidationError
    """
    if not entity_id:
        raise ValidationError("entity_id cannot be empty", "entity_id")
    
    # Entity IDs must follow the format: domain.object_id
    if "." not in entity_id:
        raise ValidationError(
            "entity_id must be in format 'domain.object_id' (e.g., 'light.living_room')",
            "entity_id"
        )
    
    parts = entity_id.split(".", 1)
    domain = parts[0]
    object_id = parts[1]
    
    if not domain or not object_id:
        raise ValidationError(
            "entity_id must have both domain and object_id (e.g., 'light.living_room')",
            "entity_id"
        )
    
    # Domain and object_id should only contain lowercase letters, numbers, and underscores
    if not re.match(r'^[a-z0-9_]+$', domain):
        raise ValidationError(
            "entity_id domain must contain only lowercase letters, numbers, and underscores",
            "entity_id"
        )
    
    if not re.match(r'^[a-z0-9_]+$', object_id):
        raise ValidationError(
            "entity_id object_id must contain only lowercase letters, numbers, and underscores",
            "entity_id"
        )


def validate_domain(domain: str) -> None:
    """Validate service domain parameter.
    
    Ensures the domain follows Home Assistant naming conventions.
    
    Args:
        domain: The service domain to validate
    
    Raises:
        ValidationError: If the domain format is invalid
    
    Examples:
        >>> validate_domain("light")  # OK
        >>> validate_domain("homeassistant")  # OK
        >>> validate_domain("Invalid")  # Raises ValidationError
        >>> validate_domain("")  # Raises ValidationError
    """
    if not domain:
        raise ValidationError("domain cannot be empty", "domain")
    
    # Domain should only contain lowercase letters, numbers, and underscores
    if not re.match(r'^[a-z0-9_]+$', domain):
        raise ValidationError(
            "domain must contain only lowercase letters, numbers, and underscores",
            "domain"
        )


def validate_service(service: str) -> None:
    """Validate service name parameter.
    
    Ensures the service name follows Home Assistant naming conventions.
    
    Args:
        service: The service name to validate
    
    Raises:
        ValidationError: If the service name format is invalid
    
    Examples:
        >>> validate_service("turn_on")  # OK
        >>> validate_service("reload")  # OK
        >>> validate_service("Invalid")  # Raises ValidationError
        >>> validate_service("")  # Raises ValidationError
    """
    if not service:
        raise ValidationError("service cannot be empty", "service")
    
    # Service name should only contain lowercase letters, numbers, and underscores
    if not re.match(r'^[a-z0-9_]+$', service):
        raise ValidationError(
            "service must contain only lowercase letters, numbers, and underscores",
            "service"
        )


def validate_required_parameter(value: Any, parameter_name: str) -> None:
    """Validate that a required parameter is present.
    
    Args:
        value: The parameter value (may be None)
        parameter_name: Name of the parameter (for error messages)
    
    Raises:
        ValidationError: If the parameter is None or missing
    
    Examples:
        >>> validate_required_parameter("value", "file_path")  # OK
        >>> validate_required_parameter(None, "file_path")  # Raises ValidationError
    """
    if value is None:
        raise ValidationError(
            f"Required parameter '{parameter_name}' is missing",
            parameter_name
        )


def validate_template(template: str) -> None:
    """Validate template parameter.
    
    Ensures the template is a non-empty string.
    
    Args:
        template: The template string to validate
    
    Raises:
        ValidationError: If the template is invalid
    
    Examples:
        >>> validate_template("{{ states('sensor.temp') }}")  # OK
        >>> validate_template("")  # Raises ValidationError
        >>> validate_template(None)  # Raises ValidationError
        >>> validate_template(123)  # Raises ValidationError
    """
    if template is None:
        raise ValidationError("template cannot be None", "template")
    
    if not isinstance(template, str):
        raise ValidationError(
            f"template must be a string, got {type(template).__name__}",
            "template"
        )
    
    if not template.strip():
        raise ValidationError("template cannot be empty", "template")


def validate_boolean(value: Any, parameter_name: str) -> None:
    """Validate that a parameter is a boolean.
    
    Args:
        value: The value to validate
        parameter_name: Name of the parameter (for error messages)
    
    Raises:
        ValidationError: If the value is not a boolean
    
    Examples:
        >>> validate_boolean(True, "validate_entities")  # OK
        >>> validate_boolean(False, "validate_entities")  # OK
        >>> validate_boolean("true", "validate_entities")  # Raises ValidationError
        >>> validate_boolean(1, "validate_entities")  # Raises ValidationError
        >>> validate_boolean(None, "validate_entities")  # Raises ValidationError
    """
    if not isinstance(value, bool):
        raise ValidationError(
            f"{parameter_name} must be a boolean, got {type(value).__name__}",
            parameter_name
        )

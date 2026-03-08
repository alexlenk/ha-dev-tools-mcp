"""Configuration Manager implementation."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from yaml.constructor import ConstructorError
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from .connection import LocalHAConnection, HAAPIConnection
from .types import (
    ConfigFile,
    ConfigFileType,
    ConfigError,
    HAConnection,
    HAInstance,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
)

# Configure logging
logger = logging.getLogger(__name__)


class HAConfigurationManager:
    """Home Assistant Configuration Manager."""
    
    def __init__(self):
        self._connections: Dict[str, HAConnection] = {}
        self._instances: Dict[str, HAInstance] = {}
        self._current_instance_id: Optional[str] = None
    
    async def add_instance(self, instance: HAInstance) -> None:
        """Add HA instance to manager."""
        self._instances[instance.id] = instance
        
        # Create appropriate connection based on type
        if instance.connection_type.value == "local":
            connection = LocalHAConnection(
                instance.id,
                instance.connection_config.url
            )
        elif instance.connection_type.value == "remote_api":
            # Use API-based connection for remote instances
            access_token = instance.connection_config.access_token
            if not access_token:
                raise ConfigError(
                    "Access token required for remote API connections",
                    "MISSING_ACCESS_TOKEN",
                    instance.id
                )
            
            connection = HAAPIConnection(
                instance.id,
                instance.connection_config.url,
                access_token
            )
        else:
            raise ConfigError(
                f"Unsupported connection type: {instance.connection_type.value}",
                "UNSUPPORTED_CONNECTION_TYPE",
                instance.id
            )
        
        self._connections[instance.id] = connection
        
        # Establish connection immediately
        await connection.connect()
    
    async def list_config_files(self, instance_id: str) -> List[ConfigFile]:
        """List configuration files in HA instance."""
        connection = self._get_connection(instance_id)
        config_files: List[ConfigFile] = []
        
        try:
            # Common HA configuration directories and files
            directories = [".", "packages", "automations", "scripts"]
            
            for directory in directories:
                try:
                    files = await connection.list_files(directory)
                    
                    for file_path in files:
                        try:
                            stats = await self._get_file_stats(connection, file_path)
                            config_files.append(ConfigFile(
                                path=file_path,
                                type=self._determine_file_type(file_path),
                                last_modified=stats["last_modified"],
                                size=stats["size"]
                            ))
                        except Exception:
                            # Skip files that can't be processed
                            continue
                        
                except Exception:
                    # Directory might not exist, continue with others
                    continue
            
            # Sort files by path for consistent ordering
            config_files.sort(key=lambda f: f.path)
            return config_files
            
        except Exception as e:
            raise ConfigError(
                f"Failed to list configuration files: {e}",
                "CONFIG_LIST_FAILED",
                instance_id
            )
    
    async def read_config_file(self, instance_id: str, file_path: str) -> str:
        """Read configuration file content."""
        connection = self._get_connection(instance_id)
        
        try:
            return await connection.read_file(file_path)
        except Exception as e:
            raise ConfigError(
                f"Failed to read configuration file {file_path}: {e}",
                "CONFIG_READ_FAILED",
                instance_id,
                file_path
            )
    
    async def write_config_file(
        self, instance_id: str, file_path: str, content: str
    ) -> None:
        """Write configuration file with validation and automatic backup."""
        connection = self._get_connection(instance_id)
        
        # Validate YAML before writing
        validation = await self.validate_yaml(content)
        if not validation.valid:
            error_messages = [error.message for error in validation.errors]
            raise ConfigError(
                f"Invalid YAML content: {', '.join(error_messages)}",
                "INVALID_YAML",
                instance_id,
                file_path
            )
        
        try:
            # Create automatic backup if file exists
            try:
                existing_content = await connection.read_file(file_path)
                if existing_content.strip():  # Only backup if file has content
                    await self.create_backup(instance_id, file_path)
            except Exception:
                # File doesn't exist or can't be read, no backup needed
                pass
            
            # Write the new content
            await connection.write_file(file_path, content)
            
        except Exception as e:
            raise ConfigError(
                f"Failed to write configuration file {file_path}: {e}",
                "CONFIG_WRITE_FAILED",
                instance_id,
                file_path
            )
    
    async def validate_yaml(self, content: str) -> ValidationResult:
        """Validate YAML content with HA schema compliance."""
        result = ValidationResult(valid=True, errors=[], warnings=[])
        
        try:
            # Parse YAML to check syntax
            parsed_data = yaml.safe_load(content)
            
            # Basic HA schema validation
            if parsed_data is not None:
                await self._validate_ha_schema(parsed_data, result)
                
        except (ParserError, ScannerError, ConstructorError) as e:
            result.valid = False
            
            # Extract line and column if available
            line = getattr(e, 'problem_mark', None)
            line_num = line.line + 1 if line else None
            col_num = line.column + 1 if line else None
            
            result.errors.append(ValidationError(
                line=line_num,
                column=col_num,
                message=str(e),
                code="YAML_SYNTAX_ERROR",
                severity=ValidationSeverity.ERROR
            ))
        except Exception as e:
            result.valid = False
            result.errors.append(ValidationError(
                message=f"Unexpected validation error: {e}",
                code="VALIDATION_ERROR",
                severity=ValidationSeverity.ERROR
            ))
        
        return result
    
    async def _validate_ha_schema(self, data: any, result: ValidationResult) -> None:
        """Validate Home Assistant specific schema rules."""
        if not isinstance(data, dict):
            return
        
        # Check for common HA configuration sections
        ha_sections = ['homeassistant', 'automation', 'script', 'sensor', 'binary_sensor', 'switch']
        
        # Validate homeassistant section if present
        if 'homeassistant' in data:
            ha_config = data['homeassistant']
            if isinstance(ha_config, dict):
                # Check required fields
                if 'name' not in ha_config:
                    result.warnings.append(ValidationWarning(
                        message="homeassistant section missing 'name' field",
                        code="HA_MISSING_NAME",
                        suggestion="Add 'name: Your Home Name' to homeassistant section"
                    ))
                
                # Validate latitude/longitude if present
                if 'latitude' in ha_config:
                    try:
                        lat = float(ha_config['latitude'])
                        if not (-90 <= lat <= 90):
                            result.errors.append(ValidationError(
                                message="latitude must be between -90 and 90",
                                code="HA_INVALID_LATITUDE",
                                severity=ValidationSeverity.ERROR
                            ))
                            result.valid = False
                    except (ValueError, TypeError):
                        result.errors.append(ValidationError(
                            message="latitude must be a valid number",
                            code="HA_INVALID_LATITUDE_TYPE",
                            severity=ValidationSeverity.ERROR
                        ))
                        result.valid = False
                
                if 'longitude' in ha_config:
                    try:
                        lon = float(ha_config['longitude'])
                        if not (-180 <= lon <= 180):
                            result.errors.append(ValidationError(
                                message="longitude must be between -180 and 180",
                                code="HA_INVALID_LONGITUDE",
                                severity=ValidationSeverity.ERROR
                            ))
                            result.valid = False
                    except (ValueError, TypeError):
                        result.errors.append(ValidationError(
                            message="longitude must be a valid number",
                            code="HA_INVALID_LONGITUDE_TYPE",
                            severity=ValidationSeverity.ERROR
                        ))
                        result.valid = False
        
        # Validate automation structure if present
        if 'automation' in data:
            await self._validate_automation_schema(data['automation'], result)
    
    async def _validate_automation_schema(self, automations: any, result: ValidationResult) -> None:
        """Validate automation schema."""
        if not isinstance(automations, list):
            if isinstance(automations, dict):
                automations = [automations]
            else:
                result.errors.append(ValidationError(
                    message="automation must be a list or dictionary",
                    code="HA_INVALID_AUTOMATION_TYPE",
                    severity=ValidationSeverity.ERROR
                ))
                result.valid = False
                return
        
        for i, automation in enumerate(automations):
            if not isinstance(automation, dict):
                result.errors.append(ValidationError(
                    message=f"automation[{i}] must be a dictionary",
                    code="HA_INVALID_AUTOMATION_ITEM",
                    severity=ValidationSeverity.ERROR
                ))
                result.valid = False
                continue
            
            # Check required fields
            if 'trigger' not in automation:
                result.errors.append(ValidationError(
                    message=f"automation[{i}] missing required 'trigger' field",
                    code="HA_MISSING_TRIGGER",
                    severity=ValidationSeverity.ERROR
                ))
                result.valid = False
            
            if 'action' not in automation:
                result.errors.append(ValidationError(
                    message=f"automation[{i}] missing required 'action' field",
                    code="HA_MISSING_ACTION",
                    severity=ValidationSeverity.ERROR
                ))
                result.valid = False
            
            # Recommend alias for better debugging
            if 'alias' not in automation:
                result.warnings.append(ValidationWarning(
                    message=f"automation[{i}] missing 'alias' field",
                    code="HA_MISSING_ALIAS",
                    suggestion="Add 'alias: Descriptive Name' for easier debugging"
                ))
    
    async def create_backup(self, instance_id: str, file_path: str) -> str:
        """Create backup of configuration file."""
        connection = self._get_connection(instance_id)
        
        try:
            content = await connection.read_file(file_path)
            timestamp = datetime.now().isoformat().replace(":", "-")
            backup_path = f"{file_path}.backup.{timestamp}"
            
            await connection.write_file(backup_path, content)
            return backup_path
            
        except Exception as e:
            raise ConfigError(
                f"Failed to create backup for {file_path}: {e}",
                "BACKUP_FAILED",
                instance_id,
                file_path
            )
    
    async def restore_backup(self, instance_id: str, backup_id: str) -> None:
        """Restore file from backup."""
        connection = self._get_connection(instance_id)
        
        try:
            backup_content = await connection.read_file(backup_id)
            
            # Extract original path from backup filename
            original_path = backup_id.split(".backup.")[0]
            
            await connection.write_file(original_path, backup_content)
            
        except Exception as e:
            raise ConfigError(
                f"Failed to restore backup {backup_id}: {e}",
                "RESTORE_FAILED",
                instance_id
            )
    
    async def switch_instance(self, instance_id: str) -> None:
        """Switch to different HA instance."""
        if instance_id not in self._instances:
            raise ConfigError(
                f"Instance {instance_id} not found",
                "INSTANCE_NOT_FOUND"
            )
        
        connection = self._connections.get(instance_id)
        if connection and not connection.is_connected:
            await connection.connect()
        
        self._current_instance_id = instance_id
    
    async def list_instances(self) -> List[HAInstance]:
        """List all configured HA instances."""
        return list(self._instances.values())
    
    def _get_connection(self, instance_id: str) -> HAConnection:
        """Get connection for instance."""
        connection = self._connections.get(instance_id)
        if not connection:
            raise ConfigError(
                f"No connection found for instance {instance_id}",
                "CONNECTION_NOT_FOUND",
                instance_id
            )
        return connection
    
    async def _get_file_stats(
        self, connection: HAConnection, file_path: str
    ) -> Dict[str, any]:
        """Get file statistics."""
        try:
            # For local connections, get actual file stats
            if hasattr(connection, 'base_path'):
                full_path = connection.base_path / file_path
                if full_path.exists():
                    stat = full_path.stat()
                    return {
                        "last_modified": datetime.fromtimestamp(stat.st_mtime),
                        "size": stat.st_size
                    }
            
            # Fallback for other connection types or if file doesn't exist
            return {
                "last_modified": datetime.now(),
                "size": 0
            }
        except Exception:
            # Return defaults if stats can't be retrieved
            return {
                "last_modified": datetime.now(),
                "size": 0
            }
    
    def _determine_file_type(self, file_path: str) -> ConfigFileType:
        """Determine configuration file type from path."""
        path_lower = file_path.lower()
        
        if "automation" in path_lower:
            return ConfigFileType.AUTOMATION
        elif "script" in path_lower:
            return ConfigFileType.SCRIPT
        elif "package" in path_lower:
            return ConfigFileType.PACKAGE
        else:
            return ConfigFileType.CONFIGURATION
    async def close(self) -> None:
        """Close all connections and clean up resources.

        This should be called when the manager is no longer needed to ensure
        proper cleanup of all HTTP sessions and connections.
        """
        for connection in self._connections.values():
            try:
                if hasattr(connection, 'disconnect') and callable(getattr(connection, 'disconnect', None)):
                    await connection.disconnect()
                elif hasattr(connection, 'close') and callable(getattr(connection, 'close', None)):
                    await connection.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        self._connections.clear()
        self._instances.clear()
        self._current_instance_id = None

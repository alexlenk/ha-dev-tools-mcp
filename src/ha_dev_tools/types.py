"""Type definitions for Home Assistant Configuration Manager."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel


class ConnectionType(str, Enum):
    """Types of HA connections."""
    LOCAL = "local"
    REMOTE_API = "remote_api"
    CLOUD = "cloud"


class AuthMethod(str, Enum):
    """Authentication methods."""
    TOKEN = "token"
    PASSWORD = "password"
    CERTIFICATE = "certificate"


class ConfigFileType(str, Enum):
    """Types of configuration files."""
    AUTOMATION = "automation"
    SCRIPT = "script"
    PACKAGE = "package"
    CONFIGURATION = "configuration"


class ValidationSeverity(str, Enum):
    """Validation message severity levels."""
    ERROR = "error"
    WARNING = "warning"


class TunnelConfig(BaseModel):
    """Tunnel configuration for remote connections."""
    type: str  # cloudflare, vpn, ssh
    config: Dict[str, Any]


class ProxyConfig(BaseModel):
    """Proxy configuration."""
    host: str
    port: int
    auth: Optional[Dict[str, str]] = None


class EncryptedCredentials(BaseModel):
    """Encrypted credential storage."""
    encrypted_data: str
    key_id: str
    algorithm: str


class ConnectionConfig(BaseModel):
    """Connection configuration for HA instances."""
    url: str
    port: Optional[int] = None
    ssl: Optional[bool] = None
    access_token: Optional[str] = None  # For API connections
    tunnel_config: Optional[TunnelConfig] = None
    proxy_config: Optional[ProxyConfig] = None


class AuthConfig(BaseModel):
    """Authentication configuration."""
    method: AuthMethod
    credentials: EncryptedCredentials
    token_expiry: Optional[datetime] = None


class InstanceCapabilities(BaseModel):
    """Capabilities of an HA instance."""
    has_file_access: bool
    has_addons: bool
    has_custom_components: bool
    supported_apis: List[str]
    file_editor_available: bool = False
    custom_component_available: bool = False


class HAInstance(BaseModel):
    """Home Assistant instance configuration."""
    id: str
    name: str
    connection_type: ConnectionType
    connection_config: ConnectionConfig
    auth_config: AuthConfig
    capabilities: InstanceCapabilities


class ConfigFile(BaseModel):
    """Configuration file metadata."""
    path: str
    type: ConfigFileType
    last_modified: datetime
    size: int


class ValidationError(BaseModel):
    """YAML validation error."""
    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    code: str
    severity: ValidationSeverity


class ValidationWarning(BaseModel):
    """YAML validation warning."""
    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    code: str
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of YAML validation."""
    valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationWarning]


class ConfigError(Exception):
    """Configuration management error."""
    
    def __init__(
        self,
        message: str,
        code: str,
        instance_id: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.code = code
        self.instance_id = instance_id
        self.file_path = file_path
        self.details = details or {}


class ConnectionError(Exception):
    """Connection error."""
    
    def __init__(
        self,
        message: str,
        code: str,
        instance_id: str,
        retryable: bool = True
    ):
        super().__init__(message)
        self.code = code
        self.instance_id = instance_id
        self.retryable = retryable


class HAConnection(Protocol):
    """Protocol for HA connections."""
    
    instance_id: str
    is_connected: bool
    
    async def connect(self) -> None:
        """Establish connection to HA instance."""
        ...
    
    async def disconnect(self) -> None:
        """Disconnect from HA instance."""
        ...
    
    async def list_files(self, directory: str) -> List[str]:
        """List files in directory."""
        ...
    
    async def read_file(self, file_path: str) -> str:
        """Read file content."""
        ...
    
    async def write_file(self, file_path: str, content: str) -> None:
        """Write file content."""
        ...
    
    async def ping(self) -> bool:
        """Check connection health."""
        ...


class ConfigurationManager(Protocol):
    """Protocol for configuration management."""
    
    async def list_config_files(self, instance_id: str) -> List[ConfigFile]:
        """List configuration files."""
        ...
    
    async def read_config_file(self, instance_id: str, file_path: str) -> str:
        """Read configuration file."""
        ...
    
    async def write_config_file(
        self, instance_id: str, file_path: str, content: str
    ) -> None:
        """Write configuration file."""
        ...
    
    async def validate_yaml(self, content: str) -> ValidationResult:
        """Validate YAML content."""
        ...
    
    async def create_backup(self, instance_id: str, file_path: str) -> str:
        """Create backup of file."""
        ...
    
    async def restore_backup(self, instance_id: str, backup_id: str) -> None:
        """Restore file from backup."""
        ...
    
    async def switch_instance(self, instance_id: str) -> None:
        """Switch to different HA instance."""
        ...
    
    async def list_instances(self) -> List[HAInstance]:
        """List available HA instances."""
        ...


# File save related types

class SaveErrorCode(str, Enum):
    """Error codes for file save operations."""
    
    # Parameter validation
    MUTUALLY_EXCLUSIVE = "MUTUALLY_EXCLUSIVE_PARAMETERS"
    INVALID_PATH = "INVALID_PATH"
    
    # Security
    PATH_TRAVERSAL = "PATH_TRAVERSAL_DETECTED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    
    # File system
    DISK_SPACE = "INSUFFICIENT_DISK_SPACE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    WRITE_FAILED = "WRITE_FAILED"


@dataclass
class SaveResult:
    """Result of a file save operation."""
    local_path: str
    file_size: int
    remote_path: str


@dataclass
class SaveConfig:
    """Configuration for file save feature."""
    max_file_size: int = 10 * 1024 * 1024  # 10MB default
    max_file_size_limit: int = 100 * 1024 * 1024  # 100MB absolute max

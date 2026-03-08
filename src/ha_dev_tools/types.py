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


# Download-related types

class DownloadErrorCode(str, Enum):
    """Error codes for download operations."""
    
    # Parameter validation
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    MUTUALLY_EXCLUSIVE = "MUTUALLY_EXCLUSIVE_PARAMETERS"
    BATCH_SIZE_EXCEEDED = "BATCH_SIZE_EXCEEDED"
    
    # Security
    INVALID_DOWNLOAD_DIR = "INVALID_DOWNLOAD_DIR"
    PATH_TRAVERSAL = "PATH_TRAVERSAL_DETECTED"
    OUTSIDE_CONFIG_DIR = "OUTSIDE_CONFIG_DIR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    
    # File system
    DISK_SPACE = "INSUFFICIENT_DISK_SPACE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    
    # Download
    NETWORK_ERROR = "NETWORK_ERROR"
    HASH_MISMATCH = "HASH_MISMATCH"
    COMPRESSION_ERROR = "COMPRESSION_ERROR"
    REGISTRY_ERROR = "REGISTRY_ERROR"
    FILE_CHANGED = "FILE_CHANGED_DURING_RESUME"


@dataclass
class DownloadResult:
    """Result of a single file download."""
    local_path: str
    file_size: int
    content_hash: str
    remote_path: str
    compressed: bool
    compression_ratio: Optional[float]
    download_time: float
    timestamp: datetime


@dataclass
class DownloadFailure:
    """Information about a failed download."""
    remote_path: str
    error_code: str
    error_message: str


@dataclass
class BatchDownloadResult:
    """Result of a batch download operation."""
    successful: List[DownloadResult]
    failed: List[DownloadFailure]
    total_size: int
    total_time: float


@dataclass
class DownloadMetadata:
    """Metadata tracked for each download."""
    local_path: str
    remote_path: str
    file_size: int
    content_hash: str
    timestamp: datetime
    compressed: bool
    compression_ratio: Optional[float]
    exists: bool  # Whether file still exists on disk


@dataclass
class CleanupResult:
    """Result of cleanup operation."""
    removed_count: int
    freed_bytes: int
    errors: List[str]


@dataclass
class DownloadConfig:
    """Configuration for download feature."""
    download_dir: Path
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    compression_threshold: float = 0.10  # 10% minimum reduction
    partial_download_ttl: int = 1  # hours
    registry_path: Optional[Path] = None
    
    def __post_init__(self):
        """Set default registry path if not provided."""
        if self.registry_path is None:
            self.registry_path = self.download_dir / ".download_registry.json"

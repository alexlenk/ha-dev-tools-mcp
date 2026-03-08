"""Local Home Assistant connection implementation."""

from pathlib import Path
from typing import List

import aiofiles

from ..types import ConnectionError


class LocalHAConnection:
    """Local filesystem connection to Home Assistant."""
    
    def __init__(self, instance_id: str, base_path: str):
        self.instance_id = instance_id
        self.base_path = Path(base_path).resolve()
        self.is_connected = False
    
    async def connect(self) -> None:
        """Connect to local HA instance."""
        try:
            # Verify base path exists and is accessible
            if not self.base_path.exists():
                raise ConnectionError(
                    f"Base path does not exist: {self.base_path}",
                    "PATH_NOT_FOUND",
                    self.instance_id,
                    False
                )
            
            # Check for configuration.yaml to confirm it's an HA instance
            config_path = self.base_path / "configuration.yaml"
            if not config_path.exists():
                raise ConnectionError(
                    f"No configuration.yaml found at {self.base_path}",
                    "NOT_HA_INSTANCE",
                    self.instance_id,
                    False
                )
            
            self.is_connected = True
            
        except OSError as e:
            raise ConnectionError(
                f"Failed to access HA instance at {self.base_path}: {e}",
                "CONNECTION_FAILED",
                self.instance_id,
                True
            )
    
    async def disconnect(self) -> None:
        """Disconnect from HA instance."""
        self.is_connected = False
    
    async def list_files(self, directory: str) -> List[str]:
        """List YAML files in directory."""
        self._ensure_connected()
        
        try:
            full_path = self.base_path / directory
            if not full_path.exists():
                return []
            
            yaml_files = []
            for item in full_path.iterdir():
                if item.is_file() and item.suffix in ['.yaml', '.yml']:
                    # Return relative path from base
                    rel_path = item.relative_to(self.base_path)
                    yaml_files.append(str(rel_path))
            
            return yaml_files
            
        except OSError as e:
            raise ConnectionError(
                f"Failed to list files in {directory}: {e}",
                "FILE_LIST_FAILED",
                self.instance_id,
                True
            )
    
    async def read_file(self, file_path: str) -> str:
        """Read file content."""
        self._ensure_connected()
        
        try:
            full_path = self.base_path / file_path
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                return await f.read()
                
        except OSError as e:
            raise ConnectionError(
                f"Failed to read file {file_path}: {e}",
                "FILE_READ_FAILED",
                self.instance_id,
                True
            )
    
    async def write_file(self, file_path: str, content: str) -> None:
        """Write file content."""
        self._ensure_connected()
        
        try:
            full_path = self.base_path / file_path
            
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                await f.write(content)
                
        except OSError as e:
            raise ConnectionError(
                f"Failed to write file {file_path}: {e}",
                "FILE_WRITE_FAILED",
                self.instance_id,
                False
            )
    
    async def ping(self) -> bool:
        """Check if connection is healthy."""
        try:
            return self.base_path.exists()
        except OSError:
            return False
    
    def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self.is_connected:
            raise ConnectionError(
                "Connection not established. Call connect() first.",
                "NOT_CONNECTED",
                self.instance_id,
                True
            )
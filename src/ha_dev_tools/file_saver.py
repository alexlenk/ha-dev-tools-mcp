"""File saver for saving large files to local temporary directory."""

import tempfile
from pathlib import Path

import aiofiles

from .types import SaveResult
from .path_validator import SecurityError


class FileSaver:
    """Handles saving files to local temporary directory."""

    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB default
        """
        Initialize file saver.

        Args:
            max_file_size: Maximum file size in bytes (default 10MB)
        """
        self.max_file_size = max_file_size
        self.temp_dir = Path(tempfile.gettempdir()) / "ha-dev-tools"

    async def save_file(self, remote_path: str, content: str) -> SaveResult:
        """
        Save file content to local temporary directory.

        Args:
            remote_path: Original file path on HA instance (e.g., "config/automations.yaml")
            content: File content as string

        Returns:
            SaveResult with local path and file size

        Raises:
            SecurityError: If path validation fails or file too large
            IOError: If file write fails
        """
        # Validate file size
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self.max_file_size:
            raise SecurityError(
                f"File size {len(content_bytes)} exceeds limit {self.max_file_size}"
            )

        # Sanitize path
        sanitized_path = self._sanitize_path(remote_path)

        # Create local path mirroring remote structure
        local_path = self.temp_dir / sanitized_path

        # Create parent directories
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file (newline='' preserves original line endings)
        async with aiofiles.open(local_path, "w", encoding="utf-8", newline="") as f:
            await f.write(content)

        return SaveResult(
            local_path=str(local_path),
            file_size=len(content_bytes),
            remote_path=remote_path,
        )

    def _sanitize_path(self, remote_path: str) -> str:
        """
        Sanitize remote path to prevent traversal attacks.

        Args:
            remote_path: Original remote path

        Returns:
            Sanitized path safe for local filesystem

        Raises:
            SecurityError: If path contains traversal sequences
        """
        # Remove leading slashes
        path = remote_path.lstrip("/")

        # Check for traversal sequences
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            raise SecurityError(f"Invalid path: {remote_path}")

        # Normalize path separators
        path = path.replace("\\", "/")

        return path

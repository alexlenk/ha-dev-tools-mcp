"""File uploader for uploading local workspace files to Home Assistant."""

import hashlib
from pathlib import Path
from typing import Optional

import aiofiles

from .types import UploadResult


class FileUploader:
    """Reads a local file, validates it, uploads to HA, and returns result."""

    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        """
        Initialize file uploader.

        Args:
            max_file_size: Maximum file size in bytes (default 10MB)
        """
        self.max_file_size = max_file_size

    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        api_client,
        validate_yaml: bool = True,
        expected_hash: Optional[str] = None,
    ) -> UploadResult:
        """
        Upload a local file to Home Assistant.

        Reads the file from the local workspace, validates size, computes
        a SHA-256 checksum, and uploads via the api_client.

        Args:
            local_path: Path to the local file
            remote_path: Target path on Home Assistant
            api_client: HAAPIClient instance with write_file method
            validate_yaml: Validate YAML syntax before upload (default True)
            expected_hash: Expected remote hash for conflict detection

        Returns:
            UploadResult with paths, size, checksum, and write response

        Raises:
            FileNotFoundError: If local file does not exist
            ValueError: If file exceeds max_file_size
        """
        path = Path(local_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        if not path.is_file():
            raise FileNotFoundError(f"Path is not a file: {local_path}")

        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(
                f"File too large: {file_size} bytes exceeds "
                f"limit of {self.max_file_size} bytes"
            )

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()

        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

        result = await api_client.write_file(
            file_path=remote_path,
            content=content,
            expected_hash=expected_hash,
            validate_before_write=validate_yaml,
        )

        return UploadResult(
            local_path=str(path),
            remote_path=remote_path,
            file_size=file_size,
            checksum=checksum,
            verified=True,
            write_result=result,
        )

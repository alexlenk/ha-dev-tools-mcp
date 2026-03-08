"""Path validation for download security."""

from pathlib import Path
from typing import Tuple, Optional


class PathValidator:
    """Validates download paths for security."""
    
    @staticmethod
    def validate_download_dir(path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate download directory is in allowed location.
        
        Args:
            path: Path to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        # Must be under user's home directory or explicitly allowed paths
        allowed_roots = [
            Path.home(),
            Path("/tmp"),  # For testing
        ]
        
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            return False, f"Cannot resolve path: {e}"
        
        for root in allowed_roots:
            try:
                resolved.relative_to(root)
                return True, None
            except ValueError:
                continue
        
        allowed_paths_str = ', '.join(str(r) for r in allowed_roots)
        return False, f"Download directory must be under: {allowed_paths_str}"
    
    @staticmethod
    def sanitize_remote_path(remote_path: str) -> Tuple[str, bool]:
        """
        Sanitize remote path to prevent traversal attacks.
        
        Args:
            remote_path: Remote file path to sanitize
            
        Returns:
            (sanitized_path, was_modified) tuple
        """
        # Remove any path traversal sequences
        original = remote_path
        sanitized = remote_path.replace("../", "").replace("..\\", "")
        sanitized = sanitized.lstrip("/\\")
        
        return sanitized, sanitized != original

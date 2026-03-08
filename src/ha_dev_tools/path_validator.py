"""Path validation for file save security."""


class SecurityError(Exception):
    """Security-related error for file operations."""

    pass


class PathValidator:
    """Validates file paths for security."""

    @staticmethod
    def sanitize_remote_path(remote_path: str) -> str:
        """
        Sanitize remote path to prevent traversal attacks.

        Args:
            remote_path: Remote file path to sanitize

        Returns:
            Sanitized path safe for local filesystem

        Raises:
            SecurityError: If path contains traversal sequences
        """
        # Strip leading slashes
        path = remote_path.lstrip("/")

        # Check for traversal sequences
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            raise SecurityError(f"Invalid path: {remote_path}")

        # Normalize path separators
        path = path.replace("\\", "/")

        return path

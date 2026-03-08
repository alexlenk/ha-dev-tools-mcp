"""
Conflict resolution utilities for Home Assistant configuration files.

This module provides utilities for detecting version conflicts and generating
diffs between local and remote file versions.
"""

import difflib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ConflictType(Enum):
    """Types of version conflicts."""
    REMOTE_NEWER = "remote_newer"
    BOTH_MODIFIED = "both_modified"
    LOCAL_DELETED = "local_deleted"
    NO_CONFLICT = "no_conflict"


@dataclass
class FileMetadata:
    """Metadata for a file version."""
    path: str
    content_hash: str
    modified_at: str  # ISO 8601 timestamp
    size: Optional[int] = None


@dataclass
class ConflictInfo:
    """Information about a detected version conflict."""
    file_path: str
    local_hash: str
    local_modified: str
    remote_hash: str
    remote_modified: str
    conflict_type: ConflictType

    def has_conflict(self) -> bool:
        """Check if there is an actual conflict."""
        return self.conflict_type != ConflictType.NO_CONFLICT


@dataclass
class FileDiff:
    """Diff information between two file versions."""
    file_path: str
    local_content: str
    remote_content: str
    unified_diff: str
    conflict_lines: List[int]

    def has_differences(self) -> bool:
        """Check if there are any differences between versions."""
        return len(self.conflict_lines) > 0


def detect_conflict(
    local_metadata: FileMetadata,
    remote_metadata: FileMetadata
) -> ConflictInfo:
    """
    Detect version conflicts between local and remote file metadata.

    Args:
        local_metadata: Metadata for the local file version
        remote_metadata: Metadata for the remote file version

    Returns:
        ConflictInfo object describing the conflict status

    Property: For any file, if the remote hash differs from the local hash,
              a version conflict should be detected.
    """
    # Compare hashes first (most reliable indicator)
    hashes_match = local_metadata.content_hash == remote_metadata.content_hash

    if hashes_match:
        # No conflict if hashes match
        conflict_type = ConflictType.NO_CONFLICT
    else:
        # Hashes differ - determine conflict type
        try:
            local_time = datetime.fromisoformat(local_metadata.modified_at.replace('Z', '+00:00'))
            remote_time = datetime.fromisoformat(remote_metadata.modified_at.replace('Z', '+00:00'))

            if remote_time > local_time:
                # Remote is newer
                conflict_type = ConflictType.REMOTE_NEWER
            else:
                # Both modified (local is newer or same time but different content)
                conflict_type = ConflictType.BOTH_MODIFIED
        except (ValueError, AttributeError):
            # If timestamp parsing fails, assume both modified
            conflict_type = ConflictType.BOTH_MODIFIED

    return ConflictInfo(
        file_path=local_metadata.path,
        local_hash=local_metadata.content_hash,
        local_modified=local_metadata.modified_at,
        remote_hash=remote_metadata.content_hash,
        remote_modified=remote_metadata.modified_at,
        conflict_type=conflict_type
    )


def generate_diff(
    local_content: str,
    remote_content: str,
    file_path: str = "file"
) -> FileDiff:
    """
    Generate a unified diff between local and remote file content.

    Args:
        local_content: Content of the local file version
        remote_content: Content of the remote file version
        file_path: Path to the file (for display purposes)

    Returns:
        FileDiff object containing diff information

    Property: For any two different file contents, the diff should highlight
              all lines that differ between versions.
    """
    # Split content into lines for diffing
    local_lines = local_content.splitlines(keepends=True)
    remote_lines = remote_content.splitlines(keepends=True)

    # Generate unified diff
    diff_lines = list(difflib.unified_diff(
        local_lines,
        remote_lines,
        fromfile=f"local/{file_path}",
        tofile=f"remote/{file_path}",
        lineterm=""
    ))

    # Join diff lines into a single string
    unified_diff = "".join(diff_lines)

    # Identify conflict lines (lines that differ)
    conflict_lines = []
    for i, line in enumerate(diff_lines):
        if line.startswith('+') or line.startswith('-'):
            # Skip the file headers
            if not line.startswith('+++') and not line.startswith('---'):
                conflict_lines.append(i)

    return FileDiff(
        file_path=file_path,
        local_content=local_content,
        remote_content=remote_content,
        unified_diff=unified_diff,
        conflict_lines=conflict_lines
    )

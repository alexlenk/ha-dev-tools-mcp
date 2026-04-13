"""Sync manifest for tracking file synchronization state between HA and local workspace."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class FileStatus(str, Enum):
    """Sync status of a file relative to the remote HA instance."""

    CURRENT = "current"  # local and remote checksums match
    STALE = "stale"  # remote changed, local unchanged
    LOCAL_ONLY = "local_only"  # exists locally but not on HA
    REMOTE_ONLY = "remote_only"  # exists on HA but not downloaded
    CONFLICT = "conflict"  # both local and remote changed since last sync
    UNKNOWN = "unknown"  # no metadata available


@dataclass
class ManifestEntry:
    """Metadata for a single synced file."""

    remote_path: str
    local_path: str
    local_checksum: str
    remote_checksum: str
    last_synced: str  # ISO 8601
    file_size: int


# Static and dynamic file groups.
# Static groups have hardcoded paths; dynamic groups are resolved at runtime
# via resolve_file_group().
FILE_GROUPS: Dict[str, List[str]] = {
    "core": [
        "configuration.yaml",
        "automations.yaml",
        "scripts.yaml",
        "scenes.yaml",
    ],
    "packages": [],  # dynamically populated via list_files("packages/")
    "dashboards": [],  # dynamically populated: .storage/lovelace*
    "storage": [],  # dynamically populated: .storage/automation, .storage/script, etc.
    "all": [],  # dynamically populated: all files
}


def _compute_file_checksum(path: Path) -> str:
    """Compute SHA-256 hex digest of a local file.

    Args:
        path: Path to the file on disk.

    Returns:
        Hex-encoded SHA-256 checksum string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyncManifest:
    """Tracks sync state for files between HA and the local workspace.

    Persists as ``.ha-sync/manifest.json`` inside the workspace directory.
    """

    def __init__(self, workspace_dir: str = "~/ha-dev-workspace/") -> None:
        self.workspace_dir = Path(workspace_dir).expanduser().resolve()
        self.manifest_dir = self.workspace_dir / ".ha-sync"
        self.manifest_file = self.manifest_dir / "manifest.json"
        self.entries: Dict[str, ManifestEntry] = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load manifest from disk. No-op if the file doesn't exist.

        Corrupted JSON is handled gracefully by resetting to an empty manifest.
        """
        if not self.manifest_file.exists():
            return

        try:
            data = json.loads(self.manifest_file.read_text(encoding="utf-8"))
            for key, val in data.get("files", {}).items():
                self.entries[key] = ManifestEntry(**val)
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupted manifest — start fresh
            self.entries = {}

    def persist(self) -> None:
        """Write the current manifest to disk, creating directories as needed."""
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        data = {"files": {k: asdict(v) for k, v in self.entries.items()}}
        self.manifest_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Entry management
    # ------------------------------------------------------------------

    def update_entry(
        self,
        remote_path: str,
        local_path: str,
        local_checksum: str,
        remote_checksum: str,
        file_size: int,
    ) -> None:
        """Create or update a manifest entry after a sync or upload operation."""
        self.entries[remote_path] = ManifestEntry(
            remote_path=remote_path,
            local_path=local_path,
            local_checksum=local_checksum,
            remote_checksum=remote_checksum,
            last_synced=datetime.now(timezone.utc).isoformat(),
            file_size=file_size,
        )

    def get_entry(self, remote_path: str) -> Optional[ManifestEntry]:
        """Return the manifest entry for *remote_path*, or ``None``."""
        return self.entries.get(remote_path)

    def all_entries(self) -> Dict[str, ManifestEntry]:
        """Return a shallow copy of all manifest entries."""
        return dict(self.entries)

    # ------------------------------------------------------------------
    # Status resolution
    # ------------------------------------------------------------------

    def get_status(
        self, remote_path: str, current_remote_checksum: str
    ) -> FileStatus:
        """Determine the sync status of a file.

        Args:
            remote_path: The file's path on the HA instance.
            current_remote_checksum: The latest SHA-256 checksum reported by HA.

        Returns:
            A :class:`FileStatus` value describing the relationship between
            the local copy and the remote version.
        """
        entry = self.entries.get(remote_path)
        if entry is None:
            return FileStatus.REMOTE_ONLY

        # Remote hasn't changed since last sync
        if entry.remote_checksum == current_remote_checksum:
            local_path = Path(entry.local_path)
            if not local_path.exists():
                return FileStatus.REMOTE_ONLY
            return FileStatus.CURRENT

        # Remote changed — check whether local was also modified
        local_path = Path(entry.local_path)
        if not local_path.exists():
            return FileStatus.STALE

        local_checksum = _compute_file_checksum(local_path)
        if local_checksum == entry.local_checksum:
            # Local unchanged, remote changed
            return FileStatus.STALE
        else:
            # Both changed
            return FileStatus.CONFLICT

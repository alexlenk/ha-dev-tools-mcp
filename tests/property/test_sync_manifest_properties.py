"""Property-based tests for SyncManifest."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from hypothesis import given, settings, HealthCheck, strategies as st

from ha_dev_tools.sync_manifest import (
    FileStatus,
    SyncManifest,
    _compute_file_checksum,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# File content: arbitrary text excluding surrogates
content_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=50_000,
)

# SHA-256 hex digest (64 lowercase hex chars)
checksum_strategy = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)

# Simple remote path segments
path_segment = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_.",
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: ".." not in s)

remote_path_strategy = st.lists(path_segment, min_size=1, max_size=4).map(
    lambda parts: "/".join(parts)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workspace():
    workspace = Path(tempfile.mkdtemp(prefix="ha-sync-pbt-")).resolve()
    return workspace


def _cleanup(workspace: Path):
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Property 1: Checksum consistency
# random content → write to file → _compute_file_checksum() matches SHA-256
# Validates: Requirement 2.3
# ---------------------------------------------------------------------------


@given(content=content_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_checksum_consistency(content):
    """_compute_file_checksum returns the same SHA-256 as hashing the raw bytes."""
    workspace = _make_workspace()
    try:
        file_path = workspace / "test_file.txt"
        file_path.write_text(content, encoding="utf-8")

        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        actual = _compute_file_checksum(file_path)

        assert (
            actual == expected
        ), f"Checksum mismatch: expected {expected}, got {actual}"
    finally:
        _cleanup(workspace)


# ---------------------------------------------------------------------------
# Property 2: Status correctness
# random checksum pairs → correct FileStatus
# Validates: Requirements 2.10, 2.17
# ---------------------------------------------------------------------------


@given(
    remote_checksum_at_sync=checksum_strategy,
    current_remote_checksum=checksum_strategy,
    local_changed=st.booleans(),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_status_correctness(
    remote_checksum_at_sync,
    current_remote_checksum,
    local_changed,
):
    """get_status returns the correct FileStatus for any checksum combination."""
    workspace = _make_workspace()
    try:
        manifest = SyncManifest(workspace_dir=str(workspace))

        # Create a local file so the path exists
        local_file = workspace / "test.yaml"
        original_content = "original"
        local_file.write_text(original_content, encoding="utf-8")
        local_checksum = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

        # Optionally modify the local file to simulate local edits
        if local_changed:
            modified_content = "modified"
            local_file.write_text(modified_content, encoding="utf-8")

        manifest.update_entry(
            remote_path="test.yaml",
            local_path=str(local_file),
            local_checksum=local_checksum,
            remote_checksum=remote_checksum_at_sync,
            file_size=len(original_content),
        )

        status = manifest.get_status("test.yaml", current_remote_checksum)

        remote_unchanged = remote_checksum_at_sync == current_remote_checksum
        current_local_checksum = _compute_file_checksum(local_file)
        local_unchanged = current_local_checksum == local_checksum

        if remote_unchanged:
            assert status == FileStatus.CURRENT
        elif local_unchanged:
            assert status == FileStatus.STALE
        else:
            assert status == FileStatus.CONFLICT
    finally:
        _cleanup(workspace)


@given(current_remote_checksum=checksum_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_status_remote_only_when_no_entry(current_remote_checksum):
    """get_status returns REMOTE_ONLY when there is no manifest entry."""
    workspace = _make_workspace()
    try:
        manifest = SyncManifest(workspace_dir=str(workspace))
        status = manifest.get_status("unknown.yaml", current_remote_checksum)
        assert status == FileStatus.REMOTE_ONLY
    finally:
        _cleanup(workspace)


# ---------------------------------------------------------------------------
# Property 3: Manifest round-trip
# random entries → persist → load → entries match
# Validates: Requirement 2.10
# ---------------------------------------------------------------------------

manifest_entry_strategy = st.fixed_dictionaries(
    {
        "remote_path": remote_path_strategy,
        "local_path": st.just("/tmp/placeholder"),  # overwritten per-entry
        "local_checksum": checksum_strategy,
        "remote_checksum": checksum_strategy,
        "file_size": st.integers(min_value=0, max_value=10 * 1024 * 1024),
    }
)


@given(entries=st.lists(manifest_entry_strategy, min_size=0, max_size=20))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_manifest_round_trip(entries):
    """persist → load preserves every manifest entry."""
    workspace = _make_workspace()
    try:
        manifest = SyncManifest(workspace_dir=str(workspace))

        # Populate entries (use remote_path as key, so later duplicates win)
        for entry in entries:
            local_path = str(workspace / entry["remote_path"])
            manifest.update_entry(
                remote_path=entry["remote_path"],
                local_path=local_path,
                local_checksum=entry["local_checksum"],
                remote_checksum=entry["remote_checksum"],
                file_size=entry["file_size"],
            )

        manifest.persist()

        # Load into a fresh instance
        loaded = SyncManifest(workspace_dir=str(workspace))
        loaded.load()

        # Build expected set (last write wins for duplicate remote_paths)
        expected_keys = {e["remote_path"] for e in entries}
        assert set(loaded.entries.keys()) == expected_keys

        for key, loaded_entry in loaded.entries.items():
            original = manifest.entries[key]
            assert loaded_entry.remote_path == original.remote_path
            assert loaded_entry.local_path == original.local_path
            assert loaded_entry.local_checksum == original.local_checksum
            assert loaded_entry.remote_checksum == original.remote_checksum
            assert loaded_entry.file_size == original.file_size
            assert loaded_entry.last_synced == original.last_synced
    finally:
        _cleanup(workspace)


@given(entries=st.lists(manifest_entry_strategy, min_size=1, max_size=10))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_manifest_persist_is_valid_json(entries):
    """The persisted manifest file is always valid JSON."""
    workspace = _make_workspace()
    try:
        manifest = SyncManifest(workspace_dir=str(workspace))
        for entry in entries:
            manifest.update_entry(
                remote_path=entry["remote_path"],
                local_path=str(workspace / entry["remote_path"]),
                local_checksum=entry["local_checksum"],
                remote_checksum=entry["remote_checksum"],
                file_size=entry["file_size"],
            )
        manifest.persist()

        raw = manifest.manifest_file.read_text(encoding="utf-8")
        data = json.loads(raw)  # must not raise
        assert "files" in data
        assert isinstance(data["files"], dict)
    finally:
        _cleanup(workspace)

"""Unit tests for SyncManifest, FileStatus, and resolve_file_group."""

import hashlib
import json
from unittest.mock import AsyncMock

import pytest

from ha_dev_tools.sync_manifest import (
    FILE_GROUPS,
    FileStatus,
    ManifestEntry,
    SyncManifest,
    _compute_file_checksum,
    resolve_file_group,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def manifest(tmp_path):
    """Create a SyncManifest using tmp_path as workspace."""
    return SyncManifest(workspace_dir=str(tmp_path))


@pytest.fixture
def local_file(tmp_path):
    """Write a local file and return (path, content, checksum)."""
    content = "homeassistant:\n  name: Test\n"
    file_path = tmp_path / "configuration.yaml"
    file_path.write_text(content, encoding="utf-8")
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return file_path, content, checksum


# ------------------------------------------------------------------
# load() tests
# ------------------------------------------------------------------


def test_load_no_existing_file(manifest):
    """load() with no manifest.json on disk leaves entries empty."""
    manifest.load()
    assert manifest.entries == {}


def test_load_existing_manifest(manifest, tmp_path):
    """load() populates entries from an existing manifest.json."""
    manifest_dir = tmp_path / ".ha-sync"
    manifest_dir.mkdir()
    data = {
        "files": {
            "configuration.yaml": {
                "remote_path": "configuration.yaml",
                "local_path": str(tmp_path / "configuration.yaml"),
                "local_checksum": "abc123",
                "remote_checksum": "abc123",
                "last_synced": "2026-04-13T10:00:00+00:00",
                "file_size": 42,
            }
        }
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

    manifest.load()

    assert "configuration.yaml" in manifest.entries
    entry = manifest.entries["configuration.yaml"]
    assert isinstance(entry, ManifestEntry)
    assert entry.remote_checksum == "abc123"
    assert entry.file_size == 42


def test_load_corrupted_json(manifest, tmp_path):
    """load() resets to empty entries when manifest.json is corrupted."""
    manifest_dir = tmp_path / ".ha-sync"
    manifest_dir.mkdir()
    (manifest_dir / "manifest.json").write_text("NOT VALID JSON {{{", encoding="utf-8")

    manifest.load()

    assert manifest.entries == {}


def test_load_corrupted_structure(manifest, tmp_path):
    """load() resets when JSON is valid but structure is wrong."""
    manifest_dir = tmp_path / ".ha-sync"
    manifest_dir.mkdir()
    # Valid JSON but missing required ManifestEntry fields
    data = {"files": {"bad.yaml": {"remote_path": "bad.yaml"}}}
    (manifest_dir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

    manifest.load()

    assert manifest.entries == {}


# ------------------------------------------------------------------
# persist() tests
# ------------------------------------------------------------------


def test_persist_creates_directory_and_file(manifest, tmp_path):
    """persist() creates .ha-sync/ directory and writes manifest.json."""
    manifest.update_entry(
        remote_path="test.yaml",
        local_path=str(tmp_path / "test.yaml"),
        local_checksum="aaa",
        remote_checksum="bbb",
        file_size=10,
    )

    manifest.persist()

    manifest_file = tmp_path / ".ha-sync" / "manifest.json"
    assert manifest_file.exists()

    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert "test.yaml" in data["files"]
    assert data["files"]["test.yaml"]["local_checksum"] == "aaa"


def test_persist_overwrites_existing(manifest, tmp_path):
    """persist() overwrites a previous manifest.json."""
    manifest.update_entry(
        remote_path="a.yaml",
        local_path="/a",
        local_checksum="x",
        remote_checksum="y",
        file_size=1,
    )
    manifest.persist()

    manifest.update_entry(
        remote_path="b.yaml",
        local_path="/b",
        local_checksum="x2",
        remote_checksum="y2",
        file_size=2,
    )
    manifest.persist()

    data = json.loads(
        (tmp_path / ".ha-sync" / "manifest.json").read_text(encoding="utf-8")
    )
    assert "a.yaml" in data["files"]
    assert "b.yaml" in data["files"]


# ------------------------------------------------------------------
# update_entry() tests
# ------------------------------------------------------------------


def test_update_entry_creates_new(manifest):
    """update_entry() creates a new ManifestEntry."""
    manifest.update_entry(
        remote_path="automations.yaml",
        local_path="/workspace/automations.yaml",
        local_checksum="abc",
        remote_checksum="def",
        file_size=100,
    )

    entry = manifest.entries["automations.yaml"]
    assert entry.remote_path == "automations.yaml"
    assert entry.local_checksum == "abc"
    assert entry.remote_checksum == "def"
    assert entry.file_size == 100
    assert entry.last_synced  # non-empty ISO timestamp


def test_update_entry_overwrites_existing(manifest):
    """update_entry() replaces an existing entry for the same remote_path."""
    manifest.update_entry(
        remote_path="scripts.yaml",
        local_path="/ws/scripts.yaml",
        local_checksum="old",
        remote_checksum="old_r",
        file_size=50,
    )
    manifest.update_entry(
        remote_path="scripts.yaml",
        local_path="/ws/scripts.yaml",
        local_checksum="new",
        remote_checksum="new_r",
        file_size=75,
    )

    entry = manifest.entries["scripts.yaml"]
    assert entry.local_checksum == "new"
    assert entry.remote_checksum == "new_r"
    assert entry.file_size == 75


# ------------------------------------------------------------------
# get_entry() / all_entries()
# ------------------------------------------------------------------


def test_get_entry_returns_none_for_missing(manifest):
    """get_entry() returns None when the path is not tracked."""
    assert manifest.get_entry("nonexistent.yaml") is None


def test_get_entry_returns_entry(manifest):
    """get_entry() returns the ManifestEntry for a tracked path."""
    manifest.update_entry("a.yaml", "/a", "c1", "c2", 10)
    entry = manifest.get_entry("a.yaml")
    assert entry is not None
    assert entry.local_checksum == "c1"


def test_all_entries_returns_copy(manifest):
    """all_entries() returns a shallow copy, not the internal dict."""
    manifest.update_entry("x.yaml", "/x", "c", "c", 1)
    entries = manifest.all_entries()
    entries["injected"] = "bad"
    assert "injected" not in manifest.entries


# ------------------------------------------------------------------
# get_status() tests
# ------------------------------------------------------------------


def test_status_remote_only_no_entry(manifest):
    """get_status() returns REMOTE_ONLY when no manifest entry exists."""
    status = manifest.get_status("unknown.yaml", "some_checksum")
    assert status == FileStatus.REMOTE_ONLY


def test_status_remote_only_local_deleted(manifest, tmp_path):
    """get_status() returns REMOTE_ONLY when local file was deleted."""
    # Entry exists but local file does not
    manifest.update_entry(
        remote_path="deleted.yaml",
        local_path=str(tmp_path / "deleted.yaml"),
        local_checksum="abc",
        remote_checksum="same_remote",
        file_size=10,
    )

    status = manifest.get_status("deleted.yaml", "same_remote")
    assert status == FileStatus.REMOTE_ONLY


def test_status_current(manifest, local_file):
    """get_status() returns CURRENT when checksums match and local exists."""
    file_path, _content, checksum = local_file

    manifest.update_entry(
        remote_path="configuration.yaml",
        local_path=str(file_path),
        local_checksum=checksum,
        remote_checksum=checksum,
        file_size=file_path.stat().st_size,
    )

    status = manifest.get_status("configuration.yaml", checksum)
    assert status == FileStatus.CURRENT


def test_status_stale_remote_changed_local_unchanged(manifest, local_file):
    """get_status() returns STALE when remote changed but local is untouched."""
    file_path, _content, checksum = local_file
    original_remote = "original_remote_checksum"

    manifest.update_entry(
        remote_path="configuration.yaml",
        local_path=str(file_path),
        local_checksum=checksum,
        remote_checksum=original_remote,
        file_size=file_path.stat().st_size,
    )

    # Remote has a new checksum, local file content unchanged
    new_remote_checksum = "new_remote_checksum"
    status = manifest.get_status("configuration.yaml", new_remote_checksum)
    assert status == FileStatus.STALE


def test_status_conflict_both_changed(manifest, tmp_path):
    """get_status() returns CONFLICT when both local and remote changed."""
    # Create local file with NEW content (different from what was synced)
    file_path = tmp_path / "automations.yaml"
    file_path.write_text("modified locally", encoding="utf-8")

    manifest.update_entry(
        remote_path="automations.yaml",
        local_path=str(file_path),
        local_checksum="original_local_checksum",  # differs from current file
        remote_checksum="original_remote_checksum",
        file_size=100,
    )

    # Remote also changed
    status = manifest.get_status("automations.yaml", "new_remote_checksum")
    assert status == FileStatus.CONFLICT


def test_status_stale_local_file_deleted_remote_changed(manifest, tmp_path):
    """get_status() returns STALE when local deleted and remote changed."""
    manifest.update_entry(
        remote_path="gone.yaml",
        local_path=str(tmp_path / "gone.yaml"),
        local_checksum="old",
        remote_checksum="old_remote",
        file_size=5,
    )

    # Remote changed, local file doesn't exist
    status = manifest.get_status("gone.yaml", "new_remote")
    assert status == FileStatus.STALE


# ------------------------------------------------------------------
# _compute_file_checksum()
# ------------------------------------------------------------------


def test_compute_file_checksum(tmp_path):
    """_compute_file_checksum() returns correct SHA-256 hex digest."""
    content = "hello world"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content.encode("utf-8"))

    result = _compute_file_checksum(file_path)
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert result == expected


def test_compute_file_checksum_missing_file(tmp_path):
    """_compute_file_checksum() raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        _compute_file_checksum(tmp_path / "nope.txt")


# ------------------------------------------------------------------
# resolve_file_group() tests
# ------------------------------------------------------------------


@pytest.fixture
def mock_api_client():
    """Mock api_client with list_files returning a sample file list."""
    client = AsyncMock()
    client.list_files.return_value = [
        {"path": "configuration.yaml"},
        {"path": "automations.yaml"},
        {"path": "packages/lights.yaml"},
        {"path": "packages/climate.yaml"},
        {"path": ".storage/lovelace.dashboard_main"},
        {"path": ".storage/lovelace.dashboard_mobile"},
        {"path": ".storage/automation"},
        {"path": ".storage/script"},
        {"path": ".storage/scene"},
        {"path": ".storage/input_boolean"},
        {"path": ".storage/timer"},
        {"path": ".storage/counter"},
        {"path": ".storage/core.entity_registry"},
    ]
    return client


@pytest.mark.asyncio
async def test_resolve_core_group(mock_api_client):
    """core group returns the static list without calling api_client."""
    result = await resolve_file_group("core", mock_api_client)

    assert result == FILE_GROUPS["core"]
    mock_api_client.list_files.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_packages_group(mock_api_client):
    """packages group returns only files under packages/."""
    result = await resolve_file_group("packages", mock_api_client)

    assert result == ["packages/lights.yaml", "packages/climate.yaml"]


@pytest.mark.asyncio
async def test_resolve_dashboards_group(mock_api_client):
    """dashboards group returns only .storage/lovelace* files."""
    result = await resolve_file_group("dashboards", mock_api_client)

    assert result == [
        ".storage/lovelace.dashboard_main",
        ".storage/lovelace.dashboard_mobile",
    ]


@pytest.mark.asyncio
async def test_resolve_storage_group(mock_api_client):
    """storage group returns .storage/automation, script, scene, input_*, timer, counter."""
    result = await resolve_file_group("storage", mock_api_client)

    expected = [
        ".storage/automation",
        ".storage/script",
        ".storage/scene",
        ".storage/input_boolean",
        ".storage/timer",
        ".storage/counter",
    ]
    assert result == expected


@pytest.mark.asyncio
async def test_resolve_all_group(mock_api_client):
    """all group returns every file path from list_files."""
    result = await resolve_file_group("all", mock_api_client)

    assert len(result) == 13
    assert "configuration.yaml" in result
    assert ".storage/core.entity_registry" in result


@pytest.mark.asyncio
async def test_resolve_unknown_group(mock_api_client):
    """Unknown group raises ValueError."""
    with pytest.raises(ValueError, match="Unknown file group"):
        await resolve_file_group("nonexistent", mock_api_client)


# ------------------------------------------------------------------
# Round-trip: persist → load
# ------------------------------------------------------------------


def test_manifest_round_trip(tmp_path):
    """Entries survive a persist → load cycle."""
    m1 = SyncManifest(workspace_dir=str(tmp_path))
    m1.update_entry("a.yaml", "/a", "c1", "c2", 100)
    m1.update_entry("b.yaml", "/b", "c3", "c4", 200)
    m1.persist()

    m2 = SyncManifest(workspace_dir=str(tmp_path))
    m2.load()

    assert set(m2.entries.keys()) == {"a.yaml", "b.yaml"}
    assert m2.entries["a.yaml"].local_checksum == "c1"
    assert m2.entries["b.yaml"].file_size == 200

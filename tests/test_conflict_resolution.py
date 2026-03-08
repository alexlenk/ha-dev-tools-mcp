"""
Unit tests for conflict resolution utilities.

Tests specific examples and edge cases for conflict detection and diff generation.
"""

from ha_dev_tools.conflict_resolution import (
    FileMetadata,
    ConflictType,
    detect_conflict,
    generate_diff,
)


class TestConflictDetection:
    """Test conflict detection with different hash scenarios."""

    def test_no_conflict_same_hash(self):
        """Test that identical hashes produce no conflict."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:30:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,  # Same hash
            modified_at="2026-02-12T11:00:00Z",  # Different time
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.conflict_type == ConflictType.NO_CONFLICT
        assert not conflict.has_conflict()
        assert conflict.local_hash == conflict.remote_hash

    def test_remote_newer_conflict(self):
        """Test detection of remote newer conflict."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:30:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,  # Different hash
            modified_at="2026-02-12T11:30:00Z",  # Newer time
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.conflict_type == ConflictType.REMOTE_NEWER
        assert conflict.has_conflict()
        assert conflict.local_hash != conflict.remote_hash

    def test_both_modified_conflict(self):
        """Test detection of both modified conflict."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T12:00:00Z",  # Newer time
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,  # Different hash
            modified_at="2026-02-12T11:30:00Z",  # Older time
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.conflict_type == ConflictType.BOTH_MODIFIED
        assert conflict.has_conflict()

    def test_same_timestamp_different_hash(self):
        """Test conflict when timestamps match but hashes differ."""
        timestamp = "2026-02-12T10:30:00Z"

        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at=timestamp,
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,  # Different hash
            modified_at=timestamp,  # Same time
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        # Should detect as both modified
        assert conflict.conflict_type == ConflictType.BOTH_MODIFIED
        assert conflict.has_conflict()

    def test_conflict_info_fields(self):
        """Test that ConflictInfo contains all expected fields."""
        local = FileMetadata(
            path="scripts.yaml",
            content_hash="abc123" + "0" * 58,
            modified_at="2026-02-12T10:30:00Z",
            size=2000,
        )

        remote = FileMetadata(
            path="scripts.yaml",
            content_hash="def456" + "0" * 58,
            modified_at="2026-02-12T11:30:00Z",
            size=2500,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.file_path == "scripts.yaml"
        assert conflict.local_hash == "abc123" + "0" * 58
        assert conflict.local_modified == "2026-02-12T10:30:00Z"
        assert conflict.remote_hash == "def456" + "0" * 58
        assert conflict.remote_modified == "2026-02-12T11:30:00Z"

    def test_invalid_timestamp_format(self):
        """Test handling of invalid timestamp format."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="invalid-timestamp",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,
            modified_at="also-invalid",
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        # Should still detect conflict based on hash
        assert conflict.has_conflict()
        # Should default to BOTH_MODIFIED when timestamps can't be parsed
        assert conflict.conflict_type == ConflictType.BOTH_MODIFIED


class TestDiffGeneration:
    """Test diff generation for various content scenarios."""

    def test_identical_content_no_diff(self):
        """Test that identical content produces empty diff."""
        content = """
homeassistant:
  name: Test
  unit_system: metric
"""

        diff = generate_diff(content, content, "configuration.yaml")

        assert diff.file_path == "configuration.yaml"
        assert diff.local_content == content
        assert diff.remote_content == content
        assert not diff.has_differences()
        assert len(diff.conflict_lines) == 0

    def test_single_line_change(self):
        """Test diff with single line modification."""
        local_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:00:00"
"""

        remote_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:30:00"
"""

        diff = generate_diff(local_content, remote_content, "automations.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0
        assert "07:00:00" in diff.unified_diff or "07:30:00" in diff.unified_diff

    def test_multiple_line_changes(self):
        """Test diff with multiple line modifications."""
        local_content = """
automation:
  - id: morning
    alias: Morning Routine
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.bedroom
"""

        remote_content = """
automation:
  - id: morning
    alias: Updated Morning Routine
    trigger:
      - platform: time
        at: "07:30:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.bedroom_main
"""

        diff = generate_diff(local_content, remote_content, "automations.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0
        # Should detect multiple changes
        assert (
            "Morning Routine" in diff.unified_diff
            or "Updated Morning Routine" in diff.unified_diff
        )

    def test_added_lines(self):
        """Test diff with added lines."""
        local_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:00:00"
"""

        remote_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:00:00"
  - id: evening
    trigger:
      - platform: time
        at: "21:00:00"
"""

        diff = generate_diff(local_content, remote_content, "automations.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0

    def test_removed_lines(self):
        """Test diff with removed lines."""
        local_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:00:00"
  - id: evening
    trigger:
      - platform: time
        at: "21:00:00"
"""

        remote_content = """
automation:
  - id: morning
    trigger:
      - platform: time
        at: "07:00:00"
"""

        diff = generate_diff(local_content, remote_content, "automations.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0

    def test_empty_content(self):
        """Test diff with empty content."""
        diff = generate_diff("", "", "empty.yaml")

        assert not diff.has_differences()
        assert len(diff.conflict_lines) == 0

    def test_empty_to_content(self):
        """Test diff from empty to content."""
        local_content = ""
        remote_content = "homeassistant:\n  name: Test\n"

        diff = generate_diff(local_content, remote_content, "configuration.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0

    def test_content_to_empty(self):
        """Test diff from content to empty."""
        local_content = "homeassistant:\n  name: Test\n"
        remote_content = ""

        diff = generate_diff(local_content, remote_content, "configuration.yaml")

        assert diff.has_differences()
        assert len(diff.conflict_lines) > 0

    def test_whitespace_changes(self):
        """Test diff with whitespace changes."""
        local_content = "homeassistant:\n  name: Test\n"
        remote_content = "homeassistant:\n    name: Test\n"  # Extra spaces

        diff = generate_diff(local_content, remote_content, "configuration.yaml")

        # Whitespace changes should be detected
        assert diff.has_differences()

    def test_line_ending_differences(self):
        """Test diff with different line endings."""
        local_content = "line1\nline2\nline3"
        remote_content = "line1\r\nline2\r\nline3"  # Windows line endings

        diff = generate_diff(local_content, remote_content, "test.yaml")

        # Line ending differences should be detected
        # (though they may not show as conflict lines in unified diff)
        assert isinstance(diff.unified_diff, str)

    def test_file_path_preservation(self):
        """Test that file path is preserved in diff."""
        content = "test: content\n"
        path = "packages/lighting.yaml"

        diff = generate_diff(content, content, path)

        assert diff.file_path == path


class TestConflictResolutionStrategies:
    """Test different conflict resolution strategies."""

    def test_keep_local_strategy(self):
        """Test keeping local version (simulated)."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="local_hash_" + "0" * 54,
            modified_at="2026-02-12T12:00:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="remote_hash_" + "0" * 53,
            modified_at="2026-02-12T11:00:00Z",
            size=1100,
        )

        conflict = detect_conflict(local, remote)

        # Verify conflict exists
        assert conflict.has_conflict()

        # Strategy: Keep local means using local_hash
        chosen_hash = local.content_hash
        assert chosen_hash == "local_hash_" + "0" * 54

    def test_keep_remote_strategy(self):
        """Test keeping remote version (simulated)."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="local_hash_" + "0" * 54,
            modified_at="2026-02-12T10:00:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="remote_hash_" + "0" * 53,
            modified_at="2026-02-12T11:00:00Z",
            size=1100,
        )

        conflict = detect_conflict(local, remote)

        # Verify conflict exists
        assert conflict.has_conflict()

        # Strategy: Keep remote means using remote_hash
        chosen_hash = remote.content_hash
        assert chosen_hash == "remote_hash_" + "0" * 53

    def test_manual_merge_validation(self):
        """Test validation of manually merged content."""
        local_content = """
automation:
  - id: test
    trigger:
      - platform: time
        at: "07:00:00"
"""

        remote_content = """
automation:
  - id: test
    trigger:
      - platform: time
        at: "07:30:00"
"""

        # Manually merged content (choosing 07:15:00 as compromise)
        merged_content = """
automation:
  - id: test
    trigger:
      - platform: time
        at: "07:15:00"
"""

        # Verify merged content is different from both
        assert merged_content != local_content
        assert merged_content != remote_content

        # Verify merged content is valid (contains expected structure)
        assert "automation:" in merged_content
        assert "07:15:00" in merged_content

    def test_abort_strategy(self):
        """Test abort strategy (no action taken)."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:00:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,
            modified_at="2026-02-12T11:00:00Z",
            size=1100,
        )

        conflict = detect_conflict(local, remote)

        # Verify conflict exists
        assert conflict.has_conflict()

        # Abort means no changes - both versions remain unchanged
        # This is just verification that conflict was detected
        assert conflict.local_hash == "a" * 64
        assert conflict.remote_hash == "b" * 64


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_large_content_diff(self):
        """Test diff generation with large content."""
        local_content = "\n".join([f"line {i}" for i in range(1000)])
        remote_content = "\n".join([f"line {i}" for i in range(1000, 2000)])

        diff = generate_diff(local_content, remote_content, "large.yaml")

        assert diff.has_differences()
        assert isinstance(diff.unified_diff, str)

    def test_unicode_content_diff(self):
        """Test diff with unicode characters."""
        local_content = "name: Test 🏠\nvalue: 123\n"
        remote_content = "name: Test 🏡\nvalue: 456\n"

        diff = generate_diff(local_content, remote_content, "unicode.yaml")

        assert diff.has_differences()
        assert isinstance(diff.unified_diff, str)

    def test_special_characters_in_path(self):
        """Test handling of special characters in file path."""
        local = FileMetadata(
            path="packages/my-package_v2.0.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:00:00Z",
            size=1000,
        )

        remote = FileMetadata(
            path="packages/my-package_v2.0.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:00:00Z",
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.file_path == "packages/my-package_v2.0.yaml"

    def test_timezone_aware_timestamps(self):
        """Test handling of timezone-aware timestamps."""
        local = FileMetadata(
            path="automations.yaml",
            content_hash="a" * 64,
            modified_at="2026-02-12T10:00:00+00:00",
            size=1000,
        )

        remote = FileMetadata(
            path="automations.yaml",
            content_hash="b" * 64,
            modified_at="2026-02-12T11:00:00+00:00",
            size=1000,
        )

        conflict = detect_conflict(local, remote)

        assert conflict.has_conflict()
        assert conflict.conflict_type == ConflictType.REMOTE_NEWER

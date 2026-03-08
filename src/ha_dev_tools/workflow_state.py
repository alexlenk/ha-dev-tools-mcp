"""Workflow state management for Home Assistant development workflows.

This module provides data structures and methods for tracking development workflow
state across sessions, enabling workflow resumption and conflict detection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import json


class WorkflowType(str, Enum):
    """Types of development workflows."""

    AUTOMATION = "automation"
    TEMPLATE = "template"
    CONFIGURATION = "configuration"
    PACKAGE = "package"
    SCRIPT = "script"


class WorkflowStatus(str, Enum):
    """Status of a workflow."""

    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class FileStatus(str, Enum):
    """Status of a file in a workflow."""

    CLEAN = "clean"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    UPLOADED = "uploaded"


@dataclass
class WorkflowFile:
    """Represents a file tracked in a workflow.

    Attributes:
        local_path: Path to file in local workspace
        remote_path: Path to file on HA instance
        downloaded_at: ISO 8601 timestamp when file was downloaded
        remote_hash: SHA-256 hash of remote file at download time
        remote_modified: ISO 8601 timestamp of remote file modification
        status: Current status of the file
    """

    local_path: str
    remote_path: str
    downloaded_at: str
    remote_hash: str
    remote_modified: str
    status: FileStatus = FileStatus.CLEAN

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "local_path": self.local_path,
            "remote_path": self.remote_path,
            "downloaded_at": self.downloaded_at,
            "remote_hash": self.remote_hash,
            "remote_modified": self.remote_modified,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowFile":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            local_path=data["local_path"],
            remote_path=data["remote_path"],
            downloaded_at=data["downloaded_at"],
            remote_hash=data["remote_hash"],
            remote_modified=data["remote_modified"],
            status=FileStatus(data["status"]),
        )


@dataclass
class WorkflowState:
    """Represents the state of a development workflow.

    Attributes:
        workflow_id: Unique identifier for the workflow
        workflow_type: Type of workflow (automation, template, etc.)
        current_step: Current step number in the workflow
        total_steps: Total number of steps in the workflow
        files: List of files tracked in this workflow
        started_at: ISO 8601 timestamp when workflow started
        last_updated: ISO 8601 timestamp of last update
        status: Current status of the workflow
    """

    workflow_id: str
    workflow_type: WorkflowType
    current_step: int
    total_steps: int
    files: List[WorkflowFile] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: WorkflowStatus = WorkflowStatus.IN_PROGRESS

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "files": [f.to_dict() for f in self.files],
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowState":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            workflow_id=data["workflow_id"],
            workflow_type=WorkflowType(data["workflow_type"]),
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            files=[WorkflowFile.from_dict(f) for f in data["files"]],
            started_at=data["started_at"],
            last_updated=data["last_updated"],
            status=WorkflowStatus(data["status"]),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowState":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class WorkflowStateManager:
    """Manages workflow state persistence and lifecycle.

    This class handles creating, updating, loading, and persisting workflow state
    to the local workspace directory.
    """

    def __init__(self, workspace_path: str = "~/ha-dev-workspace"):
        """Initialize the workflow state manager.

        Args:
            workspace_path: Path to the local workspace directory
        """
        self.workspace_path = Path(workspace_path).expanduser()
        self.workflow_dir = self.workspace_path / ".ha-workflow"
        self.state_file = self.workflow_dir / "state.json"
        self._current_workflow: Optional[WorkflowState] = None

    def _ensure_workflow_dir(self) -> None:
        """Create .ha-workflow directory if it doesn't exist."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    def create_workflow(
        self, workflow_type: WorkflowType, files: List[Dict], total_steps: int = 1
    ) -> WorkflowState:
        """Create a new workflow.

        Args:
            workflow_type: Type of workflow to create
            files: List of file dictionaries with remote_path, local_path, etc.
            total_steps: Total number of steps in the workflow

        Returns:
            The created WorkflowState
        """
        import uuid

        workflow_id = str(uuid.uuid4())
        workflow_files = [WorkflowFile.from_dict(f) for f in files]

        workflow = WorkflowState(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            current_step=1,
            total_steps=total_steps,
            files=workflow_files,
            status=WorkflowStatus.IN_PROGRESS,
        )

        self._current_workflow = workflow
        self._save_state(workflow)

        return workflow

    def update_step(self, workflow_id: str, step: int) -> None:
        """Update the current step of a workflow.

        Args:
            workflow_id: ID of the workflow to update
            step: New step number
        """
        workflow = self._load_workflow(workflow_id)
        if workflow:
            workflow.current_step = step
            workflow.last_updated = datetime.now(timezone.utc).isoformat()
            self._save_state(workflow)

    def mark_file_modified(self, workflow_id: str, file_path: str) -> None:
        """Mark a file as modified in the workflow.

        Args:
            workflow_id: ID of the workflow
            file_path: Path to the file (local or remote)
        """
        workflow = self._load_workflow(workflow_id)
        if workflow:
            for file in workflow.files:
                if file.local_path == file_path or file.remote_path == file_path:
                    file.status = FileStatus.MODIFIED
                    break
            workflow.last_updated = datetime.now(timezone.utc).isoformat()
            self._save_state(workflow)

    def detect_conflicts(self, workflow_id: str) -> List[WorkflowFile]:
        """Detect files with conflicts in the workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            List of WorkflowFile objects with conflict status
        """
        workflow = self._load_workflow(workflow_id)
        if not workflow:
            return []

        return [f for f in workflow.files if f.status == FileStatus.CONFLICT]

    def complete_workflow(self, workflow_id: str) -> None:
        """Mark a workflow as completed and clean up.

        Args:
            workflow_id: ID of the workflow to complete
        """
        workflow = self._load_workflow(workflow_id)
        if workflow:
            workflow.status = WorkflowStatus.COMPLETED
            workflow.last_updated = datetime.now(timezone.utc).isoformat()
            self._save_state(workflow)

            # Clear current workflow if it's the one being completed
            if (
                self._current_workflow
                and self._current_workflow.workflow_id == workflow_id
            ):
                self._current_workflow = None

    def load_current_workflow(self) -> Optional[WorkflowState]:
        """Load the current workflow from disk.

        Returns:
            The current WorkflowState or None if no workflow exists
        """
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                workflow = WorkflowState.from_dict(data)
                self._current_workflow = workflow
                return workflow
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Handle corrupted state file
            self._handle_corrupted_state(e)
            return None

    def _load_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load a workflow by ID.

        Args:
            workflow_id: ID of the workflow to load

        Returns:
            The WorkflowState or None if not found
        """
        # For now, we only support one active workflow
        # In the future, this could load from archived workflows
        current = self.load_current_workflow()
        if current and current.workflow_id == workflow_id:
            return current
        return None

    def _save_state(self, workflow: WorkflowState) -> None:
        """Save workflow state to disk.

        Args:
            workflow: The workflow state to save
        """
        self._ensure_workflow_dir()

        with open(self.state_file, "w") as f:
            json.dump(workflow.to_dict(), f, indent=2)

    def _handle_corrupted_state(self, error: Exception) -> None:
        """Handle corrupted state file gracefully.

        Args:
            error: The exception that occurred
        """
        # Backup the corrupted file
        if self.state_file.exists():
            backup_path = self.state_file.with_suffix(".json.corrupted")
            self.state_file.rename(backup_path)

        # Log the error (in a real implementation, use proper logging)
        print(f"Warning: Corrupted workflow state file. Backed up to {backup_path}")
        print(f"Error: {error}")

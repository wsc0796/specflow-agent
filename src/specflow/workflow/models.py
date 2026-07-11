"""Workflow State Machine models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from specflow.workflow.exceptions import WorkflowError


class WorkflowState(StrEnum):
    """Supported workflow states for M4."""

    CREATED = "created"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class StateTransition:
    """One accepted workflow state transition."""

    from_state: WorkflowState
    to_state: WorkflowState
    sequence: int
    reason: str = ""

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise WorkflowError("StateTransition.sequence must be positive")
        if self.from_state == self.to_state:
            raise WorkflowError("StateTransition must change state")


@dataclass(frozen=True)
class WorkflowSnapshot:
    """Serializable workflow state snapshot."""

    current_state: WorkflowState
    history: tuple[StateTransition, ...] = field(default_factory=tuple)

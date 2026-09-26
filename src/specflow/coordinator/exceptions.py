from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

AbortFutureState = Literal["cancelled_before_start", "running", "finished_unvalidated", "pending"]


@dataclass(frozen=True)
class SchedulerAbortAgent:
    """One bounded observation of a submitted Future during deadline abort."""

    agent_id: str
    cancel_attempted: bool
    cancel_succeeded: bool
    state_during_abort: AbortFutureState
    state_after_cleanup: AbortFutureState

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "cancel_attempted": self.cancel_attempted,
            "cancel_succeeded": self.cancel_succeeded,
            "state_during_abort": self.state_during_abort,
            "state_after_cleanup": self.state_after_cleanup,
        }


@dataclass(frozen=True)
class SchedulerAbortAudit:
    """Safe scheduler evidence for a deadline abort after cleanup."""

    reason: Literal["deadline_exceeded"]
    stage_index: int
    agents: tuple[SchedulerAbortAgent, ...]
    cleanup_completed: bool
    version: int = 1

    def with_stage_index(self, stage_index: int) -> SchedulerAbortAudit:
        return replace(self, stage_index=stage_index)

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "reason": self.reason,
            "stage_index": self.stage_index,
            "agents": [agent.as_dict() for agent in self.agents],
            "cleanup_completed": self.cleanup_completed,
        }


class CoordinatorError(Exception):
    """Base exception for coordinator-related errors."""


class StateTransitionError(CoordinatorError):
    """Illegal state transition in the workflow state machine."""


class ScheduleExecutionError(CoordinatorError):
    """Scheduler execution failed."""

    def __init__(self, message: str, *, scheduler_abort: SchedulerAbortAudit | None = None) -> None:
        super().__init__(message)
        self.scheduler_abort = scheduler_abort


class RevisionError(CoordinatorError):
    """Revision operation failed."""

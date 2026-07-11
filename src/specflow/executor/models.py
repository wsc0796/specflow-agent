"""Agent Executor models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from specflow.workflow import StateTransition, WorkflowState


class ExecutionStatus(StrEnum):
    """Execution outcome status."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class StepResult:
    """Structured result returned by an abstract step handler."""

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("StepResult.metadata keys must be non-empty strings")
            if not isinstance(value, str):
                raise ValueError("StepResult.metadata values must be strings")


@dataclass(frozen=True)
class ExecutionContext:
    """In-memory context passed to step handlers."""

    current_state: WorkflowState
    completed_steps: tuple[str, ...]
    step_results: MappingProxyType[str, StepResult]

    @classmethod
    def build(
        cls,
        *,
        current_state: WorkflowState,
        completed_steps: set[str],
        step_results: dict[str, StepResult],
    ) -> ExecutionContext:
        """Build an immutable handler-facing execution context."""
        return cls(
            current_state=current_state,
            completed_steps=tuple(sorted(completed_steps)),
            step_results=MappingProxyType(dict(step_results)),
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Structured result for one executor step."""

    status: ExecutionStatus
    executed_step: str
    previous_state: WorkflowState
    current_state: WorkflowState
    success: bool
    metadata: dict[str, str] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    history: tuple[StateTransition, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.success and self.status != ExecutionStatus.SUCCESS:
            raise ValueError("Successful execution must have success status")
        if not self.success and self.status != ExecutionStatus.FAILED:
            raise ValueError("Failed execution must have failed status")
        if not self.executed_step.strip():
            raise ValueError("ExecutionResult.executed_step must not be empty")
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("ExecutionResult.metadata must be string-to-string")

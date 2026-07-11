"""Workflow transition rules."""

from __future__ import annotations

from specflow.workflow.models import WorkflowState

LEGAL_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.CREATED: frozenset({WorkflowState.ANALYZING}),
    WorkflowState.ANALYZING: frozenset({WorkflowState.GENERATING, WorkflowState.FAILED}),
    WorkflowState.GENERATING: frozenset({WorkflowState.REVIEWING, WorkflowState.FAILED}),
    WorkflowState.REVIEWING: frozenset({WorkflowState.COMPLETED, WorkflowState.FAILED}),
    WorkflowState.COMPLETED: frozenset(),
    WorkflowState.FAILED: frozenset(),
}

TERMINAL_STATES = frozenset({WorkflowState.COMPLETED, WorkflowState.FAILED})


def can_transition(from_state: WorkflowState, to_state: WorkflowState) -> bool:
    """Return whether a transition is legal in T-012."""
    return to_state in LEGAL_TRANSITIONS[from_state]

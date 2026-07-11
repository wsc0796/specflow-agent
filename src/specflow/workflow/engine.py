"""Deterministic Workflow State Machine engine."""

from __future__ import annotations

from specflow.workflow.exceptions import WorkflowTransitionError
from specflow.workflow.models import StateTransition, WorkflowSnapshot, WorkflowState
from specflow.workflow.transitions import TERMINAL_STATES, can_transition


class WorkflowEngine:
    """Manage workflow state transitions and state history."""

    def __init__(
        self,
        current_state: WorkflowState = WorkflowState.CREATED,
        history: tuple[StateTransition, ...] = (),
    ) -> None:
        self._current_state = current_state
        self._history = list(history)
        self._validate_history()

    @property
    def current_state(self) -> WorkflowState:
        """Return the current workflow state."""
        return self._current_state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        """Return accepted transitions in deterministic order."""
        return tuple(self._history)

    @classmethod
    def restore(cls, snapshot: WorkflowSnapshot) -> WorkflowEngine:
        """Restore a workflow engine from a snapshot."""
        return cls(current_state=snapshot.current_state, history=snapshot.history)

    def transition(self, to_state: WorkflowState, *, reason: str = "") -> StateTransition:
        """Move to another state if the transition is legal."""
        if self._current_state in TERMINAL_STATES:
            raise WorkflowTransitionError(
                f"Workflow is terminal at {self._current_state}; cannot transition to {to_state}"
            )
        if not can_transition(self._current_state, to_state):
            raise WorkflowTransitionError(
                f"Illegal workflow transition: {self._current_state} -> {to_state}"
            )

        transition = StateTransition(
            from_state=self._current_state,
            to_state=to_state,
            sequence=len(self._history) + 1,
            reason=reason.strip(),
        )
        self._history.append(transition)
        self._current_state = to_state
        return transition

    def snapshot(self) -> WorkflowSnapshot:
        """Return a stable snapshot of current state and history."""
        return WorkflowSnapshot(current_state=self._current_state, history=self.history)

    def _validate_history(self) -> None:
        if not self._history:
            if self._current_state != WorkflowState.CREATED:
                raise WorkflowTransitionError(
                    "Workflow current state cannot advance without history"
                )
            return

        expected_from = WorkflowState.CREATED
        for expected_sequence, transition in enumerate(self._history, start=1):
            if transition.sequence != expected_sequence:
                raise WorkflowTransitionError("Workflow history sequence is not contiguous")
            if transition.from_state != expected_from:
                raise WorkflowTransitionError("Workflow history does not match transition order")
            if not can_transition(transition.from_state, transition.to_state):
                raise WorkflowTransitionError(
                    f"Illegal workflow history transition: "
                    f"{transition.from_state} -> {transition.to_state}"
                )
            expected_from = transition.to_state

        if self._current_state != expected_from:
            raise WorkflowTransitionError("Workflow current state does not match history")

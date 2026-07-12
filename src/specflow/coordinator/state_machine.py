"""Multi-agent workflow state machine — tracks lifecycle from creation through completion."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from specflow.coordinator.exceptions import StateTransitionError


class MultiAgentWorkflowState(StrEnum):
    """All possible states of a multi-agent workflow."""

    CREATED = "created"
    PLANNING = "planning"
    ANALYZING = "analyzing"
    EXECUTING_SPECIALISTS = "executing_specialists"
    SYNTHESIZING = "synthesizing"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Legal transition table ──────────────────────────────────────────
# Maps each source state to the set of destination states allowed.
_LEGAL_TRANSITIONS: dict[MultiAgentWorkflowState, frozenset[MultiAgentWorkflowState]] = {
    MultiAgentWorkflowState.CREATED: frozenset({MultiAgentWorkflowState.PLANNING}),
    MultiAgentWorkflowState.PLANNING: frozenset(
        {MultiAgentWorkflowState.ANALYZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.ANALYZING: frozenset(
        {MultiAgentWorkflowState.EXECUTING_SPECIALISTS, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.EXECUTING_SPECIALISTS: frozenset(
        {MultiAgentWorkflowState.SYNTHESIZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.SYNTHESIZING: frozenset(
        {MultiAgentWorkflowState.REVIEWING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.REVIEWING: frozenset(
        {
            MultiAgentWorkflowState.COMPLETED,
            MultiAgentWorkflowState.REVISING,
            MultiAgentWorkflowState.FAILED,
        }
    ),
    MultiAgentWorkflowState.REVISING: frozenset(
        {MultiAgentWorkflowState.SYNTHESIZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.COMPLETED: frozenset(),
    MultiAgentWorkflowState.FAILED: frozenset(),
}


# A single entry in the transition history.
#   (from_state, to_state, reason, iso_timestamp)
TransitionHistoryEntry = tuple[str, str, str, str]


class MultiAgentWorkflowEngine:
    """Finite-state machine for orchestrating a multi-agent workflow.

    The engine enforces legal transitions, tracks revision count, and
    maintains an audit trail of all state changes.
    """

    def __init__(self, max_revision_rounds: int = 3) -> None:
        self._state: MultiAgentWorkflowState = MultiAgentWorkflowState.CREATED
        self._revision_count: int = 0
        self._max_rounds: int = max_revision_rounds
        self._history: list[TransitionHistoryEntry] = []

    # ── Public properties ───────────────────────────────────────────

    @property
    def state(self) -> MultiAgentWorkflowState:
        """Current workflow state."""
        return self._state

    @property
    def revision_count(self) -> int:
        """Number of revision rounds that have occurred."""
        return self._revision_count

    @property
    def max_revision_rounds(self) -> int:
        """Maximum number of revision rounds allowed."""
        return self._max_rounds

    @property
    def history(self) -> tuple[TransitionHistoryEntry, ...]:
        """Immutable snapshot of the transition history."""
        return tuple(self._history)

    @property
    def revision_exhausted(self) -> bool:
        """``True`` when revision rounds have exceeded the configured maximum."""
        return self._revision_count > self._max_rounds

    # ── State transitions ───────────────────────────────────────────

    def transition(self, to_state: MultiAgentWorkflowState, reason: str = "") -> None:
        """Attempt a legal transition from the current state to *to_state*.

        Parameters
        ----------
        to_state:
            The destination state.
        reason:
            Optional human-readable reason for the transition (stored in history).

        Raises
        ------
        StateTransitionError
            If the transition is not allowed by the legal transition table.
        """
        legal = _LEGAL_TRANSITIONS.get(self._state, frozenset())
        if to_state not in legal:
            raise StateTransitionError(
                f"Illegal transition: {self._state.value} -> {to_state.value}"
            )

        from_state = self._state

        # Increment revision counter when entering REVISING
        if to_state is MultiAgentWorkflowState.REVISING:
            self._revision_count += 1

        self._state = to_state
        timestamp = datetime.now(timezone.utc).isoformat()
        self._history.append((from_state.value, to_state.value, reason, timestamp))

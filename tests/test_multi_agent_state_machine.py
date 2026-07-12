"""Tests for MultiAgentWorkflowState and MultiAgentWorkflowEngine."""

from __future__ import annotations

import pytest

from specflow.coordinator.exceptions import StateTransitionError
from specflow.coordinator.state_machine import MultiAgentWorkflowEngine, MultiAgentWorkflowState


class TestMultiAgentWorkflowState:
    """Verify the enum has all expected states and their string values."""

    def test_all_states_present(self) -> None:
        values = {s.value for s in MultiAgentWorkflowState}
        expected = {
            "created",
            "planning",
            "analyzing",
            "executing_specialists",
            "synthesizing",
            "reviewing",
            "revising",
            "completed",
            "failed",
        }
        assert values == expected

    def test_str_enum(self) -> None:
        assert str(MultiAgentWorkflowState.CREATED) == "created"
        assert str(MultiAgentWorkflowState.COMPLETED) == "completed"
        assert str(MultiAgentWorkflowState.FAILED) == "failed"


class TestMultiAgentWorkflowEngine:
    """Verify state machine transitions and revision tracking."""

    # ── Happy path ──────────────────────────────────────────────────

    def test_normal_flow_reaches_completed(self) -> None:
        """Normal flow: CREATED -> PLANNING -> ANALYZING -> EXECUTING_SPECIALISTS
        -> SYNTHESIZING -> REVIEWING -> COMPLETED."""
        engine = MultiAgentWorkflowEngine()

        engine.transition(MultiAgentWorkflowState.PLANNING, "start plan")
        assert engine.state is MultiAgentWorkflowState.PLANNING

        engine.transition(MultiAgentWorkflowState.ANALYZING, "enrichment")
        assert engine.state is MultiAgentWorkflowState.ANALYZING

        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "specialist agents")
        assert engine.state is MultiAgentWorkflowState.EXECUTING_SPECIALISTS

        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "merge results")
        assert engine.state is MultiAgentWorkflowState.SYNTHESIZING

        engine.transition(MultiAgentWorkflowState.REVIEWING, "final review")
        assert engine.state is MultiAgentWorkflowState.REVIEWING

        engine.transition(MultiAgentWorkflowState.COMPLETED, "all good")
        assert engine.state is MultiAgentWorkflowState.COMPLETED

        assert engine.revision_count == 0
        assert engine.revision_exhausted is False

    # ── Revision flow ───────────────────────────────────────────────

    def test_revision_flow(self) -> None:
        """Revision path: REVIEWING -> REVISING -> SYNTHESIZING -> REVIEWING."""
        engine = MultiAgentWorkflowEngine(max_revision_rounds=3)

        # Fast-forward to REVIEWING via normal flow
        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.ANALYZING, "a")
        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "e")
        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")

        # Review says "revise"
        engine.transition(MultiAgentWorkflowState.REVISING, "needs revision")
        assert engine.state is MultiAgentWorkflowState.REVISING
        assert engine.revision_count == 1

        # Revise -> re-synthesize -> re-review
        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "re-synthesize")
        assert engine.state is MultiAgentWorkflowState.SYNTHESIZING

        engine.transition(MultiAgentWorkflowState.REVIEWING, "re-review")
        assert engine.state is MultiAgentWorkflowState.REVIEWING

        engine.transition(MultiAgentWorkflowState.COMPLETED, "approved")
        assert engine.state is MultiAgentWorkflowState.COMPLETED
        assert engine.revision_count == 1

    # ── Revision exhausted ──────────────────────────────────────────

    def test_revision_exhaustion_detected(self) -> None:
        """When revision_count exceeds max_revision_rounds, exhausted is True."""
        engine = MultiAgentWorkflowEngine(max_revision_rounds=2)

        assert engine.revision_exhausted is False

        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.ANALYZING, "a")
        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "e")
        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")

        # Round 1
        engine.transition(MultiAgentWorkflowState.REVISING, "r1")
        assert engine.revision_count == 1
        assert engine.revision_exhausted is False

        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")

        # Round 2 — at limit (2), so > 2 is False
        engine.transition(MultiAgentWorkflowState.REVISING, "r2")
        assert engine.revision_count == 2
        assert engine.revision_exhausted is False  # 2 > 2 is False

        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")

        # Round 3 — exceeds limit
        engine.transition(MultiAgentWorkflowState.REVISING, "r3")
        assert engine.revision_count == 3
        assert engine.revision_exhausted is True  # 3 > 2 is True

    # ── Infrastructure failure ──────────────────────────────────────

    def test_failure_from_any_state(self) -> None:
        """FAILED is reachable from most states."""
        engine = MultiAgentWorkflowEngine()

        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.FAILED, "infra crash")
        assert engine.state is MultiAgentWorkflowState.FAILED

    def test_failure_from_executing_specialists(self) -> None:
        """FAILED from EXECUTING_SPECIALISTS is legal."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.ANALYZING, "a")
        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "e")
        engine.transition(MultiAgentWorkflowState.FAILED, "agent error")
        assert engine.state is MultiAgentWorkflowState.FAILED

    # ── Illegal transitions ─────────────────────────────────────────

    def test_illegal_transition_raises(self) -> None:
        """Transition COMPLETED -> PLANNING should raise."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.ANALYZING, "a")
        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "e")
        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")
        engine.transition(MultiAgentWorkflowState.COMPLETED, "done")

        with pytest.raises(StateTransitionError, match="Illegal transition"):
            engine.transition(MultiAgentWorkflowState.PLANNING)

    def test_skip_state_raises(self) -> None:
        """CREATED -> ANALYZING (skipping PLANNING) should raise."""
        engine = MultiAgentWorkflowEngine()
        with pytest.raises(StateTransitionError, match="Illegal transition"):
            engine.transition(MultiAgentWorkflowState.ANALYZING)

    # ── Terminal states ─────────────────────────────────────────────

    def test_terminal_completed_rejects_further_transitions(self) -> None:
        """Once COMPLETED, any further transition raises."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.ANALYZING, "a")
        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "e")
        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "s")
        engine.transition(MultiAgentWorkflowState.REVIEWING, "r")
        engine.transition(MultiAgentWorkflowState.COMPLETED, "done")

        with pytest.raises(StateTransitionError):
            engine.transition(MultiAgentWorkflowState.PLANNING)
        with pytest.raises(StateTransitionError):
            engine.transition(MultiAgentWorkflowState.FAILED)

    def test_terminal_failed_rejects_further_transitions(self) -> None:
        """Once FAILED, any further transition raises."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "p")
        engine.transition(MultiAgentWorkflowState.FAILED, "crash")

        with pytest.raises(StateTransitionError):
            engine.transition(MultiAgentWorkflowState.PLANNING)
        with pytest.raises(StateTransitionError):
            engine.transition(MultiAgentWorkflowState.COMPLETED)

    # ── History tracking ────────────────────────────────────────────

    def test_history_records_all_transitions(self) -> None:
        """History contains every transition in order."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "start")

        assert len(engine.history) == 1
        from_state, to_state, reason, timestamp = engine.history[0]
        assert from_state == "created"
        assert to_state == "planning"
        assert reason == "start"
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

    def test_history_is_immutable_snapshot(self) -> None:
        """Modifying history tuple should raise."""
        engine = MultiAgentWorkflowEngine()
        engine.transition(MultiAgentWorkflowState.PLANNING, "start")
        hist = engine.history
        with pytest.raises(TypeError):
            hist[0] = ("x", "y", "z", "t")  # type: ignore[index]

    # ── Revision count default ──────────────────────────────────────

    def test_default_max_revision_rounds(self) -> None:
        engine = MultiAgentWorkflowEngine()
        assert engine.max_revision_rounds == 3
        assert engine.revision_count == 0

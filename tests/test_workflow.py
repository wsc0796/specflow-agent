import pytest

from specflow.workflow import (
    StateTransition,
    WorkflowEngine,
    WorkflowSnapshot,
    WorkflowState,
    WorkflowTransitionError,
)


def test_new_workflow_starts_created() -> None:
    engine = WorkflowEngine()

    assert engine.current_state == WorkflowState.CREATED
    assert engine.history == ()


def test_happy_path_transitions_to_completed_with_history() -> None:
    engine = WorkflowEngine()

    engine.transition(WorkflowState.ANALYZING, reason="start analysis")
    engine.transition(WorkflowState.GENERATING, reason="analysis done")
    engine.transition(WorkflowState.REVIEWING, reason="artifacts ready")
    engine.transition(WorkflowState.COMPLETED, reason="review passed")

    assert engine.current_state == WorkflowState.COMPLETED
    assert [entry.sequence for entry in engine.history] == [1, 2, 3, 4]
    assert [entry.from_state for entry in engine.history] == [
        WorkflowState.CREATED,
        WorkflowState.ANALYZING,
        WorkflowState.GENERATING,
        WorkflowState.REVIEWING,
    ]
    assert [entry.to_state for entry in engine.history] == [
        WorkflowState.ANALYZING,
        WorkflowState.GENERATING,
        WorkflowState.REVIEWING,
        WorkflowState.COMPLETED,
    ]
    assert engine.history[0].reason == "start analysis"


@pytest.mark.parametrize(
    ("active_state", "failed_history"),
    [
        (
            WorkflowState.ANALYZING,
            (
                StateTransition(
                    from_state=WorkflowState.CREATED,
                    to_state=WorkflowState.ANALYZING,
                    sequence=1,
                ),
            ),
        ),
        (
            WorkflowState.GENERATING,
            (
                StateTransition(
                    from_state=WorkflowState.CREATED,
                    to_state=WorkflowState.ANALYZING,
                    sequence=1,
                ),
                StateTransition(
                    from_state=WorkflowState.ANALYZING,
                    to_state=WorkflowState.GENERATING,
                    sequence=2,
                ),
            ),
        ),
        (
            WorkflowState.REVIEWING,
            (
                StateTransition(
                    from_state=WorkflowState.CREATED,
                    to_state=WorkflowState.ANALYZING,
                    sequence=1,
                ),
                StateTransition(
                    from_state=WorkflowState.ANALYZING,
                    to_state=WorkflowState.GENERATING,
                    sequence=2,
                ),
                StateTransition(
                    from_state=WorkflowState.GENERATING,
                    to_state=WorkflowState.REVIEWING,
                    sequence=3,
                ),
            ),
        ),
    ],
)
def test_active_states_can_transition_to_failed(
    active_state: WorkflowState,
    failed_history: tuple[StateTransition, ...],
) -> None:
    engine = WorkflowEngine(current_state=active_state, history=failed_history)

    engine.transition(WorkflowState.FAILED, reason="runtime failure")

    assert engine.current_state == WorkflowState.FAILED
    assert engine.history[-1].to_state == WorkflowState.FAILED
    assert engine.history[-1].reason == "runtime failure"


def test_illegal_transition_is_rejected() -> None:
    engine = WorkflowEngine()

    with pytest.raises(WorkflowTransitionError):
        engine.transition(WorkflowState.GENERATING)

    assert engine.current_state == WorkflowState.CREATED
    assert engine.history == ()


@pytest.mark.parametrize("terminal_state", [WorkflowState.COMPLETED, WorkflowState.FAILED])
def test_terminal_states_reject_further_transitions(terminal_state: WorkflowState) -> None:
    history = (
        StateTransition(
            from_state=WorkflowState.CREATED,
            to_state=WorkflowState.ANALYZING,
            sequence=1,
        ),
        StateTransition(
            from_state=WorkflowState.ANALYZING,
            to_state=WorkflowState.GENERATING,
            sequence=2,
        ),
        StateTransition(
            from_state=WorkflowState.GENERATING,
            to_state=WorkflowState.REVIEWING,
            sequence=3,
        ),
        StateTransition(
            from_state=WorkflowState.REVIEWING,
            to_state=terminal_state,
            sequence=4,
        ),
    )
    engine = WorkflowEngine(current_state=terminal_state, history=history)

    with pytest.raises(WorkflowTransitionError):
        engine.transition(WorkflowState.FAILED)


def test_workflow_can_restore_from_snapshot_and_continue() -> None:
    original = WorkflowEngine()
    original.transition(WorkflowState.ANALYZING)
    original.transition(WorkflowState.GENERATING)

    restored = WorkflowEngine.restore(original.snapshot())
    restored.transition(WorkflowState.REVIEWING)
    restored.transition(WorkflowState.COMPLETED)

    assert restored.current_state == WorkflowState.COMPLETED
    assert [entry.sequence for entry in restored.history] == [1, 2, 3, 4]
    assert original.current_state == WorkflowState.GENERATING
    assert len(original.history) == 2


def test_restore_rejects_history_that_does_not_match_current_state() -> None:
    snapshot = WorkflowSnapshot(
        current_state=WorkflowState.GENERATING,
        history=(
            StateTransition(
                from_state=WorkflowState.CREATED,
                to_state=WorkflowState.ANALYZING,
                sequence=1,
            ),
        ),
    )

    with pytest.raises(WorkflowTransitionError):
        WorkflowEngine.restore(snapshot)


def test_restore_rejects_advanced_state_without_history() -> None:
    snapshot = WorkflowSnapshot(current_state=WorkflowState.GENERATING)

    with pytest.raises(WorkflowTransitionError):
        WorkflowEngine.restore(snapshot)


def test_restore_rejects_non_contiguous_history() -> None:
    snapshot = WorkflowSnapshot(
        current_state=WorkflowState.GENERATING,
        history=(
            StateTransition(
                from_state=WorkflowState.CREATED,
                to_state=WorkflowState.ANALYZING,
                sequence=1,
            ),
            StateTransition(
                from_state=WorkflowState.ANALYZING,
                to_state=WorkflowState.GENERATING,
                sequence=3,
            ),
        ),
    )

    with pytest.raises(WorkflowTransitionError):
        WorkflowEngine.restore(snapshot)

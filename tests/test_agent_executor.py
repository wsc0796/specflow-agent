import pytest

from specflow.executor import AgentExecutor, ExecutionError, ExecutionStatus, StepResult
from specflow.workflow import (
    StateTransition,
    WorkflowSnapshot,
    WorkflowState,
    WorkflowTransitionError,
)


class FakeHandler:
    def __init__(self, metadata: dict[str, str] | None = None) -> None:
        self.calls = 0
        self.seen_states: list[WorkflowState] = []
        self.seen_completed_steps: list[tuple[str, ...]] = []
        self._metadata = metadata or {}

    def execute(self, execution_context):
        self.calls += 1
        self.seen_states.append(execution_context.current_state)
        self.seen_completed_steps.append(execution_context.completed_steps)
        return StepResult(metadata=self._metadata)


class FailingHandler:
    def __init__(self, error: Exception) -> None:
        self.calls = 0
        self._error = error

    def execute(self, execution_context):
        self.calls += 1
        raise self._error


class InvalidHandler:
    def execute(self, execution_context):
        return {"not": "a StepResult"}


def handlers(**overrides):
    base = {
        "analyze": FakeHandler({"phase": "analyze"}),
        "generate": FakeHandler({"phase": "generate"}),
        "review": FakeHandler({"phase": "review"}),
    }
    base.update(overrides)
    return base


def test_created_start_enters_analyzing_without_worker_handler() -> None:
    executor = AgentExecutor(handlers())

    result = executor.start()

    assert result.status == ExecutionStatus.SUCCESS
    assert result.executed_step == "start"
    assert result.previous_state == WorkflowState.CREATED
    assert result.current_state == WorkflowState.ANALYZING
    assert result.success
    assert result.metadata == {"state": "analyzing"}
    assert [transition.to_state for transition in result.history] == [WorkflowState.ANALYZING]


def test_execute_alias_runs_current_step() -> None:
    executor = AgentExecutor(handlers())

    result = executor.execute()

    assert result.executed_step == "start"
    assert executor.current_state == WorkflowState.ANALYZING


def test_three_fake_handlers_complete_full_chain() -> None:
    fake_handlers = handlers()
    executor = AgentExecutor(fake_handlers)

    results = executor.execute_until_complete()

    assert [result.executed_step for result in results] == [
        "start",
        "analyze",
        "generate",
        "review",
    ]
    assert executor.current_state == WorkflowState.COMPLETED
    assert all(result.success for result in results)
    assert fake_handlers["analyze"].calls == 1
    assert fake_handlers["generate"].calls == 1
    assert fake_handlers["review"].calls == 1


def test_restored_context_marks_prior_steps_completed_from_history() -> None:
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
                sequence=2,
            ),
        ),
    )
    generate_handler = FakeHandler({"phase": "generate"})
    executor = AgentExecutor.restore(snapshot, handlers(generate=generate_handler))

    executor.execute()

    assert generate_handler.calls == 1
    assert generate_handler.seen_completed_steps == [("analyze", "start")]


def test_analyze_handler_failure_enters_failed() -> None:
    executor = AgentExecutor(handlers(analyze=FailingHandler(RuntimeError("analysis broke"))))
    executor.execute_next()

    result = executor.execute_next()

    assert result.status == ExecutionStatus.FAILED
    assert result.executed_step == "analyze"
    assert result.previous_state == WorkflowState.ANALYZING
    assert result.current_state == WorkflowState.FAILED
    assert result.error_type == "RuntimeError"
    assert result.error_message == "analysis broke"


def test_generate_handler_failure_enters_failed() -> None:
    executor = AgentExecutor(handlers(generate=FailingHandler(ValueError("bad generation"))))
    executor.execute_next()
    executor.execute_next()

    result = executor.execute_next()

    assert result.status == ExecutionStatus.FAILED
    assert result.executed_step == "generate"
    assert result.previous_state == WorkflowState.GENERATING
    assert result.current_state == WorkflowState.FAILED
    assert result.error_type == "ValueError"


def test_review_handler_failure_enters_failed() -> None:
    executor = AgentExecutor(handlers(review=FailingHandler(TimeoutError("review timeout"))))
    executor.execute_next()
    executor.execute_next()
    executor.execute_next()

    result = executor.execute_next()

    assert result.status == ExecutionStatus.FAILED
    assert result.executed_step == "review"
    assert result.previous_state == WorkflowState.REVIEWING
    assert result.current_state == WorkflowState.FAILED
    assert result.error_type == "TimeoutError"


def test_failure_result_preserves_history() -> None:
    executor = AgentExecutor(handlers(generate=FailingHandler(RuntimeError("down"))))
    executor.execute_next()
    executor.execute_next()

    result = executor.execute_next()

    assert [transition.to_state for transition in result.history] == [
        WorkflowState.ANALYZING,
        WorkflowState.GENERATING,
        WorkflowState.FAILED,
    ]
    assert result.history[-1].reason == "generate failed"


def test_completed_state_cannot_execute_again() -> None:
    executor = AgentExecutor(handlers())
    executor.execute_until_complete()

    with pytest.raises(ExecutionError):
        executor.execute_next()


def test_failed_state_cannot_be_silently_resumed() -> None:
    executor = AgentExecutor(handlers(analyze=FailingHandler(RuntimeError("boom"))))
    executor.execute_next()
    executor.execute_next()

    with pytest.raises(ExecutionError):
        executor.execute_next()


def test_legal_intermediate_snapshot_can_restore_and_continue() -> None:
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
                sequence=2,
            ),
        ),
    )
    fake_handlers = handlers()
    executor = AgentExecutor.restore(snapshot, fake_handlers)

    results = executor.execute_until_complete()

    assert [result.executed_step for result in results] == ["generate", "review"]
    assert executor.current_state == WorkflowState.COMPLETED
    assert fake_handlers["analyze"].calls == 0
    assert fake_handlers["generate"].calls == 1
    assert fake_handlers["review"].calls == 1


def test_illegal_history_restore_is_rejected() -> None:
    snapshot = WorkflowSnapshot(current_state=WorkflowState.GENERATING)

    with pytest.raises(WorkflowTransitionError):
        AgentExecutor.restore(snapshot, handlers())


def test_same_step_is_not_called_twice_in_one_executor() -> None:
    fake_handlers = handlers()
    executor = AgentExecutor(fake_handlers)
    executor.execute_until_complete()

    with pytest.raises(ExecutionError):
        executor.execute_next()

    assert fake_handlers["analyze"].calls == 1
    assert fake_handlers["generate"].calls == 1
    assert fake_handlers["review"].calls == 1


def test_invalid_handler_result_fails_clearly() -> None:
    executor = AgentExecutor(handlers(analyze=InvalidHandler()))
    executor.execute_next()

    result = executor.execute_next()

    assert result.status == ExecutionStatus.FAILED
    assert result.executed_step == "analyze"
    assert result.error_type == "ExecutionError"
    assert "StepHandler.execute must return StepResult" in result.error_message
    assert executor.current_state == WorkflowState.FAILED


def test_sensitive_error_message_is_redacted() -> None:
    executor = AgentExecutor(
        handlers(
            analyze=FailingHandler(
                RuntimeError(
                    "failed with api_key=secret123 token=raw-secret password=hunter2 "
                    "sk-abc123def456ghi789jkl012mno345pqr678"
                )
            )
        )
    )
    executor.execute_next()

    result = executor.execute_next()

    assert result.status == ExecutionStatus.FAILED
    assert "secret123" not in result.error_message
    assert "raw-secret" not in result.error_message
    assert "hunter2" not in result.error_message
    assert "abc123def" not in result.error_message
    assert "api_key=<redacted>" in result.error_message
    assert "token=<redacted>" in result.error_message
    assert "password=<redacted>" in result.error_message
    assert "sk-<redacted>" in result.error_message

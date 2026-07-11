"""Deterministic Agent Executor."""

from __future__ import annotations

from collections.abc import Mapping

from specflow.context import _redact_secrets, _strip_control
from specflow.executor.exceptions import ExecutionError
from specflow.executor.handlers import StepHandler
from specflow.executor.models import ExecutionContext, ExecutionResult, ExecutionStatus, StepResult
from specflow.workflow import (
    TERMINAL_STATES,
    StateTransition,
    WorkflowEngine,
    WorkflowSnapshot,
    WorkflowState,
)

STEP_FOR_STATE: dict[WorkflowState, str] = {
    WorkflowState.CREATED: "start",
    WorkflowState.ANALYZING: "analyze",
    WorkflowState.GENERATING: "generate",
    WorkflowState.REVIEWING: "review",
}

NEXT_STATE_FOR_STEP: dict[str, WorkflowState] = {
    "start": WorkflowState.ANALYZING,
    "analyze": WorkflowState.GENERATING,
    "generate": WorkflowState.REVIEWING,
    "review": WorkflowState.COMPLETED,
}

STEP_FOR_TRANSITION: dict[tuple[WorkflowState, WorkflowState], str] = {
    (WorkflowState.CREATED, WorkflowState.ANALYZING): "start",
    (WorkflowState.ANALYZING, WorkflowState.GENERATING): "analyze",
    (WorkflowState.GENERATING, WorkflowState.REVIEWING): "generate",
    (WorkflowState.REVIEWING, WorkflowState.COMPLETED): "review",
}


class AgentExecutor:
    """Execute abstract workflow steps and advance the Workflow State Machine."""

    def __init__(
        self,
        handlers: Mapping[str, StepHandler],
        *,
        workflow: WorkflowEngine | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._workflow = workflow or WorkflowEngine()
        self._completed_steps = _completed_steps_from_history(self._workflow.history)
        self._step_results: dict[str, StepResult] = {}

    @property
    def current_state(self) -> WorkflowState:
        """Return the current workflow state."""
        return self._workflow.current_state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        """Return workflow state transition history."""
        return self._workflow.history

    @property
    def step_results(self) -> dict[str, StepResult]:
        """Return a copy of completed step results."""
        return dict(self._step_results)

    @classmethod
    def restore(
        cls,
        snapshot: WorkflowSnapshot,
        handlers: Mapping[str, StepHandler],
    ) -> AgentExecutor:
        """Restore an executor from a valid workflow snapshot."""
        return cls(handlers=handlers, workflow=WorkflowEngine.restore(snapshot))

    def execute_next(self) -> ExecutionResult:
        """Execute one step for the current workflow state."""
        previous_state = self._workflow.current_state
        if previous_state in TERMINAL_STATES:
            raise ExecutionError(f"Cannot execute terminal workflow state: {previous_state}")

        step = self._step_for_state(previous_state)
        if step in self._completed_steps:
            raise ExecutionError(f"Step already executed in this executor: {step}")

        if previous_state == WorkflowState.CREATED:
            self._workflow.transition(WorkflowState.ANALYZING, reason="executor start")
            self._completed_steps.add(step)
            return self._success(
                step=step,
                previous_state=previous_state,
                result=StepResult(metadata={"state": WorkflowState.ANALYZING.value}),
            )

        handler = self._handler_for_step(step)
        try:
            result = handler.execute(self._context())
            if not isinstance(result, StepResult):
                raise ExecutionError("StepHandler.execute must return StepResult")
        except Exception as exc:
            return self._fail(step=step, previous_state=previous_state, error=exc)

        self._completed_steps.add(step)
        self._step_results[step] = result
        if step == "start":
            return self._success(step=step, previous_state=WorkflowState.CREATED, result=result)

        self._workflow.transition(NEXT_STATE_FOR_STEP[step], reason=f"{step} succeeded")
        return self._success(step=step, previous_state=previous_state, result=result)

    def execute_until_complete(self) -> list[ExecutionResult]:
        """Execute steps until the workflow reaches a terminal state."""
        results: list[ExecutionResult] = []
        while self.current_state not in TERMINAL_STATES:
            result = self.execute_next()
            results.append(result)
            if not result.success:
                break
        return results

    def snapshot(self) -> WorkflowSnapshot:
        """Return the underlying workflow snapshot."""
        return self._workflow.snapshot()

    def execute(self) -> ExecutionResult:
        """Execute one step for the current workflow state."""
        return self.execute_next()

    def start(self) -> ExecutionResult:
        """Start a created workflow and enter the analyzing state."""
        if self.current_state != WorkflowState.CREATED:
            raise ExecutionError(f"Cannot start workflow from state: {self.current_state}")
        return self.execute_next()

    def _step_for_state(self, state: WorkflowState) -> str:
        try:
            return STEP_FOR_STATE[state]
        except KeyError as exc:
            raise ExecutionError(f"No executable step for workflow state: {state}") from exc

    def _handler_for_step(self, step: str) -> StepHandler:
        try:
            return self._handlers[step]
        except KeyError as exc:
            raise ExecutionError(f"Missing handler for step: {step}") from exc

    def _context(self) -> ExecutionContext:
        return ExecutionContext.build(
            current_state=self._workflow.current_state,
            completed_steps=self._completed_steps,
            step_results=self._step_results,
        )

    def _success(
        self,
        *,
        step: str,
        previous_state: WorkflowState,
        result: StepResult,
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            executed_step=step,
            previous_state=previous_state,
            current_state=self._workflow.current_state,
            success=True,
            metadata=dict(sorted(result.metadata.items())),
            history=self._workflow.history,
        )

    def _fail(
        self,
        *,
        step: str,
        previous_state: WorkflowState,
        error: Exception,
    ) -> ExecutionResult:
        if self._workflow.current_state != WorkflowState.FAILED:
            self._workflow.transition(WorkflowState.FAILED, reason=f"{step} failed")
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            executed_step=step,
            previous_state=previous_state,
            current_state=self._workflow.current_state,
            success=False,
            error_type=type(error).__name__,
            error_message=_safe_error_message(str(error)),
            history=self._workflow.history,
        )


def _safe_error_message(message: str) -> str:
    """Redact secrets from execution error messages."""
    return _strip_control(_redact_secrets(message))


def _completed_steps_from_history(history: tuple[StateTransition, ...]) -> set[str]:
    """Derive completed executor steps from validated workflow history."""
    completed_steps: set[str] = set()
    for transition in history:
        step = STEP_FOR_TRANSITION.get((transition.from_state, transition.to_state))
        if step is not None:
            completed_steps.add(step)
    return completed_steps

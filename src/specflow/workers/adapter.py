"""Adapter between Worker Framework and Agent Executor."""

from __future__ import annotations

from collections.abc import Callable

from specflow.executor import ExecutionContext, StepResult
from specflow.workers.base import Worker
from specflow.workers.exceptions import WorkerExecutionError
from specflow.workers.models import WorkerContext, WorkerResult, sanitize_worker_text

RESERVED_STEP_METADATA_KEYS = frozenset({"worker_name", "worker_role", "worker_version"})


class WorkerStepHandler:
    """Adapt one Worker to the T-013 StepHandler protocol."""

    def __init__(
        self,
        worker: Worker,
        worker_context: WorkerContext | Callable[[ExecutionContext], WorkerContext],
    ) -> None:
        self._worker = worker
        self._worker_context = worker_context

    def execute(self, execution_context: ExecutionContext) -> StepResult:
        """Execute the worker and convert WorkerResult into StepResult."""
        try:
            worker_context = self._resolve_worker_context(execution_context)
            result = self._worker.execute(worker_context)
        except Exception as exc:
            message = sanitize_worker_text(str(exc))
            raise WorkerExecutionError(message) from exc

        if not isinstance(result, WorkerResult):
            raise WorkerExecutionError("Worker.execute must return WorkerResult")
        if result.worker_name != self._worker.name or result.worker_role != self._worker.role:
            raise WorkerExecutionError("WorkerResult identity does not match worker metadata")
        if not result.success:
            message = result.error_message or "Worker failed without error message"
            if result.error_type:
                message = f"{result.error_type}: {message}"
            raise WorkerExecutionError(message)
        reserved_keys = RESERVED_STEP_METADATA_KEYS.intersection(result.metadata)
        if reserved_keys:
            keys = ", ".join(sorted(reserved_keys))
            raise WorkerExecutionError(f"Worker metadata uses reserved keys: {keys}")

        metadata = {
            "worker_name": result.worker_name,
            "worker_role": result.worker_role.value,
            "worker_version": self._worker.version,
        }
        metadata.update(dict(result.metadata))
        for key, value in result.output:
            metadata[f"output.{key}"] = value
        return StepResult(metadata=metadata)

    def _resolve_worker_context(self, execution_context: ExecutionContext) -> WorkerContext:
        if callable(self._worker_context):
            context = self._worker_context(execution_context)
        else:
            context = self._worker_context
        if not isinstance(context, WorkerContext):
            raise WorkerExecutionError("Worker context factory must return WorkerContext")
        return context

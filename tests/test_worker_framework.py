import pytest

from specflow.executor import AgentExecutor, ExecutionStatus
from specflow.workers import (
    BaseWorker,
    DuplicateWorkerError,
    WorkerContext,
    WorkerExecutionError,
    WorkerMetadata,
    WorkerNotFoundError,
    WorkerRegistry,
    WorkerResult,
    WorkerRole,
    WorkerStepHandler,
    WorkerValidationError,
)


class FakeWorker(BaseWorker):
    def __init__(
        self,
        *,
        name: str,
        role: WorkerRole,
        output: tuple[tuple[str, str], ...] = (),
    ) -> None:
        super().__init__(
            WorkerMetadata(
                name=name,
                role=role,
                version="1.0.0",
                description=f"Fake {role.value} worker",
            )
        )
        self.calls = 0
        self.output = output or (("artifact", role.value),)

    def execute(self, context: WorkerContext) -> WorkerResult:
        self.calls += 1
        return WorkerResult.success_result(
            worker_name=self.name,
            worker_role=self.role,
            output=self.output,
            metadata={"run_id": context.run_id},
        )


class FakeAnalyzeWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__(name="fake-analyze", role=WorkerRole.ANALYZE)


class FakeGenerateWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__(name="fake-generate", role=WorkerRole.GENERATE)


class FakeReviewWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__(name="fake-review", role=WorkerRole.REVIEW)


class FailingWorker(FakeWorker):
    def execute(self, context: WorkerContext) -> WorkerResult:
        self.calls += 1
        return WorkerResult.failure_result(
            worker_name=self.name,
            worker_role=self.role,
            error_type="WorkerFailed",
            error_message="worker failed",
        )


class ThrowingWorker(FakeWorker):
    def execute(self, context: WorkerContext) -> WorkerResult:
        self.calls += 1
        raise RuntimeError("boom token=raw-secret")


class InvalidWorker(FakeWorker):
    def execute(self, context: WorkerContext):
        self.calls += 1
        return {"invalid": "result"}


def worker_context() -> WorkerContext:
    return WorkerContext.build(
        run_id="run-001",
        requirement="Analyze this project",
        project_context="PROJECT_CONTEXT",
        prior_outputs=(("previous", "value"),),
        metadata={"source": "test"},
    )


def test_valid_worker_metadata() -> None:
    metadata = WorkerMetadata(
        name="fake-analyze",
        role=WorkerRole.ANALYZE,
        version="1.0.0",
        description="Fake analyze worker",
    )

    assert metadata.name == "fake-analyze"
    assert metadata.role == WorkerRole.ANALYZE


def test_invalid_worker_name_is_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerMetadata(name=" ", role=WorkerRole.ANALYZE, version="1.0.0", description="x")


@pytest.mark.parametrize("version", ["", " ", "latest", "dev"])
def test_invalid_version_is_rejected(version: str) -> None:
    with pytest.raises(WorkerValidationError):
        WorkerMetadata(name="worker", role=WorkerRole.ANALYZE, version=version, description="x")


def test_unknown_worker_role_is_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerMetadata(name="worker", role="unknown", version="1.0.0", description="x")


def test_worker_context_valid_build() -> None:
    context = worker_context()

    assert context.run_id == "run-001"
    assert context.prior_outputs == (("previous", "value"),)
    assert context.metadata["source"] == "test"


def test_missing_requirement_is_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerContext.build(run_id="run-001", requirement=" ")


def test_invalid_prior_outputs_are_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerContext.build(
            run_id="run-001",
            requirement="Analyze this project",
            prior_outputs=(("too", "many", "values"),),
        )


def test_worker_result_success_contract() -> None:
    result = WorkerResult.success_result(
        worker_name="worker",
        worker_role=WorkerRole.ANALYZE,
        output=(("goal", "ok"),),
    )

    assert result.success
    assert result.output == (("goal", "ok"),)
    assert result.error_message is None


def test_worker_result_failure_contract() -> None:
    result = WorkerResult.failure_result(
        worker_name="worker",
        worker_role=WorkerRole.ANALYZE,
        error_type="RuntimeError",
        error_message="failed",
    )

    assert not result.success
    assert result.requires_review
    assert result.error_type == "RuntimeError"
    assert result.error_message == "failed"


def test_worker_result_success_error_conflict_is_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerResult(
            worker_name="worker",
            worker_role=WorkerRole.ANALYZE,
            success=True,
            error_type="RuntimeError",
            error_message="failed",
        )


def test_worker_result_unknown_role_is_rejected() -> None:
    with pytest.raises(WorkerValidationError):
        WorkerResult(worker_name="worker", worker_role="unknown", success=True)


def test_registry_registers_and_gets_worker() -> None:
    registry = WorkerRegistry()
    worker = FakeAnalyzeWorker()

    registry.register(worker)

    assert registry.get(WorkerRole.ANALYZE) is worker


def test_duplicate_role_registration_is_rejected() -> None:
    registry = WorkerRegistry()
    registry.register(FakeAnalyzeWorker())

    with pytest.raises(DuplicateWorkerError):
        registry.register(FakeWorker(name="other-analyze", role=WorkerRole.ANALYZE))


def test_duplicate_name_registration_is_rejected() -> None:
    registry = WorkerRegistry()
    registry.register(FakeAnalyzeWorker())

    with pytest.raises(DuplicateWorkerError):
        registry.register(FakeWorker(name="fake-analyze", role=WorkerRole.GENERATE))


def test_missing_worker_lookup_fails() -> None:
    registry = WorkerRegistry()

    with pytest.raises(WorkerNotFoundError):
        registry.get(WorkerRole.REVIEW)


def test_registry_metadata_order_is_deterministic() -> None:
    registry = WorkerRegistry()
    registry.register(FakeReviewWorker())
    registry.register(FakeAnalyzeWorker())
    registry.register(FakeGenerateWorker())

    assert [metadata.role for metadata in registry.metadata()] == [
        WorkerRole.ANALYZE,
        WorkerRole.GENERATE,
        WorkerRole.REVIEW,
    ]


def test_fake_worker_adapter_returns_step_result() -> None:
    worker = FakeAnalyzeWorker()
    handler = WorkerStepHandler(worker, worker_context())

    step_result = handler.execute(None)

    assert step_result.metadata["worker_name"] == "fake-analyze"
    assert step_result.metadata["worker_role"] == "analyze"
    assert step_result.metadata["output.artifact"] == "analyze"


def test_worker_success_drives_executor_state() -> None:
    analyze = FakeAnalyzeWorker()
    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(analyze, worker_context()),
            "generate": WorkerStepHandler(FakeGenerateWorker(), worker_context()),
            "review": WorkerStepHandler(FakeReviewWorker(), worker_context()),
        }
    )

    results = executor.execute_until_complete()

    assert executor.current_state.value == "completed"
    assert all(result.success for result in results)
    assert analyze.calls == 1


def test_worker_failure_drives_executor_to_failed() -> None:
    failing = FailingWorker(name="fake-analyze", role=WorkerRole.ANALYZE)
    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(failing, worker_context()),
            "generate": WorkerStepHandler(FakeGenerateWorker(), worker_context()),
            "review": WorkerStepHandler(FakeReviewWorker(), worker_context()),
        }
    )
    executor.start()

    result = executor.execute()

    assert result.status == ExecutionStatus.FAILED
    assert result.current_state.value == "failed"
    assert result.error_type == "WorkerExecutionError"
    assert "WorkerFailed: worker failed" in result.error_message


def test_worker_exception_drives_executor_to_failed() -> None:
    throwing = ThrowingWorker(name="fake-analyze", role=WorkerRole.ANALYZE)
    executor = AgentExecutor({"analyze": WorkerStepHandler(throwing, worker_context())})
    executor.start()

    result = executor.execute()

    assert result.status == ExecutionStatus.FAILED
    assert result.error_type == "WorkerExecutionError"
    assert "raw-secret" not in result.error_message
    assert "token=<redacted>" in result.error_message


def test_invalid_worker_return_fails_clearly() -> None:
    invalid = InvalidWorker(name="fake-analyze", role=WorkerRole.ANALYZE)
    handler = WorkerStepHandler(invalid, worker_context())

    with pytest.raises(WorkerExecutionError, match="Worker.execute must return WorkerResult"):
        handler.execute(None)


def test_worker_metadata_cannot_override_reserved_step_metadata() -> None:
    worker = FakeAnalyzeWorker()
    handler = WorkerStepHandler(
        worker,
        worker_context(),
    )
    worker.execute = lambda context: WorkerResult.success_result(  # type: ignore[method-assign]
        worker_name=worker.name,
        worker_role=worker.role,
        metadata={"worker_name": "spoofed"},
    )

    with pytest.raises(WorkerExecutionError, match="reserved keys"):
        handler.execute(None)


def test_same_step_does_not_call_worker_twice() -> None:
    analyze = FakeAnalyzeWorker()
    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(analyze, worker_context()),
            "generate": WorkerStepHandler(FakeGenerateWorker(), worker_context()),
            "review": WorkerStepHandler(FakeReviewWorker(), worker_context()),
        }
    )

    executor.execute_until_complete()

    assert analyze.calls == 1


def test_worker_result_redacts_secret_error_message() -> None:
    result = WorkerResult.failure_result(
        worker_name="worker",
        worker_role=WorkerRole.ANALYZE,
        error_type="RuntimeError",
        error_message="api_key=secret123 password=hunter2 token=raw-secret",
    )

    assert "secret123" not in result.error_message
    assert "hunter2" not in result.error_message
    assert "raw-secret" not in result.error_message
    assert "api_key=<redacted>" in result.error_message
    assert "password=<redacted>" in result.error_message
    assert "token=<redacted>" in result.error_message

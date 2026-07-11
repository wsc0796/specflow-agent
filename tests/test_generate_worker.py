import json

from specflow.context import ProjectContext
from specflow.executor import AgentExecutor, StepResult
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import LLMRequest, MockLLMClient
from specflow.technology import Evidence
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerRole, WorkerStepHandler
from specflow.workers.analyze import AnalysisOutput
from specflow.workers.generate import GenerateWorker, GenerationOutput
from specflow.workflow import WorkflowState


def _project_context(**overrides) -> ProjectContext:
    values = {
        "project_name": "demo-api",
        "root_path": "D:/private/demo-api",
        "language": "python",
        "frameworks": ["fastapi"],
        "validation_library": "pydantic",
        "orm": "sqlalchemy",
        "database": "sqlite",
        "test_framework": "pytest",
        "lint_tools": ["ruff"],
        "dependency_files": ["pyproject.toml"],
        "entry_candidates": ["src/main.py"],
        "top_level_directories": ["src", "tests"],
        "total_files": 12,
        "ignored_directories": [".git", ".venv"],
        "oversized_files": [],
        "parse_warnings": [],
        "technology_evidence": [Evidence(file="pyproject.toml", matched="fastapi")],
        "generated_at": "2026-07-11T12:00:00+00:00",
    }
    values.update(overrides)
    return ProjectContext(**values)


def _analysis(degraded: bool = False) -> AnalysisOutput:
    return AnalysisOutput(
        requirement_summary="Add a safe export endpoint.",
        goals=("Expose export endpoint",),
        non_goals=("Do not implement authentication",),
        assumptions=("Existing FastAPI app is available",),
        affected_components=("api", "services"),
        risks=("Path traversal",),
        acceptance_criteria=("Reject invalid paths", "Return export metadata"),
        evidence=("PROJECT_CONTEXT.md",),
        requires_review=degraded,
        degraded=degraded,
    )


def _generation_json(analysis: AnalysisOutput, **overrides) -> str:
    payload = {
        "requirement_summary": analysis.requirement_summary,
        "proposed_solution": "Add a read-only export planning endpoint.",
        "architecture_or_design": "Route delegates to service validation.",
        "affected_components": ["services", "api"],
        "implementation_steps": ["Add schema", "Add route", "Add service tests"],
        "api_or_data_changes": ["GET /exports/plan"],
        "test_plan": ["pytest route tests", "pytest service tests"],
        "risks": ["Path validation mistakes"],
        "acceptance_criteria_mapping": [
            {
                "criterion": "Reject invalid paths",
                "implementation": "Validate resolved path stays inside repository.",
            },
            {
                "criterion": "Return export metadata",
                "implementation": "Return deterministic metadata payload.",
            },
        ],
        "analysis_hash": analysis.analysis_hash,
        "requires_review": False,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class CapturingLLMClient(MockLLMClient):
    def __init__(self, response_content: str) -> None:
        super().__init__(response_content=response_content)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest):
        self.requests.append(request)
        return super().complete(request)


class StaticAnalyzeHandler:
    def execute(self, execution_context):
        return StepResult(metadata={"analysis_hash": "already-completed"})


def _context(analysis: AnalysisOutput | None = None) -> WorkerContext:
    prior_outputs = ()
    if analysis is not None:
        prior_outputs = (("analysis_json", analysis.to_json()),)
    return WorkerContext.build(
        run_id="run-016",
        requirement="Add export endpoint",
        project_context="sanitized project context",
        prior_outputs=prior_outputs,
    )


def _worker(
    tmp_path,
    analysis: AnalysisOutput | None = None,
    response: str | None = None,
    fail_with: Exception | None = None,
):
    analysis = analysis or _analysis()
    return GenerateWorker(
        project_context=_project_context(),
        llm_client=MockLLMClient(
            response_content=response or _generation_json(analysis),
            fail_with=fail_with,
        ),
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
        fallback_manager=FallbackManager(RetryStrategy(max_retries=1)),
        budget_manager=TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=512)
        ),
    )


def _output_from_result(result) -> GenerationOutput:
    return GenerationOutput.from_json(
        dict(result.output)["generation_json"],
        analysis_hash=dict(result.output)["analysis_hash"],
    )


def test_generate_worker_returns_generation_output(tmp_path) -> None:
    analysis = _analysis()

    result = _worker(tmp_path, analysis=analysis).execute(_context(analysis))
    output = _output_from_result(result)

    assert result.success
    assert output.proposed_solution == "Add a read-only export planning endpoint."
    assert output.analysis_hash == analysis.analysis_hash
    assert dict(result.output)["generation_hash"] == output.generation_hash


def test_missing_analysis_output_fails(tmp_path) -> None:
    result = _worker(tmp_path).execute(_context(None))

    assert not result.success
    assert result.error_type == "MissingAnalysisOutput"


def test_invalid_analysis_output_is_rejected(tmp_path) -> None:
    context = WorkerContext.build(
        run_id="run-016",
        requirement="Add export endpoint",
        project_context="ctx",
        prior_outputs=(("analysis_json", '{"bad":"shape"}'),),
    )

    result = _worker(tmp_path).execute(context)

    assert not result.success
    assert "Invalid AnalysisOutput" in result.error_message


def test_degraded_analysis_propagates_review_flags(tmp_path) -> None:
    analysis = _analysis(degraded=True)

    output = _output_from_result(_worker(tmp_path, analysis=analysis).execute(_context(analysis)))

    assert output.degraded
    assert output.requires_review


def test_analysis_hash_is_preserved(tmp_path) -> None:
    analysis = _analysis()

    result = _worker(tmp_path, analysis=analysis).execute(_context(analysis))

    assert dict(result.output)["analysis_hash"] == analysis.analysis_hash
    assert result.metadata["analysis_hash"] == analysis.analysis_hash


def test_acceptance_criteria_mapping_is_structured(tmp_path) -> None:
    analysis = _analysis()

    output = _output_from_result(_worker(tmp_path, analysis=analysis).execute(_context(analysis)))

    assert output.acceptance_criteria_mapping == (
        ("Reject invalid paths", "Validate resolved path stays inside repository."),
        ("Return export metadata", "Return deterministic metadata payload."),
    )


def test_implementation_steps_are_stable(tmp_path) -> None:
    analysis = _analysis()
    response = _generation_json(
        analysis,
        implementation_steps=["Add route", "Add schema", "Add route"],
    )

    output = _output_from_result(
        _worker(tmp_path, analysis=analysis, response=response).execute(_context(analysis))
    )

    assert output.implementation_steps == ("Add route", "Add schema")


def test_worker_does_not_generate_code_modifications(tmp_path) -> None:
    analysis = _analysis()

    output = _output_from_result(_worker(tmp_path, analysis=analysis).execute(_context(analysis)))

    assert "```" not in output.to_json()
    assert "git commit" not in output.to_json().lower()


def test_mock_llm_response_is_used(tmp_path) -> None:
    analysis = _analysis()
    response = _generation_json(analysis, proposed_solution="Mocked generation.")

    output = _output_from_result(
        _worker(tmp_path, analysis=analysis, response=response).execute(_context(analysis))
    )

    assert output.proposed_solution == "Mocked generation."


def test_llm_failure_enters_fallback(tmp_path) -> None:
    analysis = _analysis()

    result = _worker(tmp_path, analysis=analysis, fail_with=TimeoutError("timeout")).execute(
        _context(analysis)
    )
    output = _output_from_result(result)

    assert result.success
    assert output.degraded
    assert result.metadata["fallback_level"] == "rule_baseline"


def test_invalid_generation_response_degrades(tmp_path) -> None:
    analysis = _analysis()

    output = _output_from_result(
        _worker(tmp_path, analysis=analysis, response='{"too":"little"}').execute(
            _context(analysis)
        )
    )

    assert output.degraded
    assert output.requires_review


def test_sensitive_data_not_in_output_or_trace(tmp_path) -> None:
    analysis = _analysis()
    response = _generation_json(
        analysis,
        risks=["api_key=sk-abc123def456ghi789jkl012"],
    )

    result = _worker(tmp_path, analysis=analysis, response=response).execute(_context(analysis))
    raw_trace = (tmp_path / "run-016-generate.json").read_text(encoding="utf-8")

    assert "sk-abc123" not in dict(result.output)["generation_json"]
    assert "api_key=" not in dict(result.output)["generation_json"]
    assert result.metadata["degraded"] == "true"
    assert "sk-abc123" not in raw_trace
    assert "Add export endpoint" not in raw_trace


def test_worker_result_contract_is_correct(tmp_path) -> None:
    analysis = _analysis()

    result = _worker(tmp_path, analysis=analysis).execute(_context(analysis))

    assert result.worker_name == "generate-worker"
    assert result.worker_role == WorkerRole.GENERATE
    assert result.success


def test_adapter_integrates_with_executor(tmp_path) -> None:
    analysis = _analysis()
    handler = WorkerStepHandler(_worker(tmp_path, analysis=analysis), _context(analysis))
    executor = AgentExecutor({"analyze": StaticAnalyzeHandler(), "generate": handler})

    executor.start()
    executor.execute()
    result = executor.execute()

    assert result.success
    assert result.executed_step == "generate"
    assert result.current_state == WorkflowState.REVIEWING
    assert "output.generation_hash" in result.metadata


def test_same_step_does_not_repeat_worker_call(tmp_path) -> None:
    analysis = _analysis()
    client = CapturingLLMClient(_generation_json(analysis))
    worker = GenerateWorker(
        project_context=_project_context(),
        llm_client=client,
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
        fallback_manager=FallbackManager(RetryStrategy(max_retries=1)),
        budget_manager=TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=64)
        ),
    )
    executor = AgentExecutor(
        {
            "analyze": StaticAnalyzeHandler(),
            "generate": WorkerStepHandler(worker, _context(analysis)),
        }
    )

    executor.start()
    executor.execute()
    executor.execute()

    assert len(client.requests) == 1


def test_generation_hash_is_stable(tmp_path) -> None:
    analysis = _analysis()

    first = _output_from_result(_worker(tmp_path / "first", analysis).execute(_context(analysis)))
    second = _output_from_result(_worker(tmp_path / "second", analysis).execute(_context(analysis)))

    assert first.generation_hash == second.generation_hash

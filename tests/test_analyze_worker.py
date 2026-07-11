import json

import pytest

from specflow.context import ProjectContext
from specflow.executor import AgentExecutor
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import LLMRequest, MockLLMClient
from specflow.technology import Evidence
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerRole, WorkerStepHandler
from specflow.workers.analyze import AnalysisOutput, AnalyzeWorker
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


def _analysis_json(**overrides) -> str:
    payload = {
        "requirement_summary": "Add a safe export endpoint.",
        "goals": ["Expose export endpoint", "Validate path inputs"],
        "non_goals": ["Do not implement authentication"],
        "assumptions": ["Existing FastAPI app is available"],
        "affected_components": ["api", "services"],
        "risks": ["Path traversal"],
        "acceptance_criteria": ["Reject invalid paths", "Return export metadata"],
        "evidence": ["PROJECT_CONTEXT.md", "pyproject.toml: fastapi"],
        "requires_review": False,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _worker(tmp_path, response: str | None = None, fail_with: Exception | None = None):
    return AnalyzeWorker(
        project_context=_project_context(),
        llm_client=MockLLMClient(
            response_content=response or _analysis_json(),
            fail_with=fail_with,
        ),
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
        fallback_manager=FallbackManager(RetryStrategy(max_retries=1)),
        budget_manager=TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=512)
        ),
    )


def _context(requirement: str = "Add export endpoint") -> WorkerContext:
    return WorkerContext.build(
        run_id="run-015",
        requirement=requirement,
        project_context="sanitized project context",
    )


class CapturingLLMClient(MockLLMClient):
    def __init__(self, response_content: str) -> None:
        super().__init__(response_content=response_content)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest):
        self.requests.append(request)
        return super().complete(request)


def _output_from_result(result) -> AnalysisOutput:
    output = dict(result.output)
    return AnalysisOutput.from_json(output["analysis_json"])


def test_analyze_worker_metadata_is_valid(tmp_path) -> None:
    worker = _worker(tmp_path)

    assert worker.name == "analyze-worker"
    assert worker.role == WorkerRole.ANALYZE
    assert worker.version == "1.0.0"
    assert "requirement" in worker.description.lower()


def test_analyze_worker_returns_structured_output(tmp_path) -> None:
    result = _worker(tmp_path).execute(_context())
    output = _output_from_result(result)

    assert result.success
    assert output.requirement_summary == "Add a safe export endpoint."
    assert output.goals == ("Expose export endpoint", "Validate path inputs")
    assert output.non_goals == ("Do not implement authentication",)
    assert output.requires_review is False
    assert output.degraded is False
    assert dict(result.output)["analysis_hash"] == output.analysis_hash


def test_empty_requirement_fails_before_runtime(tmp_path) -> None:
    with pytest.raises(Exception):
        WorkerContext.build(run_id="run-015", requirement=" ", project_context="ctx")


def test_invalid_project_context_returns_failure(tmp_path) -> None:
    worker = AnalyzeWorker(
        project_context=_project_context(language="unknown"),
        llm_client=MockLLMClient(response_content=_analysis_json()),
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
    )

    result = worker.execute(_context())

    assert not result.success
    assert result.error_type == "ContextBuildError"


def test_analysis_output_rejects_missing_fields() -> None:
    with pytest.raises(ValueError):
        AnalysisOutput.from_json('{"requirement_summary":"missing"}')


def test_analysis_output_rejects_non_boolean_flags() -> None:
    with pytest.raises(ValueError):
        AnalysisOutput.from_json(_analysis_json(requires_review="false"))


def test_affected_components_order_is_stable(tmp_path) -> None:
    response = _analysis_json(affected_components=["services", "api", "api"])

    output = _output_from_result(_worker(tmp_path, response=response).execute(_context()))

    assert output.affected_components == ("api", "services")


def test_acceptance_criteria_order_is_stable(tmp_path) -> None:
    response = _analysis_json(acceptance_criteria=["B criterion", "A criterion"])

    output = _output_from_result(_worker(tmp_path, response=response).execute(_context()))

    assert output.acceptance_criteria == ("A criterion", "B criterion")


def test_source_evidence_is_preserved(tmp_path) -> None:
    output = _output_from_result(_worker(tmp_path).execute(_context()))

    assert output.evidence == ("PROJECT_CONTEXT.md", "pyproject.toml: fastapi")


def test_mock_llm_response_is_used(tmp_path) -> None:
    response = _analysis_json(requirement_summary="Mocked analysis.")

    output = _output_from_result(_worker(tmp_path, response=response).execute(_context()))

    assert output.requirement_summary == "Mocked analysis."


def test_llm_failure_enters_existing_fallback(tmp_path) -> None:
    result = _worker(tmp_path, fail_with=TimeoutError("timeout")).execute(_context())
    output = _output_from_result(result)

    assert result.success
    assert output.degraded
    assert output.requires_review
    assert result.metadata["fallback_level"] == "rule_baseline"


def test_invalid_structured_response_returns_controlled_degraded_result(tmp_path) -> None:
    result = _worker(tmp_path, response='{"requirement_summary":"too little"}').execute(_context())
    output = _output_from_result(result)

    assert result.success
    assert output.degraded
    assert output.requires_review
    assert "manual review" in output.risks[0].lower()


def test_invalid_structured_array_items_return_degraded_result(tmp_path) -> None:
    response = _analysis_json(goals=[{"bad": "shape"}])

    result = _worker(tmp_path, response=response).execute(_context())
    output = _output_from_result(result)

    assert result.success
    assert output.degraded
    assert output.requires_review


def test_degraded_result_requires_review(tmp_path) -> None:
    output = _output_from_result(_worker(tmp_path, response="not json").execute(_context()))

    assert output.degraded
    assert output.requires_review


def test_invalid_structure_trace_records_rule_baseline_fallback(tmp_path) -> None:
    _worker(tmp_path, response='{"requirement_summary":"too little"}').execute(_context())

    payload = json.loads((tmp_path / "run-015-analyze.json").read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
    assert payload["fallback_level"] == "rule_baseline"


def test_trace_contains_required_metadata(tmp_path) -> None:
    _worker(tmp_path).execute(_context())

    payload = json.loads((tmp_path / "run-015-analyze.json").read_text(encoding="utf-8"))
    assert payload["prompt_name"] == "analyze_requirement"
    assert payload["prompt_version"] == "1.0.0"
    assert len(payload["prompt_hash"]) == 64
    assert len(payload["context_hash"]) == 64
    assert payload["metadata"]["worker_name"] == "analyze-worker"
    assert payload["metadata"]["worker_role"] == "analyze"


def test_trace_run_id_is_filename_safe(tmp_path) -> None:
    context = WorkerContext.build(
        run_id="run/015",
        requirement="Add export endpoint",
        project_context="sanitized project context",
    )

    result = _worker(tmp_path).execute(context)

    assert result.success
    assert (tmp_path / "run-015-analyze.json").exists()


def test_trace_does_not_store_sensitive_body(tmp_path) -> None:
    _worker(tmp_path).execute(_context("Add endpoint with api_key=sk-abc123def456ghi789jkl012"))

    raw = (tmp_path / "run-015-analyze.json").read_text(encoding="utf-8")
    assert "api_key" not in raw
    assert "sk-abc123" not in raw
    assert "Add endpoint" not in raw
    assert "safe export endpoint" not in raw


def test_worker_step_handler_integrates_with_executor(tmp_path) -> None:
    handler = WorkerStepHandler(_worker(tmp_path), _context())
    executor = AgentExecutor({"analyze": handler})

    executor.start()
    result = executor.execute()

    assert result.success
    assert result.executed_step == "analyze"
    assert result.current_state == WorkflowState.GENERATING
    assert result.metadata["worker_role"] == "analyze"
    assert "output.analysis_hash" in result.metadata


def test_llm_request_respects_reserved_response_budget(tmp_path) -> None:
    client = CapturingLLMClient(response_content=_analysis_json())
    worker = AnalyzeWorker(
        project_context=_project_context(),
        llm_client=client,
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
        fallback_manager=FallbackManager(RetryStrategy(max_retries=1)),
        budget_manager=TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=64)
        ),
    )

    result = worker.execute(_context())

    assert result.success
    assert client.requests[0].max_tokens == 64


def test_worker_does_not_directly_modify_workflow_state(tmp_path) -> None:
    worker_result = _worker(tmp_path).execute(_context())

    assert worker_result.success
    assert worker_result.worker_role == WorkerRole.ANALYZE


def test_same_input_produces_stable_hash(tmp_path) -> None:
    first = _output_from_result(_worker(tmp_path / "first").execute(_context()))
    second = _output_from_result(_worker(tmp_path / "second").execute(_context()))

    assert first.analysis_hash == second.analysis_hash
    assert first.to_json() == second.to_json()

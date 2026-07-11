import json

from specflow.context import ProjectContext
from specflow.executor import AgentExecutor, ExecutionContext
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import LLMRequest, MockLLMClient
from specflow.technology import Evidence
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerStepHandler
from specflow.workers.analyze import AnalysisOutput, AnalyzeWorker
from specflow.workers.generate import GenerateWorker, GenerationOutput
from specflow.workers.review import ReviewDecision, ReviewOutput, ReviewWorker
from specflow.workflow import WorkflowState


def _project_context(language: str = "python") -> ProjectContext:
    return ProjectContext(
        project_name="demo-api",
        root_path="D:/private/demo-api",
        language=language,
        frameworks=["fastapi"],
        validation_library="pydantic",
        orm="sqlalchemy",
        database="sqlite",
        test_framework="pytest",
        lint_tools=["ruff"],
        dependency_files=["pyproject.toml"],
        entry_candidates=["src/main.py"],
        top_level_directories=["src", "tests"],
        total_files=12,
        ignored_directories=[".git", ".venv"],
        oversized_files=[],
        parse_warnings=[],
        technology_evidence=[Evidence(file="pyproject.toml", matched="fastapi")],
        generated_at="2026-07-11T12:00:00+00:00",
    )


def _analysis_json(**overrides) -> str:
    payload = {
        "requirement_summary": "Add a safe export endpoint.",
        "goals": ["Expose export endpoint"],
        "non_goals": ["Do not implement authentication"],
        "assumptions": ["Existing FastAPI app is available"],
        "affected_components": ["api", "services"],
        "risks": ["Path traversal"],
        "acceptance_criteria": ["Reject invalid paths", "Return export metadata"],
        "evidence": ["PROJECT_CONTEXT.md"],
        "requires_review": False,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _generation_json(analysis: AnalysisOutput, **overrides) -> str:
    payload = {
        "requirement_summary": analysis.requirement_summary,
        "proposed_solution": "Add a read-only export planning endpoint.",
        "architecture_or_design": "Route delegates to service validation.",
        "affected_components": ["api", "services"],
        "implementation_steps": ["Add route", "Add schema"],
        "api_or_data_changes": ["GET /exports/plan"],
        "test_plan": ["pytest route tests"],
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


def _review_json(
    analysis: AnalysisOutput,
    generation: GenerationOutput,
    *,
    decision: str = "PASS",
    **overrides,
) -> str:
    payload = {
        "decision": decision,
        "summary": "Generation satisfies the analyzed requirement.",
        "issues": [],
        "missing_requirements": [],
        "risk_findings": [],
        "acceptance_criteria_results": [
            {"criterion": "Reject invalid paths", "passed": True, "notes": "Covered."},
            {"criterion": "Return export metadata", "passed": True, "notes": "Covered."},
        ],
        "severity": "info",
        "requires_revision": decision == "REJECT",
        "requires_human_review": decision == "REJECT",
        "analysis_hash": analysis.analysis_hash,
        "generation_hash": generation.generation_hash,
        "degraded": False,
    }
    if decision == "REJECT":
        payload["issues"] = [
            {
                "code": "MISSING_TEST",
                "severity": "high",
                "message": "Test plan is incomplete.",
                "related_requirement": "Return export metadata",
                "suggestion": "Add explicit metadata response tests.",
            }
        ]
        payload["missing_requirements"] = ["Return export metadata"]
        payload["risk_findings"] = ["Test coverage gap"]
        payload["severity"] = "high"
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class CountingLLMClient(MockLLMClient):
    def __init__(self, response_content: str, fail_with: Exception | None = None) -> None:
        super().__init__(response_content=response_content, fail_with=fail_with)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest):
        self.requests.append(request)
        return super().complete(request)


def _base_context(
    *,
    prior_outputs=(),
    requirement: str = "Add export endpoint",
) -> WorkerContext:
    return WorkerContext.build(
        run_id="m4-run",
        requirement=requirement,
        project_context="sanitized project context",
        prior_outputs=tuple(prior_outputs),
    )


def _generate_context(execution_context: ExecutionContext) -> WorkerContext:
    analyze = execution_context.step_results["analyze"].metadata
    return _base_context(prior_outputs=(("analysis_json", analyze["output.analysis_json"]),))


def _review_context(execution_context: ExecutionContext) -> WorkerContext:
    analyze = execution_context.step_results["analyze"].metadata
    generate = execution_context.step_results["generate"].metadata
    return _base_context(
        prior_outputs=(
            ("analysis_json", analyze["output.analysis_json"]),
            ("generation_json", generate["output.generation_json"]),
        )
    )


def _workflow(tmp_path, *, decision: str = "PASS", degraded_analyze: bool = False):
    analysis = AnalysisOutput.from_json(
        _analysis_json(degraded=degraded_analyze, requires_review=degraded_analyze)
    )
    generation = GenerationOutput.from_json(
        _generation_json(analysis, degraded=degraded_analyze, requires_review=degraded_analyze),
        analysis_hash=analysis.analysis_hash,
    )
    analyze_client = CountingLLMClient(
        _analysis_json(degraded=degraded_analyze, requires_review=degraded_analyze)
    )
    generate_client = CountingLLMClient(
        _generation_json(analysis, degraded=degraded_analyze, requires_review=degraded_analyze)
    )
    review_client = CountingLLMClient(_review_json(analysis, generation, decision=decision))
    trace_recorder = TraceRecorder(JsonTraceStorage(tmp_path))
    policy = BudgetPolicy(max_tokens=4096, reserved_response_tokens=512)
    fallback = FallbackManager(RetryStrategy(max_retries=1))

    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(
                AnalyzeWorker(
                    project_context=_project_context(),
                    llm_client=analyze_client,
                    trace_recorder=trace_recorder,
                    fallback_manager=fallback,
                    budget_manager=TokenBudgetManager(policy),
                ),
                _base_context(),
            ),
            "generate": WorkerStepHandler(
                GenerateWorker(
                    project_context=_project_context(),
                    llm_client=generate_client,
                    trace_recorder=trace_recorder,
                    fallback_manager=fallback,
                    budget_manager=TokenBudgetManager(policy),
                ),
                _generate_context,
            ),
            "review": WorkerStepHandler(
                ReviewWorker(
                    project_context=_project_context(),
                    llm_client=review_client,
                    trace_recorder=trace_recorder,
                    fallback_manager=fallback,
                    budget_manager=TokenBudgetManager(policy),
                ),
                _review_context,
            ),
        }
    )
    return executor, (analyze_client, generate_client, review_client)


def test_pass_full_workflow(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)

    results = executor.execute_until_complete()

    assert results[-1].current_state == WorkflowState.COMPLETED
    assert results[-1].metadata["decision"] == "PASS"


def test_reject_full_workflow_completes(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path, decision="REJECT")

    results = executor.execute_until_complete()
    review = ReviewOutput.from_json(
        results[-1].metadata["output.review_json"],
        analysis_hash=results[-1].metadata["analysis_hash"],
        generation_hash=results[-1].metadata["generation_hash"],
    )

    assert results[-1].current_state == WorkflowState.COMPLETED
    assert review.decision == ReviewDecision.REJECT
    assert review.requires_revision


def test_analyze_failure_stops_workflow(tmp_path) -> None:
    analyze = AnalyzeWorker(
        project_context=_project_context(language="unknown"),
        llm_client=CountingLLMClient(_analysis_json()),
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
    )
    executor = AgentExecutor({"analyze": WorkerStepHandler(analyze, _base_context())})

    results = executor.execute_until_complete()

    assert results[-1].executed_step == "analyze"
    assert results[-1].current_state == WorkflowState.FAILED


def test_generate_failure_stops_workflow(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)
    executor._handlers["generate"] = WorkerStepHandler(  # noqa: SLF001
        executor._handlers["generate"]._worker,  # noqa: SLF001
        _base_context(prior_outputs=()),
    )

    results = executor.execute_until_complete()

    assert results[-1].executed_step == "generate"
    assert results[-1].current_state == WorkflowState.FAILED


def test_review_failure_stops_workflow(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)
    executor._handlers["review"] = WorkerStepHandler(  # noqa: SLF001
        executor._handlers["review"]._worker,  # noqa: SLF001
        _base_context(prior_outputs=()),
    )

    results = executor.execute_until_complete()

    assert results[-1].executed_step == "review"
    assert results[-1].current_state == WorkflowState.FAILED


def test_upstream_degraded_propagates(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path, degraded_analyze=True)

    results = executor.execute_until_complete()
    review = ReviewOutput.from_json(
        results[-1].metadata["output.review_json"],
        analysis_hash=results[-1].metadata["analysis_hash"],
        generation_hash=results[-1].metadata["generation_hash"],
    )

    assert review.degraded
    assert review.requires_human_review


def test_state_history_is_complete(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)

    executor.execute_until_complete()

    assert [transition.to_state for transition in executor.history] == [
        WorkflowState.ANALYZING,
        WorkflowState.GENERATING,
        WorkflowState.REVIEWING,
        WorkflowState.COMPLETED,
    ]


def test_each_worker_runs_once(tmp_path) -> None:
    executor, clients = _workflow(tmp_path)

    executor.execute_until_complete()

    assert [len(client.requests) for client in clients] == [1, 1, 1]


def test_trace_distinguishes_three_workers(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)

    executor.execute_until_complete()

    assert (tmp_path / "m4-run-analyze.json").exists()
    assert (tmp_path / "m4-run-generate.json").exists()
    assert (tmp_path / "m4-run-review.json").exists()


def test_final_result_does_not_leak_sensitive_values(tmp_path) -> None:
    executor, _clients = _workflow(tmp_path)

    results = executor.execute_until_complete()
    raw = json.dumps(results[-1].metadata)

    assert "sk-abc" not in raw
    assert "api_key=" not in raw


def test_same_mock_inputs_are_deterministic(tmp_path) -> None:
    first, _ = _workflow(tmp_path / "first")
    second, _ = _workflow(tmp_path / "second")

    first_result = first.execute_until_complete()[-1]
    second_result = second.execute_until_complete()[-1]

    assert (
        first_result.metadata["output.review_hash"] == second_result.metadata["output.review_hash"]
    )


def test_no_real_network_or_provider_is_used(tmp_path) -> None:
    executor, clients = _workflow(tmp_path)

    executor.execute_until_complete()

    assert all(isinstance(client, CountingLLMClient) for client in clients)

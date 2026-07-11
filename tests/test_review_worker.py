import json

from specflow.context import ProjectContext
from specflow.executor import AgentExecutor, StepResult
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import MockLLMClient
from specflow.technology import Evidence
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerStepHandler
from specflow.workers.analyze import AnalysisOutput
from specflow.workers.generate import GenerationOutput
from specflow.workers.review import ReviewDecision, ReviewOutput, ReviewWorker
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


def _generation(analysis: AnalysisOutput, degraded: bool = False) -> GenerationOutput:
    return GenerationOutput(
        requirement_summary=analysis.requirement_summary,
        proposed_solution="Add a read-only export planning endpoint.",
        architecture_or_design="Route delegates to service validation.",
        affected_components=("api", "services"),
        implementation_steps=("Add route", "Add schema"),
        api_or_data_changes=("GET /exports/plan",),
        test_plan=("pytest route tests",),
        risks=("Path validation mistakes",),
        acceptance_criteria_mapping=(
            ("Reject invalid paths", "Validate resolved path stays inside repository."),
            ("Return export metadata", "Return deterministic metadata payload."),
        ),
        analysis_hash=analysis.analysis_hash,
        requires_review=degraded,
        degraded=degraded,
    )


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
        "requires_human_review": False,
        "analysis_hash": analysis.analysis_hash,
        "generation_hash": generation.generation_hash,
        "degraded": False,
    }
    if decision == "REJECT":
        payload.update(
            {
                "summary": "Generation misses an acceptance criterion.",
                "issues": [
                    {
                        "code": "MISSING_TEST",
                        "severity": "high",
                        "message": "Test plan is incomplete.",
                        "related_requirement": "Return export metadata",
                        "suggestion": "Add explicit metadata response tests.",
                    }
                ],
                "missing_requirements": ["Return export metadata"],
                "risk_findings": ["Test coverage gap"],
                "severity": "high",
                "requires_human_review": True,
            }
        )
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class StaticHandler:
    def __init__(self, metadata: dict[str, str] | None = None) -> None:
        self.calls = 0
        self._metadata = metadata or {}

    def execute(self, execution_context):
        self.calls += 1
        return StepResult(metadata=self._metadata)


def _context(analysis: AnalysisOutput | None, generation: GenerationOutput | None) -> WorkerContext:
    prior_outputs = []
    if analysis is not None:
        prior_outputs.append(("analysis_json", analysis.to_json()))
    if generation is not None:
        prior_outputs.append(("generation_json", generation.to_json()))
    return WorkerContext.build(
        run_id="run-017",
        requirement="Add export endpoint",
        project_context="sanitized project context",
        prior_outputs=tuple(prior_outputs),
    )


def _worker(
    tmp_path,
    analysis: AnalysisOutput | None = None,
    generation: GenerationOutput | None = None,
    response: str | None = None,
    fail_with: Exception | None = None,
):
    analysis = analysis or _analysis()
    generation = generation or _generation(analysis)
    return ReviewWorker(
        project_context=_project_context(),
        llm_client=MockLLMClient(
            response_content=response or _review_json(analysis, generation),
            fail_with=fail_with,
        ),
        trace_recorder=TraceRecorder(JsonTraceStorage(tmp_path)),
        fallback_manager=FallbackManager(RetryStrategy(max_retries=1)),
        budget_manager=TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=512)
        ),
    )


def _output_from_result(result) -> ReviewOutput:
    output = dict(result.output)
    return ReviewOutput.from_json(
        output["review_json"],
        analysis_hash=output["analysis_hash"],
        generation_hash=output["generation_hash"],
    )


def test_pass_review_output(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    result = _worker(tmp_path, analysis, generation).execute(_context(analysis, generation))
    output = _output_from_result(result)

    assert result.success
    assert output.decision == ReviewDecision.PASS
    assert not output.requires_revision


def test_reject_review_is_successful_worker_execution(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)
    response = _review_json(analysis, generation, decision="REJECT")

    result = _worker(tmp_path, analysis, generation, response=response).execute(
        _context(analysis, generation)
    )
    output = _output_from_result(result)

    assert result.success
    assert output.decision == ReviewDecision.REJECT
    assert output.requires_revision
    assert result.metadata["decision"] == "REJECT"


def test_reject_workflow_still_completes(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)
    response = _review_json(analysis, generation, decision="REJECT")
    review_handler = WorkerStepHandler(
        _worker(tmp_path, analysis, generation, response=response),
        _context(analysis, generation),
    )
    executor = AgentExecutor(
        {
            "analyze": StaticHandler(),
            "generate": StaticHandler(),
            "review": review_handler,
        }
    )

    results = executor.execute_until_complete()

    assert results[-1].success
    assert results[-1].current_state == WorkflowState.COMPLETED
    assert results[-1].metadata["decision"] == "REJECT"


def test_review_worker_input_failure_fails_workflow(tmp_path) -> None:
    analysis = _analysis()
    review_handler = WorkerStepHandler(
        _worker(tmp_path),
        _context(analysis, None),
    )
    executor = AgentExecutor(
        {
            "analyze": StaticHandler(),
            "generate": StaticHandler(),
            "review": review_handler,
        }
    )

    results = executor.execute_until_complete()

    assert not results[-1].success
    assert results[-1].current_state == WorkflowState.FAILED


def test_missing_analysis_output_fails(tmp_path) -> None:
    generation = _generation(_analysis())

    result = _worker(tmp_path).execute(_context(None, generation))

    assert not result.success
    assert result.error_type == "MissingAnalysisOutput"


def test_missing_generation_output_fails(tmp_path) -> None:
    analysis = _analysis()

    result = _worker(tmp_path).execute(_context(analysis, None))

    assert not result.success
    assert result.error_type == "MissingGenerationOutput"


def test_hash_lineage_is_preserved(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    result = _worker(tmp_path, analysis, generation).execute(_context(analysis, generation))

    assert dict(result.output)["analysis_hash"] == analysis.analysis_hash
    assert dict(result.output)["generation_hash"] == generation.generation_hash


def test_issue_order_and_severity_are_stable(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)
    response = _review_json(
        analysis,
        generation,
        decision="REJECT",
        issues=[
            {
                "code": "B",
                "severity": "medium",
                "message": "Second",
                "related_requirement": "R2",
                "suggestion": "S2",
            },
            {
                "code": "A",
                "severity": "high",
                "message": "First",
                "related_requirement": "R1",
                "suggestion": "S1",
            },
        ],
    )

    output = _output_from_result(
        _worker(tmp_path, analysis, generation, response=response).execute(
            _context(analysis, generation)
        )
    )

    assert [issue.code for issue in output.issues] == ["A", "B"]
    assert output.severity == "high"


def test_acceptance_criteria_are_checked(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    output = _output_from_result(
        _worker(tmp_path, analysis, generation).execute(_context(analysis, generation))
    )

    assert output.acceptance_criteria_results == (
        ("Reject invalid paths", True, "Covered."),
        ("Return export metadata", True, "Covered."),
    )


def test_degraded_upstream_requires_human_review(tmp_path) -> None:
    analysis = _analysis(degraded=True)
    generation = _generation(analysis, degraded=True)

    output = _output_from_result(
        _worker(tmp_path, analysis, generation).execute(_context(analysis, generation))
    )

    assert output.degraded
    assert output.requires_human_review


def test_llm_failure_enters_fallback(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    result = _worker(tmp_path, analysis, generation, fail_with=TimeoutError("timeout")).execute(
        _context(analysis, generation)
    )
    output = _output_from_result(result)

    assert result.success
    assert output.degraded
    assert output.requires_human_review


def test_invalid_response_degrades(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    output = _output_from_result(
        _worker(tmp_path, analysis, generation, response='{"too":"little"}').execute(
            _context(analysis, generation)
        )
    )

    assert output.degraded
    assert output.decision == ReviewDecision.REJECT


def test_sensitive_data_is_sanitized(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)
    response = _review_json(
        analysis,
        generation,
        risk_findings=["api_key=sk-abc123def456ghi789jkl012"],
    )

    result = _worker(tmp_path, analysis, generation, response=response).execute(
        _context(analysis, generation)
    )
    raw_trace = (tmp_path / "run-017-review.json").read_text(encoding="utf-8")

    assert "sk-abc123" not in dict(result.output)["review_json"]
    assert "api_key=" not in dict(result.output)["review_json"]
    assert "Add export endpoint" not in raw_trace


def test_review_does_not_trigger_rework_loop(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)
    response = _review_json(analysis, generation, decision="REJECT")
    generate_handler = StaticHandler()
    review_handler = WorkerStepHandler(
        _worker(tmp_path, analysis, generation, response=response),
        _context(analysis, generation),
    )
    executor = AgentExecutor(
        {
            "analyze": StaticHandler(),
            "generate": generate_handler,
            "review": review_handler,
        }
    )

    executor.execute_until_complete()

    assert executor.current_state == WorkflowState.COMPLETED
    assert generate_handler.calls == 1


def test_review_hash_is_stable(tmp_path) -> None:
    analysis = _analysis()
    generation = _generation(analysis)

    first = _output_from_result(
        _worker(tmp_path / "first", analysis, generation).execute(_context(analysis, generation))
    )
    second = _output_from_result(
        _worker(tmp_path / "second", analysis, generation).execute(_context(analysis, generation))
    )

    assert first.review_hash == second.review_hash

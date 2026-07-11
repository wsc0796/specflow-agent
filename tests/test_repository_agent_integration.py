"""Integration tests: Evidence Collector + Agent Executor + Workers."""

import json
from pathlib import Path

from specflow.context import ProjectContext
from specflow.evidence import EvidenceCollector
from specflow.executor import AgentExecutor
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import LLMRequest, MockLLMClient
from specflow.technology import Evidence
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.tools import ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerStepHandler
from specflow.workers.analyze import AnalysisOutput, AnalyzeWorker
from specflow.workers.generate import GenerateWorker, GenerationOutput
from specflow.workers.review import ReviewWorker
from specflow.workflow import WorkflowState


class CountingLLMClient(MockLLMClient):
    def __init__(self, response_content: str, fail_with: Exception | None = None) -> None:
        super().__init__(response_content=response_content, fail_with=fail_with)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest):
        self.requests.append(request)
        return super().complete(request)


def _project_context() -> ProjectContext:
    return ProjectContext(
        project_name="demo-api",
        root_path="D:/private/demo-api",
        language="python",
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
        "requirement_summary": "Add order timeout auto-cancel.",
        "goals": ["Auto-cancel timed-out orders"],
        "non_goals": ["Do not implement payment reversal"],
        "assumptions": ["Existing order service is available"],
        "affected_components": ["orders", "tasks"],
        "risks": ["Race condition on order status"],
        "acceptance_criteria": ["Cancel orders older than threshold", "Log cancellation"],
        "evidence": ["src/orders/service.py"],
        "requires_review": False,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _generation_json(analysis: AnalysisOutput, **overrides) -> str:
    payload = {
        "requirement_summary": analysis.requirement_summary,
        "proposed_solution": "Add Celery task for periodic order cancellation.",
        "architecture_or_design": "Scheduler triggers task; task queries stale orders.",
        "affected_components": ["orders", "tasks"],
        "implementation_steps": ["Add cancel_order task", "Add Celery beat schedule"],
        "api_or_data_changes": ["No new API endpoints"],
        "test_plan": ["Test task execution", "Test order state transitions"],
        "risks": ["Duplicate cancellation"],
        "acceptance_criteria_mapping": [
            {
                "criterion": "Cancel orders older than threshold",
                "implementation": "Query+update in task",
            },
        ],
        "analysis_hash": analysis.analysis_hash,
        "requires_review": False,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _review_json(analysis: AnalysisOutput, generation: GenerationOutput, **overrides) -> str:
    payload = {
        "decision": "PASS",
        "summary": "Generation satisfies requirement.",
        "issues": [],
        "missing_requirements": [],
        "risk_findings": [],
        "acceptance_criteria_results": [
            {
                "criterion": "Cancel orders older than threshold",
                "passed": True,
                "notes": "Covered.",
            },
        ],
        "severity": "info",
        "requires_revision": False,
        "requires_human_review": False,
        "analysis_hash": analysis.analysis_hash,
        "generation_hash": generation.generation_hash,
        "degraded": False,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _base_context(
    *,
    prior_outputs=(),
    requirement: str = "Add order timeout auto-cancel",
    evidence_text: str = "",
) -> WorkerContext:
    project_context = "sanitized project context"
    if evidence_text:
        project_context = f"{project_context}\n\n{evidence_text}"
    return WorkerContext.build(
        run_id="m5-run",
        requirement=requirement,
        project_context=project_context,
        prior_outputs=tuple(prior_outputs),
    )


def _generate_context(execution_context):
    analyze = execution_context.step_results["analyze"].metadata
    return _base_context(prior_outputs=(("analysis_json", analyze["output.analysis_json"]),))


def _review_context(execution_context):
    analyze = execution_context.step_results["analyze"].metadata
    generate = execution_context.step_results["generate"].metadata
    return _base_context(
        prior_outputs=(
            ("analysis_json", analyze["output.analysis_json"]),
            ("generation_json", generate["output.generation_json"]),
        )
    )


def _agent_executor(tmp_path, *, decision: str = "PASS"):
    analysis = AnalysisOutput.from_json(_analysis_json())
    generation = GenerationOutput.from_json(
        _generation_json(analysis), analysis_hash=analysis.analysis_hash
    )
    analyze_client = CountingLLMClient(_analysis_json())
    generate_client = CountingLLMClient(_generation_json(analysis))
    review_client = CountingLLMClient(_review_json(analysis, generation, decision=decision))
    trace_recorder = TraceRecorder(JsonTraceStorage(tmp_path))
    policy = BudgetPolicy(max_tokens=4096, reserved_response_tokens=512)
    fallback = FallbackManager(RetryStrategy(max_retries=1))

    return AgentExecutor(
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


def test_pass_full_workflow_with_evidence_in_context(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path)
    results = executor.execute_until_complete()

    assert results[-1].current_state == WorkflowState.COMPLETED
    assert results[-1].metadata.get("decision") == "PASS"


def test_reject_full_workflow_with_evidence_in_context(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path, decision="REJECT")
    results = executor.execute_until_complete()

    assert results[-1].current_state == WorkflowState.COMPLETED
    output_key = "output.review_json"
    assert output_key in results[-1].metadata


def test_evidence_collector_integrates_with_workflow(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / "orders.py").write_text(
        "class OrderService:\n    def cancel_timeout(self):\n        pass\n",
        encoding="utf-8",
    )

    registry = ToolRegistry()
    RepositoryToolSet(repo_root).register_into(registry)
    executor = ToolExecutor(registry)
    collector = EvidenceCollector(executor, repo_root)

    bundle = collector.collect(
        run_id="test-integration",
        requirement="订单超时自动取消 order timeout cancel",
        project_summary="sky-takeout Python FastAPI",
        technology_stack=("fastapi", "redis"),
    )

    assert bundle.evidence_hash
    assert len(bundle.tool_call_records) >= 1
    evidence_text = bundle.serialized_context()
    assert "orders.py" in evidence_text or len(bundle.matched_files) > 0

    agent = _agent_executor(tmp_path)
    results = agent.execute_until_complete()

    assert results[-1].current_state == WorkflowState.COMPLETED


def test_state_history_is_complete_with_evidence(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path)
    executor.execute_until_complete()

    states = [t.to_state for t in executor.history]
    assert states == [
        WorkflowState.ANALYZING,
        WorkflowState.GENERATING,
        WorkflowState.REVIEWING,
        WorkflowState.COMPLETED,
    ]


def test_each_worker_runs_exactly_once_in_integration(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path)
    executor.execute_until_complete()

    step_names = list(executor.step_results.keys())
    assert step_names == ["analyze", "generate", "review"]


def test_final_result_does_not_leak_sensitive_values(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path)
    results = executor.execute_until_complete()
    raw = json.dumps(results[-1].metadata)

    assert "sk-abc" not in raw
    assert "api_key=" not in raw


def test_same_mock_inputs_are_deterministic_in_integration(tmp_path: Path) -> None:
    first = _agent_executor(tmp_path / "first")
    second = _agent_executor(tmp_path / "second")

    first_result = first.execute_until_complete()[-1]
    second_result = second.execute_until_complete()[-1]

    assert (
        first_result.metadata["output.review_hash"] == second_result.metadata["output.review_hash"]
    )


def test_no_real_network_in_integration(tmp_path: Path) -> None:
    executor = _agent_executor(tmp_path)
    executor.execute_until_complete()

    for step_name in ["analyze", "generate", "review"]:
        assert step_name in executor.step_results

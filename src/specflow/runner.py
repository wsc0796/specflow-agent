"""Run orchestration: wires evidence collection + workers + artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from specflow.artifacts import ArtifactStore, RunManifest
from specflow.artifacts.models import _hash_text, _now_iso
from specflow.context import ProjectContext
from specflow.evidence import EvidenceCollector
from specflow.evidence.models import EvidenceCollectionConfig
from specflow.executor import AgentExecutor, ExecutionContext
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import (
    LLMClient,
    LLMConfigurationError,
    MockLLMClient,
    OpenAICompatibleConfig,
    OpenAICompatibleLLMClient,
)
from specflow.policy import DEFAULT_POLICY, ExecutionBudget, ExecutionPolicy, PolicyValidator
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.tools import ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import AnalysisOutput, GenerationOutput, WorkerContext, WorkerStepHandler
from specflow.workers.analyze import AnalyzeWorker
from specflow.workers.generate import GenerateWorker
from specflow.workers.review import ReviewWorker


def run(
    *,
    repo: Path,
    requirement: str,
    output: Path,
    provider: str = "mock",
    model: str = "",
    mock: bool = False,
    max_files: int = 5,
    policy: ExecutionPolicy = DEFAULT_POLICY,
) -> int:
    """Run the complete specification generation pipeline. Returns exit code."""
    started_at = _now_iso()
    PolicyValidator().validate(policy)
    execution_budget = ExecutionBudget(policy)
    run_id = _generate_run_id(repo, requirement)
    if not requirement.strip() or max_files <= 0:
        _write_error_artifact(
            output, run_id, started_at, "Requirement and max_files must be non-empty"
        )
        return 2
    use_mock = mock or provider == "mock"

    effective_provider = "mock" if use_mock else provider
    effective_model = "mock-model" if use_mock else (model or "unknown")

    if use_mock:
        mock_clients = _create_mock_clients(requirement)
        analyze_client = mock_clients["analyze"]
        generate_client = mock_clients["generate"]
        review_client = mock_clients["review"]
    else:
        try:
            real_client = _create_llm_client(provider, model, use_mock)
        except LLMConfigurationError:
            _write_error_artifact(output, run_id, started_at, "PROVIDER_CONFIGURATION_FAILED")
            return 2
        analyze_client = generate_client = review_client = real_client

    analyze_client = _PolicyBoundLLMClient(analyze_client, execution_budget)
    generate_client = _PolicyBoundLLMClient(generate_client, execution_budget)
    review_client = _PolicyBoundLLMClient(review_client, execution_budget)

    if not repo.exists() or not repo.is_dir():
        _write_error_artifact(output, run_id, started_at, "REPOSITORY_NOT_FOUND")
        return 2

    registry = ToolRegistry()
    try:
        RepositoryToolSet(repo).register_into(registry)
    except Exception:
        _write_error_artifact(output, run_id, started_at, "REPOSITORY_TOOL_SETUP_FAILED")
        return 2

    evidence_config = EvidenceCollectionConfig(
        max_selected_files=min(max_files, policy.repository.max_selected_files),
        max_total_evidence_chars=policy.repository.max_total_evidence_chars,
        max_tool_calls=20,
    )
    tool_executor = ToolExecutor(registry)
    collector = EvidenceCollector(tool_executor, repo, config=evidence_config)
    try:
        evidence = collector.collect(
            run_id=run_id,
            requirement=requirement,
            project_summary=_repo_summary(repo),
            technology_stack=(),
        )
    except Exception:
        _write_error_artifact(output, run_id, started_at, "EVIDENCE_COLLECTION_FAILED")
        return 3

    project_context = ProjectContext(
        project_name=repo.resolve().name,
        root_path=str(repo.resolve()),
        language="python",
        frameworks=[],
        validation_library="",
        orm="",
        database="",
        test_framework="pytest",
        lint_tools=[],
        dependency_files=[],
        entry_candidates=[],
        top_level_directories=[],
        total_files=evidence.discovered_file_count,
        ignored_directories=[],
        oversized_files=[],
        parse_warnings=list(evidence.warnings),
        technology_evidence=[],
        generated_at=started_at,
    )

    trace_dir = output / ".traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_recorder = TraceRecorder(JsonTraceStorage(trace_dir))
    token_policy = BudgetPolicy(
        max_tokens=policy.max_agent_input_tokens + policy.max_agent_output_tokens,
        reserved_response_tokens=policy.max_agent_output_tokens,
    )
    fallback = FallbackManager(RetryStrategy(max_retries=1))

    evidence_text = evidence.serialized_context()

    analyze_worker = AnalyzeWorker(
        project_context=project_context,
        llm_client=analyze_client,
        trace_recorder=trace_recorder,
        fallback_manager=fallback,
        budget_manager=TokenBudgetManager(token_policy),
        model=effective_model,
    )
    generate_worker = GenerateWorker(
        project_context=project_context,
        llm_client=generate_client,
        trace_recorder=trace_recorder,
        fallback_manager=fallback,
        budget_manager=TokenBudgetManager(token_policy),
        model=effective_model,
    )
    review_worker = ReviewWorker(
        project_context=project_context,
        llm_client=review_client,
        trace_recorder=trace_recorder,
        fallback_manager=fallback,
        budget_manager=TokenBudgetManager(token_policy),
        model=effective_model,
    )

    def _build_worker_context(exec_ctx: ExecutionContext) -> WorkerContext:
        prior_outputs: list[tuple[str, str]] = []
        for step_name in ("analyze", "generate"):
            sr = exec_ctx.step_results.get(step_name)
            if sr is not None:
                for key, value in sr.metadata.items():
                    if key.startswith("output."):
                        prior_outputs.append((key.removeprefix("output."), value))
        return WorkerContext.build(
            run_id=run_id,
            requirement=requirement,
            project_context=evidence_text,
            prior_outputs=tuple(prior_outputs),
        )

    base_worker_context = WorkerContext.build(
        run_id=run_id,
        requirement=requirement,
        project_context=evidence_text,
    )

    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(analyze_worker, base_worker_context),
            "generate": WorkerStepHandler(generate_worker, _build_worker_context),
            "review": WorkerStepHandler(review_worker, _build_worker_context),
        }
    )

    try:
        results = executor.execute_until_complete()
    except Exception:
        _write_error_artifact(output, run_id, started_at, "WORKFLOW_EXECUTION_FAILED")
        return 3

    if not results or results[-1].current_state.value == "failed":
        _write_error_artifact(output, run_id, started_at, "Workflow execution failed")
        return 3

    final = results[-1]
    analysis_json = _extract_output(results, "analysis_json")
    generation_json = _extract_output(results, "generation_json")
    review_json = _extract_output(results, "review_json")
    analysis_hash = _extract_output(results, "analysis_hash")
    generation_hash = _extract_output(results, "generation_hash")
    review_hash = _extract_output(results, "review_hash")
    review_decision = _extract_metadata(results, "decision", "UNKNOWN")
    degraded = _extract_metadata(results, "degraded", "false") == "true"
    requires_review = _extract_metadata(results, "requires_review", "false") == "true"
    requires_human_review = _extract_metadata(results, "requires_human_review", "false") == "true"

    completed_at = _now_iso()
    manifest = RunManifest(
        schema_version="1.0.0",
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        status=final.current_state.value,
        provider_type=effective_provider,
        model=effective_model,
        repository_root=str(repo.resolve()),
        requirement=requirement,
        requirement_hash=_hash_text(requirement),
        evidence_hash=evidence.evidence_hash,
        analysis_hash=analysis_hash,
        generation_hash=generation_hash,
        review_hash=review_hash,
        review_decision=review_decision,
        degraded=degraded,
        requires_review=requires_review or requires_human_review,
        tool_call_count=len(evidence.tool_call_records),
        warnings=evidence.warnings,
    )

    store = ArtifactStore(output)
    try:
        store.write_run(
            run_id=run_id,
            manifest=manifest,
            evidence=evidence,
            analysis_json=analysis_json,
            generation_json=generation_json,
            review_json=review_json,
            tool_calls_json=json.dumps(
                [
                    r.as_dict() if hasattr(r, "as_dict") else asdict(r) if is_dataclass(r) else {}
                    for r in evidence.tool_call_records
                ],
                ensure_ascii=False,
                indent=2,
            ),
            trace_json=_load_run_traces(trace_dir, run_id),
        )
    except Exception:
        _write_error_artifact(output, run_id, started_at, "ARTIFACT_WRITE_FAILED")
        return 3

    if degraded or requires_review or requires_human_review:
        return 4
    return 0


def _create_llm_client(provider: str, model: str, use_mock: bool) -> LLMClient:
    """Create a real LLM client; mock clients are created per-worker."""
    if use_mock:
        raise LLMConfigurationError("_create_llm_client should not be called in mock mode")
    config = OpenAICompatibleConfig.from_env()
    return OpenAICompatibleLLMClient(config)


class _PolicyBoundLLMClient:
    """Apply one run budget to every legacy-worker provider call and retry."""

    def __init__(self, delegate: LLMClient, budget: ExecutionBudget) -> None:
        self._delegate = delegate
        self._budget = budget

    def complete(self, request):
        self._budget.reserve_llm_call()
        return self._delegate.complete(request)


def _create_mock_clients(
    requirement: str,
    *,
    requires_human_review: bool = False,
) -> dict[str, MockLLMClient]:
    """Build internally consistent deterministic Worker responses for CLI smoke runs."""
    analysis = AnalysisOutput.from_json(
        json.dumps(
            {
                "requirement_summary": requirement,
                "goals": ["Produce a reviewable implementation plan."],
                "non_goals": ["Do not modify the target repository."],
                "assumptions": ["Repository evidence is read-only."],
                "affected_components": ["repository"],
                "risks": ["Repository evidence may be incomplete."],
                "acceptance_criteria": ["Persist three structured Worker outputs."],
                "evidence": ["Repository evidence bundle"],
                "requires_review": False,
                "degraded": False,
            },
            ensure_ascii=False,
        )
    )
    generation = GenerationOutput.from_json(
        json.dumps(
            {
                "requirement_summary": analysis.requirement_summary,
                "proposed_solution": "Use the existing Worker pipeline to generate a bounded plan.",
                "architecture_or_design": (
                    "Analyze evidence, generate a plan, then review the result."
                ),
                "affected_components": ["runner", "workers"],
                "implementation_steps": ["Execute workers in workflow order."],
                "api_or_data_changes": ["No target repository changes."],
                "test_plan": ["Validate the complete mock workflow."],
                "risks": ["Human review remains required for production changes."],
                "acceptance_criteria_mapping": [
                    {
                        "criterion": "Persist three structured Worker outputs.",
                        "implementation": "Persist each Worker output as an artifact.",
                    }
                ],
                "analysis_hash": analysis.analysis_hash,
                "requires_review": False,
                "degraded": False,
            },
            ensure_ascii=False,
        ),
        analysis_hash=analysis.analysis_hash,
    )
    review = json.dumps(
        {
            "decision": "PASS",
            "summary": "Mock generation is structurally consistent with its analysis.",
            "issues": [],
            "missing_requirements": [],
            "risk_findings": [],
            "acceptance_criteria_results": [
                {
                    "criterion": "Persist three structured Worker outputs.",
                    "passed": True,
                    "notes": "All three outputs are present.",
                }
            ],
            "severity": "info",
            "requires_revision": False,
            "requires_human_review": requires_human_review,
            "analysis_hash": analysis.analysis_hash,
            "generation_hash": generation.generation_hash,
            "degraded": False,
        },
        ensure_ascii=False,
    )
    return {
        "analyze": MockLLMClient(response_content=analysis.to_json()),
        "generate": MockLLMClient(response_content=generation.to_json()),
        "review": MockLLMClient(response_content=review),
    }


def _extract_output(results: list, key: str, default: str = "{}") -> str:
    """Walk executor results in reverse and return the first match for output.{key}."""
    for r in reversed(results):
        value = r.metadata.get(f"output.{key}")
        if value:
            return value
    return default


def _extract_metadata(results: list, key: str, default: str = "") -> str:
    """Walk executor results in reverse and return the first match for a metadata key."""
    for r in reversed(results):
        value = r.metadata.get(key)
        if value is not None:
            return value
    return default


def _load_run_traces(trace_dir: Path, run_id: str) -> str:
    """Return only this run's metadata-only Worker trace records as JSON."""
    trace_paths = sorted(trace_dir.glob(f"{run_id}-*.json"))
    traces = [json.loads(path.read_text(encoding="utf-8")) for path in trace_paths]
    if len(traces) != 3:
        raise ValueError("Completed workflow must produce exactly three Worker traces")
    return json.dumps(traces, ensure_ascii=False, indent=2)


def _generate_run_id(repo: Path, requirement: str) -> str:
    raw = f"{repo.resolve()}|{requirement}"
    hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"run-{hash_hex}"


def _repo_summary(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        return f"Python project with pyproject.toml at {repo.name}"
    return f"Project at {repo.name}"


def _write_error_artifact(output: Path, run_id: str, started_at: str, error: str) -> None:
    try:
        output.mkdir(parents=True, exist_ok=True)
        error_path = output / f"{run_id}-error.json"
        error_path.write_text(
            json.dumps(
                {"run_id": run_id, "started_at": started_at, "error": error},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

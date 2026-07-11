"""Run orchestration: wires evidence collection + workers + artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from specflow.artifacts import ArtifactStore, RunManifest
from specflow.artifacts.models import _hash_text, _now_iso
from specflow.context import ProjectContext
from specflow.evidence import EvidenceCollector
from specflow.executor import AgentExecutor
from specflow.fallback import FallbackManager, RetryStrategy
from specflow.llm import (
    LLMClient,
    LLMConfigurationError,
    MockLLMClient,
    OpenAICompatibleConfig,
    OpenAICompatibleLLMClient,
)
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.tools import ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet
from specflow.trace import JsonTraceStorage, TraceRecorder
from specflow.workers import WorkerContext, WorkerStepHandler
from specflow.workers.analyze import AnalyzeWorker


def run(
    *,
    repo: Path,
    requirement: str,
    output: Path,
    provider: str = "mock",
    model: str = "",
    mock: bool = False,
) -> int:
    """Run the complete specification generation pipeline. Returns exit code."""
    started_at = _now_iso()
    run_id = _generate_run_id(requirement, started_at)
    use_mock = mock or provider == "mock"

    llm_client = _create_llm_client(provider, model, use_mock)
    effective_provider = "mock" if use_mock else provider
    effective_model = "mock-model" if use_mock else (model or "unknown")

    if not repo.exists() or not repo.is_dir():
        _write_error_artifact(output, run_id, started_at, f"Repository not found: {repo}")
        return 2

    registry = ToolRegistry()
    try:
        RepositoryToolSet(repo).register_into(registry)
    except Exception as exc:
        _write_error_artifact(output, run_id, started_at, str(exc))
        return 2

    tool_executor = ToolExecutor(registry)
    collector = EvidenceCollector(tool_executor, repo)
    try:
        evidence = collector.collect(
            run_id=run_id,
            requirement=requirement,
            project_summary=_repo_summary(repo),
            technology_stack=(),
        )
    except Exception as exc:
        _write_error_artifact(output, run_id, started_at, str(exc))
        return 3

    project_context = ProjectContext(
        project_name=repo.name,
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
        total_files=len(evidence.matched_files),
        ignored_directories=[],
        oversized_files=[],
        parse_warnings=list(evidence.warnings),
        technology_evidence=[],
        generated_at=started_at,
    )

    trace_dir = output / ".traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_recorder = TraceRecorder(JsonTraceStorage(trace_dir))
    policy = BudgetPolicy(max_tokens=8192, reserved_response_tokens=2048)
    fallback = FallbackManager(RetryStrategy(max_retries=1))

    evidence_text = evidence.serialized_context()
    worker_context = WorkerContext.build(
        run_id=run_id,
        requirement=requirement,
        project_context=evidence_text,
    )

    analyze_worker = AnalyzeWorker(
        project_context=project_context,
        llm_client=llm_client,
        trace_recorder=trace_recorder,
        fallback_manager=fallback,
        budget_manager=TokenBudgetManager(policy),
        model=effective_model,
    )

    executor = AgentExecutor(
        {
            "analyze": WorkerStepHandler(analyze_worker, worker_context),
        }
    )

    try:
        results = executor.execute_until_complete()
    except Exception as exc:
        _write_error_artifact(output, run_id, started_at, str(exc))
        return 3

    if not results or results[-1].current_state.value == "failed":
        _write_error_artifact(output, run_id, started_at, "Workflow execution failed")
        return 3

    final = results[-1]
    analysis_json = final.metadata.get("output.analysis_json", "{}")
    generation_json = final.metadata.get("output.generation_json", "{}")
    review_json = final.metadata.get("output.review_json", "{}")
    analysis_hash = final.metadata.get("output.analysis_hash", "")
    generation_hash = final.metadata.get("output.generation_hash", "")
    review_hash = final.metadata.get("output.review_hash", "")
    review_decision = final.metadata.get("decision", "UNKNOWN")
    degraded = final.metadata.get("degraded", "false") == "true"
    requires_review = final.metadata.get("requires_review", "false") == "true"

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
        requires_review=requires_review,
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
                [r.as_dict() if hasattr(r, "as_dict") else {} for r in evidence.tool_call_records],
                ensure_ascii=False,
                indent=2,
            ),
            trace_json="[]",
        )
    except Exception as exc:
        _write_error_artifact(output, run_id, started_at, str(exc))
        return 3

    if degraded:
        return 4
    return 0


_MOCK_ANALYSIS = (
    '{"requirement_summary":"mock","goals":[],"non_goals":[],'
    '"assumptions":[],"affected_components":[],"risks":[],'
    '"acceptance_criteria":[],"evidence":[],'
    '"requires_review":false,"degraded":true}'
)


def _create_llm_client(provider: str, model: str, use_mock: bool) -> LLMClient:
    if use_mock:
        return MockLLMClient(response_content=_MOCK_ANALYSIS)
    try:
        config = OpenAICompatibleConfig.from_env()
        return OpenAICompatibleLLMClient(config)
    except LLMConfigurationError as exc:
        raise SystemExit(f"Provider configuration error: {exc}") from exc


def _generate_run_id(requirement: str, started_at: str) -> str:
    raw = f"{requirement}|{started_at}"
    hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    safe_date = started_at[:19].replace(":", "-")
    return f"run-{safe_date}-{hash_hex}"


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

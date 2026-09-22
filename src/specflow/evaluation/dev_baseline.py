"""Legacy Dev attempts and evaluation-side observation; no task-quality proxy scores."""

from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from statistics import fmean
from threading import Lock

from specflow.evaluation.dataset_v1 import (
    SOURCE_PATHS,
    SOURCE_PROFILE,
    DevCase,
    _object,
    _plain_path,
    load_dev_dataset,
    prepare_source_snapshot,
    validate_frozen_dev,
    validate_source_snapshot,
)
from specflow.evaluation.validators import validate_artifacts
from specflow.llm.exceptions import LLMConfigurationError
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.policy import DEFAULT_POLICY
from specflow.prompts import PromptRegistry
from specflow.runner import RequestObservation, run
from specflow.runner_multi import _build_registry, run_multi_agent

RUNTIME_ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_FIELDS = {"mode", "repo", "output", "provider", "model", "max_files", "requirement"}
SEMANTIC_EVALUATORS = (
    "task_success",
    "fact_evidence_coverage",
    "citation_support",
    "safe_abstention",
)
LEGACY_BENCHMARK_MAX_SELECTED_FILES = 5
MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES = 10
DAY11_BENCHMARK_MAX_SELECTED_FILES = 5


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _runtime_identity(mode: str = "legacy") -> dict:
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(RUNTIME_ROOT), *args], encoding="utf-8"
        ).strip()

    identity = {
        "code_revision": git("rev-parse", "HEAD"),
        "code_worktree_status": git(
            "status",
            "--porcelain",
            "--",
            "src",
            "prompts",
            "pyproject.toml",
            "uv.lock",
            "scripts/run_dev_baseline.py",
        ),
        "python": sys.version.split()[0],
    }
    if mode == "legacy":
        registry = PromptRegistry(RUNTIME_ROOT / "prompts")
        prompts = {}
        for name in ("analyze_requirement", "generate_spec", "review_generation"):
            prompt = registry.get(name, "1.0.0")
            prompts[name] = {"version": prompt.version, "hash": prompt.prompt_hash}
        identity["legacy_prompts"] = prompts
        return identity
    if mode != "multi-agent":
        raise ValueError("Unknown runtime identity mode")

    from specflow.agents.adapter import _build_user_message
    from specflow.plan.enricher import SemanticPlanEnricher

    agents = {}
    for registered in _build_registry().list_agents():
        system_prompt = f"You are the **{registered.role.value}** agent. {registered.description}"
        agents[registered.agent_id] = {
            "role": registered.role.value,
            "prompt_id": registered.prompt_id,
            "prompt_version": registered.prompt_version,
            "input_schema_id": registered.input_schema_id,
            "output_schema_id": registered.output_schema_id,
            "system_prompt_hash": sha256(system_prompt.encode()).hexdigest(),
        }
    identity["multi_agent_prompts"] = {
        "plan_enrichment": {
            "prompt_id_pattern": "enrichment/{role}/v1",
            "prompt_version": "1.0.0",
            "builder_source_hash": sha256(
                inspect.getsource(SemanticPlanEnricher._build_enrichment_prompt).encode()
            ).hexdigest(),
            "temperature": 0.0,
            "max_tokens": 1024,
            "response_format": "json",
        },
        "agent_user_message_builder_hash": sha256(
            inspect.getsource(_build_user_message).encode()
        ).hexdigest(),
        "agents": agents,
    }
    return identity


def _separate(target: Path, output: Path) -> None:
    _plain_path(target)
    _plain_path(output)
    a, b = target.resolve(), output.resolve()
    if a == b or a in b.parents or b in a.parents:
        raise ValueError("Snapshot and output must be separate directories")


def prepare_baseline(workspace: Path, dataset_root: Path, target: Path, output: Path) -> dict:
    """Prepare identities and mirror configuration without any product call."""
    _separate(target, output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Prepared output must be new; existing records cannot be overwritten")
    dataset = load_dev_dataset(dataset_root)
    validate_frozen_dev(workspace, dataset_root, dataset)
    if target.exists():
        validate_source_snapshot(workspace, dataset.revision, target)
    else:
        prepare_source_snapshot(workspace, dataset.revision, target)
    config = {
        "schema_version": "day10-dev-v1",
        "mode": "legacy",
        "provider": "unknown",
        "model": "unknown",
        "run_identity_frozen": False,
        "workspace": str(workspace.resolve()),
        "dataset_root": str(dataset_root.resolve()),
        "target": str(target.resolve()),
        "output": str(output.resolve()),
        "suite": dataset.manifest["suite"],
        "dataset_version": "v1",
        "annotation_version": "v1",
        "dataset_freeze_commit": dataset.manifest["freeze_commit"],
        "repository_revision": dataset.revision,
        "source_profile": SOURCE_PROFILE,
        "source_paths": list(SOURCE_PATHS),
        "planned_ids": [c.case_id for c in dataset.cases],
        "model_input_keys": ["requirement"],
        "policy": asdict(DEFAULT_POLICY),
        "effective_legacy_limits": {
            "max_files": 5,
            "max_tool_calls": 20,
            "fallback_max_retries": 1,
            "temperature": 0.0,
            "max_agent_input_tokens": DEFAULT_POLICY.tokens.max_agent_input_tokens,
            "max_agent_output_tokens": DEFAULT_POLICY.tokens.max_agent_output_tokens,
            "max_file_bytes": DEFAULT_POLICY.repository.max_file_bytes,
            "max_evidence_chars": DEFAULT_POLICY.repository.max_total_evidence_chars,
        },
        "comparison_protocol": {
            "paired_mode": "multi-agent",
            "paired_execution_day": 11,
            "paired_effective_limits_status": "not_comparable; current selected-file caps differ",
            "known_limit_difference": {
                "max_selected_files": {"legacy": 5, "multi_agent": 10},
                "source": "runner.py evidence_config; runner_multi.py EvidenceCollectionConfig",
                "disposition": "record only; no policy or runtime tuning in Day 10",
            },
            "paired_prompt_status": "not_frozen; topology-specific prompts need Day 11 inventory",
            "receiver_protocol": "per_receiver_final_request; no union across receivers",
            "legacy_primary_receiver": "generate",
        },
        "evaluators": {"SF-EVAL": "v1", "SF-EVALUATORS": "v1"},
        "runtime": _runtime_identity("legacy"),
        "created_at": _now(),
    }
    _write_configs(output, config)
    _write(
        output / "prepared.json",
        {
            "status": "prepared_only",
            "planned_count": 20,
            "attempted_count": 0,
            "not_started_count": 20,
            "holdout_opened": False,
            "blockers": ["Live Provider/model identity is not frozen."],
        },
    )
    return config


def prepare_multi_agent_baseline(
    workspace: Path,
    dataset_root: Path,
    target: Path,
    output: Path,
    *,
    legacy_config: Path,
) -> dict:
    """Prepare Day 11 from the frozen Day 10 identity without a product call."""
    _separate(target, output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Prepared output must be new; existing records cannot be overwritten")
    dataset = load_dev_dataset(dataset_root)
    validate_frozen_dev(workspace, dataset_root, dataset)
    validate_source_snapshot(workspace, dataset.revision, target)
    legacy = _object(legacy_config)
    shared = {
        "suite": dataset.manifest["suite"],
        "dataset_version": "v1",
        "annotation_version": "v1",
        "dataset_freeze_commit": dataset.manifest["freeze_commit"],
        "repository_revision": dataset.revision,
        "source_profile": SOURCE_PROFILE,
        "planned_ids": [case.case_id for case in dataset.cases],
        "model_input_keys": ["requirement"],
    }
    if legacy.get("mode") != "legacy" or any(
        legacy.get(key) != value for key, value in shared.items()
    ):
        raise ValueError("Day 10 identity does not match the frozen Day 11 inputs")
    if legacy.get("policy") != asdict(DEFAULT_POLICY):
        raise ValueError("Day 10 policy differs from the current shared policy")
    if legacy.get("provider") not in {"mock", "openai-compatible"}:
        raise ValueError("Day 10 Provider identity is not frozen")

    config = {
        "schema_version": "day11-dev-v1",
        "mode": "multi-agent",
        "provider": legacy["provider"],
        "model": legacy["model"],
        "run_identity_frozen": False,
        "workspace": str(workspace.resolve()),
        "dataset_root": str(dataset_root.resolve()),
        "target": str(target.resolve()),
        "output": str(output.resolve()),
        **shared,
        "source_paths": list(SOURCE_PATHS),
        "policy": asdict(DEFAULT_POLICY),
        "product_default_multi_agent_limits": {
            "max_selected_files": min(
                MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES,
                DEFAULT_POLICY.repository.max_selected_files,
            ),
        },
        "effective_multi_agent_limits": {
            "max_selected_files": DAY11_BENCHMARK_MAX_SELECTED_FILES,
            "max_total_evidence_chars": DEFAULT_POLICY.repository.max_total_evidence_chars,
            "max_tool_calls": 20,
            "max_parallel_agents": DEFAULT_POLICY.max_parallel_agents,
            "max_revisions": DEFAULT_POLICY.max_revisions,
            "guarded_agent_llm_calls": DEFAULT_POLICY.max_llm_calls,
            "coordinator_enrichment_calls": 6,
            "coordinator_calls_counted_by_runtime_guard": False,
            "plan_enrichment_max_tokens": 1024,
            "agent_max_tokens": DEFAULT_POLICY.tokens.max_agent_output_tokens,
            "temperature": 0.0,
            "agent_runner_max_retries": 0,
            "provider_internal_retries": 0,
            "max_file_bytes": DEFAULT_POLICY.repository.max_file_bytes,
        },
        "comparison_protocol": {
            "paired_mode": "legacy",
            "paired_result_commit": "271d409cb0164ffa998a47b164abed3682c60801",
            "receiver_protocol": "per_receiver_actual_llm_request; no union across receivers",
            "multi_agent_primary_receiver": "repository-analyst-agent-v1",
            "known_limit_difference": {
                "max_selected_files": {
                    "legacy": LEGACY_BENCHMARK_MAX_SELECTED_FILES,
                    "multi_agent_product_default": (MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES),
                    "multi_agent_benchmark": DAY11_BENCHMARK_MAX_SELECTED_FILES,
                },
                "status": "pending_learner_decision",
            },
        },
        "fairness_decision": {
            "status": "pending_learner_decision",
            "selected_experiment": None,
            "legacy_max_selected_files": LEGACY_BENCHMARK_MAX_SELECTED_FILES,
            "multi_agent_product_default_max_selected_files": (
                MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
            ),
            "multi_agent_benchmark_max_selected_files": DAY11_BENCHMARK_MAX_SELECTED_FILES,
        },
        "evaluators": {"SF-EVAL": "v1", "SF-EVALUATORS": "v1"},
        "artifact_profile": {
            "contract_run_success": (
                "portfolio_multi_agent_mock@5f2815d (not silently reused for live Dataset v1)"
            ),
            "artifact_observation": "current_multi_agent_artifacts_v1",
        },
        "runtime": _runtime_identity("multi-agent"),
        "created_at": _now(),
        "paired_day10_config": str(legacy_config.resolve()),
    }
    _write_configs(output, config)
    _write(
        output / "prepared.json",
        {
            "status": "prepared_only",
            "planned_count": 20,
            "attempted_count": 0,
            "not_started_count": 20,
            "holdout_opened": False,
            "blockers": [
                "Run identity is not frozen for the Day 11 code revision.",
                "Fairness decision is pending learner review.",
            ],
        },
    )
    return config


def _write_configs(output: Path, config: dict) -> None:
    _write(output / "run-config.json", config)
    if config.get("mode") == "legacy":
        _write(output / "day11-mirror-config.json", {**config, "mode": "multi-agent"})


def _provider_identity(provider: str, model: str) -> dict:
    if provider == "mock" and model == "mock-model":
        return {"provider": provider, "model": model, "evidence_level": "mock_contract"}
    if provider != "openai-compatible" or not model or model == "unknown":
        raise ValueError("Explicit Provider/model identity is required")
    try:
        config = OpenAICompatibleConfig.from_env()
    except LLMConfigurationError:
        raise ValueError("Live Provider environment is incomplete or invalid") from None
    if config.model != model:
        raise ValueError("Requested model differs from actual provider config.model")
    return {
        "provider": provider,
        "model": model,
        "base_url": config.base_url,
        "provider_timeout_seconds": config.timeout_seconds,
        "evidence_level": "live_provider",
        "provider_model_version": "unknown unless immutable provider identity is supplied",
    }


def freeze_run_identity(output: Path, *, provider: str, model: str) -> dict:
    if (output / "attempts.json").exists():
        raise ValueError("Cannot change identity after an attempt")
    identity = _provider_identity(provider, model)
    config = _object(output / "run-config.json")
    mode = config.get("mode", "legacy")
    runtime = _runtime_identity(mode)
    if provider != "mock" and runtime["code_worktree_status"]:
        raise ValueError("Live runtime code must be committed before identity freeze")
    config.update(
        provider=provider,
        model=model,
        provider_identity=identity,
        runtime=runtime,
        run_identity_frozen=True,
        frozen_at=_now(),
    )
    _write_configs(output, config)
    return config


def record_fairness_decision(output: Path, decision: str) -> dict:
    """Record the learner's experiment choice without changing product defaults."""
    if (output / "attempts.json").exists():
        raise ValueError("Cannot change fairness decision after an attempt")
    config = _object(output / "run-config.json")
    if config.get("mode") != "multi-agent":
        raise ValueError("Fairness decisions apply only to the Multi-Agent Dev run")
    config["product_default_multi_agent_limits"] = {
        "max_selected_files": MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES,
    }
    if decision == "current-topology-as-is":
        config["effective_multi_agent_limits"]["max_selected_files"] = (
            MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
        )
        config["fairness_decision"] = {
            "status": "not_selected_for_official_day11",
            "selected_experiment": decision,
            "legacy_max_selected_files": LEGACY_BENCHMARK_MAX_SELECTED_FILES,
            "multi_agent_product_default_max_selected_files": (
                MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
            ),
            "multi_agent_benchmark_max_selected_files": (
                MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
            ),
            "confounder": "effective max_selected_files differs across the two paths",
            "not_comparable_dimensions": [
                "source_reference_and_evidence_counts",
                "fact_evidence_coverage",
                "task_success",
                "citation_support",
                "safe_abstention",
                "token_cost",
                "latency",
            ],
        }
    elif decision == "controlled-cap-at-5":
        config["effective_multi_agent_limits"]["max_selected_files"] = (
            DAY11_BENCHMARK_MAX_SELECTED_FILES
        )
        config["fairness_decision"] = {
            "status": "approved",
            "selected_experiment": decision,
            "legacy_max_selected_files": LEGACY_BENCHMARK_MAX_SELECTED_FILES,
            "multi_agent_product_default_max_selected_files": (
                MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
            ),
            "multi_agent_benchmark_max_selected_files": DAY11_BENCHMARK_MAX_SELECTED_FILES,
            "isolated_variable": "topology",
        }
    else:
        raise ValueError("Unknown fairness decision")
    config["comparison_protocol"]["known_limit_difference"]["status"] = config["fairness_decision"][
        "status"
    ]
    _write_configs(output, config)
    return config


def build_adapter_input(
    case: DevCase, *, repo: Path, output: Path, provider: str, model: str, mode: str
) -> dict:
    """Common answer-free product input envelope for either topology."""
    if mode not in {"legacy", "multi-agent"}:
        raise ValueError("Unknown adapter mode")
    return {
        "mode": mode,
        "repo": str(repo.resolve()),
        "output": str(output.resolve()),
        "provider": provider,
        "model": model,
        "max_files": (
            LEGACY_BENCHMARK_MAX_SELECTED_FILES
            if mode == "legacy"
            else DAY11_BENCHMARK_MAX_SELECTED_FILES
        ),
        **case.product_input(),
    }


def execute_worker(payload: dict) -> int:
    """Product-side process: no Dataset path, annotations, or evaluator invocation."""
    if set(payload) != PAYLOAD_FIELDS:
        raise ValueError("Unexpected product input fields")
    mode = payload["mode"]
    expected_max_files = {
        "legacy": LEGACY_BENCHMARK_MAX_SELECTED_FILES,
        "multi-agent": DAY11_BENCHMARK_MAX_SELECTED_FILES,
    }.get(mode)
    if (
        expected_max_files is None
        or payload["max_files"] != expected_max_files
        or not isinstance(payload["requirement"], str)
    ):
        raise ValueError("Invalid frozen product input")
    _provider_identity(payload["provider"], payload["model"])
    target, output = Path(payload["repo"]), Path(payload["output"])
    _separate(target, output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Worker output must be new")
    records = []
    observation_failed = False
    observation_lock = Lock()

    def observe(event: RequestObservation) -> None:
        nonlocal observation_failed
        try:
            record = asdict(event)
            if mode == "multi-agent":
                record["receiver"] = record.pop("worker")
            with observation_lock:
                records.append(record)
                _write(output / "llm-requests.json", records)
        except Exception:
            observation_failed = True
            raise

    try:
        if mode == "legacy":
            return run(
                repo=target,
                requirement=payload["requirement"],
                output=output,
                provider=payload["provider"],
                model=payload["model"],
                max_files=5,
                request_observer=observe,
            )
        benchmark_policy = replace(
            DEFAULT_POLICY,
            repository=replace(
                DEFAULT_POLICY.repository,
                max_selected_files=DAY11_BENCHMARK_MAX_SELECTED_FILES,
            ),
        )
        return run_multi_agent(
            repo=target,
            requirement=payload["requirement"],
            output=output,
            mock=payload["provider"] == "mock",
            provider=payload["provider"],
            model=payload["model"],
            policy=benchmark_policy,
            request_observer=observe,
        )
    finally:
        try:
            _write(
                output / "observation-status.json",
                {
                    "status": "incomplete" if observation_failed else "complete",
                    "boundary": (
                        "budgeted_legacy_client.complete"
                        if mode == "legacy"
                        else "multi_agent_llm_client.complete"
                    ),
                    "observed_call_count": len(records),
                    "http_delivery": "unknown",
                    "product_returned_control": True,
                },
            )
        except OSError:
            pass  # Parent classifies an absent status as unknown.


def launch_worker(payload_path: Path) -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specflow.evaluation.dev_baseline",
            "--worker-input",
            str(payload_path),
        ],
        cwd=RUNTIME_ROOT,
        capture_output=True,
        timeout=DEFAULT_POLICY.max_wall_time_seconds + 30,
        check=False,
    )
    return result.returncode


def _unknown_result(reason: str, *, version: str = "v1-hypothesis") -> dict:
    return {
        "version": version,
        "evaluator_status": "incomplete",
        "verdict": "unknown",
        "reason": reason,
        "evidence_locators": [],
    }


def _multi_agent_artifact_observation(artifact: Path) -> tuple[dict, dict | None, dict | None]:
    required = (
        "manifest.json",
        "metrics.json",
        "agent-outputs.json",
        "handoffs.json",
        "traces.json",
        "sources.json",
        "checkpoints.json",
        "artifact-integrity.json",
        "_COMPLETE",
    )
    findings = [f"missing:{name}" for name in required if not (artifact / name).is_file()]
    manifest = metrics = None
    try:
        manifest = _object(artifact / "manifest.json")
        metrics = _object(artifact / "metrics.json")
        integrity = _object(artifact / "artifact-integrity.json")
        hashes = integrity.get("artifact_hashes")
        if not isinstance(hashes, dict):
            findings.append("artifact_integrity_invalid")
        else:
            for name, digest in hashes.items():
                path = artifact / str(name)
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or not isinstance(digest, str)
                    or sha256(path.read_bytes()).hexdigest() != digest
                ):
                    findings.append(f"artifact_hash_mismatch:{name}")
    except (OSError, ValueError, KeyError, TypeError):
        findings.append("artifact_json_unreadable")
    observation = {
        "version": "current_multi_agent_artifacts_v1",
        "evaluator_status": "valid" if manifest is not None else "incomplete",
        "verdict": "pass" if not findings else "fail",
        "raw_findings": findings,
        "required_artifacts": list(required),
    }
    return observation, manifest, metrics


def inspect_attempt(output: Path, target: Path, *, mode: str = "legacy") -> dict:
    result = {
        "product_terminal_state": "unknown",
        "artifact_directory": None,
        "observation_status": "unknown",
        "observation_locator": None,
        "evaluator_results": {
            name: _unknown_result("Requires evidence mapping and calibrated review.")
            for name in SEMANTIC_EVALUATORS
        },
    }
    if mode == "legacy":
        result["evaluator_results"]["contract_run_success"] = {
            "version": "v1",
            "profile": "portfolio_multi_agent_mock@5f2815d",
            "evaluator_status": "valid",
            "verdict": "N/A",
            "reason": "Profile does not apply to Legacy.",
        }
        result["evaluator_results"]["legacy_artifact_validation"] = _unknown_result(
            "No readable artifact set.", version="existing_core"
        )
    elif mode == "multi-agent":
        result["evaluator_results"]["contract_run_success"] = {
            "version": "v1",
            "profile": "portfolio_multi_agent_mock@5f2815d",
            "evaluator_status": "incomplete",
            "verdict": "unknown",
            "reason": (
                "The frozen profile is Mock portfolio-only; no live Dataset v1 profile is frozen."
            ),
        }
        result["evaluator_results"]["artifact_validation"] = _unknown_result(
            "No readable Multi-Agent artifact set.", version="current_multi_agent_artifacts_v1"
        )
        result["evaluator_results"]["source_reference_validity"] = _unknown_result(
            "The Legacy sources path profile does not match Multi-Agent sources.json."
        )
    else:
        raise ValueError("Unknown attempt inspection mode")
    request_records: list[dict] = []
    try:
        status = _object(output / "observation-status.json")
        result["observation_status"] = status["status"]
        result["observation_metadata"] = status
        if (output / "llm-requests.json").is_file():
            _plain_path(output / "llm-requests.json")
            records = json.loads((output / "llm-requests.json").read_text(encoding="utf-8"))
            if not isinstance(records, list) or len(records) != status.get("observed_call_count"):
                result["observation_status"] = "incomplete"
            else:
                request_records = [record for record in records if isinstance(record, dict)]
            result["observation_locator"] = str(output / "llm-requests.json")
        elif status.get("observed_call_count") != 0:
            result["observation_status"] = "incomplete"
    except (OSError, ValueError, KeyError):
        result["observation_status"] = "unknown"
    run_dirs = [
        path
        for path in output.glob("run-*")
        if path.is_dir()
        and not path.is_symlink()
        and ((mode == "multi-agent") == path.name.startswith("run-multi-"))
    ]
    if len(run_dirs) == 1:
        artifact = run_dirs[0]
        result["artifact_directory"] = str(artifact)
        try:
            if mode == "multi-agent":
                observation, manifest, metrics = _multi_agent_artifact_observation(artifact)
                result["evaluator_results"]["artifact_validation"] = observation
                if manifest is None:
                    raise ValueError("Unreadable Multi-Agent manifest")
                result["product_terminal_state"] = manifest.get("workflow_state", "unknown")
                result["run_id"] = manifest.get("run_id", "unknown")
                result["degraded"] = (
                    bool(metrics.get("degraded_count", 0)) if metrics is not None else "unknown"
                )
                coordinator_requests = sum(
                    record.get("receiver") == "coordinator_enricher" for record in request_records
                )
                if metrics is not None:
                    input_tokens = metrics.get("input_tokens")
                    output_tokens = metrics.get("output_tokens")
                    total_tokens = metrics.get("total_tokens")
                    valid_usage = all(
                        isinstance(value, int) and not isinstance(value, bool) and value >= 0
                        for value in (input_tokens, output_tokens, total_tokens)
                    )
                    result["usage_observation"] = {
                        "scope": "agent_stage_results_only; excludes Coordinator enrichment",
                        "request_count": len(request_records),
                        "metered_agent_request_count": metrics.get("llm_call_count", "unknown"),
                        "unmetered_enrichment_request_count": coordinator_requests,
                        "observed_input_tokens_subtotal": input_tokens
                        if valid_usage
                        else "unknown",
                        "observed_output_tokens_subtotal": output_tokens
                        if valid_usage
                        else "unknown",
                        "observed_total_tokens_subtotal": total_tokens
                        if valid_usage
                        else "unknown",
                        "all_provider_usage_complete": valid_usage and coordinator_requests == 0,
                    }
            else:
                manifest = _object(artifact / "manifest.json")
                result["product_terminal_state"] = manifest.get("status", "unknown")
                result["run_id"] = manifest.get("run_id", "unknown")
                result["degraded"] = manifest.get("degraded", "unknown")
            result["terminal_evidence"] = str(artifact / "manifest.json")
            if mode == "legacy":
                findings = validate_artifacts(artifact, target, require_live=False)
                result["evaluator_results"]["legacy_artifact_validation"] = {
                    "version": "existing_core",
                    "evaluator_status": "valid",
                    "verdict": "fail" if findings else "pass",
                    "raw_findings": [asdict(f) for f in findings],
                }
        except (OSError, ValueError, TypeError, KeyError):
            pass
    result["error_artifacts"] = [str(p) for p in output.glob("run-*-error.json") if p.is_file()]
    return result


def summarize_attempts(
    planned_ids: list[str], attempts: list[dict], *, mode: str = "legacy"
) -> dict:
    latencies = [a["wall_time_ms"] for a in attempts if a.get("wall_time_ms") is not None]
    count = len(attempts)
    if mode == "multi-agent":
        usage = [attempt.get("usage_observation", {}) for attempt in attempts]
        complete_count = sum(item.get("all_provider_usage_complete") is True for item in usage)
        input_values = [
            item.get("observed_input_tokens_subtotal")
            for item in usage
            if isinstance(item.get("observed_input_tokens_subtotal"), int)
            and not isinstance(item.get("observed_input_tokens_subtotal"), bool)
        ]
        output_values = [
            item.get("observed_output_tokens_subtotal")
            for item in usage
            if isinstance(item.get("observed_output_tokens_subtotal"), int)
            and not isinstance(item.get("observed_output_tokens_subtotal"), bool)
        ]
        total_values = [
            item.get("observed_total_tokens_subtotal")
            for item in usage
            if isinstance(item.get("observed_total_tokens_subtotal"), int)
            and not isinstance(item.get("observed_total_tokens_subtotal"), bool)
        ]
        token_cost = {
            "population": "all_attempted_case_runs",
            "request_count": sum(
                item.get("request_count", 0)
                for item in usage
                if isinstance(item.get("request_count"), int)
            ),
            "complete_run_count": complete_count,
            "attempted_run_count": count,
            "unknown_run_count": count - complete_count,
            "telemetry_coverage": complete_count / count if count else "N/A",
            "observed_input_tokens_subtotal": sum(input_values),
            "observed_output_tokens_subtotal": sum(output_values),
            "observed_total_tokens_subtotal": sum(total_values),
            "full_total": sum(total_values)
            if count and complete_count == count
            else ("unknown" if count else "N/A"),
            "comparison_status": "comparable"
            if count and complete_count == count
            else ("not_comparable" if count else "N/A"),
            "reason": "Current metrics omit Coordinator enrichment usage.",
        }
    elif mode == "legacy":
        token_cost = {
            "population": "all_attempted_case_runs",
            "observed_subtotal": "unknown",
            "full_total": "unknown" if count else "N/A",
            "telemetry_coverage": "unknown" if count else "N/A",
            "comparison_status": "not_comparable" if count else "N/A",
            "reason": "Worker trace usage does not establish all-call completeness.",
        }
    else:
        raise ValueError("Unknown attempt summary mode")
    return {
        "planned_count": len(planned_ids),
        "attempted_count": count,
        "not_started_count": len(set(planned_ids) - {a["case_id"] for a in attempts}),
        "not_started_ids": [c for c in planned_ids if c not in {a["case_id"] for a in attempts}],
        "latency_ms": {
            "observed_count": len(latencies),
            "mean": fmean(latencies) if latencies else "N/A",
        },
        "token_cost": token_cost,
        "task_success": {"pass": 0, "fail": 0, "unknown": count, "N/A": 0},
        "terminal_counts": dict(
            Counter(a.get("product_terminal_state", "unknown") for a in attempts)
        ),
    }


def _validate_controlled_multi_agent_config(config: dict) -> None:
    fairness = config.get("fairness_decision", {})
    if fairness.get("selected_experiment") == "current-topology-as-is":
        raise ValueError("Only controlled-cap-at-5 is approved for the official Day 11 run")
    if fairness.get("status") != "approved":
        raise ValueError("Fairness decision has not been approved")
    expected = (
        fairness.get("selected_experiment") == "controlled-cap-at-5"
        and fairness.get("legacy_max_selected_files") == LEGACY_BENCHMARK_MAX_SELECTED_FILES
        and fairness.get("multi_agent_product_default_max_selected_files")
        == MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
        and fairness.get("multi_agent_benchmark_max_selected_files")
        == DAY11_BENCHMARK_MAX_SELECTED_FILES
        and config.get("product_default_multi_agent_limits", {}).get("max_selected_files")
        == MULTI_AGENT_PRODUCT_DEFAULT_MAX_SELECTED_FILES
        and config.get("effective_multi_agent_limits", {}).get("max_selected_files")
        == DAY11_BENCHMARK_MAX_SELECTED_FILES
    )
    if not expected:
        raise ValueError("Invalid controlled benchmark configuration")


def run_prepared(output: Path) -> dict:
    """Execute one fixed Dev pass; journal every attempt before spawning a child."""
    config = _object(output / "run-config.json")
    mode = config.get("mode")
    if mode not in {"legacy", "multi-agent"}:
        raise ValueError("Unknown prepared execution mode")
    if mode == "multi-agent":
        _validate_controlled_multi_agent_config(config)
    if not config.get("run_identity_frozen"):
        raise ValueError("Run identity has not been frozen")
    if (output / "attempts.json").exists():
        raise ValueError("Existing attempts cannot be repeated or overwritten")
    if _provider_identity(config["provider"], config["model"]) != config["provider_identity"]:
        raise ValueError("Provider identity changed after freeze")
    if _runtime_identity(mode) != config["runtime"] or config["policy"] != asdict(DEFAULT_POLICY):
        raise ValueError("Runtime identity or policy changed after freeze")
    target = Path(config["target"])
    _separate(target, output)
    dataset = load_dev_dataset(Path(config["dataset_root"]))
    validate_frozen_dev(Path(config["workspace"]), Path(config["dataset_root"]), dataset)
    if (
        dataset.revision != config["repository_revision"]
        or [c.case_id for c in dataset.cases] != config["planned_ids"]
    ):
        raise ValueError("Dataset identity changed after prepare")
    validate_source_snapshot(Path(config["workspace"]), dataset.revision, target)
    attempts = []
    for case in dataset.cases:
        attempt_id = f"{case.case_id}-{uuid.uuid4().hex[:12]}"
        case_output = output / "attempts" / attempt_id
        payload = build_adapter_input(
            case,
            repo=target,
            output=case_output,
            provider=config["provider"],
            model=config["model"],
            mode=mode,
        )
        payload_path = output / "inputs" / f"{attempt_id}.json"
        _write(payload_path, payload)
        attempt = {
            "case_id": case.case_id,
            "attempt_id": attempt_id,
            "attempt_status": "started",
            "started_at": _now(),
            "exit_code": None,
            "wall_time_ms": None,
        }
        attempts.append(attempt)
        _write(output / "attempts.json", attempts)
        start = time.perf_counter()
        interrupted = False
        try:
            attempt["exit_code"] = launch_worker(payload_path)
            attempt["attempt_status"] = "returned"
        except KeyboardInterrupt:
            attempt["attempt_status"] = "interrupted"
            interrupted = True
        except (OSError, subprocess.TimeoutExpired) as exc:
            attempt["attempt_status"] = "execution_error"
            attempt["error_type"] = type(exc).__name__
        finally:
            attempt["wall_time_ms"] = round((time.perf_counter() - start) * 1000, 3)
            attempt["ended_at"] = _now()
            attempt.update(inspect_attempt(case_output, target, mode=mode))
            _write(output / "attempts.json", attempts)
        if interrupted:
            break
    report = {
        "config": config,
        "summary": summarize_attempts(config["planned_ids"], attempts, mode=mode),
        "attempts": attempts,
        "status": "recorded; semantic review pending",
    }
    report_slug = "legacy" if mode == "legacy" else "multi-agent"
    _write(output / f"{report_slug}-dev-report.json", report)
    attempted_ids = {a["case_id"] for a in attempts}
    _write(
        output / "evaluator-review-inputs.json",
        {
            "usage": "Evaluator-only, after execution",
            "cases": [c.annotations for c in dataset.cases if c.case_id in attempted_ids],
        },
    )
    lines = [
        f"# {'Legacy' if mode == 'legacy' else 'Multi-Agent'} Dev Report",
        "",
        f"模式：{config['provider_identity']['evidence_level']}；语义评分待复核。",
        "",
        f"Planned {len(config['planned_ids'])} / Attempted {len(attempts)} / "
        f"Not started {report['summary']['not_started_count']}",
        "",
        "| Case | Exit | Product state | Observation | Task success |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {a['case_id']} | {a['exit_code']} | {a['product_terminal_state']} | "
        f"{a['observation_status']} | unknown |"
        for a in attempts
    )
    lines += ["", "完整 Token 成本 unknown，比较状态 not_comparable；结构校验不代表任务成功。", ""]
    (output / f"{report_slug}-dev-report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or explicitly execute Dataset v1 Dev by frozen topology."
    )
    parser.add_argument("--worker-input", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("legacy", "multi-agent"), default="legacy")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--legacy-config",
        type=Path,
        default=RUNTIME_ROOT / "data/day10/legacy-dev/run-config.json",
    )
    parser.add_argument("--provider", choices=("mock", "openai-compatible"))
    parser.add_argument("--model")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--freeze-identity", action="store_true")
    action.add_argument("--execute", action="store_true")
    action.add_argument(
        "--fairness-decision",
        choices=("current-topology-as-is", "controlled-cap-at-5"),
    )
    args = parser.parse_args(argv)
    try:
        if args.worker_input:
            return execute_worker(_object(args.worker_input))
        output = args.output or (
            RUNTIME_ROOT / "data/day10/legacy-dev"
            if args.mode == "legacy"
            else RUNTIME_ROOT / "data/day11/multi-agent-dev"
        )
        if not args.freeze_identity and (args.provider or args.model):
            raise ValueError(
                "Provider/model options require --freeze-identity; overrides are not ignored"
            )
        if args.execute:
            run_prepared(output)
        elif args.freeze_identity:
            freeze_run_identity(
                output, provider=args.provider or "unknown", model=args.model or "unknown"
            )
        elif args.fairness_decision:
            record_fairness_decision(output, args.fairness_decision)
        else:
            if args.mode == "legacy":
                prepare_baseline(
                    RUNTIME_ROOT,
                    RUNTIME_ROOT / "docs/study/datasets/v1",
                    RUNTIME_ROOT / "data/day10/target",
                    output,
                )
            else:
                prepare_multi_agent_baseline(
                    RUNTIME_ROOT,
                    RUNTIME_ROOT / "docs/study/datasets/v1",
                    RUNTIME_ROOT / "data/day10/target",
                    output,
                    legacy_config=args.legacy_config,
                )
        print(json.dumps({"status": "recorded", "output": str(output)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Configuration objects and provider payloads must never appear in errors.
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error_type": type(exc).__name__,
                    "message": str(exc)
                    if isinstance(exc, ValueError)
                    else "Input or observation unavailable",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Legacy Dev attempts and evaluation-side observation; no task-quality proxy scores."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean

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

RUNTIME_ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_FIELDS = {"mode", "repo", "output", "provider", "model", "max_files", "requirement"}
SEMANTIC_EVALUATORS = (
    "task_success",
    "fact_evidence_coverage",
    "citation_support",
    "safe_abstention",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _runtime_identity() -> dict:
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(RUNTIME_ROOT), *args], encoding="utf-8"
        ).strip()

    registry = PromptRegistry(RUNTIME_ROOT / "prompts")
    prompts = {}
    for name in ("analyze_requirement", "generate_spec", "review_generation"):
        prompt = registry.get(name, "1.0.0")
        prompts[name] = {"version": prompt.version, "hash": prompt.prompt_hash}
    return {
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
        "legacy_prompts": prompts,
        "python": sys.version.split()[0],
    }


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
        "runtime": _runtime_identity(),
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


def _write_configs(output: Path, config: dict) -> None:
    _write(output / "run-config.json", config)
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
    runtime = _runtime_identity()
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


def build_adapter_input(
    case: DevCase, *, repo: Path, output: Path, provider: str, model: str, mode: str
) -> dict:
    """Common input envelope; the Day 11 mirror is plan-only in this task."""
    if mode not in {"legacy", "multi-agent"}:
        raise ValueError("Unknown adapter mode")
    return {
        "mode": mode,
        "repo": str(repo.resolve()),
        "output": str(output.resolve()),
        "provider": provider,
        "model": model,
        "max_files": 5,
        **case.product_input(),
    }


def execute_worker(payload: dict) -> int:
    """Product-side process: no Dataset path, annotations, or evaluator invocation."""
    if set(payload) != PAYLOAD_FIELDS:
        raise ValueError("Unexpected product input fields")
    if payload["mode"] != "legacy":
        raise ValueError("Day 11 Multi-Agent execution is disabled")
    if payload["max_files"] != 5 or not isinstance(payload["requirement"], str):
        raise ValueError("Invalid frozen product input")
    _provider_identity(payload["provider"], payload["model"])
    target, output = Path(payload["repo"]), Path(payload["output"])
    _separate(target, output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Worker output must be new")
    records = []
    observation_failed = False

    def observe(event: RequestObservation) -> None:
        nonlocal observation_failed
        try:
            records.append(asdict(event))
            _write(output / "llm-requests.json", records)
        except Exception:
            observation_failed = True
            raise

    try:
        return run(
            repo=target,
            requirement=payload["requirement"],
            output=output,
            provider=payload["provider"],
            model=payload["model"],
            max_files=5,
            request_observer=observe,
        )
    finally:
        try:
            _write(
                output / "observation-status.json",
                {
                    "status": "incomplete" if observation_failed else "complete",
                    "boundary": "budgeted_legacy_client.complete",
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


def inspect_attempt(output: Path, target: Path) -> dict:
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
    try:
        status = _object(output / "observation-status.json")
        result["observation_status"] = status["status"]
        result["observation_metadata"] = status
        if (output / "llm-requests.json").is_file():
            _plain_path(output / "llm-requests.json")
            records = json.loads((output / "llm-requests.json").read_text(encoding="utf-8"))
            if not isinstance(records, list) or len(records) != status.get("observed_call_count"):
                result["observation_status"] = "incomplete"
            result["observation_locator"] = str(output / "llm-requests.json")
        elif status.get("observed_call_count") != 0:
            result["observation_status"] = "incomplete"
    except (OSError, ValueError, KeyError):
        result["observation_status"] = "unknown"
    run_dirs = [p for p in output.glob("run-*") if p.is_dir() and not p.is_symlink()]
    if len(run_dirs) == 1:
        artifact = run_dirs[0]
        result["artifact_directory"] = str(artifact)
        try:
            manifest = _object(artifact / "manifest.json")
            result["product_terminal_state"] = manifest.get("status", "unknown")
            result["run_id"] = manifest.get("run_id", "unknown")
            result["degraded"] = manifest.get("degraded", "unknown")
            result["terminal_evidence"] = str(artifact / "manifest.json")
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


def summarize_attempts(planned_ids: list[str], attempts: list[dict]) -> dict:
    latencies = [a["wall_time_ms"] for a in attempts if a.get("wall_time_ms") is not None]
    count = len(attempts)
    return {
        "planned_count": len(planned_ids),
        "attempted_count": count,
        "not_started_count": len(set(planned_ids) - {a["case_id"] for a in attempts}),
        "not_started_ids": [c for c in planned_ids if c not in {a["case_id"] for a in attempts}],
        "latency_ms": {
            "observed_count": len(latencies),
            "mean": fmean(latencies) if latencies else "N/A",
        },
        "token_cost": {
            "population": "all_attempted_case_runs",
            "observed_subtotal": "unknown",
            "full_total": "unknown" if count else "N/A",
            "telemetry_coverage": "unknown" if count else "N/A",
            "comparison_status": "not_comparable" if count else "N/A",
            "reason": "Worker trace usage does not establish all-call completeness.",
        },
        "task_success": {"pass": 0, "fail": 0, "unknown": count, "N/A": 0},
        "terminal_counts": dict(
            Counter(a.get("product_terminal_state", "unknown") for a in attempts)
        ),
    }


def run_prepared(output: Path) -> dict:
    """Execute one fixed Dev pass; journal every attempt before spawning a child."""
    config = _object(output / "run-config.json")
    if config.get("mode") != "legacy":
        raise ValueError("Day 11 execution is disabled")
    if not config.get("run_identity_frozen"):
        raise ValueError("Run identity has not been frozen")
    if (output / "attempts.json").exists():
        raise ValueError("Existing attempts cannot be repeated or overwritten")
    if _provider_identity(config["provider"], config["model"]) != config["provider_identity"]:
        raise ValueError("Provider identity changed after freeze")
    if _runtime_identity() != config["runtime"] or config["policy"] != asdict(DEFAULT_POLICY):
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
            mode="legacy",
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
            attempt.update(inspect_attempt(case_output, target))
            _write(output / "attempts.json", attempts)
        if interrupted:
            break
    report = {
        "config": config,
        "summary": summarize_attempts(config["planned_ids"], attempts),
        "attempts": attempts,
        "status": "recorded; semantic review pending",
    }
    _write(output / "legacy-dev-report.json", report)
    attempted_ids = {a["case_id"] for a in attempts}
    _write(
        output / "evaluator-review-inputs.json",
        {
            "usage": "Evaluator-only, after execution",
            "cases": [c.annotations for c in dataset.cases if c.case_id in attempted_ids],
        },
    )
    lines = [
        "# Legacy Dev Report",
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
    (output / "legacy-dev-report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or explicitly execute Legacy Dataset v1 Dev."
    )
    parser.add_argument("--worker-input", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=RUNTIME_ROOT / "data/day10/legacy-dev")
    parser.add_argument("--provider", choices=("mock", "openai-compatible"))
    parser.add_argument("--model")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--freeze-identity", action="store_true")
    action.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.worker_input:
            return execute_worker(_object(args.worker_input))
        if not args.freeze_identity and (args.provider or args.model):
            raise ValueError(
                "Provider/model options require --freeze-identity; overrides are not ignored"
            )
        if args.execute:
            run_prepared(args.output)
        elif args.freeze_identity:
            freeze_run_identity(
                args.output, provider=args.provider or "unknown", model=args.model or "unknown"
            )
        else:
            prepare_baseline(
                RUNTIME_ROOT,
                RUNTIME_ROOT / "docs/study/datasets/v1",
                RUNTIME_ROOT / "data/day10/target",
                args.output,
            )
        print(json.dumps({"status": "recorded", "output": str(args.output)}, ensure_ascii=False))
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

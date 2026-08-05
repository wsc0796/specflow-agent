"""Credential-safe harness for the frozen live-provider v1 evaluation suite.

This module is deliberately separate from the mock benchmark.  It runs the
existing multi-agent runner against an OpenAI-compatible Provider, normalizes
the resulting evidence, and leaves final quality judgement to a human review.
"""

from __future__ import annotations

import codecs
import json
import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import yaml

from specflow.llm import LLMClient, OpenAICompatibleConfig, OpenAICompatibleLLMClient
from specflow.llm.models import LLMRequest, LLMResponse
from specflow.policy import DEFAULT_POLICY
from specflow.runner_multi import run_multi_agent
from specflow.tools.repository_policy import RepositoryAccessPolicy
from specflow.tools.sanitization import sanitize_tool_text

LIVE_PROVIDER = "openai-compatible"
QUALITY_CLASS = "quality"
CONTROL_CLASS = "control"
_REQUIRED_TASK_FIELDS = frozenset(
    {
        "task_id",
        "repository",
        "repository_commit",
        "user_request",
        "expected_files",
        "required_evidence",
        "required_output_fields",
        "forbidden_assumptions",
        "timeout_seconds",
        "human_notes",
    }
)
_OPTIONAL_TASK_FIELDS = frozenset({"evaluation_class", "max_llm_calls"})
_ALLOWED_TOOL_NAMES = frozenset({"list_files", "search_code", "read_file"})
_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
_PATH_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"
    r"\.(?:py|md|toml|yaml|yml|json)(?![A-Za-z0-9_.-])"
)
_SENSITIVE_KEY_RE = re.compile(
    r"^(?:api[_-]?key|authorization|password|secret|credentials?|private[_-]?key|"
    r"client[_-]?secret|access[_-]?token|refresh[_-]?token|id[_-]?token|token)$",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(
    r"(?i)\bbearer\s+(?!(?:prefix|token|header|scheme|value|auth|authentication|"
    r"credentials?|type|key|name|jwt)\b)[A-Za-z0-9._~+/=-]{8,}"
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|client[_-]?secret|credential|private[_-]?key|token)"
    r"\s*[:=]\s*([^\s,;]+)"
)
_JSON_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|authorization|password|secret|client[_-]?secret|"
    r"credential|private[_-]?key|token)[\"']?\s*:\s*)"
    r"(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^,\s}\]]+)"
)
_LIKELY_SECRET_RE = re.compile(
    r"\b(?:sk|rk)-[A-Za-z0-9_-]{12,}\b|\bghp_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b"
)
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<!\w)(?:[A-Za-z]:[\\/][^\s\"']+|/(?:Users|home|tmp|var|etc)/[^\s\"']+)"
)
_BATCH_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_EVIDENCE_FILES = frozenset(
    {
        "task.yaml",
        "config.json",
        "raw_provider_response.json",
        "tool_calls.jsonl",
        "trace.jsonl",
        "deterministic-result.json",
    }
)


class LiveEvaluationError(ValueError):
    """Raised when frozen evaluation inputs or local prerequisites are invalid."""


@dataclass(frozen=True)
class LiveEvalTask:
    """One frozen task or runtime control in the live evaluation suite."""

    task_id: str
    repository: str
    repository_commit: str
    user_request: str
    expected_files: tuple[str, ...]
    required_evidence: tuple[str, ...]
    required_output_fields: tuple[str, ...]
    forbidden_assumptions: tuple[str, ...]
    timeout_seconds: int
    human_notes: str
    evaluation_class: str
    max_llm_calls: int
    source_path: Path


@dataclass(frozen=True)
class LiveEvalSuite:
    """Parsed immutable evaluation inputs."""

    quality_tasks: tuple[LiveEvalTask, ...]
    control_tasks: tuple[LiveEvalTask, ...]
    repository: str
    repository_commit: str
    suite_lock_sha256: str = ""

    @property
    def all_tasks(self) -> tuple[LiveEvalTask, ...]:
        return self.quality_tasks + self.control_tasks


@dataclass(frozen=True)
class PricingRule:
    """Explicit, versioned token-pricing evidence supplied for a live run."""

    provider: str
    model: str
    input_usd_per_million_tokens: float
    output_usd_per_million_tokens: float
    source_url: str
    retrieved_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_usd_per_million_tokens": self.input_usd_per_million_tokens,
            "output_usd_per_million_tokens": self.output_usd_per_million_tokens,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
        }


class RedactingResponseRecorder:
    """Thread-safe opt-in capture of sanitized, successful Provider responses."""

    def __init__(self, secret_values: Iterable[str], *, max_bytes: int = 5 * 1024 * 1024) -> None:
        self._secret_values = tuple(value for value in secret_values if value)
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._responses: list[dict[str, object]] = []
        self._provider_failures: Counter[str] = Counter()
        self._provider_request_count = 0
        self._provider_response_count = 0
        self._provider_response_usage: list[tuple[int, int] | None] = []
        self._completion_count = 0
        self._captured_bytes = 0
        self._truncated = False

    def observe(self, payload: dict[str, Any]) -> None:
        """Record a response body after recursive credential and path redaction."""
        redacted = _redact_provider_value(payload, self._secret_values)
        encoded = json.dumps(redacted, ensure_ascii=False, sort_keys=True).encode("utf-8")
        with self._lock:
            self._provider_response_count += 1
            self._provider_response_usage.append(_provider_reported_usage(payload))
            if self._captured_bytes + len(encoded) > self._max_bytes:
                self._truncated = True
                return
            self._responses.append(
                {
                    "sequence": len(self._responses) + 1,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "body": redacted,
                }
            )
            self._captured_bytes += len(encoded)

    def observe_failure(self, error: Exception) -> None:
        """Record only a safe Provider failure category, never its original text."""
        category = _classify_provider_failure(error)
        with self._lock:
            self._provider_failures[category] += 1

    def observe_request(self) -> None:
        """Record a Provider invocation without retaining the request itself."""
        with self._lock:
            self._provider_request_count += 1

    def observe_completion(self, response: LLMResponse) -> None:
        """Track successful client completions without treating fallback usage as Provider data."""
        del response
        with self._lock:
            self._completion_count += 1

    def as_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": "1.0",
                "capture_kind": "provider_response_body_after_redaction",
                "redacted": True,
                "response_count": self._provider_response_count,
                "captured_response_count": len(self._responses),
                "truncated": self._truncated,
                "responses": list(self._responses),
                "provider_failure_categories": dict(sorted(self._provider_failures.items())),
                "provider_request_count": self._provider_request_count,
                "provider_usage": {
                    "response_usage_count": sum(
                        usage is not None for usage in self._provider_response_usage
                    ),
                    "response_usage_complete": self._provider_response_count > 0
                    and len(self._provider_response_usage) == self._provider_response_count
                    and all(usage is not None for usage in self._provider_response_usage),
                },
            }

    @property
    def provider_failure_categories(self) -> dict[str, int]:
        with self._lock:
            return dict(sorted(self._provider_failures.items()))

    @property
    def provider_usage(self) -> dict[str, object]:
        with self._lock:
            response_usage_complete = self._provider_response_count > 0 and all(
                usage is not None for usage in self._provider_response_usage
            )
            request_usage_complete = (
                response_usage_complete
                and self._provider_request_count == self._provider_response_count
                and self._completion_count == self._provider_response_count
            )
            input_tokens = (
                sum(usage[0] for usage in self._provider_response_usage if usage is not None)
                if response_usage_complete
                else None
            )
            output_tokens = (
                sum(usage[1] for usage in self._provider_response_usage if usage is not None)
                if response_usage_complete
                else None
            )
            return {
                "request_count": self._provider_request_count,
                "response_count": self._provider_response_count,
                "completion_count": self._completion_count,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "usage_complete": request_usage_complete,
            }


class _FailureRecordingLLMClient:
    """Keep Provider failure taxonomy available after the runner safely degrades."""

    def __init__(self, delegate: LLMClient, recorder: RedactingResponseRecorder) -> None:
        self._delegate = delegate
        self._recorder = recorder

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._recorder.observe_request()
        try:
            response = self._delegate.complete(request)
        except Exception as error:
            self._recorder.observe_failure(error)
            raise
        self._recorder.observe_completion(response)
        return response


def load_live_suite(*, tasks_dir: Path, controls_dir: Path, lock_path: Path) -> LiveEvalSuite:
    """Load the byte-locked quality tasks and controls in stable order."""
    lock = _read_json_object(lock_path, "suite lock")
    quality_paths = tuple(sorted(tasks_dir.glob("*.yaml")))
    control_paths = tuple(sorted(controls_dir.glob("*.yaml")))
    if not 5 <= len(quality_paths) <= 10:
        raise LiveEvaluationError("live-provider v1 requires five to ten quality tasks")
    if not control_paths:
        raise LiveEvaluationError("live-provider v1 requires at least one runtime control")

    _verify_locked_paths(quality_paths, lock.get("task_sha256"), "quality task")
    _verify_locked_paths(control_paths, lock.get("control_sha256"), "control")
    repository = _required_text(lock, "repository", "suite lock")
    repository_commit = _required_text(lock, "repository_commit", "suite lock")

    quality_tasks = tuple(_load_task(path, QUALITY_CLASS) for path in quality_paths)
    control_tasks = tuple(_load_task(path, CONTROL_CLASS) for path in control_paths)
    all_tasks = quality_tasks + control_tasks
    if len({task.task_id for task in all_tasks}) != len(all_tasks):
        raise LiveEvaluationError("live-provider task IDs must be unique")
    for task in all_tasks:
        if task.repository != repository or task.repository_commit != repository_commit:
            raise LiveEvaluationError("task repository identity does not match the suite lock")
    return LiveEvalSuite(
        quality_tasks=quality_tasks,
        control_tasks=control_tasks,
        repository=repository,
        repository_commit=repository_commit,
        suite_lock_sha256=_file_sha256(lock_path),
    )


def load_provider_config(
    *, environment: Mapping[str, str] | None = None, model_override: str = ""
) -> OpenAICompatibleConfig:
    """Load real-provider configuration without serializing or printing its key."""
    try:
        config = OpenAICompatibleConfig.from_env(environment)
    except Exception as exc:
        raise LiveEvaluationError("live Provider configuration is incomplete or invalid") from exc
    if not model_override.strip():
        return config
    return replace(config, model=model_override.strip())


def load_pricing_rule(path: Path, *, provider: str, model: str) -> PricingRule:
    """Load an explicit, auditable token-pricing rule for cost estimates."""
    raw = _read_yaml_object(path, "pricing rule")
    if raw.get("schema_version") != "1.0":
        raise LiveEvaluationError("pricing rule schema_version must be 1.0")
    rule = PricingRule(
        provider=_required_text(raw, "provider", "pricing rule"),
        model=_required_text(raw, "model", "pricing rule"),
        input_usd_per_million_tokens=_non_negative_number(
            raw.get("input_usd_per_million_tokens"), "input token price"
        ),
        output_usd_per_million_tokens=_non_negative_number(
            raw.get("output_usd_per_million_tokens"), "output token price"
        ),
        source_url=_required_text(raw, "source_url", "pricing rule"),
        retrieved_at=_required_text(raw, "retrieved_at", "pricing rule"),
    )
    parsed = urlsplit(rule.source_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise LiveEvaluationError("pricing rule source_url must be an HTTPS URL")
    try:
        date.fromisoformat(rule.retrieved_at)
    except ValueError as exc:
        raise LiveEvaluationError("pricing rule retrieved_at must use YYYY-MM-DD") from exc
    if rule.provider != provider or rule.model != model:
        raise LiveEvaluationError(
            "pricing rule Provider and model must match the live configuration"
        )
    return rule


def preflight_live_suite(
    *, suite: LiveEvalSuite, repository_root: Path, config: OpenAICompatibleConfig
) -> dict[str, object]:
    """Verify all deterministic preconditions before constructing a Provider client."""
    root = repository_root.resolve()
    if not root.is_dir():
        raise LiveEvaluationError("evaluation repository root does not exist")
    head = _git(root, "rev-parse", "HEAD")
    if head != suite.repository_commit:
        raise LiveEvaluationError("evaluation repository is not at the frozen commit")
    if _git(root, "status", "--porcelain"):
        raise LiveEvaluationError("evaluation repository worktree must be clean")
    for task in suite.all_tasks:
        for relative_path in (*task.expected_files, *task.required_evidence):
            if not _git_path_exists(root, suite.repository_commit, relative_path):
                raise LiveEvaluationError(
                    f"frozen evaluation file is absent from target commit: {relative_path}"
                )

    policy = RepositoryAccessPolicy(root)
    sensitive_probes = (
        ".env",
        ".env.production",
        "credentials",
        "id_rsa",
        ".ssh/id_rsa",
        "deploy/private.key",
    )
    if not all(policy.is_sensitive_path(path) for path in sensitive_probes):
        raise LiveEvaluationError("repository sensitive-path control is not configured as expected")
    return {
        "repository": suite.repository,
        "repository_commit": head,
        "repository_worktree_clean": True,
        "provider": LIVE_PROVIDER,
        "model": config.model,
        "sensitive_path_control": "passed",
    }


def run_live_suite(
    *,
    suite: LiveEvalSuite,
    repository_root: Path,
    runs_root: Path,
    config: OpenAICompatibleConfig,
    pricing: PricingRule,
    _client_factory: Callable[[OpenAICompatibleConfig, RedactingResponseRecorder], LLMClient]
    | None = None,
) -> list[dict[str, object]]:
    """Run the frozen suite sequentially and persist evidence for every attempt."""
    preflight = preflight_live_suite(
        suite=suite,
        repository_root=repository_root,
        config=config,
    )
    if pricing.provider != LIVE_PROVIDER or pricing.model != config.model:
        raise LiveEvaluationError("pricing rule does not match the live Provider configuration")
    if not suite.suite_lock_sha256:
        raise LiveEvaluationError("live evaluation suite must include a lock hash")
    if not _SHA256_RE.fullmatch(suite.suite_lock_sha256):
        raise LiveEvaluationError("live evaluation suite has an invalid lock hash")
    tasks = suite.all_tasks
    task_hashes = {task.task_id: _file_sha256(task.source_path) for task in tasks}
    if len(task_hashes) != len(tasks):
        raise LiveEvaluationError("live evaluation suite task IDs must be unique")
    harness = _specflow_provenance()
    if _client_factory is None and harness["worktree_clean"] is not True:
        raise LiveEvaluationError("SpecFlow evaluation harness worktree must be clean")
    runs_root.mkdir(parents=True, exist_ok=True)
    batch_id = _batch_id()
    execution_provenance = (
        "test_double" if _client_factory is not None else "live_openai_compatible"
    )
    batch_manifest = {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "execution_provenance": execution_provenance,
        "suite_lock_sha256": suite.suite_lock_sha256,
        "specflow_commit": harness["commit"],
        "specflow_worktree_clean": harness["worktree_clean"],
        "repository": suite.repository,
        "repository_commit": suite.repository_commit,
        "provider": LIVE_PROVIDER,
        "model": config.model,
        "pricing_rule": pricing.as_dict(),
        "quality_task_ids": [task.task_id for task in suite.quality_tasks],
        "control_task_ids": [task.task_id for task in suite.control_tasks],
        "task_sha256": task_hashes,
        "attempts": [],
    }
    manifest_path = _batch_manifest_path(runs_root, batch_id)
    # Persist the planned immutable batch before any Provider client can be constructed.
    _write_json(manifest_path, batch_manifest)
    results: list[dict[str, object]] = []
    for task in tasks:
        result = _run_one_task(
            task=task,
            repository_root=repository_root.resolve(),
            runs_root=runs_root,
            config=config,
            pricing=pricing,
            preflight=preflight,
            batch_id=batch_id,
            suite_lock_sha256=suite.suite_lock_sha256,
            execution_provenance=execution_provenance,
            specflow_commit=str(harness["commit"]),
            specflow_worktree_clean=harness["worktree_clean"] is True,
            client_factory=_client_factory,
        )
        results.append(result)
        batch_manifest["attempts"].append(
            {
                "task_id": result["task_id"],
                "evaluation_class": result["evaluation_class"],
                "attempt_directory": result["attempt_directory"],
                "task_sha256": result["task_sha256"],
                "deterministic_result_sha256": _file_sha256(
                    runs_root / str(result["attempt_directory"]) / "deterministic-result.json"
                ),
                "evidence_sha256": _attempt_evidence_hashes(
                    runs_root / str(result["attempt_directory"])
                ),
            }
        )
        _write_json(manifest_path, batch_manifest)
    batch_manifest["status"] = "completed"
    batch_manifest["completed_at"] = datetime.now(UTC).isoformat()
    _write_json(manifest_path, batch_manifest)
    return results


def build_live_report(
    runs_root: Path,
    *,
    batch_id: str,
    _allow_test_provenance: bool = False,
) -> dict[str, object]:
    """Aggregate persisted deterministic results without pretending pending review passed."""
    batch_manifest, attempts = _load_batch_attempts(
        runs_root,
        batch_id,
        allow_test_provenance=_allow_test_provenance,
    )
    quality = [item for item in attempts if item.get("evaluation_class") == QUALITY_CLASS]
    controls = [item for item in attempts if item.get("evaluation_class") == CONTROL_CLASS]
    completed = [item for item in quality if item.get("run_completed") is True]
    schema_passed = [item for item in quality if item.get("schema_passed") is True]
    quality_usage_complete = bool(quality) and all(
        item.get("provider_usage_complete") is True for item in quality
    )
    input_tokens = (
        [_as_non_negative_int(item.get("input_tokens")) for item in quality]
        if quality_usage_complete
        else []
    )
    output_tokens = (
        [_as_non_negative_int(item.get("output_tokens")) for item in quality]
        if quality_usage_complete
        else []
    )
    latencies = [
        _as_non_negative_int(item.get("outer_wall_time_ms"))
        for item in completed
        if _as_non_negative_int(item.get("outer_wall_time_ms")) > 0
    ]
    cited_total = sum(_as_non_negative_int(item.get("cited_path_count")) for item in quality)
    cited_valid = sum(_as_non_negative_int(item.get("valid_cited_path_count")) for item in quality)
    evidence_total = sum(
        _as_non_negative_int(item.get("required_evidence_count")) for item in quality
    )
    evidence_covered = sum(
        _as_non_negative_int(item.get("required_evidence_covered_count")) for item in quality
    )
    reviewed = [item for item in quality if item.get("human_review_status") != "pending"]
    evidence_supported = [item for item in reviewed if item.get("human_evidence_supported") is True]
    assumption_counts = [
        item.get("human_unsupported_assumption_count")
        for item in reviewed
        if isinstance(item.get("human_unsupported_assumption_count"), int)
    ]
    batch_usage_complete = bool(attempts) and all(
        item.get("provider_usage_complete") is True for item in attempts
    )
    costs = [item.get("estimated_cost_usd") for item in attempts]
    cost_is_known = batch_usage_complete and all(isinstance(value, int | float) for value in costs)
    failure_categories = Counter(
        str(item.get("failure_category", "unknown"))
        for item in quality
        if item.get("failure_category") != "none"
    )
    control_categories = Counter(str(item.get("failure_category", "unknown")) for item in controls)
    deterministic_pass = [item for item in quality if item.get("deterministic_status") == "passed"]
    controls_passed = [item for item in controls if item.get("deterministic_status") == "passed"]
    provider_models = sorted(
        {
            (str(item.get("provider", "unknown")), str(item.get("model", "unknown")))
            for item in attempts
        }
    )
    pricing_rules = _unique_pricing_rules(attempts)
    all_quality_passed = quality and len(deterministic_pass) == len(quality)
    all_controls_passed = not controls or len(controls_passed) == len(controls)
    return {
        "schema_version": "1.0",
        "mode": "live_provider",
        "mock_results_included": False,
        "attempt_count": len(attempts),
        "quality_task_count": len(quality),
        "control_count": len(controls),
        "status": "human_review_required"
        if all_quality_passed and all_controls_passed
        else "deterministic_failures_present",
        "batch_id": batch_id,
        "execution_provenance": batch_manifest["execution_provenance"],
        "suite_lock_sha256": batch_manifest["suite_lock_sha256"],
        "provider_models": [
            {"provider": provider, "model": model} for provider, model in provider_models
        ],
        "pricing_rules": pricing_rules,
        "metrics": {
            "completion_rate": _rate(len(completed), len(quality)),
            "schema_success_rate": _rate(len(schema_passed), len(quality)),
            "parseable_file_reference_validity_rate": _rate_or_none(cited_valid, cited_total),
            "required_evidence_coverage_rate": _rate_or_none(evidence_covered, evidence_total),
            "human_evidence_support_rate": _rate_or_none(len(evidence_supported), len(reviewed)),
            "human_unsupported_assumption_count": (
                sum(assumption_counts)
                if assumption_counts and len(assumption_counts) == len(reviewed)
                else None
            ),
            "latency_ms": {
                "sample_count": len(latencies),
                "p50": _nearest_rank(latencies, 0.50),
                "p95": _nearest_rank(latencies, 0.95),
                "average": round(fmean(latencies), 2) if latencies else None,
            },
            "quality_token_usage_complete": quality_usage_complete,
            "average_input_tokens": round(fmean(input_tokens), 2) if input_tokens else None,
            "average_output_tokens": round(fmean(output_tokens), 2) if output_tokens else None,
            "total_input_tokens": sum(input_tokens) if quality_usage_complete else None,
            "total_output_tokens": sum(output_tokens) if quality_usage_complete else None,
            "total_estimated_cost_usd": round(sum(costs), 8) if cost_is_known else None,
            "cost_estimate_status": (
                "estimated_all_declared_attempts" if cost_is_known else "provider_usage_unavailable"
            ),
            "failure_categories": dict(sorted(failure_categories.items())),
            "control_failure_categories": dict(sorted(control_categories.items())),
        },
        "runs": attempts,
    }


def render_live_report(report: Mapping[str, object]) -> str:
    """Render a conservative Markdown report from script-generated evidence."""
    metrics = _as_mapping(report.get("metrics"))
    latency = _as_mapping(metrics.get("latency_ms"))
    lines = [
        "# Live Provider Evaluation v1",
        "",
        f"Status: `{report.get('status', 'unknown')}`",
        "",
        "This report is generated from frozen-task artifacts. It contains only live",
        "OpenAI-compatible Provider attempts; Mock benchmark results are excluded.",
        "A deterministic pass is not a human quality PASS.",
        "",
        "## Sample",
        "",
        f"- Quality tasks: {report.get('quality_task_count', 0)}",
        f"- Runtime controls: {report.get('control_count', 0)}",
        f"- Total attempts: {report.get('attempt_count', 0)}",
        f"- Provider/model: {_format_provider_models(report.get('provider_models'))}",
        "",
        "## Deterministic Metrics",
        "",
        "| Metric | Result |",
        "| --- | --- |",
        f"| Completion rate | {_format_rate(metrics.get('completion_rate'))} |",
        f"| Schema success rate | {_format_rate(metrics.get('schema_success_rate'))} |",
        "| Parseable file-reference validity | "
        f"{_format_rate(metrics.get('parseable_file_reference_validity_rate'))} |",
        "| Required-evidence coverage | "
        f"{_format_rate(metrics.get('required_evidence_coverage_rate'))} |",
        f"| P50 end-to-end latency | {_format_ms(latency.get('p50'))} |",
        f"| P95 end-to-end latency | {_format_ms(latency.get('p95'))} |",
        f"| Average input tokens | {_format_number(metrics.get('average_input_tokens'))} |",
        f"| Average output tokens | {_format_number(metrics.get('average_output_tokens'))} |",
        f"| Estimated total cost | {_format_cost(metrics.get('total_estimated_cost_usd'))} |",
        f"| Cost estimate status | {metrics.get('cost_estimate_status', 'not available')} |",
        "",
        "P50/P95 use nearest-rank over completed live quality tasks only.",
        "Token averages use all quality attempts only when every quality attempt has",
        "Provider-reported usage. Cost includes all declared quality and control attempts",
        "only when every Provider request has reported usage.",
        "",
        "## Cost Rule",
        "",
    ]
    pricing_rules = report.get("pricing_rules")
    if isinstance(pricing_rules, list) and pricing_rules:
        lines.extend(
            [
                "| Provider | Model | Input USD/M token | Output USD/M token | "
                "Source | Retrieved |",
                "| --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for rule in pricing_rules:
            if not isinstance(rule, Mapping):
                continue
            row = "| {provider} | {model} | {input_price} | {output_price} |".format(
                provider=rule.get("provider", "unknown"),
                model=rule.get("model", "unknown"),
                input_price=rule.get("input_usd_per_million_tokens", "unknown"),
                output_price=rule.get("output_usd_per_million_tokens", "unknown"),
            )
            lines.append(
                f"{row} {rule.get('source_url', 'unknown')} | "
                f"{rule.get('retrieved_at', 'unknown')} |"
            )
    else:
        lines.append("No valid pricing rule was recorded; cost is unavailable.")
    lines.extend(
        [
            "",
            "## Human Review",
            "",
            "| Metric | Result |",
            "| --- | --- |",
            "| Evidence support rate | "
            f"{_format_rate(metrics.get('human_evidence_support_rate'))} |",
            "| Unsupported assumptions | "
            f"{_format_number(metrics.get('human_unsupported_assumption_count'))} |",
            "",
            "Human review records task coverage, evidence support, unsupported assumptions,",
            "and technical actionability in each `human-review.yaml`. The Agent's internal",
            "`PASS`/`REJECT` field is not used as the final evaluation decision.",
            "",
            "## Attempts",
            "",
            "| Task | Class | Completed | Deterministic | Failure category | Evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    runs = report.get("runs")
    if isinstance(runs, list):
        for item in runs:
            if not isinstance(item, Mapping):
                continue
            lines.append(
                "| {task} | {kind} | {completed} | {status} | {failure} | `{evidence}` |".format(
                    task=item.get("task_id", "unknown"),
                    kind=item.get("evaluation_class", "unknown"),
                    completed="yes" if item.get("run_completed") is True else "no",
                    status=item.get("deterministic_status", "unknown"),
                    failure=item.get("failure_category", "none"),
                    evidence=item.get("attempt_directory", "unavailable"),
                )
            )
    failed_attempts = [
        item
        for item in (runs if isinstance(runs, list) else [])
        if isinstance(item, Mapping) and item.get("failure_category") != "none"
    ]
    lines.extend(
        [
            "",
            "## Failure Examples",
            "",
        ]
    )
    if failed_attempts:
        for item in failed_attempts:
            lines.append(
                "- `{task}` ({kind}): `{failure}`; evidence `{evidence}`.".format(
                    task=item.get("task_id", "unknown"),
                    kind=item.get("evaluation_class", "unknown"),
                    failure=item.get("failure_category", "unknown"),
                    evidence=item.get("attempt_directory", "unavailable"),
                )
            )
    else:
        lines.append("- No failed attempts were recorded.")
    lines.extend(
        [
            "",
            "## Failures And Limits",
            "",
            "- Runtime controls are not included in the quality completion or schema rates.",
            "- The sample is repository-specific and too small to prove production reliability,",
            "  model accuracy, multi-tenant behavior, or high-concurrency performance.",
            "- Cost is an estimate from the recorded pricing rule and Provider-reported tokens.",
            "  It is unavailable rather than understated when any declared attempt has",
            "  unknown Provider usage.",
            "- Redacted Provider response bodies, tool logs, traces, and runner artifacts are",
            "  retained under the local ignored run directory named in the evidence column.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_live_report(report: Mapping[str, object], path: Path) -> None:
    """Write a generated report atomically."""
    _write_text(path, render_live_report(report))


def _run_one_task(
    *,
    task: LiveEvalTask,
    repository_root: Path,
    runs_root: Path,
    config: OpenAICompatibleConfig,
    pricing: PricingRule,
    preflight: Mapping[str, object],
    batch_id: str,
    suite_lock_sha256: str,
    execution_provenance: str,
    specflow_commit: str,
    specflow_worktree_clean: bool,
    client_factory: Callable[[OpenAICompatibleConfig, RedactingResponseRecorder], LLMClient] | None,
) -> dict[str, object]:
    attempt_id = _attempt_id(task.task_id)
    attempt_dir = runs_root / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(task.source_path, attempt_dir / "task.yaml")
    policy = replace(
        DEFAULT_POLICY,
        max_wall_time_seconds=task.timeout_seconds,
        max_llm_calls=task.max_llm_calls,
    )
    _write_json(
        attempt_dir / "config.json",
        {
            "schema_version": "1.0",
            "batch_id": batch_id,
            "execution_provenance": execution_provenance,
            "suite_lock_sha256": suite_lock_sha256,
            "task_sha256": _file_sha256(task.source_path),
            "provider": LIVE_PROVIDER,
            "model": config.model,
            "base_url": config.base_url,
            "provider_timeout_seconds": config.timeout_seconds,
            "api_key_configured": True,
            "task_timeout_seconds": task.timeout_seconds,
            "execution_policy_hash": policy.policy_hash(),
            "max_llm_calls": policy.max_llm_calls,
            "specflow_commit": specflow_commit,
            "specflow_worktree_clean": specflow_worktree_clean,
            "target_repository": task.repository,
            "target_repository_commit": task.repository_commit,
            "pricing_rule": pricing.as_dict(),
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    recorder = RedactingResponseRecorder((config.api_key,))
    if client_factory is None:
        base_client: LLMClient = OpenAICompatibleLLMClient(
            config,
            _response_observer=recorder.observe,
        )
    else:
        base_client = client_factory(config, recorder)
    client = _FailureRecordingLLMClient(base_client, recorder)

    t0 = time.perf_counter()
    exit_code = 3
    harness_error = ""
    try:
        exit_code = run_multi_agent(
            repo=repository_root,
            requirement=task.user_request,
            output=attempt_dir / "artifacts",
            mock=False,
            provider=LIVE_PROVIDER,
            model=config.model,
            policy=policy,
            _llm_client=client,
        )
    except Exception:
        harness_error = "EVALUATION_HARNESS_ERROR"
    outer_wall_time_ms = max(0, int((time.perf_counter() - t0) * 1000))
    capture = recorder.as_dict()
    _write_json(attempt_dir / "raw_provider_response.json", capture)
    run_dir = _find_runner_artifact_dir(attempt_dir / "artifacts")
    _write_jsonl(
        attempt_dir / "tool_calls.jsonl",
        _load_list_from_artifact(run_dir, "sources.json", "tool_calls"),
    )
    _write_jsonl(attempt_dir / "trace.jsonl", _load_list_from_artifact(run_dir, "traces.json"))
    result = _validate_attempt(
        task=task,
        attempt_dir=attempt_dir,
        run_dir=run_dir,
        repository_root=repository_root,
        pricing=pricing,
        preflight=preflight,
        exit_code=exit_code,
        outer_wall_time_ms=outer_wall_time_ms,
        provider_response_count=capture["response_count"],
        provider_failure_categories=recorder.provider_failure_categories,
        provider_usage=recorder.provider_usage,
        batch_id=batch_id,
        suite_lock_sha256=suite_lock_sha256,
        execution_provenance=execution_provenance,
        task_sha256=_file_sha256(task.source_path),
        specflow_commit=specflow_commit,
        specflow_worktree_clean=specflow_worktree_clean,
        harness_error=harness_error,
        secret_values=(config.api_key,),
    )
    _write_json(attempt_dir / "deterministic-result.json", result)
    _write_yaml(attempt_dir / "human-review.yaml", _human_review_template(task, result))
    return result


def _validate_attempt(
    *,
    task: LiveEvalTask,
    attempt_dir: Path,
    run_dir: Path | None,
    repository_root: Path,
    pricing: PricingRule,
    preflight: Mapping[str, object],
    exit_code: int,
    outer_wall_time_ms: int,
    provider_response_count: object,
    provider_failure_categories: Mapping[str, int],
    provider_usage: Mapping[str, object],
    batch_id: str,
    suite_lock_sha256: str,
    execution_provenance: str,
    task_sha256: str,
    specflow_commit: str,
    specflow_worktree_clean: bool,
    harness_error: str,
    secret_values: Sequence[str],
) -> dict[str, object]:
    manifest = _load_json_from_run(run_dir, "manifest.json")
    metrics = _load_json_from_run(run_dir, "metrics.json")
    outputs = _load_json_from_run(run_dir, "agent-outputs.json")
    sources = _load_json_from_run(run_dir, "sources.json")
    tool_records = _read_jsonl(attempt_dir / "tool_calls.jsonl")
    run_completed = exit_code == 0 and manifest.get("workflow_state") == "completed"
    schema_passed = (
        isinstance(metrics.get("schema_unvalidated_count"), int)
        and metrics.get("schema_unvalidated_count") == 0
        and _as_non_negative_int(metrics.get("schema_validated_count")) >= 6
    )
    artifact_integrity_passed = _verify_artifact_integrity(run_dir)
    required_fields_missing = [
        field for field in task.required_output_fields if not _has_output_field(outputs, field)
    ]
    cited_paths = _extract_cited_paths(outputs)
    valid_cited_paths = [
        path
        for path in cited_paths
        if _is_safe_relative_path(path)
        and _git_path_exists(repository_root, task.repository_commit, path)
    ]
    cited_set = set(cited_paths)
    source_hashes = _source_hash_mapping(sources)
    source_hashed_paths = set(source_hashes)
    repository_policy = RepositoryAccessPolicy(repository_root)
    required_evidence_cited = sorted(set(task.required_evidence).intersection(cited_set))
    required_evidence_collected = sorted(
        set(task.required_evidence).intersection(source_hashed_paths)
    )
    required_evidence_hash_verified = sorted(
        _frozen_source_hash_matches(
            source_hashes,
            repository_root,
            repository_policy,
            task.repository_commit,
            task.required_evidence,
        )
    )
    required_evidence_covered = sorted(
        set(required_evidence_cited)
        .intersection(required_evidence_collected)
        .intersection(required_evidence_hash_verified)
    )
    expected_files_covered = sorted(set(task.expected_files).intersection(cited_set))
    forbidden_hits = _forbidden_assumption_hits(outputs, task.forbidden_assumptions)
    tool_contract = _validate_tool_records(tool_records, repository_policy)
    secret_scan_passed = not _contains_unredacted_secret(attempt_dir, secret_values)
    failure_category = _failure_category(
        manifest,
        outputs,
        exit_code,
        harness_error,
        provider_failure_categories,
    )
    input_tokens = _optional_non_negative_int(provider_usage.get("input_tokens"))
    output_tokens = _optional_non_negative_int(provider_usage.get("output_tokens"))
    provider_request_count = _as_non_negative_int(provider_usage.get("request_count"))
    provider_usage_complete = provider_usage.get("usage_complete") is True
    estimated_cost = (
        _estimate_cost(input_tokens, output_tokens, pricing)
        if provider_usage_complete and input_tokens is not None and output_tokens is not None
        else None
    )
    if task.evaluation_class == CONTROL_CLASS:
        control_passed = (
            failure_category == "budget_call_limit"
            and _as_non_negative_int(provider_response_count) >= 1
        )
        deterministic_status = "passed" if control_passed and secret_scan_passed else "failed"
    else:
        checks = (
            run_completed,
            schema_passed,
            artifact_integrity_passed,
            tool_contract["passed"],
            not required_fields_missing,
            len(required_evidence_covered) == len(task.required_evidence),
            not forbidden_hits,
            secret_scan_passed,
            _as_non_negative_int(provider_response_count) >= 1,
        )
        deterministic_status = "passed" if all(checks) else "failed"
    if deterministic_status == "failed" and failure_category == "none":
        failure_category = "deterministic_validation_failed"
    return {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "execution_provenance": execution_provenance,
        "suite_lock_sha256": suite_lock_sha256,
        "specflow_commit": specflow_commit,
        "specflow_worktree_clean": specflow_worktree_clean,
        "task_id": task.task_id,
        "task_sha256": task_sha256,
        "evaluation_class": task.evaluation_class,
        "attempt_directory": attempt_dir.name,
        "provider": LIVE_PROVIDER,
        "model": preflight.get("model", "unknown"),
        "repository": task.repository,
        "repository_commit": task.repository_commit,
        "repository_worktree_clean": preflight.get("repository_worktree_clean") is True,
        "sensitive_path_control": preflight.get("sensitive_path_control"),
        "run_exit_code": exit_code,
        "run_completed": run_completed,
        "schema_passed": schema_passed,
        "artifact_integrity_passed": artifact_integrity_passed,
        "tool_contract_passed": tool_contract["passed"],
        "tool_contract_violations": tool_contract["violations"],
        "provider_response_count": _as_non_negative_int(provider_response_count),
        "provider_request_count": provider_request_count,
        "provider_usage_complete": provider_usage_complete,
        "provider_failure_categories": dict(sorted(provider_failure_categories.items())),
        "required_output_fields_missing": required_fields_missing,
        "cited_paths": cited_paths,
        "cited_path_count": len(cited_paths),
        "valid_cited_path_count": len(valid_cited_paths),
        "invalid_cited_paths": sorted(set(cited_paths) - set(valid_cited_paths)),
        "source_hashed_paths": sorted(source_hashed_paths),
        "expected_files_covered": expected_files_covered,
        "expected_file_coverage_rate": _rate_or_none(
            len(expected_files_covered), len(task.expected_files)
        ),
        "required_evidence_cited": required_evidence_cited,
        "required_evidence_collected": required_evidence_collected,
        "required_evidence_hash_verified": required_evidence_hash_verified,
        "required_evidence_covered": required_evidence_covered,
        "required_evidence_count": len(task.required_evidence),
        "required_evidence_covered_count": len(required_evidence_covered),
        "forbidden_assumption_hits": forbidden_hits,
        "secret_scan_passed": secret_scan_passed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None,
        "outer_wall_time_ms": outer_wall_time_ms,
        "estimated_cost_usd": estimated_cost,
        "cost_estimate_status": (
            "estimated" if provider_usage_complete else "provider_usage_unavailable"
        ),
        "pricing_rule": pricing.as_dict(),
        "failure_category": failure_category,
        "harness_error": harness_error or None,
        "deterministic_status": deterministic_status,
        "human_review_status": "pending",
    }


def _human_review_template(task: LiveEvalTask, result: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "task_id": task.task_id,
        "attempt_directory": result.get("attempt_directory"),
        "status": "pending",
        "reviewer": "",
        "reviewed_at": None,
        "criteria": {
            "answers_task": {"status": "pending", "notes": ""},
            "evidence_support": {"status": "pending", "notes": ""},
            "unsupported_assumptions": {"count": None, "notes": ""},
            "technical_actionability": {"status": "pending", "notes": ""},
        },
        "human_notes": task.human_notes,
        "final_decision": "pending",
    }


def _load_task(path: Path, expected_class: str) -> LiveEvalTask:
    raw = _read_yaml_object(path, "live evaluation task")
    missing = _REQUIRED_TASK_FIELDS - raw.keys()
    unexpected = raw.keys() - (_REQUIRED_TASK_FIELDS | _OPTIONAL_TASK_FIELDS)
    if missing or unexpected:
        raise LiveEvaluationError(
            f"task {path.name} has invalid fields: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    task_id = _required_text(raw, "task_id", path.name)
    if not _TASK_ID_RE.fullmatch(task_id):
        raise LiveEvaluationError(f"task {path.name} has an unsafe task_id")
    evaluation_class = str(raw.get("evaluation_class", QUALITY_CLASS))
    if evaluation_class != expected_class:
        raise LiveEvaluationError(f"task {path.name} has an unexpected evaluation_class")
    expected_files = _relative_path_list(raw, "expected_files", path.name)
    required_evidence = _relative_path_list(raw, "required_evidence", path.name)
    required_output_fields = _text_list(raw, "required_output_fields", path.name)
    forbidden_assumptions = _text_list(raw, "forbidden_assumptions", path.name)
    if expected_class == QUALITY_CLASS and not required_output_fields:
        raise LiveEvaluationError(f"quality task {path.name} needs required_output_fields")
    timeout_seconds = raw.get("timeout_seconds")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise LiveEvaluationError(f"task {path.name} timeout_seconds must be an integer")
    if not 1 <= timeout_seconds <= 600:
        raise LiveEvaluationError(f"task {path.name} timeout_seconds must be between 1 and 600")
    max_llm_calls = raw.get("max_llm_calls", DEFAULT_POLICY.max_llm_calls)
    if not isinstance(max_llm_calls, int) or isinstance(max_llm_calls, bool) or max_llm_calls < 1:
        raise LiveEvaluationError(f"task {path.name} max_llm_calls must be a positive integer")
    return LiveEvalTask(
        task_id=task_id,
        repository=_required_text(raw, "repository", path.name),
        repository_commit=_required_text(raw, "repository_commit", path.name),
        user_request=_required_text(raw, "user_request", path.name),
        expected_files=expected_files,
        required_evidence=required_evidence,
        required_output_fields=required_output_fields,
        forbidden_assumptions=forbidden_assumptions,
        timeout_seconds=timeout_seconds,
        human_notes=_required_text(raw, "human_notes", path.name),
        evaluation_class=evaluation_class,
        max_llm_calls=max_llm_calls,
        source_path=path,
    )


def _verify_locked_paths(paths: Sequence[Path], raw_hashes: object, label: str) -> None:
    if not isinstance(raw_hashes, dict):
        raise LiveEvaluationError(f"suite lock has no {label} hash mapping")
    expected = {path.name for path in paths}
    if set(raw_hashes) != expected:
        raise LiveEvaluationError(f"suite lock {label} names do not match the files on disk")
    for path in paths:
        expected_hash = raw_hashes.get(path.name)
        if not isinstance(expected_hash, str) or _file_sha256(path) != expected_hash:
            raise LiveEvaluationError(f"frozen {label} was modified: {path.name}")


def _read_yaml_object(path: Path, description: str) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LiveEvaluationError(f"cannot read {description}: {path}") from exc
    if not isinstance(raw, dict):
        raise LiveEvaluationError(f"{description} must be a mapping: {path}")
    return raw


def _read_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveEvaluationError(f"cannot read {description}: {path}") from exc
    if not isinstance(raw, dict):
        raise LiveEvaluationError(f"{description} must be a JSON object: {path}")
    return raw


def _required_text(raw: Mapping[str, object], key: str, description: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LiveEvaluationError(f"{description} {key} must be non-empty text")
    return value.strip()


def _relative_path_list(raw: Mapping[str, object], key: str, description: str) -> tuple[str, ...]:
    values = _text_list(raw, key, description)
    if not values or any(not _is_safe_relative_path(value) for value in values):
        raise LiveEvaluationError(f"{description} {key} must contain safe relative paths")
    return values


def _text_list(raw: Mapping[str, object], key: str, description: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise LiveEvaluationError(f"{description} {key} must be a list of non-empty text")
    return tuple(item.strip() for item in value)


def _non_negative_number(value: object, description: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise LiveEvaluationError(f"{description} must be a non-negative number")
    return float(value)


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise LiveEvaluationError("evaluation repository Git preflight failed")
    return completed.stdout.strip()


def _git_path_exists(repository_root: Path, commit: str, relative_path: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "cat-file", "-e", f"{commit}:{relative_path}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _find_runner_artifact_dir(artifacts_root: Path) -> Path | None:
    if not artifacts_root.is_dir():
        return None
    candidates = sorted(
        path
        for path in artifacts_root.iterdir()
        if path.is_dir() and not path.is_symlink() and path.name.startswith("run-multi-")
    )
    return candidates[0] if len(candidates) == 1 else None


def _load_json_from_run(run_dir: Path | None, filename: str) -> dict[str, Any]:
    if run_dir is None:
        return {}
    path = run_dir / filename
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_list_from_artifact(
    run_dir: Path | None, filename: str, key: str | None = None
) -> list[object]:
    if run_dir is None:
        return []
    try:
        raw = json.loads((run_dir / filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if key is not None:
        raw = raw.get(key) if isinstance(raw, dict) else None
    return raw if isinstance(raw, list) else []


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, values: Iterable[object]) -> None:
    lines = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
    _write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _write_yaml(path: Path, value: object) -> None:
    _write_text(path, yaml.safe_dump(value, allow_unicode=True, sort_keys=True))


def _read_jsonl(path: Path) -> list[object]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    values: list[object] = []
    for line in lines:
        try:
            values.append(json.loads(line))
        except json.JSONDecodeError:
            return []
    return values


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _verify_artifact_integrity(run_dir: Path | None) -> bool:
    if run_dir is None or not (run_dir / "_COMPLETE").is_file():
        return False
    integrity = _load_json_from_run(run_dir, "artifact-integrity.json")
    hashes = integrity.get("artifact_hashes")
    if not isinstance(hashes, dict) or not hashes:
        return False
    for filename, expected_hash in hashes.items():
        path = run_dir / str(filename)
        if (
            not isinstance(expected_hash, str)
            or not path.is_file()
            or _file_sha256(path) != expected_hash
        ):
            return False
    return True


def _has_output_field(outputs: Mapping[str, object], field: str) -> bool:
    root, separator, nested = field.partition(".")
    if not separator or root not in outputs:
        return False
    current: object = outputs[root]
    for component in nested.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return False
        current = current[component]
    return current is not None


def _extract_cited_paths(value: object) -> list[str]:
    paths: set[str] = set()
    for text in _iter_text(value):
        paths.update(_PATH_REFERENCE_RE.findall(text))
    return sorted(path for path in paths if _is_safe_relative_path(path))


def _source_hash_mapping(sources: Mapping[str, object]) -> dict[str, str]:
    raw_hashes = sources.get("source_hashes")
    if not isinstance(raw_hashes, Mapping):
        return {}
    return {
        path: digest
        for path, digest in raw_hashes.items()
        if isinstance(path, str)
        and _is_safe_relative_path(path)
        and isinstance(digest, str)
        and _SHA256_RE.fullmatch(digest)
    }


def _frozen_source_hash_matches(
    source_hashes: Mapping[str, str],
    repository_root: Path,
    policy: RepositoryAccessPolicy,
    repository_commit: str,
    required_paths: Sequence[str],
) -> set[str]:
    matched: set[str] = set()
    for relative_path in required_paths:
        observed = source_hashes.get(relative_path)
        expected = _frozen_sanitized_source_hash(
            repository_root,
            policy,
            repository_commit,
            relative_path,
        )
        if observed is not None and observed == expected:
            matched.add(relative_path)
    return matched


def _frozen_sanitized_source_hash(
    repository_root: Path,
    policy: RepositoryAccessPolicy,
    repository_commit: str,
    relative_path: str,
) -> str | None:
    """Recreate the ReadFileTool hash from the clean, commit-pinned checkout."""
    if not _git_path_exists(repository_root, repository_commit, relative_path):
        return None
    try:
        path, _ = policy.resolve_file(relative_path)
        with path.open("rb") as handle:
            data = handle.read(policy.limits.max_file_bytes + 1)
    except OSError:
        return None
    if b"\x00" in data:
        return None
    truncated = len(data) > policy.limits.max_file_bytes
    payload = data[: policy.limits.max_file_bytes]
    try:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        content = decoder.decode(payload, final=not truncated)
    except UnicodeDecodeError:
        return None
    sanitized_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        sanitized_lines.append(f"{sanitize_tool_text(body)}{line[len(body) :]}")
    sanitized_content = "".join(sanitized_lines)
    return sha256(sanitized_content.encode("utf-8")).hexdigest()


def _iter_text(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text(item)


def _forbidden_assumption_hits(outputs: object, assumptions: Sequence[str]) -> list[str]:
    text = "\n".join(_iter_text(outputs)).casefold()
    return sorted(assumption for assumption in assumptions if assumption.casefold() in text)


def _validate_tool_records(
    records: Sequence[object], policy: RepositoryAccessPolicy
) -> dict[str, object]:
    violations: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            violations.append("malformed_tool_record")
            continue
        tool_name = record.get("tool_name")
        if tool_name not in _ALLOWED_TOOL_NAMES:
            violations.append(f"tool_not_allowed:{tool_name}")
        arguments = record.get("arguments_summary")
        if isinstance(arguments, str):
            for path in re.findall(r"(?:^|[,\s])path=([^,\s]+)", arguments):
                normalized = path.strip("'\"")
                if policy.is_sensitive_path(normalized):
                    violations.append(f"sensitive_path:{normalized}")
    return {"passed": not violations, "violations": sorted(set(violations))}


def _contains_unredacted_secret(path: Path, secret_values: Sequence[str]) -> bool:
    needles = [value for value in secret_values if value]
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(value in text for value in needles):
            return True
        if _BEARER_RE.search(text):
            return True
        if _LIKELY_SECRET_RE.search(text):
            return True
        if _ABSOLUTE_PATH_RE.search(text):
            return True
    return False


def _redact_provider_value(value: object, secret_values: Sequence[str]) -> object:
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                embedded = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(embedded, Mapping | list):
                    return json.dumps(
                        _redact_provider_value(embedded, secret_values),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
        result = value
        for secret in secret_values:
            result = result.replace(secret, "<redacted>")
        result = _BEARER_RE.sub("Bearer <redacted>", result)
        result = _JSON_SENSITIVE_ASSIGNMENT_RE.sub(r'\1"<redacted>"', result)
        result = _SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", result)
        result = _LIKELY_SECRET_RE.sub("<redacted>", result)
        return _ABSOLUTE_PATH_RE.sub("<absolute-path-redacted>", result)
    if isinstance(value, list):
        return [_redact_provider_value(item, secret_values) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): "<redacted>"
            if _SENSITIVE_KEY_RE.search(str(key))
            else _redact_provider_value(item, secret_values)
            for key, item in value.items()
        }
    return value


def _provider_reported_usage(payload: Mapping[str, object]) -> tuple[int, int] | None:
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None
    input_tokens = _optional_non_negative_int(usage.get("prompt_tokens", usage.get("input_tokens")))
    output_tokens = _optional_non_negative_int(
        usage.get("completion_tokens", usage.get("output_tokens"))
    )
    if input_tokens is None or output_tokens is None:
        return None
    return input_tokens, output_tokens


def _failure_category(
    manifest: Mapping[str, object],
    outputs: Mapping[str, object],
    exit_code: int,
    harness_error: str,
    provider_failure_categories: Mapping[str, int],
) -> str:
    if harness_error:
        return "evaluation_harness_error"
    candidates: list[str] = []
    error = manifest.get("error")
    if isinstance(error, str):
        candidates.append(error)
    for value in _iter_text(outputs):
        if "_" in value and len(value) <= 80:
            candidates.append(value)
    joined = " ".join(candidates).upper()
    if "CALL_BUDGET" in joined or "BUDGET_LLM_CALLS" in joined:
        return "budget_call_limit"
    if "TOKEN_BUDGET" in joined:
        return "budget_token_limit"
    if "TIME_BUDGET" in joined or "PROVIDER_TIMEOUT" in joined:
        return "timeout"
    if "PROVIDER_AUTH" in joined:
        return "provider_auth"
    if "PROVIDER_RATE" in joined:
        return "provider_rate_limited"
    if "PROVIDER_SERVER" in joined:
        return "provider_server"
    if "PROVIDER_CONNECTION" in joined:
        return "provider_connection"
    if "SCHEMA" in joined or "JSON_PARSE" in joined:
        return "schema_or_response"
    if provider_failure_categories:
        return sorted(provider_failure_categories)[0]
    if exit_code == 0:
        return "none"
    if exit_code == 2:
        return "configuration"
    return "runtime_failure"


def _classify_provider_failure(error: Exception) -> str:
    """Map a caught Provider exception to a low-cardinality, non-secret category."""
    message = str(error).casefold()
    if "auth" in message or "401" in message or "403" in message:
        return "provider_auth"
    if "rate" in message or "429" in message:
        return "provider_rate_limited"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "server" in message or any(code in message for code in ("500", "502", "503")):
        return "provider_server"
    if "network" in message or "connection" in message or "transport" in message:
        return "provider_connection"
    if "response" in message or "json" in message:
        return "provider_response_invalid"
    return "provider_other"


def _estimate_cost(input_tokens: int, output_tokens: int, pricing: PricingRule) -> float:
    return round(
        (input_tokens / 1_000_000) * pricing.input_usd_per_million_tokens
        + (output_tokens / 1_000_000) * pricing.output_usd_per_million_tokens,
        8,
    )


def _load_batch_attempts(
    runs_root: Path,
    batch_id: str,
    *,
    allow_test_provenance: bool,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Load exactly the immutable attempt set declared by one completed batch."""
    manifest = _read_json_object(_batch_manifest_path(runs_root, batch_id), "batch manifest")
    if manifest.get("schema_version") != "1.0" or manifest.get("batch_id") != batch_id:
        raise LiveEvaluationError("batch manifest identity is invalid")
    if manifest.get("status") != "completed":
        raise LiveEvaluationError("batch manifest is incomplete")

    provenance = manifest.get("execution_provenance")
    if provenance not in {"live_openai_compatible", "test_double"}:
        raise LiveEvaluationError("batch manifest has an invalid execution provenance")
    if provenance == "test_double" and not allow_test_provenance:
        raise LiveEvaluationError("test-double evidence cannot produce a live Provider report")
    if (
        provenance == "live_openai_compatible"
        and manifest.get("specflow_worktree_clean") is not True
    ):
        raise LiveEvaluationError("live batch was not executed from a clean SpecFlow worktree")

    suite_lock_sha256 = manifest.get("suite_lock_sha256")
    specflow_commit = manifest.get("specflow_commit")
    repository_commit = manifest.get("repository_commit")
    if not all(
        isinstance(value, str) and _SHA256_RE.fullmatch(value) for value in (suite_lock_sha256,)
    ):
        raise LiveEvaluationError("batch manifest has an invalid suite lock hash")
    if not _is_git_commit(specflow_commit) or not _is_git_commit(repository_commit):
        raise LiveEvaluationError("batch manifest has an invalid commit identity")

    quality_task_ids = _manifest_task_ids(manifest, "quality_task_ids", QUALITY_CLASS)
    control_task_ids = _manifest_task_ids(manifest, "control_task_ids", CONTROL_CLASS)
    if set(quality_task_ids).intersection(control_task_ids):
        raise LiveEvaluationError("batch manifest task IDs overlap")
    if not allow_test_provenance and (not 5 <= len(quality_task_ids) <= 10 or not control_task_ids):
        raise LiveEvaluationError(
            "live Provider report requires five to ten quality tasks and a control"
        )
    task_classes = {
        **{task_id: QUALITY_CLASS for task_id in quality_task_ids},
        **{task_id: CONTROL_CLASS for task_id in control_task_ids},
    }
    task_hashes = manifest.get("task_sha256")
    if not isinstance(task_hashes, Mapping) or set(task_hashes) != set(task_classes):
        raise LiveEvaluationError("batch manifest task hashes do not match its task set")
    if any(
        not isinstance(value, str) or not _SHA256_RE.fullmatch(value)
        for value in task_hashes.values()
    ):
        raise LiveEvaluationError("batch manifest has an invalid task hash")

    declarations = manifest.get("attempts")
    if not isinstance(declarations, list) or len(declarations) != len(task_classes):
        raise LiveEvaluationError(
            "batch manifest attempt count does not match its planned task set"
        )
    results: list[dict[str, object]] = []
    seen_task_ids: set[str] = set()
    seen_directories: set[str] = set()
    resolved_root = runs_root.resolve()
    for declaration in declarations:
        if not isinstance(declaration, Mapping):
            raise LiveEvaluationError("batch manifest has a malformed attempt declaration")
        task_id = declaration.get("task_id")
        evaluation_class = declaration.get("evaluation_class")
        directory_name = declaration.get("attempt_directory")
        result_sha256 = declaration.get("deterministic_result_sha256")
        evidence_sha256 = declaration.get("evidence_sha256")
        if (
            not isinstance(task_id, str)
            or task_id not in task_classes
            or evaluation_class != task_classes[task_id]
            or not _is_attempt_directory_name(directory_name)
            or not isinstance(result_sha256, str)
            or not _SHA256_RE.fullmatch(result_sha256)
            or declaration.get("task_sha256") != task_hashes[task_id]
            or not _is_evidence_hash_mapping(evidence_sha256)
            or evidence_sha256.get("deterministic-result.json") != result_sha256
            or task_id in seen_task_ids
            or directory_name in seen_directories
        ):
            raise LiveEvaluationError(
                "batch manifest has an invalid or duplicate attempt declaration"
            )
        attempt_dir = runs_root / directory_name
        if (
            attempt_dir.is_symlink()
            or not attempt_dir.is_dir()
            or attempt_dir.resolve().parent != resolved_root
        ):
            raise LiveEvaluationError("batch attempt directory is missing or unsafe")
        result_path = attempt_dir / "deterministic-result.json"
        if not result_path.is_file() or _file_sha256(result_path) != result_sha256:
            raise LiveEvaluationError("batch attempt result hash does not match the manifest")
        if _attempt_evidence_hashes(attempt_dir) != dict(evidence_sha256):
            raise LiveEvaluationError("batch attempt evidence hash does not match the manifest")
        task_copy = attempt_dir / "task.yaml"
        if not task_copy.is_file() or _file_sha256(task_copy) != task_hashes[task_id]:
            raise LiveEvaluationError("batch attempt task copy does not match the frozen task")
        result = _read_json_object(result_path, "deterministic result")
        config = _read_json_object(attempt_dir / "config.json", "attempt config")
        _validate_batch_attempt_identity(
            result=result,
            config=config,
            manifest=manifest,
            task_id=task_id,
            evaluation_class=evaluation_class,
            directory_name=directory_name,
            task_sha256=str(task_hashes[task_id]),
        )
        review = _read_yaml_object(attempt_dir / "human-review.yaml", "human review")
        result_with_review = _apply_human_review(result, review, task_id, directory_name)
        results.append(result_with_review)
        seen_task_ids.add(task_id)
        seen_directories.add(directory_name)
    if seen_task_ids != set(task_classes):
        raise LiveEvaluationError("batch manifest does not declare every planned task exactly once")
    return manifest, results


def _attempt_evidence_hashes(attempt_dir: Path) -> dict[str, str]:
    """Hash immutable attempt evidence while deliberately leaving human review mutable."""
    hashes: dict[str, str] = {}
    for filename in sorted(_ATTEMPT_EVIDENCE_FILES):
        path = attempt_dir / filename
        if not path.is_file() or path.is_symlink():
            raise LiveEvaluationError(f"attempt evidence is missing or unsafe: {filename}")
        hashes[filename] = _file_sha256(path)
    artifacts_root = attempt_dir / "artifacts"
    if artifacts_root.exists():
        if not artifacts_root.is_dir() or artifacts_root.is_symlink():
            raise LiveEvaluationError("attempt runner artifacts are unsafe")
        for path in sorted(artifacts_root.rglob("*")):
            if path.is_symlink():
                raise LiveEvaluationError("attempt runner artifacts contain a link")
            if path.is_file():
                relative = path.relative_to(attempt_dir).as_posix()
                hashes[relative] = _file_sha256(path)
    return hashes


def _is_evidence_hash_mapping(value: object) -> bool:
    if not isinstance(value, Mapping) or not _ATTEMPT_EVIDENCE_FILES.issubset(value):
        return False
    return all(
        isinstance(path, str)
        and _is_safe_relative_path(path)
        and isinstance(digest, str)
        and _SHA256_RE.fullmatch(digest)
        for path, digest in value.items()
    )


def _manifest_task_ids(
    manifest: Mapping[str, object], key: str, evaluation_class: str
) -> tuple[str, ...]:
    values = manifest.get(key)
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not _TASK_ID_RE.fullmatch(value) for value in values)
        or len(set(values)) != len(values)
    ):
        raise LiveEvaluationError(f"batch manifest has invalid {evaluation_class} task IDs")
    return tuple(values)


def _validate_batch_attempt_identity(
    *,
    result: Mapping[str, object],
    config: Mapping[str, object],
    manifest: Mapping[str, object],
    task_id: str,
    evaluation_class: str,
    directory_name: str,
    task_sha256: str,
) -> None:
    expected = {
        "batch_id": manifest["batch_id"],
        "execution_provenance": manifest["execution_provenance"],
        "suite_lock_sha256": manifest["suite_lock_sha256"],
        "specflow_commit": manifest["specflow_commit"],
        "specflow_worktree_clean": manifest["specflow_worktree_clean"],
        "repository": manifest["repository"],
        "repository_commit": manifest["repository_commit"],
        "provider": manifest["provider"],
        "model": manifest["model"],
    }
    if (
        result.get("task_id") != task_id
        or result.get("evaluation_class") != evaluation_class
        or result.get("task_sha256") != task_sha256
        or result.get("attempt_directory") != directory_name
        or result.get("pricing_rule") != manifest.get("pricing_rule")
        or any(result.get(key) != value for key, value in expected.items())
    ):
        raise LiveEvaluationError("batch deterministic result identity does not match its manifest")
    config_expected = {
        "batch_id": manifest["batch_id"],
        "execution_provenance": manifest["execution_provenance"],
        "suite_lock_sha256": manifest["suite_lock_sha256"],
        "specflow_commit": manifest["specflow_commit"],
        "specflow_worktree_clean": manifest["specflow_worktree_clean"],
        "target_repository": manifest["repository"],
        "target_repository_commit": manifest["repository_commit"],
        "provider": manifest["provider"],
        "model": manifest["model"],
        "task_sha256": task_sha256,
        "pricing_rule": manifest["pricing_rule"],
    }
    if any(config.get(key) != value for key, value in config_expected.items()):
        raise LiveEvaluationError("batch attempt config identity does not match its manifest")


def _apply_human_review(
    result: Mapping[str, object], review: Mapping[str, object], task_id: str, directory_name: str
) -> dict[str, object]:
    if review.get("task_id") != task_id or review.get("attempt_directory") != directory_name:
        raise LiveEvaluationError("human review does not match its evaluation attempt")
    result_with_review: dict[str, object] = dict(result)
    result_with_review["human_review_status"] = review.get("status", "pending")
    criteria = review.get("criteria")
    if isinstance(criteria, Mapping):
        support = criteria.get("evidence_support")
        if isinstance(support, Mapping):
            result_with_review["human_evidence_supported"] = support.get("status") == "passed"
        assumptions = criteria.get("unsupported_assumptions")
        if isinstance(assumptions, Mapping):
            result_with_review["human_unsupported_assumption_count"] = assumptions.get("count")
    return result_with_review


def _unique_pricing_rules(attempts: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for attempt in attempts:
        rule = attempt.get("pricing_rule")
        if not isinstance(rule, Mapping):
            continue
        normalized = {
            key: rule.get(key)
            for key in (
                "provider",
                "model",
                "input_usd_per_million_tokens",
                "output_usd_per_million_tokens",
                "source_url",
                "retrieved_at",
            )
        }
        key = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            rules.append(normalized)
    return rules


def _read_json_object_if_present(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _read_yaml_object_if_present(path: Path) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return raw if isinstance(raw, dict) else None


def _attempt_id(task_id: str) -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{task_id}-{uuid4().hex[:8]}"


def _batch_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}"


def _batch_manifest_path(runs_root: Path, batch_id: str) -> Path:
    if not _BATCH_ID_RE.fullmatch(batch_id):
        raise LiveEvaluationError("batch ID is invalid")
    return runs_root / "batches" / f"{batch_id}.json"


def _is_attempt_directory_name(value: object) -> bool:
    if not isinstance(value, str) or not value or "/" in value or "\\" in value:
        return False
    return value not in {".", ".."} and not Path(value).is_absolute()


def _is_git_commit(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _specflow_provenance() -> dict[str, object]:
    source_root = Path(__file__).resolve().parents[3]
    return {
        "commit": _git(source_root, "rev-parse", "HEAD"),
        "worktree_clean": not bool(_git(source_root, "status", "--porcelain")),
    }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _is_safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return bool(value.strip()) and not path.is_absolute() and ".." not in path.parts


def _as_non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _optional_non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _rate_or_none(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _nearest_rank(values: Sequence[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * percentile) + 0.999999) - 1))
    return ordered[index]


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _format_rate(value: object) -> str:
    return f"{float(value) * 100:.2f}%" if isinstance(value, int | float) else "not available"


def _format_ms(value: object) -> str:
    return f"{value} ms" if isinstance(value, int | float) else "not available"


def _format_number(value: object) -> str:
    return str(value) if isinstance(value, int | float) else "not available"


def _format_cost(value: object) -> str:
    return f"USD {float(value):.8f}" if isinstance(value, int | float) else "not available"


def _format_provider_models(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "not available"
    pairs = [
        f"{item.get('provider', 'unknown')} / {item.get('model', 'unknown')}"
        for item in value
        if isinstance(item, Mapping)
    ]
    return ", ".join(pairs) if pairs else "not available"

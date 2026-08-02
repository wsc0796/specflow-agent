"""Phase 6 pilot harness: deterministic rule scoring, cost metrics, blind packs.

The pilot validates the evaluation protocol on the frozen fixture repository.
It never produces quality conclusions: outputs are protocol/stability evidence
only, and every run records its execution mode (mock vs live).
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from specflow.evaluation.models import EvaluationCase
from specflow.policy.defaults import DEFAULT_POLICY
from specflow.policy.models import ExecutionPolicy
from specflow.runner import run as run_legacy
from specflow.runner_multi import run_multi_agent


@dataclass(frozen=True)
class EvaluationCandidate:
    """Unified candidate envelope derived from a pipeline run."""

    case_id: str
    pipeline: str
    execution_mode: str
    proposed_changes: tuple[str, ...] = ()
    affected_files: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    implementation_steps: tuple[str, ...] = ()
    test_plan: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    rollback: str = ""
    uncertainties: tuple[str, ...] = ()
    pipeline_metrics: dict[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pipeline_metrics",
            dict(self.pipeline_metrics or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_cases(cases_dir: Path) -> tuple[EvaluationCase, ...]:
    """Load frozen pilot cases from JSON files."""
    cases: list[EvaluationCase] = []
    for path in sorted(cases_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            EvaluationCase(
                case_id=payload["case_id"],
                title=payload["title"],
                requirement=payload["requirement"],
                repository_type=payload["repository_type"],
                expected_domains=tuple(payload["expected_domains"]),
                expected_file_patterns=tuple(payload["expected_file_patterns"]),
                expected_risks=tuple(payload["expected_risks"]),
                expected_acceptance_topics=tuple(payload["expected_acceptance_topics"]),
                forbidden_claims=tuple(payload["forbidden_claims"]),
                human_review_notes=payload["human_review_notes"],
            )
        )
    return tuple(cases)


def rule_score(
    case: EvaluationCase,
    candidate: EvaluationCandidate,
    *,
    repo: Path,
    run_success: bool,
    budget_violation: bool,
) -> dict[str, object]:
    """Deterministic rule metrics; identical inputs always yield identical scores."""
    affected = set(candidate.affected_files)
    evidence_refs = set(candidate.evidence_refs)
    referenced_existing = {
        ref for ref in candidate.evidence_refs if ref.startswith("app/") or ref.startswith("tests/")
    }
    existing_paths = {
        str(path.relative_to(repo)).replace("\\", "/")
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    referenced_exists = len(referenced_existing) > 0 and referenced_existing <= existing_paths
    expected_recall = (
        len(set(case.expected_file_patterns) & affected) / len(case.expected_file_patterns)
        if case.expected_file_patterns
        else 0.0
    )
    forbidden = [
        claim for claim in case.forbidden_claims if claim in " ".join(candidate.proposed_changes)
    ]
    claim_text = " ".join(candidate.proposed_changes).lower()
    unsupported_claims = (
        1
        if any(word in claim_text for word in ("guarantee", "always", "never fails", "production"))
        else 0
    )
    risk_coverage = len(set(case.expected_risks) & set(candidate.risks)) / len(case.expected_risks)
    uncertainty_calibrated = (
        bool(candidate.uncertainties) if case.case_id.endswith("vague") else True
    )
    return {
        "schema_valid": True,
        "evidence_ref_valid": len(candidate.evidence_refs) == len(evidence_refs),
        "referenced_path_exists": referenced_exists,
        "claim_evidence_coverage": (
            len(referenced_existing) / len(candidate.evidence_refs)
            if candidate.evidence_refs
            else 0.0
        ),
        "unsupported_claim_rate": unsupported_claims,
        "expected_module_recall": expected_recall,
        "test_plan_coverage": 1.0 if candidate.test_plan else 0.0,
        "risk_coverage": risk_coverage,
        "uncertainty_calibration": uncertainty_calibrated,
        "budget_violation": budget_violation,
        "run_success": run_success,
        "forbidden_claim_count": len(forbidden),
    }


def cost_metrics(run_dir: Path) -> dict[str, object]:
    """Collect cost facts from a run's metrics budget snapshot."""
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.is_file():
        nested = list(run_dir.glob("run-multi-*/metrics.json"))
        if nested:
            metrics_path = nested[0]
    if not metrics_path.is_file():
        manifest = _read_json(run_dir / "manifest.json") or _read_json(
            run_dir / "run-*" / "manifest.json"
        )
        if manifest and manifest.get("provider_type") == "mock":
            return {
                "provider_call_attempts": 0,
                "successful_provider_calls": 0,
                "failed_provider_calls": 0,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "unknown_usage_calls": 0,
                "wall_clock_ms": 0,
                "revision_rounds": 0,
                "accounting": "mock_no_provider",
            }
        return {"missing": True}
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    snapshot = metrics.get("budget_snapshot", {})
    provider = snapshot.get("provider_calls", {})
    tokens = snapshot.get("tokens", {})
    revision = snapshot.get("revision", {})
    return {
        "provider_call_attempts": provider.get("attempts", 0),
        "successful_provider_calls": provider.get("successful", 0),
        "failed_provider_calls": provider.get("failed", 0),
        "input_tokens": tokens.get("input_tokens", 0),
        "output_tokens": tokens.get("output_tokens", 0),
        "total_tokens": tokens.get("total_tokens", 0),
        "unknown_usage_calls": tokens.get("unknown_calls", 0),
        "wall_clock_ms": snapshot.get("timing", {}).get("wall_clock_elapsed_ms", 0),
        "revision_rounds": revision.get("rounds", 0),
    }


def blind_pack(candidates: list[EvaluationCandidate], seed: int = 0) -> dict[str, Any]:
    """Anonymize candidates: pipeline identity is hidden behind stable IDs."""
    rng = random.Random(seed)
    order = list(range(len(candidates)))
    rng.shuffle(order)
    packs = []
    for anonymous_index, source_index in enumerate(order):
        candidate = candidates[source_index]
        packs.append(
            {
                "anonymous_id": f"ANON-{anonymous_index:03d}",
                "case_id": candidate.case_id,
                "proposed_changes": list(candidate.proposed_changes),
                "affected_files": list(candidate.affected_files),
                "evidence_refs": list(candidate.evidence_refs),
                "implementation_steps": list(candidate.implementation_steps),
                "test_plan": list(candidate.test_plan),
                "risks": list(candidate.risks),
                "rollback": candidate.rollback,
                "uncertainties": list(candidate.uncertainties),
            }
        )
    return {"packs": packs}


def run_pilot_mock_smoke(
    *,
    repo: Path,
    cases: tuple[EvaluationCase, ...],
    output: Path,
    policy: ExecutionPolicy | None = None,
) -> tuple[dict[str, Any], ...]:
    """Execute 5 cases x 3 pipelines in mock mode (harness validation only)."""
    policy = policy or DEFAULT_POLICY
    output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for case in cases:
        for pipeline in ("single", "legacy", "six-role"):
            run_dir = output / case.case_id / pipeline
            run_dir.mkdir(parents=True, exist_ok=True)
            if pipeline == "six-role":
                exit_code = run_multi_agent(
                    repo=repo,
                    requirement=case.requirement,
                    output=run_dir,
                    mock=True,
                    policy=policy,
                )
                manifest = _read_json(run_dir / "run-multi-*" / "manifest.json")
            elif pipeline == "legacy":
                exit_code = run_legacy(
                    repo=repo,
                    requirement=case.requirement,
                    output=run_dir,
                    provider="mock",
                    max_files=5,
                )
                manifest = _read_json(run_dir / "run-*" / "manifest.json")
            else:
                exit_code, manifest = _run_single_mock(
                    case.case_id,
                    case.requirement,
                    run_dir,
                )
            candidate = _derive_candidate(case, pipeline, run_dir, manifest, exit_code)
            results.append(candidate.as_dict())
    return tuple(results)


def _run_single_mock(
    case_id: str,
    requirement: str,
    run_dir: Path,
) -> tuple[int, dict[str, Any] | None]:
    """Deterministic mock single-agent pipeline (harness validation only)."""
    manifest = {
        "case_id": case_id,
        "pipeline": "single",
        "execution_mode": "mock",
        "workflow_state": "completed",
        "provider_type": "mock",
        "model": "mock-model",
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "candidate.json").write_text(
        json.dumps(
            {
                "proposed_changes": ["Plan generated for requirement: " + requirement],
                "affected_files": [],
                "evidence_refs": [],
                "implementation_steps": ["Inspect evidence", "Draft a bounded plan"],
                "test_plan": ["Validate the requested behavior"],
                "risks": [],
                "rollback": "restore previous commit",
                "uncertainties": ["mock single-agent has no evidence collection"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return 0, manifest


def _derive_candidate(
    case: EvaluationCase,
    pipeline: str,
    run_dir: Path,
    manifest: dict[str, Any] | None,
    exit_code: int,
) -> EvaluationCandidate:
    """Derive a unified candidate summary from native run artifacts."""
    affected: list[str] = []
    proposed: list[str] = []
    risks: list[str] = []
    test_plan: list[str] = []
    uncertainties: list[str] = []
    evidence_refs: list[str] = []

    multi_dirs = list(run_dir.glob("run-multi-*"))
    if multi_dirs:
        multi_dir = multi_dirs[0]
        outputs = _read_json(multi_dir / "agent-outputs.json") or {}
        for result in outputs.values():
            output = result.get("output") if isinstance(result, dict) else None
            if not isinstance(output, dict):
                continue
            proposed.extend(
                output.get("implementation_steps", [])
                if isinstance(output.get("implementation_steps"), list)
                else [output.get("summary", "")]
            )
            affected.extend(
                item for item in output.get("affected_components", []) if isinstance(item, str)
            )
            risks.extend(item for item in output.get("risks", []) if isinstance(item, str))
            test_plan.extend(
                item for item in output.get("test_scenarios", []) if isinstance(item, str)
            )
            evidence_refs.extend(
                item for item in output.get("evidence_refs", []) if isinstance(item, str)
            )
    else:
        candidate_file = run_dir / "candidate.json"
        if candidate_file.is_file():
            candidate = json.loads(candidate_file.read_text(encoding="utf-8"))
            proposed = list(candidate.get("proposed_changes", []))
            affected = list(candidate.get("affected_files", []))
            evidence_refs = list(candidate.get("evidence_refs", []))
            risks = list(candidate.get("risks", []))
            test_plan = list(candidate.get("test_plan", []))
            uncertainties = list(candidate.get("uncertainties", []))
        else:
            legacy_dirs = [path for path in run_dir.glob("run-*") if path.is_dir()]
            if legacy_dirs:
                legacy_dir = legacy_dirs[0]
                generation = _read_json(legacy_dir / "generation.json") or {}
                review = _read_json(legacy_dir / "review.json") or {}
                sources = _read_json(legacy_dir / "sources.json") or {}
                proposed = [
                    item
                    for item in generation.get("implementation_steps", [])
                    if isinstance(item, str)
                ]
                if not proposed and isinstance(generation.get("proposed_solution"), str):
                    proposed = [generation["proposed_solution"]]
                affected = [
                    item
                    for item in generation.get("affected_components", [])
                    if isinstance(item, str)
                ]
                evidence_refs = [
                    item for item in sources.get("selected_files", []) if isinstance(item, str)
                ]
                risks = [item for item in generation.get("risks", []) if isinstance(item, str)]
                test_plan = [
                    item for item in generation.get("test_plan", []) if isinstance(item, str)
                ]
                uncertainties = [
                    item
                    for key in ("issues", "missing_requirements")
                    for item in review.get(key, [])
                    if isinstance(item, str)
                ]

    return EvaluationCandidate(
        case_id=case.case_id,
        pipeline=pipeline,
        execution_mode="mock",
        proposed_changes=tuple(proposed),
        affected_files=tuple(dict.fromkeys(affected)),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        implementation_steps=tuple(proposed),
        test_plan=tuple(test_plan),
        risks=tuple(dict.fromkeys(risks)),
        rollback="restore previous commit",
        uncertainties=tuple(uncertainties),
        pipeline_metrics={
            "exit_code": exit_code,
            "workflow_state": (manifest or {}).get("workflow_state", "unknown"),
        },
    )


def _read_json(pattern: str | Path) -> dict[str, Any] | None:
    from glob import glob

    matches = glob(str(pattern)) if isinstance(pattern, str) else [str(pattern)]
    if not matches:
        return None
    try:
        return json.loads(Path(matches[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)

"""Deterministic, mock-only portfolio benchmark over the existing multi-agent runner."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from specflow.runner_multi import run_multi_agent


@dataclass(frozen=True)
class BenchmarkCase:
    """A versioned, fixture-grounded portfolio benchmark case."""

    case_id: str
    category: str
    title: str
    requirement: str
    expected_file_patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.case_id or any(part in self.case_id for part in ("/", "\\", "..")):
            raise ValueError("Benchmark case_id must be a safe identifier")
        if self.category not in {
            "repository_understanding",
            "change_planning",
            "review_risk",
        }:
            raise ValueError("Benchmark category is invalid")
        if not self.title.strip() or not self.requirement.strip():
            raise ValueError("Benchmark title and requirement must not be empty")
        if not self.expected_file_patterns:
            raise ValueError("Benchmark expected_file_patterns must not be empty")
        if any(not _is_safe_relative_path(path) for path in self.expected_file_patterns):
            raise ValueError("Benchmark expected file path is unsafe")


def load_benchmark_cases(suite: Path) -> tuple[BenchmarkCase, ...]:
    """Load an exactly-12-case suite in stable filename order."""
    cases: list[BenchmarkCase] = []
    for path in sorted(suite.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Benchmark case must be a JSON object: {path.name}")
        try:
            cases.append(
                BenchmarkCase(
                    case_id=str(raw["case_id"]),
                    category=str(raw["category"]),
                    title=str(raw["title"]),
                    requirement=str(raw["requirement"]),
                    expected_file_patterns=tuple(map(str, raw["expected_file_patterns"])),
                )
            )
        except KeyError as exc:
            raise ValueError(f"Benchmark case missing required field: {path.name}") from exc
    result = tuple(cases)
    if len(result) != 12:
        raise ValueError("Portfolio benchmark suite must contain exactly 12 cases")
    if len({case.case_id for case in result}) != len(result):
        raise ValueError("Portfolio benchmark case IDs must be unique")
    category_counts = Counter(case.category for case in result)
    if category_counts != {
        "repository_understanding": 4,
        "change_planning": 4,
        "review_risk": 4,
    }:
        raise ValueError("Portfolio benchmark must contain four cases in each category")
    return result


def run_mock_benchmark(
    cases: tuple[BenchmarkCase, ...], *, repo: Path, output: Path
) -> dict[str, object]:
    """Run each case once through mock multi-agent execution and aggregate evidence."""
    if output.exists() and any(output.iterdir()):
        raise ValueError("Benchmark output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, object]] = []
    for case in cases:
        missing = [path for path in case.expected_file_patterns if not (repo / path).is_file()]
        if missing:
            runs.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "status": "failed",
                    "error_codes": ["fixture_file_missing"],
                    "missing_files": missing,
                }
            )
            continue

        case_output = output / case.case_id
        exit_code = run_multi_agent(
            repo=repo,
            requirement=case.requirement,
            output=case_output,
            mock=True,
        )
        run_dirs = sorted(case_output.glob("run-multi-*"))
        if exit_code != 0 or len(run_dirs) != 1:
            runs.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "status": "failed",
                    "error_codes": ["multi_agent_run_failed"],
                }
            )
            continue
        runs.append(_read_run(case, run_dirs[0], output))
    return _aggregate(runs)


def normalized_baseline(report: dict[str, object]) -> dict[str, object]:
    """Remove runtime-specific values before committing mock baseline evidence."""
    return {
        "schema_version": "1.0",
        "mode": "mock_contract",
        "status": report["status"],
        "case_count": report["case_count"],
        "categories": report["categories"],
        "metrics": {
            key: report["metrics"][key]
            for key in (
                "schema_pass_rate",
                "run_success_rate",
                "degraded_rate",
                "fallback_rate",
                "total_input_tokens",
                "total_output_tokens",
                "error_code_counts",
            )
        },
        "runs": [
            {
                "case_id": run["case_id"],
                "category": run["category"],
                "status": run["status"],
                "schema_validated": run.get("schema_validated", False),
                "error_codes": run["error_codes"],
            }
            for run in report["runs"]
        ],
    }


def write_json(value: dict[str, object], path: Path) -> None:
    """Write stable JSON evidence without implicit directories outside the caller scope."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_run(case: BenchmarkCase, run_dir: Path, output: Path) -> dict[str, object]:
    try:
        required = (
            "manifest.json",
            "metrics.json",
            "agent-outputs.json",
            "handoffs.json",
            "traces.json",
            "sources.json",
            "checkpoints.json",
        )
        if any(
            not (run_dir / name).is_file() or (run_dir / name).is_symlink() for name in required
        ):
            raise ValueError("Benchmark artifact set is incomplete")
        manifest = _read_json(run_dir / "manifest.json")
        metrics = _read_json(run_dir / "metrics.json")
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "case_id": case.case_id,
            "category": case.category,
            "status": "failed",
            "error_codes": ["benchmark_artifact_invalid"],
        }
    schema_ok = (
        metrics.get("schema_unvalidated_count") == 0 and metrics.get("schema_validated_count") == 6
    )
    status = "passed" if manifest.get("workflow_state") == "completed" and schema_ok else "failed"
    return {
        "case_id": case.case_id,
        "category": case.category,
        "status": status,
        "artifact_directory": run_dir.relative_to(output).as_posix(),
        "schema_validated": schema_ok,
        "degraded": bool(metrics.get("degraded_count", 0)),
        "fallback": bool(metrics.get("fallback_count", 0)),
        "input_tokens": _as_non_negative_int(metrics.get("input_tokens")),
        "output_tokens": _as_non_negative_int(metrics.get("output_tokens")),
        "wall_time_ms": _as_non_negative_int(metrics.get("wall_time_ms")),
        "error_codes": [] if status == "passed" else ["benchmark_contract_failed"],
    }


def _aggregate(runs: list[dict[str, object]]) -> dict[str, object]:
    total = len(runs)
    passed = sum(run["status"] == "passed" for run in runs)
    categories = {
        category: {
            "total": sum(run["category"] == category for run in runs),
            "passed": sum(
                run["category"] == category and run["status"] == "passed" for run in runs
            ),
        }
        for category in ("repository_understanding", "change_planning", "review_risk")
    }
    metric_runs = [run for run in runs if run["status"] == "passed"]
    error_codes = Counter(code for run in runs for code in run["error_codes"])
    latencies = [run.get("wall_time_ms", 0) for run in metric_runs]
    return {
        "schema_version": "1.0",
        "mode": "mock_contract",
        "status": "passed" if passed == total else "failed",
        "case_count": total,
        "categories": categories,
        "metrics": {
            "schema_pass_rate": _rate(
                sum(run.get("schema_validated", False) for run in runs), total
            ),
            "run_success_rate": _rate(passed, total),
            "degraded_rate": _rate(sum(run.get("degraded", False) for run in runs), total),
            "fallback_rate": _rate(sum(run.get("fallback", False) for run in runs), total),
            "total_input_tokens": sum(run.get("input_tokens", 0) for run in metric_runs),
            "total_output_tokens": sum(run.get("output_tokens", 0) for run in metric_runs),
            "latency_ms": {
                "min": min(latencies, default=0),
                "max": max(latencies, default=0),
                "average": round(fmean(latencies), 2) if latencies else 0.0,
            },
            "error_code_counts": dict(sorted(error_codes.items())),
        },
        "runs": runs,
    }


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Benchmark artifact must be a JSON object")
    return value


def _as_non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value.strip()) and not path.is_absolute() and ".." not in path.parts

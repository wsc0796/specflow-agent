import json
from pathlib import Path

import pytest

from specflow.cli import main
from specflow.evaluation.benchmark import (
    BenchmarkCase,
    load_benchmark_cases,
    normalized_baseline,
    run_mock_benchmark,
)

SUITE = Path("benchmarks/cases")
FIXTURE = Path("benchmarks/fixtures/portfolio-python")


def test_portfolio_suite_has_exact_category_distribution() -> None:
    cases = load_benchmark_cases(SUITE)

    assert len(cases) == 12
    assert {case.category for case in cases} == {
        "repository_understanding",
        "change_planning",
        "review_risk",
    }
    assert sum(case.category == "repository_understanding" for case in cases) == 4
    assert sum(case.category == "change_planning" for case in cases) == 4
    assert sum(case.category == "review_risk" for case in cases) == 4


def test_benchmark_rejects_missing_fixture_file(tmp_path: Path) -> None:
    case = BenchmarkCase(
        case_id="missing_fixture",
        category="repository_understanding",
        title="Missing fixture",
        requirement="Explain the missing file.",
        expected_file_patterns=("missing.py",),
    )
    report = run_mock_benchmark((case,), repo=tmp_path, output=tmp_path / "out")

    assert report["status"] == "failed"
    assert report["runs"][0]["error_codes"] == ["fixture_file_missing"]


def test_benchmark_rejects_non_empty_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "old.json").write_text("{}", encoding="utf-8")
    case = BenchmarkCase(
        case_id="one_case",
        category="repository_understanding",
        title="One case",
        requirement="Explain the fixture.",
        expected_file_patterns=("README.md",),
    )

    with pytest.raises(ValueError, match="must be empty"):
        run_mock_benchmark((case,), repo=FIXTURE, output=output)


def test_normalized_baseline_excludes_latency_and_artifact_path() -> None:
    report = {
        "status": "passed",
        "case_count": 1,
        "categories": {"repository_understanding": {"total": 1, "passed": 1}},
        "metrics": {
            "schema_pass_rate": 1.0,
            "run_success_rate": 1.0,
            "degraded_rate": 0.0,
            "fallback_rate": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "latency_ms": {"average": 5.0},
            "error_code_counts": {},
        },
        "runs": [
            {
                "case_id": "one_case",
                "category": "repository_understanding",
                "status": "passed",
                "schema_validated": True,
                "artifact_directory": "one_case/run-multi-abc",
                "error_codes": [],
            }
        ],
    }

    baseline = normalized_baseline(report)
    serialized = json.dumps(baseline, sort_keys=True)
    assert "latency" not in serialized
    assert "artifact_directory" not in serialized


def test_benchmark_cli_writes_report_and_baseline(tmp_path: Path) -> None:
    output = tmp_path / "output"
    baseline = tmp_path / "baseline.json"

    with pytest.raises(SystemExit) as result:
        main(
            [
                "benchmark",
                "--suite",
                str(SUITE),
                "--repo",
                str(FIXTURE),
                "--output",
                str(output),
                "--baseline",
                str(baseline),
            ]
        )

    assert result.value.code == 0
    report = json.loads((output / "benchmark-report.json").read_text(encoding="utf-8"))
    assert report["case_count"] == 12
    assert report["status"] == "passed"
    assert json.loads(baseline.read_text(encoding="utf-8"))["case_count"] == 12

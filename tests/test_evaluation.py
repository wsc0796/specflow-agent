import json
from pathlib import Path

import pytest

from specflow.evaluation import (
    EvaluationCase,
    EvaluationMode,
    EvaluationScore,
    EvaluationStatus,
    ScoreSource,
    load_cases,
    run_mock_evaluation,
)
from specflow.evaluation.exceptions import EvaluationError
from specflow.evaluation.report import report_as_dict
from specflow.evaluation.rubric import RUBRIC_DIMENSIONS


def _case() -> EvaluationCase:
    return EvaluationCase(
        case_id="health_contract",
        title="Health contract",
        requirement="Add a health endpoint contract.",
        repository_type="python",
        expected_domains=("api",),
        expected_file_patterns=("app.py",),
        expected_risks=("regression",),
        expected_acceptance_topics=("test",),
        forbidden_claims=("already implemented",),
        human_review_notes="Use existing app module.",
    )


def test_case_rejects_missing_case_id() -> None:
    with pytest.raises(EvaluationError, match="case_id"):
        EvaluationCase(**{**_case().__dict__, "case_id": ""})


def test_case_rejects_empty_requirement() -> None:
    with pytest.raises(EvaluationError, match="requirement"):
        EvaluationCase(**{**_case().__dict__, "requirement": " "})


def test_score_rejects_invalid_range() -> None:
    with pytest.raises(EvaluationError, match="0, 1, or 2"):
        EvaluationScore("security", 3, ScoreSource.HUMAN, "Invalid score")


def test_rubric_has_ten_manual_dimensions() -> None:
    assert len(RUBRIC_DIMENSIONS) == 10
    assert "security" in RUBRIC_DIMENSIONS


def test_loads_committed_real_repository_cases() -> None:
    cases = load_cases(Path("evaluation/cases"))

    assert [case.case_id for case in cases] == [
        "category_dish_cache_invalidation",
        "dish_cache_consistency",
        "login_failure_rate_limit",
    ]


def test_mock_evaluation_is_repeatable_and_separates_human_scores(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text("# health endpoint contract\n", encoding="utf-8")

    first = run_mock_evaluation((_case(),), repository, tmp_path / "first")
    second = run_mock_evaluation((_case(),), repository, tmp_path / "second")

    assert first.status == EvaluationStatus.PASSED
    assert second.status == EvaluationStatus.PASSED
    assert report_as_dict(first) == report_as_dict(second)
    assert first.mode == EvaluationMode.MOCK_CONTRACT
    assert first.live_validation_status == EvaluationStatus.BLOCKED
    assert not first.runs[0].human_scores
    assert (
        json.loads(
            (
                tmp_path
                / "first"
                / "health_contract"
                / next((tmp_path / "first" / "health_contract").glob("run-*")).name
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )["provider_type"]
        == "mock"
    )


def test_mock_evaluation_detects_missing_grounding_file(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    report = run_mock_evaluation((_case(),), repository, tmp_path / "result")

    assert report.status == EvaluationStatus.FAILED
    assert report.runs[0].findings[0].code == "case_file_missing"

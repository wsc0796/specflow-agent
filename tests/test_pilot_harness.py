"""Phase 6 harness tests: deterministic scoring, anonymity, mock smoke."""

from __future__ import annotations

import json
from pathlib import Path

from specflow.evaluation.models import EvaluationCase
from specflow.evaluation.pilot import (
    EvaluationCandidate,
    blind_pack,
    load_cases,
    rule_score,
    run_pilot_mock_smoke,
)


def _case() -> EvaluationCase:
    return EvaluationCase(
        case_id="pilot_01_single_file",
        title="Order cancellation plan",
        requirement="Design order cancellation",
        repository_type="small_fastapi_fixture",
        expected_domains=("orders", "api"),
        expected_file_patterns=("app/orders.py",),
        expected_risks=("非法状态流转",),
        expected_acceptance_topics=("取消接口行为",),
        forbidden_claims=("production-ready",),
        human_review_notes="n/a",
    )


def _candidate() -> EvaluationCandidate:
    return EvaluationCandidate(
        case_id="pilot_01_single_file",
        pipeline="six-role",
        execution_mode="mock",
        proposed_changes=("Add cancel endpoint",),
        affected_files=("app/orders.py",),
        evidence_refs=("app/orders.py",),
        implementation_steps=("step",),
        test_plan=("test cancel",),
        risks=("非法状态流转",),
        rollback="restore",
        uncertainties=(),
        pipeline_metrics={"exit_code": 0},
    )


def test_load_cases_reads_frozen_pilot_set() -> None:
    cases = load_cases(Path("evaluation/pilot/cases"))
    assert len(cases) == 5
    assert {case.case_id for case in cases} == {
        "pilot_01_single_file",
        "pilot_02_two_modules",
        "pilot_03_api_config_tests",
        "pilot_04_security_reliability",
        "pilot_05_vague_requirement",
    }


def test_rule_score_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app").mkdir()
    (repo / "app" / "orders.py").write_text("# orders", encoding="utf-8")
    case = _case()
    first = rule_score(case, _candidate(), repo=repo, run_success=True, budget_violation=False)
    second = rule_score(case, _candidate(), repo=repo, run_success=True, budget_violation=False)
    assert first == second
    assert first["expected_module_recall"] == 1.0
    assert first["run_success"] is True
    assert first["forbidden_claim_count"] == 0


def test_blind_pack_hides_pipeline_identity() -> None:
    candidates = [
        _candidate(),
        EvaluationCandidate(
            case_id="pilot_01_single_file",
            pipeline="legacy",
            execution_mode="mock",
            proposed_changes=("x",),
            pipeline_metrics={},
        ),
    ]
    pack = blind_pack(candidates, seed=7)
    serialized = json.dumps(pack)
    assert "six-role" not in serialized
    assert "legacy" not in serialized
    assert len(pack["packs"]) == 2
    assert "seed" not in pack
    assert [item["anonymous_id"] for item in pack["packs"]] == [
        "ANON-000",
        "ANON-001",
    ]


def test_mock_smoke_produces_fifteen_runs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app").mkdir()
    for name in ("auth.py", "cache.py", "catalog.py", "main.py", "orders.py"):
        (repo / "app" / name).write_text(f"# {name}", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_orders.py").write_text("# tests", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    output = tmp_path / "pilot"
    results = run_pilot_mock_smoke(
        repo=repo,
        cases=(_case(),),
        output=output,
    )
    assert len(results) == 3  # 1 case x 3 pipelines (mock smoke, not the full 15)
    for result in results:
        assert result["execution_mode"] == "mock"
        assert result["pipeline"] in {"single", "legacy", "six-role"}

    by_pipeline = {result["pipeline"]: result for result in results}
    single = by_pipeline["single"]
    assert "app/orders.py" not in single["affected_files"]
    assert "非法状态流转" not in single["risks"]

    legacy = by_pipeline["legacy"]
    assert legacy["proposed_changes"]
    assert legacy["test_plan"]

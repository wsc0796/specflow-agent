"""Report protocol counterexamples. No model or business-semantic score is produced."""

import copy

import pytest

from specflow.contract_review.common import digest
from specflow.contract_review.protocol import ReviewResult, WorkItem
from specflow.contract_review.report_validation import validate_report


@pytest.fixture
def report_context():
    ref = {"source_id": "s", "selector": {"kind": "full"}}
    sources = {
        "s": {"body": "Only queued may cancel.", "body_hash": digest(b"Only queued may cancel.")}
    }
    frozen = {
        "target_manifest": [{"target_id": "t"}],
        "check_manifest": [{"check_id": "c", "target_id": "t"}],
        "adoption_records": [{"adoption_id": "a", "target_id": "t", "disposition": "adopted"}],
        "verification_evidence_adoptions": [],
    }
    report = {
        "schema_version": "contract-review-report-payload.v2.1",
        "summary": "静态违约示意。",
        "coverage": [
            {"target_id": "t", "status": "covered", "source_refs": [ref], "missing_information": []}
        ],
        "check_results": [
            {
                "check_id": "c",
                "status": "checked",
                "finding_ids": ["f"],
                "source_refs": [ref],
                "observation_refs": [],
                "missing_information": [],
            }
        ],
        "rule_uses": [{"adoption_id": "a", "usage": "support", "explanation": "本次显式依据。"}],
        "findings": [
            {
                "id": "f",
                "target_ids": ["t"],
                "judgment_status": "supported_deviation",
                "affected_artifacts": ["implementation"],
                "labels": ["implementation_contract_violation"],
                "claim": "工程测试中的候选结论，不能据此证明语义正确。",
                "rule_refs": ["a"],
                "source_refs": [ref],
                "observation_refs": [],
                "verification_evidence_refs": [],
                "execution_verification": "NOT_RUN",
                "limitations": [],
            }
        ],
        "questions": [],
        "work_items": [],
        "acceptance_items": [],
        "adopted_child_result_refs": [],
        "limitations": ["未执行业务测试。"],
    }
    return report, frozen, sources, [ref]


def test_supported_deviation_and_not_run_do_not_automatically_degrade(report_context):
    _, quality = validate_report(*report_context)
    assert quality == {
        "level": "complete",
        "gap_check_ids": [],
        "gap_target_ids": [],
        "reason_codes": [],
    }


@pytest.mark.parametrize(
    "kind",
    [
        "missing_target",
        "extra_target",
        "duplicate_target",
        "missing_check",
        "duplicate_finding",
        "duplicate_rule_use",
        "wrong_check",
        "unread_source",
        "unknown_field",
        "forged_quality",
        "unknown_observation",
    ],
)
def test_rejects_structural_and_ownership_counterexamples(report_context, kind):
    report, frozen, sources, reads = copy.deepcopy(report_context)
    if kind == "missing_target":
        report["coverage"] = []
    elif kind == "extra_target":
        report["coverage"].append({**report["coverage"][0], "target_id": "other"})
    elif kind == "duplicate_target":
        report["coverage"] *= 2
    elif kind == "missing_check":
        report["check_results"] = []
    elif kind == "duplicate_finding":
        report["findings"] *= 2
    elif kind == "duplicate_rule_use":
        report["rule_uses"] *= 2
    elif kind == "wrong_check":
        report["check_results"][0]["check_id"] = "other-input-check"
    elif kind == "unread_source":
        reads = []
    elif kind == "unknown_field":
        report["job_id"] = "forged"
    elif kind == "forged_quality":
        report["quality"] = {"level": "complete"}
    else:
        report["findings"][0]["observation_refs"] = ["another-job-observation"]
    with pytest.raises(ValueError):
        validate_report(report, frozen, sources, reads)


def test_gap_projection_is_deterministic_and_cannot_hide_behind_covered(report_context):
    report, frozen, sources, reads = report_context
    report["findings"][0]["judgment_status"] = "insufficient_evidence"
    report["findings"][0]["limitations"] = ["没有实现正文。"]
    report["check_results"][0].update(
        status="evidence_missing", missing_information=["没有实现正文。"]
    )
    with pytest.raises(ValueError):
        validate_report(report, frozen, sources, reads)
    report["coverage"][0].update(status="partial", missing_information=["没有实现正文。"])
    assert validate_report(report, frozen, sources, reads)[1] == {
        "level": "degraded",
        "gap_check_ids": ["c"],
        "gap_target_ids": ["t"],
        "reason_codes": ["missing_evidence", "target_partial"],
    }


def work_item(identifier, dependency):
    return {
        "id": identifier,
        "title": "补证",
        "finding_ids": ["f"],
        "target_ids": ["t"],
        "rule_refs": [],
        "source_refs": [],
        "handling_intent": {"kind": "obtain_evidence", "text": "补齐正文"},
        "proposed_scope": {
            "include": [{"artifact_role": "implementation", "paths": ["api.py"]}],
            "exclude": [],
        },
        "depends_on": dependency,
        "readiness": "not_ready",
        "blockers": [{"code": "dependency_not_ready", "reason": "依赖未就绪", "refs": []}],
        "acceptance_ids": [],
        "execution_authorized": False,
    }


def test_dependency_cycle_is_rejected(report_context):
    report, frozen, sources, reads = report_context
    report["work_items"] = [work_item("w1", ["w2"]), work_item("w2", ["w1"])]
    with pytest.raises(ValueError, match="Cyclic"):
        validate_report(report, frozen, sources, reads)


def test_false_authorization_does_not_accept_integer_zero():
    item = work_item("w", [])
    item["execution_authorized"] = 0
    with pytest.raises(ValueError):
        WorkItem.model_validate(item)


def test_fixed_review_cannot_accept_while_hiding_issues():
    result = {
        "schema_version": "contract-review-review-result.v2",
        "type": "review_result",
        "candidate_report_hash": "a" * 64,
        "outcome": "accept",
        "issues": [],
        "revision_feedback": "这里实际有缺口",
    }
    with pytest.raises(ValueError):
        ReviewResult.model_validate(result)

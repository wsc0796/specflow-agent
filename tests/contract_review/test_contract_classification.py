"""Report protocol counterexamples. No model or business-semantic score is produced."""

import copy

import pytest

from specflow.contract_review.common import digest
from specflow.contract_review.protocol import ReviewResult, WorkItem
from specflow.contract_review.report_validation import validate_material_refs, validate_report


@pytest.fixture
def report_context():
    ref = {"source_id": "s", "selector": {"kind": "full"}}
    sources = {
        "s": {"body": "Only queued may cancel.", "body_hash": digest(b"Only queued may cancel.")}
    }
    frozen = {
        "input_revision_id": "ir-test",
        "target_manifest": [{"target_id": "t", "api_version": "v2", "source_path": "api.py"}],
        "check_manifest": [{"check_id": "c", "target_id": "t"}],
        "adoption_records": [
            {
                "adoption_id": "a",
                "target_id": "t",
                "disposition": "adopted",
                "body_ref": ref,
                "body_hash": sources["s"]["body_hash"],
                "effective_scope_expression": {
                    "base_scope": {"api_versions": ["v2"], "source_paths": ["api.py"]},
                    "removal_slices": [],
                },
            }
        ],
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


def evidence_binding(frozen, state="applicable"):
    return {
        "evidence_id": "ev1",
        "verification_adoption_id": "ea1",
        "adopting_input_revision_id": frozen["input_revision_id"],
        "target_checks": [
            {"target_id": target["target_id"], "applicability": state}
            for target in frozen["target_manifest"]
        ],
    }


@pytest.mark.parametrize("state", ["inapplicable", "unresolved"])
def test_positive_finding_cannot_use_external_evidence_for_another_or_unknown_target(
    report_context, state
):
    report, frozen, sources, reads = report_context
    frozen["verification_evidence_adoptions"] = [evidence_binding(frozen, state)]
    report["findings"][0]["verification_evidence_refs"] = ["ev1"]
    with pytest.raises(ValueError, match="not applicable"):
        validate_report(report, frozen, sources, reads, projected_evidence_ids=["ev1"])


def test_adopted_but_unprojected_evidence_is_not_a_supporting_reference(report_context):
    report, frozen, sources, reads = report_context
    frozen["verification_evidence_adoptions"] = [evidence_binding(frozen)]
    report["findings"][0]["verification_evidence_refs"] = ["ev1"]
    with pytest.raises(ValueError, match="projected evidence"):
        validate_report(report, frozen, sources, reads)
    payload, quality = validate_report(
        report, frozen, sources, reads, projected_evidence_ids=["ev1"]
    )
    assert quality["level"] == "complete"
    assert payload["findings"][0]["execution_verification"] == "NOT_RUN"


def test_any_applicable_target_cannot_authorize_all_targets_in_a_finding(report_context):
    report, frozen, sources, reads = report_context
    frozen["target_manifest"].append(
        {"target_id": "t2", "api_version": "v2", "source_path": "other.py"}
    )
    frozen["check_manifest"].append({"check_id": "c2", "target_id": "t2"})
    rule = copy.deepcopy(frozen["adoption_records"][0])
    rule.update(adoption_id="a2", target_id="t2")
    rule["effective_scope_expression"]["base_scope"]["source_paths"] = ["other.py"]
    frozen["adoption_records"].append(rule)
    report["rule_uses"].append(
        {"adoption_id": "a2", "usage": "support", "explanation": "第二个目标"}
    )
    report["coverage"].append({**report["coverage"][0], "target_id": "t2"})
    report["check_results"].append({**report["check_results"][0], "check_id": "c2"})
    report["findings"][0]["target_ids"].append("t2")
    report["findings"][0]["rule_refs"].append("a2")
    binding = evidence_binding(frozen)
    binding["target_checks"][1]["applicability"] = "inapplicable"
    frozen["verification_evidence_adoptions"] = [binding]
    report["findings"][0]["verification_evidence_refs"] = ["ev1"]
    with pytest.raises(ValueError, match="each supported target"):
        validate_report(report, frozen, sources, reads, projected_evidence_ids=["ev1"])
    binding["target_checks"][1]["applicability"] = "applicable"
    assert (
        validate_report(report, frozen, sources, reads, projected_evidence_ids=["ev1"])[1]["level"]
        == "complete"
    )


def test_acceptance_item_also_checks_its_own_target_applicability(report_context):
    report, frozen, sources, reads = report_context
    frozen["verification_evidence_adoptions"] = [evidence_binding(frozen, "unresolved")]
    item = work_item("w", [])
    item["acceptance_ids"] = ["ac"]
    report["work_items"] = [item]
    report["acceptance_items"] = [
        {
            "id": "ac",
            "work_item_id": "w",
            "finding_ids": ["f"],
            "target_ids": ["t"],
            "rule_refs": ["a"],
            "source_refs": reads,
            "given": "固定输入",
            "when": "外部核验",
            "then": "取得状态记录",
            "verification_method": {
                "kind": "external_controlled_execution",
                "procedure": "读取提供者记录",
                "required_environment": "隔离环境",
            },
            "expected_evidence": ["原始记录"],
            "evidence_refs": ["ev1"],
            "execution_status": "NOT_RUN",
        }
    ]
    with pytest.raises(ValueError, match="not applicable"):
        validate_report(report, frozen, sources, reads, projected_evidence_ids=["ev1"])


def test_removed_or_unresolved_rule_scope_cannot_support_a_finding(report_context):
    report, frozen, sources, reads = report_context
    expression = frozen["adoption_records"][0]["effective_scope_expression"]
    expression["removal_slices"] = [{"api_versions": ["v2"], "source_paths": ["api.py"]}]
    with pytest.raises(ValueError, match="effective scope"):
        validate_report(report, frozen, sources, reads)
    expression["removal_slices"] = [
        {"api_versions": ["v2"], "endpoints": [{"method": "POST", "path": "/exports"}]}
    ]
    with pytest.raises(ValueError, match="effective scope"):
        validate_report(report, frozen, sources, reads)


@pytest.mark.parametrize(
    "reference",
    [
        {"kind": "source", "source_ref": {"source_id": "foreign", "selector": {"kind": "full"}}},
        {"kind": "rule", "adoption_id": "foreign"},
        {"kind": "observation", "observation_id": "foreign"},
    ],
)
def test_action_and_review_material_refs_are_owned_by_current_input(report_context, reference):
    _, frozen, sources, reads = report_context
    with pytest.raises(ValueError):
        validate_material_refs([reference], frozen, sources, reads)


def test_rule_body_reference_must_match_the_frozen_original(report_context):
    report, frozen, sources, reads = report_context
    frozen["adoption_records"][0]["body_hash"] = "0" * 64
    with pytest.raises(ValueError, match="Adopted rule body damaged"):
        validate_report(report, frozen, sources, reads)


def test_proposed_work_scope_cannot_escape_the_repository():
    item = work_item("w", [])
    item["proposed_scope"]["include"][0]["paths"] = ["../outside.md"]
    with pytest.raises(ValueError):
        WorkItem.model_validate(item)

"""Material projection, publication boundaries and explicit profile compatibility."""

import copy
import json

import pytest

from specflow.contract_review.common import ReviewError, digest
from specflow.contract_review.dynamic_context import RunState
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.schemas import ExecutionProfile
from specflow.contract_review.snapshot_tools import SnapshotTools


def state_for(rule_text="v2: " + "padding " * 80 + "only queued may cancel", doc_text="document"):
    profile = dynamic_profile("context-test", "controlled-test")
    target = {"target_id": "t", "api_version": "v2", "source_path": "doc.json"}
    ref = {"source_id": "rule", "selector": {"kind": "full"}}
    sources = {
        "rule": {
            "source_id": "rule",
            "path": "rule.md",
            "roles": ["contract"],
            "body": rule_text,
            "body_hash": digest(rule_text.encode()),
        },
        "doc": {
            "source_id": "doc",
            "path": "doc.json",
            "roles": ["documentation"],
            "body": json.dumps(doc_text),
            "body_hash": digest(json.dumps(doc_text).encode()),
        },
    }
    frozen = {
        "execution_profile": profile,
        "snapshot_id": "snap",
        "input_revision_id": "ir",
        "original_request": {"request": "Check selected target"},
        "target_manifest": [target],
        "check_manifest": [
            {
                "check_id": "c",
                "target_id": "t",
                "key": "field",
                "behavior": "check field",
                "rule_source_refs": [],
            }
        ],
        "adoption_records": [
            {
                "adoption_id": "a",
                "target_id": "t",
                "body_ref": ref,
                "body_hash": sources["rule"]["body_hash"],
                "disposition": "adopted",
            }
        ],
        "resolutions": [],
        "verification_evidence_adoptions": [],
    }
    context = {"frozen": frozen, "sources": sources, "verification_evidence": []}
    return RunState(context, SnapshotTools(sources, "snap"))


def test_critical_rule_tail_is_kept_in_full_and_catalog_is_not_a_read():
    state = state_for()
    data, entries = state.build("analysis")
    assert data["rule_materials"][0]["body"].endswith("only queued may cancel")
    assert len(data["rule_materials"][0]["body"]) > 500
    state.mark_projected(data, entries)
    reads, _ = state.evidence()
    assert {ref["source_id"] for ref in reads} == {"rule"}


def test_omitted_observation_is_explicit_and_cannot_claim_source_was_read():
    state = state_for(doc_text="x" * 20000)
    ref = {"source_id": "doc", "selector": {"kind": "json_pointer", "pointer": ""}}
    body = {"value": "x" * 20000}
    state.observations["large"] = {
        "observation_id": "large",
        "origin": "snapshot_tool",
        "body": body,
        "body_hash": digest(body),
        "source_refs": [ref],
        "result_kind": "data",
        "completeness": "complete",
        "truncation": None,
        "error": None,
    }
    data, entries = state.build("analysis")
    assert data["omitted_observation_ids"] == ["large"]
    assert data["observations"] == []
    state.mark_projected(data, entries)
    reads, observations = state.evidence()
    assert ref not in reads and "large" not in observations


@pytest.mark.parametrize("failure", ["oversize", "hash"])
def test_mandatory_material_failure_is_not_summarized_away(failure):
    state = state_for(rule_text="x" * 25000 if failure == "oversize" else "rule")
    if failure == "hash":
        state.context["sources"]["rule"]["body_hash"] = "0" * 64
    with pytest.raises(ReviewError) as caught:
        state.build("analysis")
    assert caught.value.code == (
        "BUDGET_EXHAUSTED" if failure == "oversize" else "SOURCE_INTEGRITY_FAILED"
    )


@pytest.mark.parametrize(
    ("status", "disposition", "published", "supported"),
    [
        ("failed", "adopted", True, False),
        ("insufficient", "rejected", True, False),
        ("completed", "adopted", False, False),
        ("insufficient", "partial", True, True),
    ],
)
def test_parent_support_uses_only_published_eligible_child_evidence(
    status, disposition, published, supported
):
    state = state_for()
    ref = {"source_id": "doc", "selector": {"kind": "full"}}
    child = {
        "result": {
            "schema_version": "contract-review-child-result.v1",
            "status": status,
            "findings": [],
            "evidence_refs": [],
            "limitations": [],
            "unresolved_gaps": [],
        },
        "evidence_trace": {
            "read_refs": [ref],
            "observations": [],
            "published_source_refs": [ref] if published else [],
            "published_observation_ids": [],
        },
    }
    state.children["child-result"] = child
    state.reviews["child-result"] = {
        "child_result_ref": "child-result",
        "disposition": disposition,
        "reason": "只处理所述部分。",
    }
    original = copy.deepcopy(child)
    assert (ref in state.evidence()[0]) is supported
    data, _ = state.build("analysis")
    assert data["child_results"][0]["result"] == original["result"]
    assert state.children["child-result"] == original


def test_v1_profile_is_byte_compatible_with_frozen_pre_task04_profile(test_profile):
    frozen = ExecutionProfile.model_validate(test_profile).frozen()
    assert digest(frozen) == "62e610f52cfda55780a1998b76d75ab734894d48fe34468cbf2a8adec681d322"
    with pytest.raises(ValueError):
        ExecutionProfile.model_validate({**test_profile, "child_model_limit": 1})

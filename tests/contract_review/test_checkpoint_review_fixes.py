"""Regressions reproduced by the independent Astra TASK-05 review."""

import copy
import json

import pytest
from test_checkpoints import (
    URL,
    HumanAdapter,
    answer,
    batch,
    footprint,
    frozen,
    post,
    revision,
    terminal,
    waiting,
)

from specflow.contract_review.report_validation import validate_report


@pytest.mark.parametrize("change", ["same_request", "changed_request", "explicit_profile"])
def test_deployment_profile_drift_requires_explicit_selection(
    running_app, controlled_adapter, change
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, _ = waiting(client, body)
        domain.worker.close()
        profile_id = body["execution_profile_id"]
        updated = copy.deepcopy(domain.profiles[profile_id])
        updated["analysis_prompt"] += " 明确的新部署配置。"
        domain.profiles[profile_id] = updated
        patch = {"request": body["request"]}
        if change == "changed_request":
            patch["request"] += " 本次增加明确检查范围。"
        elif change == "explicit_profile":
            patch["execution_profile_id"] = profile_id
        before = footprint(domain, review_id)
        response = post(client, review_id, revision(state, **patch), change, "revisions")
        if change == "explicit_profile":
            assert response.status_code == 202, response.text
            next_input = frozen(domain, review_id, response.json()["input_revision_id"])
            assert next_input["execution_profile"] == updated
        else:
            assert response.status_code == 409, response.text
            assert response.json()["error"]["code"] == "RETRY_PROFILE_UNAVAILABLE"
            assert footprint(domain, review_id) == before


class SeparateCheckAdapter:
    execution_mode = "test"

    def __init__(self, fallback):
        self.fallback = fallback

    def __getattr__(self, name):
        return getattr(self.fallback, name)

    def complete(self, payload):
        result = self.fallback.complete(payload)
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            return result
        action = json.loads(result["content"])
        report = action["report"]
        target = data["targets"][0]["target_id"]
        adoption = next(
            a["adoption_id"]
            for a in data["adoption_records"]
            if a["target_id"] == target and a["disposition"] == "adopted"
        )
        source_ref = {"source_id": data["sources"][0]["source_id"], "selector": {"kind": "full"}}
        report["findings"][0]["claim"] = "旧版客户端兼容行为缺少额外契约。"
        report["findings"][0]["limitations"] = ["仅兼容行为检查缺少原文。"]
        other = {
            **copy.deepcopy(report["findings"][0]),
            "id": "f_spelling",
            "judgment_status": "supported_deviation",
            "claim": "独立的状态字段拼写有明确规则和原文，能够交接修正文档。",
            "rule_refs": [adoption],
            "source_refs": [source_ref],
            "limitations": [],
        }
        report["findings"].append(other)
        report["check_results"][1] = {
            **report["check_results"][1],
            "status": "checked",
            "finding_ids": ["f_spelling"],
            "source_refs": [source_ref],
            "missing_information": [],
        }
        report["rule_uses"] = [
            {
                "adoption_id": adoption,
                "usage": "support",
                "explanation": "当前目标已明确采用该规则。",
            }
        ]
        report["questions"] = (
            []
            if data["resolutions"]
            else [
                {
                    "id": "q_compatibility",
                    "kind": "missing_evidence",
                    "prompt": "旧版客户端的额外兼容契约是什么？",
                    "blocking": True,
                    "target_ids": [target],
                    "finding_ids": [report["findings"][0]["id"]],
                    "work_item_ids": [],
                    "rule_refs": [],
                    "evidence_refs": [],
                    "why_blocking": "兼容检查缺少契约。",
                    "options": [],
                    "allowed_answer_types": ["mark_insufficient"],
                }
            ]
        )
        report["work_items"] = [
            {
                "id": "w_spelling",
                "title": "修正当前状态字段拼写",
                "finding_ids": ["f_spelling"],
                "target_ids": [target],
                "rule_refs": [adoption],
                "source_refs": [source_ref],
                "handling_intent": {
                    "kind": "align_documentation",
                    "text": "按已明确规则修正文档字段拼写。",
                },
                "proposed_scope": {
                    "include": [{"artifact_role": "documentation", "paths": ["docs/api.md"]}],
                    "exclude": [],
                },
                "depends_on": [],
                "readiness": "ready",
                "blockers": [],
                "acceptance_ids": ["a_spelling"],
                "execution_authorized": False,
            }
        ]
        report["acceptance_items"] = [
            {
                "id": "a_spelling",
                "work_item_id": "w_spelling",
                "finding_ids": ["f_spelling"],
                "target_ids": [target],
                "rule_refs": [adoption],
                "source_refs": [source_ref],
                "given": "当前规则和文档原文已知。",
                "when": "核对字段拼写。",
                "then": "拼写符合该规则。",
                "verification_method": {
                    "kind": "static_review",
                    "procedure": "读取契约与文档。",
                    "required_environment": "密封快照",
                },
                "expected_evidence": ["文档与契约字段摘录"],
                "evidence_refs": [],
                "execution_status": "NOT_RUN",
            }
        ]
        self.last_report = copy.deepcopy(report)
        result["content"] = json.dumps(action, ensure_ascii=False)
        return result


@pytest.mark.parametrize("rename_local_ids", [False, True])
def test_insufficient_one_check_does_not_block_independent_ready_work(
    running_app, controlled_adapter, rename_local_ids
):
    adapter = SeparateCheckAdapter(controlled_adapter())
    with running_app(adapter) as (client, domain, body):
        body = copy.deepcopy(body)
        body["targets"] = [
            {
                **body["targets"][0],
                "checks": [
                    {
                        "key": "compatibility",
                        "behavior": "旧版客户端兼容性需要额外契约",
                        "rule_selectors": [],
                    },
                    {
                        "key": "status_spelling",
                        "behavior": "文档状态字段拼写按当前明确契约检查",
                        "rule_selectors": [],
                    },
                ],
            }
        ]
        review_id, state, report = waiting(client, body)
        assert report["payload"]["work_items"][0]["readiness"] == "ready"
        raw = batch(
            state,
            report,
            [
                answer(
                    "q_compatibility", "mark_insufficient", "本轮没有额外兼容契约，保留该检查缺口。"
                )
            ],
        )
        response = post(client, review_id, raw)
        assert response.status_code == 202, response.text
        final = terminal(client, review_id)
        assert final["status"] == "completed_degraded", final
        saved = client.get(f"{URL}/{review_id}/report").json()
        assert saved["payload"]["work_items"][0]["readiness"] == "ready"
        latest = frozen(domain, review_id, response.json()["input_revision_id"])
        data = json.loads(adapter.requests[-1]["messages"][1]["content"])
        candidate = copy.deepcopy(adapter.last_report)
        if rename_local_ids:
            mapping = {item["id"]: item["id"] + "_next" for item in candidate["findings"]}
            for finding in candidate["findings"]:
                finding["id"] = mapping[finding["id"]]
            for field in ("check_results", "work_items", "acceptance_items"):
                for item in candidate[field]:
                    item["finding_ids"] = [
                        mapping[identifier] for identifier in item["finding_ids"]
                    ]
        sources = {s["source_id"]: s for s in data["sources"]}
        reads = [{"source_id": s, "selector": {"kind": "full"}} for s in sources]
        validate_report(candidate, latest, sources, reads)
        related = candidate["check_results"][0]["finding_ids"]
        candidate["work_items"][0]["finding_ids"] = related
        with pytest.raises(ValueError, match="related work"):
            validate_report(candidate, latest, sources, reads)

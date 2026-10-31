"""Bounded parent/tool/child loop; orchestration never grants write authority."""

import json
import time

from pydantic import ValidationError

from specflow.contract_review.actions import ChildResult, parse_action
from specflow.contract_review.common import ReviewError, canonical, digest, identity
from specflow.contract_review.dynamic_context import RunState, append_unique
from specflow.contract_review.inputs import match_effective_scope
from specflow.contract_review.protocol import ReviewResult
from specflow.contract_review.provider import ProviderFailure
from specflow.contract_review.report_validation import (
    keyed,
    require,
    unique,
    validate_material_refs,
    validate_report,
    validate_rule_body,
    validate_source_refs,
)
from specflow.contract_review.snapshot_tools import SnapshotTools
from specflow.contract_review.sources import select_text, strict_json
from specflow.contract_review.tool_protocol import CAPABILITIES, ToolResponse, contains_selector

CORRECTABLE = {
    "ACTION_SCHEMA_INVALID",
    "ACTION_PERMISSION_DENIED",
    "ACTION_NOT_ALLOWED",
    "OPTION_NOT_ENABLED",
}


def correction(error, code):
    if isinstance(error, ValidationError):
        issues = [
            {"path": list(item["loc"]), "type": item["type"], "message": item["msg"][:200]}
            for item in error.errors(include_input=False, include_url=False, include_context=False)[
                :5
            ]
        ]
    else:
        issues = [{"message": str(error)[:300]}]
    return {
        "code": code,
        "issues": issues,
        "message": "按冻结协议、材料范围和子结果验收要求修正动作。",
    }


class DynamicRunner:
    def __init__(self, worker, context):
        self.worker, self.ledger, self.context = worker, worker.ledger, context
        self.state = RunState(
            context, SnapshotTools(context["sources"], context["frozen"]["snapshot_id"])
        )

    def run(self):
        try:
            self._parent()
        except ReviewError as error:
            self.ledger.fail(
                self.context, error.code, time.monotonic() - self.context["started_monotonic"]
            )
        except ValueError:
            self.ledger.fail(
                self.context,
                "ACTION_PROTOCOL_ERROR",
                time.monotonic() - self.context["started_monotonic"],
            )

    def _request(self, state, role):
        data, entries = state.build(role)
        call_id, result = self.worker.model_call(state.context, role, data, entries)
        state.mark_projected(data, entries)
        try:
            raw = strict_json(result["content"])
        except ValueError:
            self.ledger.record_result(
                state.context, call_id, result, accepted=False, reason="ACTION_SCHEMA_INVALID"
            )
            raise
        try:
            route_id = self.ledger.propose(state.context, call_id, raw)
        except ReviewError as error:
            self.ledger.record_result(
                state.context, call_id, result, accepted=False, reason=error.code
            )
            raise
        return call_id, result, route_id, raw

    def _parse(self, state, raw):
        action = parse_action(
            raw,
            child=bool(state.context.get("child_id")),
            delegation=state.frozen["execution_profile"]["options"]["delegate"],
        ).model_dump(exclude_none=True)
        reads, observations = state.evidence()
        visible = {**state.frozen, "adoption_records": state.rules}
        validate_material_refs(
            action["reason"]["evidence_refs"],
            visible,
            state.context["sources"],
            reads,
            observations,
        )
        if action["action"] == "tool_call":
            action["arguments"] = state.tools.validate(action["tool"], action["arguments"])
            if state.last_operation == state.operation_key(action) and state.repeats >= 2:
                raise ReviewError("NO_PROGRESS", "重复动作在纠正后仍无信息增量。")
        return action

    def _history(self, report):
        identifiers = {
            item["report_revision_id"]
            for finding in report["findings"]
            for item in finding.get("related_findings", [])
        }
        history = {}
        if identifiers:
            with self.worker.service.store.read() as conn:
                for identifier in identifiers:
                    row = self.worker.service.store.row(
                        conn,
                        "SELECT body FROM contract_review_reports WHERE id=:id AND review_id="
                        ":review",
                        id=identifier,
                        review=self.context["review_id"],
                    )
                    if row:
                        history[identifier] = {
                            finding["id"]
                            for finding in json.loads(row["body"])["payload"]["findings"]
                        }
        return history

    def _parent(self):
        state = self.state
        corrections, reworks = 0, 0
        while True:
            call_id = result = route_id = None
            try:
                call_id, result, route_id, raw = self._request(state, "analysis")
                action = self._parse(state, raw)
                latest = self.ledger.check_reviews(
                    self.context, call_id, action["child_result_reviews"]
                )
                if action["action"] == "delegate_task":
                    self.ledger.check_delegate(self.context)
                    child_spec = self._child_scope(action, latest)
                elif action["action"] == "submit_report":
                    reads, observations = state.evidence(latest)
                    report, quality = validate_report(
                        action["report"],
                        state.frozen,
                        self.context["sources"],
                        reads,
                        observations=observations,
                        historical_reports=self._history(action["report"]),
                        projected_evidence_ids=[
                            item["evidence_id"] for item in self.context["verification_evidence"]
                        ],
                        child_reviews=list(latest.values()),
                    )
                state.reviews = self.ledger.accept_action(
                    self.context, call_id, result, route_id, action
                )
                corrections = 0
                state.feedback.pop("protocol_feedback", None)
            except (ValueError, ReviewError) as error:
                code = error.code if isinstance(error, ReviewError) else "ACTION_SCHEMA_INVALID"
                if route_id:
                    self.ledger.reject_action(self.context, call_id, result, route_id, code)
                if code not in CORRECTABLE:
                    raise
                if corrections >= 1:
                    raise ReviewError("ACTION_PROTOCOL_ERROR", "动作在纠正后仍不合法。") from None
                corrections += 1
                state.feedback["protocol_feedback"] = correction(error, code)
                continue
            if action["action"] == "tool_call":
                self._tool(state, action)
            elif action["action"] == "delegate_task":
                returned = self._child(action, call_id, child_spec)
                state.children[returned["child_result_ref"]] = returned
                state.last_operation, state.repeats = None, 0
            else:
                verdict = self._review(report)
                if verdict.outcome == "accept":
                    self.ledger.commit_report(
                        self.context,
                        report,
                        quality,
                        time.monotonic() - self.context["started_monotonic"],
                    )
                    return
                if reworks >= 1:
                    raise ReviewError("REPORT_REVIEW_FAILED", "固定复核在返工后仍未接受。")
                reworks += 1
                state.feedback["revision_feedback"] = verdict.model_dump()

    def _tool(self, state, action):
        before = state.operation_key(action)
        context = state.context
        payload = {"tool": action["tool"], "arguments": action["arguments"]}
        call_id, instance = self.ledger.reserve_call(context, "tool", payload, [], kind="tool")
        try:
            returned = self.worker.perform_io(
                context,
                call_id,
                instance,
                lambda: state.tools.execute(action["tool"], action["arguments"]),
                context["frozen"]["execution_profile"]["tool_timeout_seconds"],
                kind="tool",
            )
        except ProviderFailure as failure:
            self.ledger.record_failure(context, call_id, failure)
            raise ReviewError(failure.code, "工具依赖失败。") from None
        try:
            returned = ToolResponse.model_validate(returned).model_dump()
            if len(canonical(returned).encode("utf-8")) > 64 * 1024:
                raise ValueError("Tool output limit")
            expected_sources = (
                {action["arguments"]["source_id"]}
                if "source_id" in action["arguments"]
                else set(action["arguments"].get("source_ids", []))
            )
            expected_sources.update(action["arguments"].get("local_ref_source_ids", []))
            unique(returned["source_refs"], "tool source reference")
            for ref in returned["source_refs"]:
                if ref["source_id"] not in expected_sources or not state.tools.permitted(
                    ref["source_id"], ref["selector"]
                ):
                    raise ValueError("Tool result source mismatch")
                fragment = select_text(
                    context["sources"][ref["source_id"]]["body"], ref["selector"]
                )
                body = returned["body"]
                if action["tool"] == "read_source":
                    require(
                        isinstance(body.get("text"), str) and fragment in body["text"],
                        "Read evidence text differs from source",
                    )
                elif action["tool"] == "search_sources":
                    require(
                        any(
                            item["source_ref"] == ref
                            and item["text"] == fragment
                            and not item["truncated"]
                            for item in body.get("matches", [])
                        ),
                        "Search evidence text differs from source",
                    )
                elif action["tool"] == "inspect_python_contract":
                    require(
                        any(
                            item["text"] == fragment
                            and not item["truncated"]
                            and ref["selector"]
                            == {
                                "kind": "lines",
                                "start_line": item["start_line"],
                                "end_line": item["end_line"],
                            }
                            for item in body.get("facts", [])
                        ),
                        "Python evidence text differs from source",
                    )
                elif action["tool"] == "inspect_json_contract":
                    value = canonical(strict_json(fragment))
                    primary = (
                        ref["source_id"] == action["arguments"]["source_id"]
                        and ref["selector"]
                        == {"kind": "json_pointer", "pointer": action["arguments"]["pointer"]}
                        and "value" in body
                        and canonical(body["value"]) == value
                    )
                    resolved = any(
                        item["source_id"] == ref["source_id"]
                        and ref["selector"] == {"kind": "json_pointer", "pointer": item["pointer"]}
                        and canonical(item["value"]) == value
                        for item in body.get("resolved_refs", [])
                    )
                    require(primary or resolved, "JSON evidence value differs from source")
                if action["tool"] == "read_source" and not contains_selector(
                    {
                        "kind": "lines",
                        "start_line": action["arguments"]["start_line"],
                        "end_line": action["arguments"]["end_line"],
                    },
                    ref["selector"],
                    len(context["sources"][ref["source_id"]]["body"].splitlines()),
                ):
                    raise ValueError("Tool result escaped requested range")
        except (ValueError, TypeError, KeyError, ReviewError):
            self.ledger.record_result(
                context,
                call_id,
                {"error": "TOOL_RESULT_INVALID", "original_result_available": False},
                accepted=False,
                reason="TOOL_RESULT_INVALID",
            )
            raise ReviewError("TOOL_RESULT_INVALID", "工具没有返回完整观察。")
        with self.worker.service.store.read() as conn:
            row = self.worker.service.store.row(
                conn, "SELECT body FROM contract_review_calls WHERE id=:id", id=call_id
            )
            logical = json.loads(row["body"])["logical_call_id"]
        observation = {
            "observation_id": identity("obs"),
            "input_revision_id": context["input_id"],
            "origin": "snapshot_tool",
            "logical_call_id": logical,
            "call_id": call_id,
            "child_task_id": context.get("child_id"),
            "tool": action["tool"],
            "arguments": action["arguments"],
            **returned,
            "body_hash": digest(returned["body"]),
        }
        self.ledger.record_result(
            context, call_id, observation, accepted=True, reason="TOOL_FORMAT_AND_SCOPE_VALID"
        )
        with self.worker.service.store.transaction() as conn:
            self.ledger.fence(conn, context)
            self.worker.service.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "material_listed" if action["tool"] == "list_sources" else "material_read",
                {
                    "observation_id": observation["observation_id"],
                    "source_refs": observation["source_refs"],
                    "result_kind": observation["result_kind"],
                },
                call_id=call_id,
                child_task_id=context.get("child_id"),
            )
        state.observations[observation["observation_id"]] = observation
        after = state.operation_key(action)
        state.repeats = state.repeats + 1 if before == after == state.last_operation else 0
        state.last_operation = after
        if state.repeats >= 2:
            state.feedback["no_progress_warning"] = (
                "连续重复读取没有新信息；请改变取证路线或提交有明确缺口的报告。"
            )
        elif state.repeats == 0:
            state.feedback.pop("no_progress_warning", None)

    def _child_scope(self, action, latest):
        grants, explicit_rules, initial = {}, set(), {}
        rules = keyed(self.state.rules, "adoption_id")
        _, permitted_observations = self.state.evidence(latest)
        unique(action["allowed_material_refs"], "allowed child material")
        for ref in action["allowed_material_refs"]:
            if ref["kind"] == "source":
                source_ref = ref["source_ref"]
                identifier, selector = source_ref["source_id"], source_ref["selector"]
                if not self.state.tools.permitted(identifier, selector):
                    raise ReviewError("ACTION_PERMISSION_DENIED", "子材料来源或片段超出父权限。")
                try:
                    select_text(self.context["sources"][identifier]["body"], selector)
                except ReviewError:
                    raise ReviewError("ACTION_SCHEMA_INVALID", "子材料片段不可用。") from None
                grants.setdefault(identifier, []).append(selector)
            elif ref["kind"] == "rule":
                require(ref["adoption_id"] in rules, "Unknown child rule")
                explicit_rules.add(ref["adoption_id"])
            else:
                require(
                    ref["observation_id"] in permitted_observations,
                    "Child observation not permitted",
                )
                initial[ref["observation_id"]] = permitted_observations[ref["observation_id"]]
        paths = {self.context["sources"][identifier]["path"] for identifier in grants}
        for observation in initial.values():
            paths.update(
                self.context["sources"][ref["source_id"]]["path"]
                for ref in observation["source_refs"]
            )
        explicit_targets = {rules[identifier]["target_id"] for identifier in explicit_rules}
        targets = [
            item
            for item in self.context["frozen"]["target_manifest"]
            if item.get("source_path") in paths or item["target_id"] in explicit_targets
        ]
        return grants, explicit_rules, initial, targets

    def _child(self, action, parent_call, specification):
        identifier, reference, deadline = self.ledger.start_child(self.context, parent_call, action)
        grants, rules, initial, targets = specification
        context = {
            **self.context,
            "child_id": identifier,
            "child_deadline": deadline,
            "parent_call_id": parent_call,
            "capability_id": action["capability_id"],
            "expected_evidence": action["expected_evidence"],
            "scope_fingerprint": digest(
                {
                    key: action[key]
                    for key in (
                        "capability_id",
                        "objective",
                        "allowed_material_refs",
                        "expected_evidence",
                    )
                }
            ),
        }
        state = RunState(
            context,
            SnapshotTools(
                context["sources"],
                context["frozen"]["snapshot_id"],
                grants,
                CAPABILITIES[action["capability_id"]],
            ),
            targets=targets,
            rule_ids=rules,
            initial_observations=initial,
            objective=action["objective"],
        )
        corrections = 0
        try:
            while True:
                call_id = result = route_id = None
                try:
                    call_id, result, route_id, raw = self._request(state, "child")
                    child_action = self._parse(state, raw)
                    if child_action["action"] == "submit_report":
                        payload = self._validate_child(state, child_action["report"])
                    self.ledger.accept_action(context, call_id, result, route_id, child_action)
                    corrections = 0
                except (ValueError, ReviewError) as error:
                    code = error.code if isinstance(error, ReviewError) else "ACTION_SCHEMA_INVALID"
                    if route_id:
                        self.ledger.reject_action(context, call_id, result, route_id, code)
                    if code not in CORRECTABLE:
                        raise
                    if corrections >= 1:
                        raise ReviewError(
                            "ACTION_PROTOCOL_ERROR", "子动作在纠正后仍不合法。"
                        ) from None
                    corrections += 1
                    state.feedback["protocol_feedback"] = correction(error, code)
                    continue
                if child_action["action"] == "tool_call":
                    self._tool(state, child_action)
                else:
                    return self.ledger.finish_child(
                        context, identifier, payload, self._trace(state, payload)
                    )
        except (ValueError, ReviewError) as error:
            code = error.code if isinstance(error, ReviewError) else "ACTION_PROTOCOL_ERROR"
            if code in {
                "CALL_RESULT_UNKNOWN",
                "DEADLINE_EXCEEDED",
                "STALE_EXECUTION",
                "BUDGET_EXHAUSTED",
                "INTERRUPTED",
                "DATABASE_BUSY",
                "STORAGE_CAPACITY_EXCEEDED",
                "DEPENDENCY_UNAVAILABLE",
            }:
                raise
            payload = {
                "schema_version": "contract-review-child-result.v1",
                "status": "failed",
                "findings": [],
                "evidence_refs": [],
                "limitations": [code],
                "unresolved_gaps": ["子任务未取得合格结论。"],
            }
            return self.ledger.finish_child(
                context, identifier, payload, self._trace(state, payload), failed=True
            )

    @staticmethod
    def _trace(state, payload):
        reads, observations = state.evidence()
        published, observation_ids = [], set()
        for ref in payload["evidence_refs"]:
            if ref["kind"] == "source":
                append_unique(published, [ref["source_ref"]])
            elif ref["kind"] == "observation":
                observation_ids.add(ref["observation_id"])
        for finding in payload["findings"]:
            append_unique(published, finding["source_refs"])
            observation_ids.update(finding["observation_refs"])
        for identifier in observation_ids:
            append_unique(published, observations[identifier]["source_refs"])
        return {
            "read_refs": reads,
            "observations": list(observations.values()),
            "published_source_refs": published,
            "published_observation_ids": sorted(observation_ids),
        }

    def _validate_child(self, state, raw):
        result = ChildResult.model_validate(raw).model_dump(exclude_none=True)
        keyed(result["findings"], "id")
        reads, observations = state.evidence()
        visible = {**state.frozen, "adoption_records": state.rules}
        targets, rules = keyed(state.targets, "target_id"), keyed(state.rules, "adoption_id")
        validate_material_refs(
            result["evidence_refs"], visible, state.context["sources"], reads, observations
        )
        for finding in result["findings"]:
            for field, allowed in (
                ("target_ids", targets),
                ("rule_refs", rules),
                ("observation_refs", observations),
            ):
                unique(finding[field], field)
                require(set(finding[field]) <= set(allowed), "Child finding exceeds allowed scope")
            require(
                not finding["verification_evidence_refs"] and not finding["related_findings"],
                "Child cannot introduce ungranted external or historical evidence",
            )
            validate_source_refs(finding["source_refs"], state.context["sources"], reads)
            if finding["judgment_status"] in ("supported_deviation", "no_deviation"):
                require(
                    finding["source_refs"] or finding["observation_refs"],
                    "Child finding needs actual evidence",
                )
                for target_id in finding["target_ids"]:
                    supporting = [
                        rules[key]
                        for key in finding["rule_refs"]
                        if rules[key]["target_id"] == target_id
                        and rules[key]["disposition"] == "adopted"
                    ]
                    require(supporting, "Child positive finding needs adopted rule")
                    for rule in supporting:
                        require(
                            match_effective_scope(
                                rule["effective_scope_expression"], targets[target_id]
                            )
                            == "match",
                            "Child rule scope mismatch",
                        )
                        validate_rule_body(rule, state.context["sources"], reads)
        return result

    def _review(self, report):
        state, candidate = self.state, digest(report)
        data, entries = state.build("review", report=report, candidate_hash=candidate)
        call_id, result = self.worker.model_call(self.context, "review", data, entries)
        state.mark_projected(data, entries)
        try:
            verdict = ReviewResult.model_validate(strict_json(result["content"]))
            require(verdict.candidate_report_hash == candidate, "Fixed review candidate mismatch")
            fields = {
                "finding": "findings",
                "question": "questions",
                "work_item": "work_items",
                "acceptance": "acceptance_items",
            }
            reads, observations = state.evidence()
            for issue in verdict.issues:
                require(
                    issue.subject_id == ""
                    if issue.subject_kind == "report"
                    else issue.subject_id
                    in {item["id"] for item in report[fields[issue.subject_kind]]},
                    "Fixed review subject is invalid",
                )
                validate_material_refs(
                    [ref.model_dump() for ref in issue.evidence_refs],
                    state.frozen,
                    self.context["sources"],
                    reads,
                    observations,
                )
        except ValueError:
            self.ledger.record_result(
                self.context, call_id, result, accepted=False, reason="REVIEW_SCHEMA_INVALID"
            )
            raise ReviewError("REPORT_REVIEW_FAILED", "固定复核协议或引用非法。") from None
        self.ledger.record_result(
            self.context, call_id, result, accepted=True, reason="REVIEW_FORMAT_AND_SCOPE_VALID"
        )
        return verdict

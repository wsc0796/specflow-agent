"""Bounded targetless read loop; body visibility is checked against actual payloads."""

import re
import time
from copy import deepcopy

from specflow.contract_review.common import ReviewError, canonical, digest, identity
from specflow.contract_review.impact_schemas import IMPACT_ACTION
from specflow.contract_review.report_validation import validate_source_refs
from specflow.contract_review.snapshot_tools import SnapshotTools
from specflow.contract_review.sources import select_text, strict_json
from specflow.contract_review.tool_protocol import TOOL_ARGUMENTS, ToolResponse


class ImpactRunner:
    def __init__(self, worker, context):
        self.worker, self.context = worker, context
        self.ledger = worker.ledger.impact
        self.service = worker.service.impacts
        self.sources, self.frozen = context["sources"], context["frozen"]
        self.profile = self.frozen["execution_profile"]
        self.tools = SnapshotTools(self.sources, self.frozen["snapshot_id"])
        self.observations, self.seen, self.reads = {}, set(), []
        self.feedback = None
        self.last_operation, self.repeats = None, 0

    def material(self, ref):
        source = self.sources[ref["source_id"]]
        if digest(source["body"].encode()) != source["body_hash"]:
            raise ReviewError("SOURCE_INTEGRITY_FAILED", "密封正文已损坏。")
        body = select_text(source["body"], ref["selector"])
        return dict(
            source_ref=ref,
            body=body,
            body_hash=source["body_hash"],
            fragment_hash=digest(body.encode()),
            message_index=1,
            disposition="retained",
        )

    def build(self):
        materials = [
            self.material(value["source_ref"]) for value in self.frozen["authority_materials"]
        ]
        data = dict(
            change_request=self.frozen["change_request"],
            authority_materials=self.frozen["authority_materials"],
            confirmed_rules=self.frozen["confirmed_rules"],
            source_catalog=dict(items=[], omitted_source_count=len(self.sources)),
            available_tools=list(TOOL_ARGUMENTS),
            observations=[],
            cited_materials=[],
            omitted_observation_ids=list(self.observations),
        )
        if self.feedback:
            data["protocol_feedback"] = self.feedback

        def fits(value):
            return (
                len(self.profile["analysis_prompt"]) + len(canonical(value))
                <= self.profile["context_characters"]
            )

        if not fits(data):
            raise ReviewError("BUDGET_EXHAUSTED", "必要规则或反馈超过上下文上限。")
        for source in sorted(self.sources.values(), key=lambda value: value["path"]):
            item = {name: source[name] for name in ("source_id", "path", "roles", "body_hash")}
            item["line_count"] = len(source["body"].splitlines())
            trial = deepcopy(data)
            trial["source_catalog"]["items"].append(item)
            trial["source_catalog"]["omitted_source_count"] -= 1
            if not fits(trial):
                break
            data = trial
        for key, observation in reversed(list(self.observations.items())):
            if digest(observation["body"]) != observation["body_hash"]:
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "观察正文已损坏。")
            trial = deepcopy(data)
            trial["observations"].append(observation)
            trial["omitted_observation_ids"].remove(key)
            for ref in observation["source_refs"]:
                material = self.material(ref)
                if material not in trial["cited_materials"]:
                    trial["cited_materials"].append(material)
            if fits(trial):
                data = trial
        materials.extend(data["cited_materials"])
        materials.extend(
            dict(
                observation_id=value["observation_id"],
                body=value,
                body_hash=value["body_hash"],
                message_index=1,
                disposition="retained",
            )
            for value in data["observations"]
        )
        materials.extend(
            dict(observation_id=key, disposition="not_projected", reason="context_limit")
            for key in data["omitted_observation_ids"]
        )
        return data, materials

    def mark_projected(self, data, materials):
        for material in materials:
            if "source_ref" in material and material["source_ref"] not in self.reads:
                self.reads.append(material["source_ref"])
        self.seen.update(value["observation_id"] for value in data["observations"])

    def validate(self, raw):
        action = IMPACT_ACTION.validate_python(raw).model_dump(exclude_none=True)
        for ref in action["reason"]["evidence_refs"]:
            if ref["kind"] == "source":
                validate_source_refs([ref["source_ref"]], self.sources, self.reads)
            elif ref["observation_id"] not in self.seen:
                raise ValueError("Observation was not projected")
        if action["action"] == "tool_call":
            action["arguments"] = self.tools.validate(action["tool"], action["arguments"])
            return action
        keys, objects = set(), set()
        by_path = {value["path"]: value for value in self.sources.values()}
        for candidate in action["candidates"]:
            key = (
                candidate["source_path"],
                candidate.get("api_version"),
                canonical(candidate.get("endpoint")),
            )
            if candidate["local_key"] in keys or key in objects:
                raise ValueError("Duplicate candidate key or object")
            keys.add(candidate["local_key"])
            objects.add(key)
            source = by_path.get(candidate["source_path"])
            if source is None or candidate["artifact_role"] not in source["roles"]:
                raise ValueError("Candidate is outside the allowed source roles")
            validate_source_refs(candidate["source_refs"], self.sources, self.reads)
            if not any(ref["source_id"] == source["source_id"] for ref in candidate["source_refs"]):
                raise ValueError("Candidate object needs its own projected body")
            if not set(candidate["observation_refs"]) <= self.seen or len(
                set(candidate["observation_refs"])
            ) != len(candidate["observation_refs"]):
                raise ValueError("Candidate observation was not projected or duplicated")
            basis = [self.frozen["change_request"]]
            basis.extend(
                select_text(self.sources[ref["source_id"]]["body"], ref["selector"])
                for ref in candidate["source_refs"]
            )
            # Query echoes and catalog metadata are not factual identity evidence.
            for key in candidate["observation_refs"]:
                refs = self.observations[key]["source_refs"]
                validate_source_refs(refs, self.sources, self.reads)
                basis.extend(
                    select_text(self.sources[ref["source_id"]]["body"], ref["selector"])
                    for ref in refs
                )
            version = candidate.get("api_version")
            if version and not any(
                re.search(r"(?<![\w.-])" + re.escape(version) + r"(?![\w.-])", fragment)
                for fragment in basis
            ):
                raise ValueError(
                    "Version identity has no cited body or user-intent support; omit unknown"
                )
            endpoint = candidate.get("endpoint")
            if endpoint and not any(
                re.search(r"(?<!\w)" + re.escape(endpoint["method"]) + r"(?!\w)", fragment, re.I)
                and endpoint["path"] in re.findall(r"""(?<![^\s"'`<>])/[^\s"'`<>]+""", fragment)
                for fragment in basis
            ):
                raise ValueError(
                    "Endpoint identity has no cited body or user-intent support; omit unknown"
                )
            for check in candidate["suggested_checks"]:
                for selector in check["rule_selectors"]:
                    rule = by_path.get(selector["path"])
                    if rule is None or not set(rule["roles"]) & {"contract", "decision_reference"}:
                        raise ValueError("Suggested rule is not an allowed authority source")
                    validate_source_refs(
                        [dict(source_id=rule["source_id"], selector=selector["selector"])],
                        self.sources,
                        self.reads,
                    )
        return action

    def event(self, kind, payload):
        with self.service.store.transaction() as conn:
            self.ledger.fence(conn, self.context)
            self.service.event(conn, self.context["discovery_id"], kind, payload)

    def tool(self, action):
        payload = dict(tool=action["tool"], arguments=action["arguments"])
        call, instance = self.ledger.reserve_call(self.context, "tool", payload, [], kind="tool")
        result = self.worker.perform_io(
            self.context,
            call,
            instance,
            lambda: self.tools.execute(action["tool"], action["arguments"]),
            self.profile["tool_timeout_seconds"],
            kind="tool",
        )
        result = ToolResponse.model_validate(result).model_dump()
        for ref in result["source_refs"]:
            if not self.tools.permitted(ref["source_id"], ref["selector"]):
                raise ReviewError("ACTION_PERMISSION_DENIED", "工具返回了越界来源。")
        self.ledger.record_result(self.context, call, result, accepted=True, reason="tool_observed")
        observation = dict(
            observation_id=identity("iobs"),
            tool=action["tool"],
            arguments=action["arguments"],
            **result,
            body_hash=digest(result["body"]),
        )
        self.event("tool_observed", observation)
        self.observations[observation["observation_id"]] = observation
        signature = digest(dict(tool=action["tool"], arguments=action["arguments"], result=result))
        self.repeats = self.repeats + 1 if signature == self.last_operation else 1
        self.last_operation = signature
        if self.repeats >= 3:
            raise ReviewError("NO_PROGRESS", "相同工具与观察连续三次没有新增信息。")

    def run(self):
        failures = 0
        try:
            while True:
                data, materials = self.build()
                call, result = self.worker.model_call(self.context, "analysis", data, materials)
                self.mark_projected(data, materials)
                try:
                    raw = strict_json(result["content"])
                    self.event("action_proposed", dict(call_id=call, action=raw))
                    action = self.validate(raw)
                except (ValueError, ReviewError) as error:
                    self.ledger.record_result(
                        self.context, call, result, accepted=False, reason="ACTION_SCHEMA_INVALID"
                    )
                    failures += 1
                    if failures >= 2:
                        raise ReviewError(
                            "ACTION_PROTOCOL_ERROR", "一次纠错后发现动作仍非法。"
                        ) from error
                    self.feedback = dict(code="ACTION_SCHEMA_INVALID", message=str(error)[:2000])
                    continue
                self.ledger.record_result(
                    self.context, call, result, accepted=True, reason="action_accepted"
                )
                failures, self.feedback = 0, None
                if action["action"] == "tool_call":
                    self.tool(action)
                else:
                    candidates = [
                        dict(candidate_id=identity("candidate"), **candidate)
                        for candidate in action["candidates"]
                    ]
                    self.ledger.finish(self.context, candidates, action["unresolved"])
                    return
        except ReviewError as error:
            self.ledger.fail(
                self.context, error.code, time.monotonic() - self.context["started_monotonic"]
            )

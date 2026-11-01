"""Actual per-request material projection with mandatory rules and bounded observations."""

from copy import deepcopy

from specflow.contract_review.common import ReviewError, canonical, digest
from specflow.contract_review.inputs import project_rule_material
from specflow.contract_review.sources import select_text
from specflow.contract_review.tool_protocol import CAPABILITIES, CAPABILITY_PURPOSES


def append_unique(values, incoming):
    seen = {canonical(item) for item in values}
    for item in incoming:
        if canonical(item) not in seen:
            seen.add(canonical(item))
            values.append(item)


class RunState:
    def __init__(
        self,
        context,
        tools,
        *,
        targets=None,
        rule_ids=None,
        initial_observations=None,
        objective=None,
    ):
        self.context, self.tools = context, tools
        self.frozen = context["frozen"]
        self.targets = targets if targets is not None else self.frozen["target_manifest"]
        self.rules = [
            item
            for item in self.frozen["adoption_records"]
            if rule_ids is None or item["adoption_id"] in rule_ids
        ]
        self.observations = dict(initial_observations or {})
        self.read_refs, self.seen_observations = [], set()
        self.children, self.reviews = {}, {}
        self.feedback = {}
        self.objective = objective
        self.last_operation, self.repeats = None, 0

    def _source_material(self, ref):
        source = self.context["sources"][ref["source_id"]]
        if digest(source["body"].encode("utf-8")) != source["body_hash"]:
            raise ReviewError("SOURCE_INTEGRITY_FAILED", "必要来源原文完整性校验失败。")
        body = select_text(source["body"], ref["selector"])
        return {
            "source_ref": ref,
            "body": body,
            "body_hash": source["body_hash"],
            "fragment_hash": digest(body.encode()),
            "message_index": 1,
            "disposition": "retained",
        }

    @staticmethod
    def observation_view(observation):
        value = {
            key: observation[key]
            for key in (
                "observation_id",
                "origin",
                "source_refs",
                "result_kind",
                "body",
                "body_hash",
                "completeness",
                "truncation",
                "error",
            )
        }
        for key in ("tool", "arguments"):
            if key in observation:
                value[key] = observation[key]
        return value

    def build(self, role, *, report=None, candidate_hash=None):
        profile = self.frozen["execution_profile"]
        entries, rule_materials = [], []
        for rule in self.rules:
            if rule["disposition"] == "adopted" or self.context.get("child_id"):
                if rule.get("origin", {}).get("kind") == "project_decision":
                    material = project_rule_material(rule)
                    rule_materials.append(material)
                    entries.append(material)
                    continue
                ref = rule["body_ref"]
                if not any(item.get("source_ref") == ref for item in rule_materials):
                    material = self._source_material(ref)
                    if digest(material["body"].encode("utf-8")) != rule["body_hash"]:
                        raise ReviewError("SOURCE_INTEGRITY_FAILED", "冻结规则片段已变化。")
                    rule_materials.append(material)
                    entries.append(material)
        catalog = []
        for identifier in sorted(
            self.tools.grants, key=lambda key: self.context["sources"][key]["path"]
        ):
            source = self.context["sources"][identifier]
            catalog.append(
                {key: source[key] for key in ("source_id", "path", "roles", "body_hash")}
            )
            catalog[-1].update(
                line_count=len(source["body"].splitlines()),
                allowed_selectors=self.tools.grants[identifier],
            )
        target_ids = {item["target_id"] for item in self.targets}
        data = {
            "request": self.objective or self.frozen["original_request"]["request"],
            "targets": self.targets,
            "check_manifest": [
                item for item in self.frozen["check_manifest"] if item["target_id"] in target_ids
            ],
            "adoption_records": self.rules,
            "rule_materials": rule_materials,
            "resolutions": self.frozen["resolutions"],
            "review_directives": self.frozen.get("review_directives", []),
            "source_catalog": {"items": catalog[:20], "total": len(catalog)},
            "available_tools": sorted(self.tools.allowed_tools),
            "observations": [],
            "omitted_observation_ids": list(self.observations),
            **self.feedback,
        }
        if not self.context.get("child_id") and profile["options"]["delegate"]:
            data["available_capabilities"] = [
                {
                    "capability_id": name,
                    "description": CAPABILITY_PURPOSES[name],
                    "allowed_tools": list(tools),
                }
                for name, tools in CAPABILITIES.items()
            ]
        if self.children:
            data["child_results"] = [
                {"child_result_ref": key, "result": item["result"]}
                for key, item in self.children.items()
            ]
            data["child_result_reviews"] = list(self.reviews.values())
        if self.context.get("child_id"):
            data["capability_id"] = self.context["capability_id"]
            data["capability_description"] = CAPABILITY_PURPOSES[self.context["capability_id"]]
            data["expected_evidence"] = self.context["expected_evidence"]
        elif self.context["verification_evidence"]:
            data["verification_evidence"] = self.context["verification_evidence"]
            data["verification_evidence_adoptions"] = self.frozen["verification_evidence_adoptions"]
            entries.extend(
                {
                    "evidence_id": item["evidence_id"],
                    "body": item,
                    "body_hash": item["body_hash"],
                    "message_index": 1,
                    "disposition": "retained",
                }
                for item in self.context["verification_evidence"]
            )
        required_observations = set()
        available_observations = dict(self.observations)
        if report is not None:
            data.update(candidate_report=report, candidate_report_hash=candidate_hash)
            refs = []
            for collection in (
                "coverage",
                "check_results",
                "findings",
                "work_items",
                "acceptance_items",
            ):
                for item in report[collection]:
                    append_unique(refs, item.get("source_refs", []))
                    required_observations.update(item.get("observation_refs", []))
            for question in report["questions"]:
                for ref in question["evidence_refs"]:
                    if ref["kind"] == "source":
                        append_unique(refs, [ref["source_ref"]])
                    elif ref["kind"] == "observation":
                        required_observations.add(ref["observation_id"])
            data["cited_materials"] = [self._source_material(ref) for ref in refs]
            entries.extend(data["cited_materials"])
            for child in self.children.values():
                for observation in child["evidence_trace"].get("observations", []):
                    if observation["observation_id"] in required_observations:
                        available_observations.setdefault(
                            observation["observation_id"], observation
                        )
        for identifier in required_observations:
            if identifier not in available_observations:
                raise ReviewError("ACTION_SCHEMA_INVALID", "候选报告引用了不可取得的观察。")
            data["observations"].append(self.observation_view(available_observations[identifier]))
        data["omitted_observation_ids"] = [
            key for key in self.observations if key not in required_observations
        ]
        prompt_size = len(profile[role + "_prompt"])

        def fits(value):
            return prompt_size + len(canonical(value)) <= profile["context_characters"]

        if not fits(data):
            raise ReviewError("BUDGET_EXHAUSTED", "必保留正文超过冻结上下文上限。")
        for identifier in reversed(list(self.observations)):
            if identifier in required_observations:
                continue
            trial = {
                **data,
                "observations": [
                    *data["observations"],
                    self.observation_view(self.observations[identifier]),
                ],
                "omitted_observation_ids": [
                    key for key in data["omitted_observation_ids"] if key != identifier
                ],
            }
            if fits(trial):
                data = trial
        for observation in data["observations"]:
            entries.append(
                {
                    "observation_id": observation["observation_id"],
                    "body": observation,
                    "body_hash": observation["body_hash"],
                    "message_index": 1,
                    "disposition": "retained",
                }
            )
            entries.extend(self._source_material(ref) for ref in observation["source_refs"])
        entries.extend(
            {"observation_id": key, "disposition": "not_projected", "reason": "context_limit"}
            for key in data["omitted_observation_ids"]
        )
        return data, entries

    def mark_projected(self, data, entries):
        append_unique(
            self.read_refs, [item["source_ref"] for item in entries if "source_ref" in item]
        )
        self.seen_observations.update(item["observation_id"] for item in data["observations"])

    def evidence(self, reviews=None):
        reads = deepcopy(self.read_refs)
        observations = {
            key: self.observations[key]
            for key in self.seen_observations
            if key in self.observations
        }
        for reference, review in (self.reviews if reviews is None else reviews).items():
            if (
                review["disposition"] != "rejected"
                and self.children[reference]["result"]["status"] != "failed"
            ):
                trace = self.children[reference]["evidence_trace"]
                append_unique(reads, trace["published_source_refs"])
                observations.update(
                    {
                        item["observation_id"]: item
                        for item in trace["observations"]
                        if item["observation_id"] in trace["published_observation_ids"]
                    }
                )
        return reads, observations

    def operation_key(self, action):
        semantic = sorted(
            {
                digest(
                    {
                        key: item[key]
                        for key in (
                            "body_hash",
                            "result_kind",
                            "error",
                            "completeness",
                            "truncation",
                        )
                    }
                )
                for item in self.observations.values()
            }
        )
        return digest(
            {
                "tool": action["tool"],
                "arguments": action["arguments"],
                "gap": action["reason"]["gap"],
                "targets": self.targets,
                "materials": semantic,
            }
        )

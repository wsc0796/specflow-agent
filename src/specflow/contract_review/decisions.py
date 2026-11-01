"""Explicit project decisions, immutable version views and precise removal slices."""

import base64
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator
from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.inputs import match_effective_scope, match_scope
from specflow.contract_review.protocol import SourceRefs
from specflow.contract_review.schemas import ID, Scope, StrictModel, Text
from specflow.contract_review.sources import select_text

RulesetVersion = Annotated[int, Field(ge=0, le=2**63 - 1)]


class DeclaredProvenance(StrictModel):
    kind: Literal["declared"]
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    reference_text: Text | None = None


class ReviewProvenance(StrictModel):
    kind: Literal["review_record"]
    review_id: ID
    report_revision_id: ID
    resolution_ids: Annotated[list[ID], Field(max_length=20)]
    source_refs: SourceRefs
    claimed_approver: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @model_validator(mode="after")
    def unique_refs(self):
        if len(set(self.resolution_ids)) != len(self.resolution_ids) or len(
            {canonical(ref.model_dump()) for ref in self.source_refs}
        ) != len(self.source_refs):
            raise ValueError("Duplicate provenance reference")
        return self


Provenance = Annotated[DeclaredProvenance | ReviewProvenance, Field(discriminator="kind")]


class EffectSlice(StrictModel):
    project_decision_id: ID
    effective_scope: Scope


class DecisionBase(StrictModel):
    expected_ruleset_version: RulesetVersion
    provenance: Provenance
    actor_label: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class ConfirmDecision(DecisionBase):
    operation: Literal["confirm"]
    text: Annotated[str, Field(min_length=1, max_length=16000)]
    scope: Scope


class SupersedeDecision(DecisionBase):
    operation: Literal["supersede"]
    text: Annotated[str, Field(min_length=1, max_length=16000)]
    scope: Scope
    supersedes: Annotated[list[EffectSlice], Field(min_length=1, max_length=20)]


class WithdrawDecision(DecisionBase):
    operation: Literal["withdraw"]
    withdrawals: Annotated[list[EffectSlice], Field(min_length=1, max_length=20)]
    reason: Text


DecisionRequest = Annotated[
    ConfirmDecision | SupersedeDecision | WithdrawDecision, Field(discriminator="operation")
]


def scope_subset(part, whole):
    """Omitted dimensions are unrestricted, never an implicit finite subset."""
    return all(
        dimension in part
        and {canonical(item) for item in part[dimension]} <= {canonical(item) for item in values}
        for dimension, values in whole.items()
    )


def scopes_intersect(first, second):
    return all(
        {canonical(item) for item in first[key]} & {canonical(item) for item in second[key]}
        for key in first.keys() & second.keys()
    )


class DecisionService:
    def __init__(self, service):
        self.service, self.store = service, service.store

    @property
    def enabled(self):
        return any(
            profile["options"]["project_memory"] for profile in self.service.profiles.values()
        )

    def require_enabled(self):
        if not self.enabled:
            raise ReviewError("OPTION_NOT_ENABLED", "项目记忆尚未启用。")

    def require_project(self, conn, project_id):
        if self.store.row(conn, "SELECT id FROM projects WHERE id=:id", id=project_id) is None:
            raise ReviewError("PROJECT_NOT_FOUND", "项目不存在。", 404)

    def current_version(self, conn, project_id):
        row = self.store.row(
            conn,
            "SELECT version FROM project_contract_rulesets WHERE project_id=:id",
            id=project_id,
        )
        return row["version"] if row else 0

    def check_usage(self, conn, project_id, usage, profile, *, require_current=True):
        if usage["mode"] == "none":
            return None
        self.require_enabled()
        if not profile["options"]["project_memory"]:
            raise ReviewError("OPTION_NOT_ENABLED", "所选 profile 未启用项目记忆。")
        version = usage["expected_ruleset_version"]
        current = self.current_version(conn, project_id)
        if (require_current and version != current) or version > current:
            raise ReviewError("RULESET_VERSION_CONFLICT", "项目规则集版本已变化。")
        return version

    def records(self, conn, project_id, version):
        return [
            json.loads(row[0])
            for row in conn.execute(
                text(
                    "SELECT body FROM project_contract_decisions WHERE project_id=:project "
                    "AND introduced_version<=:version ORDER BY introduced_version"
                ),
                {"project": project_id, "version": version},
            )
        ]

    @staticmethod
    def views(records):
        removals = {}
        for record in records:
            for effect in record["effect_relations"]:
                removals.setdefault(effect["project_decision_id"], []).append(effect)
        values = []
        for record in records:
            value = {**record}
            if record["operation"] != "withdraw":
                effects = removals.get(record["project_decision_id"], [])
                value["effective_scope_expression"] = {
                    "base_scope": record["scope"],
                    "removal_slices": [effect["effective_scope"] for effect in effects],
                }
                value["removal_relations"] = effects
            values.append(value)
        return values

    def _provenance(self, conn, project_id, provenance):
        if provenance["kind"] == "declared":
            return
        review_id, report_id = provenance["review_id"], provenance["report_revision_id"]
        report = self.store.row(
            conn,
            "SELECT rr.input_id FROM contract_review_reports rr JOIN contract_reviews cr "
            "ON cr.id=rr.review_id WHERE rr.id=:report AND cr.id=:review "
            "AND cr.project_id=:project",
            report=report_id,
            review=review_id,
            project=project_id,
        )
        if report is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "来源报告不属于本项目。", 404)
        for resolution_id in provenance["resolution_ids"]:
            row = self.store.row(
                conn,
                "SELECT id FROM contract_review_resolutions WHERE id=:id AND review_id=:review "
                "AND report_id=:report AND input_id=:input",
                id=resolution_id,
                review=review_id,
                report=report_id,
                input=report["input_id"],
            )
            if row is None:
                raise ReviewError("RESOURCE_NOT_FOUND", "来源答案不属于指定报告。", 404)
        for ref in provenance["source_refs"]:
            blob = self.store.row(
                conn,
                "SELECT b.raw_bytes,b.body_hash FROM contract_review_source_blobs b "
                "JOIN contract_review_inputs i ON i.snapshot_id=b.snapshot_id "
                "WHERE b.id=:id AND i.id=:input AND i.review_id=:review",
                id=ref["source_id"],
                input=report["input_id"],
                review=review_id,
            )
            if blob is None:
                raise ReviewError("RESOURCE_NOT_FOUND", "来源片段不属于指定报告快照。", 404)
            if digest(blob["raw_bytes"]) != blob["body_hash"]:
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "来源原文字节损坏。")
            select_text(blob["raw_bytes"].decode("utf-8"), ref["selector"])

    def publish(self, project_id, request, key, original_request=None):
        self.require_enabled()
        payload = request.model_dump(exclude_none=True)
        payload_hash, key_hash = digest(payload), self.service.key_hash(key)
        scope = "project:" + project_id + ":contract-decisions"
        with self.store.transaction() as conn:
            self.require_project(conn, project_id)
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            current = self.current_version(conn, project_id)
            if current != request.expected_ruleset_version or current == 2**63 - 1:
                raise ReviewError("RULESET_VERSION_CONFLICT", "项目规则集版本已变化。")
            self._provenance(conn, project_id, payload["provenance"])
            records = self.views(self.records(conn, project_id, current))
            old = {item["project_decision_id"]: item for item in records}
            requested = payload.get("supersedes", payload.get("withdrawals", []))
            # Ownership is checked before effect validity, including mixed batches.
            if any(item["project_decision_id"] not in old for item in requested):
                raise ReviewError("RESOURCE_NOT_FOUND", "被引用决定不属于本项目。", 404)
            decision_id, version = identity("pd"), current + 1
            effects, pending = [], {}
            for item in requested:
                identifier, part = item["project_decision_id"], item["effective_scope"]
                base = old[identifier]
                removed = pending.setdefault(
                    identifier,
                    list(base.get("effective_scope_expression", {}).get("removal_slices", [])),
                )
                if (
                    base["operation"] == "withdraw"
                    or not scope_subset(part, base["scope"])
                    or ("scope" in payload and not scope_subset(part, payload["scope"]))
                    or any(scopes_intersect(part, removal) for removal in removed)
                ):
                    raise ReviewError("DECISION_SCOPE_CONFLICT", "生效切片越界或含已移除范围。")
                removed.append(part)
                effects.append(
                    {
                        "effect_relation_id": identity("effect"),
                        "record_id": decision_id,
                        "project_decision_id": identifier,
                        "operation": request.operation,
                        "effective_scope": part,
                        "introduced_ruleset_version": version,
                    }
                )
            record = {
                "project_decision_id": decision_id,
                "project_id": project_id,
                "introduced_ruleset_version": version,
                **payload,
                "effect_relations": effects,
                "actor_subject": "shared-service",
                "created_at": now(),
                "original_request": original_request if original_request is not None else payload,
            }
            self.store.reserve_records(conn, len(canonical(record).encode("utf-8")))
            self.store.execute(
                conn,
                "INSERT INTO project_contract_rulesets VALUES (:id,0) "
                "ON CONFLICT(project_id) DO NOTHING",
                id=project_id,
            )
            changed = self.store.execute(
                conn,
                "UPDATE project_contract_rulesets SET version=:next "
                "WHERE project_id=:id AND version=:old",
                id=project_id,
                next=version,
                old=current,
            )
            if changed.rowcount != 1:
                raise ReviewError("RULESET_VERSION_CONFLICT", "项目规则集版本已变化。")
            self.store.execute(
                conn,
                "INSERT INTO project_contract_decisions VALUES (:id,:project,:version,:body,:at)",
                id=decision_id,
                project=project_id,
                version=version,
                body=canonical(record),
                at=record["created_at"],
            )
            response = {**record, "ruleset_version": version}
            return self.service.remember(conn, scope, key_hash, payload_hash, 201, response)

    def list(self, project_id, ruleset_version=None, cursor=None, limit=20):
        self.require_enabled()
        with self.store.read() as conn:
            self.require_project(conn, project_id)
            current = self.current_version(conn, project_id)
            version, after = ruleset_version, None
            if cursor:
                try:
                    data = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
                    if (
                        set(data) != {"project", "version", "after"}
                        or data["project"] != project_id
                        or type(data["version"]) is not int
                        or not 0 <= data["version"] <= current
                        or (version is not None and version != data["version"])
                        or not isinstance(data["after"], list)
                        or len(data["after"]) != 2
                        or any(
                            type(item) is not str or not 1 <= len(item) <= 64
                            for item in data["after"]
                        )
                    ):
                        raise ValueError("Cursor scope mismatch")
                    version, after = data["version"], data["after"]
                except (ValueError, TypeError, KeyError, UnicodeError) as error:
                    raise ReviewError("INVALID_CURSOR", "游标无效或版本不匹配。", 422) from error
            version = current if version is None else version
            if version > current:
                raise ReviewError("RULESET_VERSION_CONFLICT", "规则集版本尚不存在。")
            values = [
                item
                for item in self.views(self.records(conn, project_id, version))
                if after is None or (item["created_at"], item["project_decision_id"]) > tuple(after)
            ]
            values.sort(key=lambda item: (item["created_at"], item["project_decision_id"]))
            page = values[:limit]
            next_cursor = (
                base64.urlsafe_b64encode(
                    canonical(
                        {
                            "project": project_id,
                            "version": version,
                            "after": [page[-1]["created_at"], page[-1]["project_decision_id"]],
                        }
                    ).encode("utf-8")
                ).decode("ascii")
                if len(values) > limit
                else None
            )
            return {"ruleset_version": version, "items": page, "next_cursor": next_cursor}

    def adopt(self, conn, project_id, frozen, usage, *, require_current=True):
        version = self.check_usage(
            conn, project_id, usage, frozen["execution_profile"], require_current=require_current
        )
        frozen["adopted_ruleset_version"] = version
        if version is None:
            return
        for decision in self.views(self.records(conn, project_id, version)):
            if decision["operation"] == "withdraw":
                continue
            expression, relations = (
                decision["effective_scope_expression"],
                decision["removal_relations"],
            )
            for target in frozen["target_manifest"]:
                outcome = match_effective_scope(expression, target)
                historical = target["api_version"] not in decision["scope"]["api_versions"]
                matched_removals = [
                    effect
                    for effect in relations
                    if match_scope(effect["effective_scope"], target) == "match"
                ]
                code = (
                    "VERSION_OUT_OF_SCOPE"
                    if historical
                    else "SCOPE_UNRESOLVED"
                    if outcome == "scope_unresolved"
                    else "WITHDRAWN_SLICE"
                    if any(effect["operation"] == "withdraw" for effect in matched_removals)
                    else "SUPERSEDED_SLICE"
                    if matched_removals
                    else "EXACT_SCOPE_MATCH"
                    if outcome == "match"
                    else "TARGET_OUT_OF_SCOPE"
                )
                frozen["adoption_records"].append(
                    {
                        "adoption_id": identity("adopt"),
                        "origin": {
                            "kind": "project_decision",
                            "project_decision_id": decision["project_decision_id"],
                            "introduced_ruleset_version": decision["introduced_ruleset_version"],
                        },
                        "input_revision_id": frozen["input_revision_id"],
                        "snapshot_id": frozen["snapshot_id"],
                        "commit_sha": frozen["commit_sha"],
                        "adopted_ruleset_version": version,
                        "provenance": decision["provenance"],
                        "actor_subject": decision["actor_subject"],
                        "body_ref": {"project_decision_id": decision["project_decision_id"]},
                        "body": decision["text"],
                        "body_hash": digest(decision["text"].encode("utf-8")),
                        "declared_scope": decision["scope"],
                        "effective_scope_expression": expression,
                        "target_id": target["target_id"],
                        "matched_target": target,
                        "disposition": "adopted"
                        if outcome == "match"
                        else "historical_only"
                        if historical
                        else "excluded",
                        "reason_code": code,
                        "reason_text": "同一目标按冻结规则集及生效切片计算，缺维度不视为匹配。",
                        "effect_relation_refs": [
                            effect["effect_relation_id"] for effect in relations
                        ],
                    }
                )

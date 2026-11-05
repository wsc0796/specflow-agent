"""Append-only external claims and frozen, per-target adoption into later inputs."""

import base64
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.protocol import RelatedFinding
from specflow.contract_review.schemas import ID, StrictModel, Text

STATUS = "provided_not_independently_verified"


class VerificationImport(StrictModel):
    expected_version: Annotated[int, Field(ge=1, le=2**63 - 1)]
    input_revision_id: ID
    report_revision_id: ID
    finding_ids: Annotated[list[ID], Field(min_length=1, max_length=100)]
    kind: Literal["external_controlled_execution"]
    environment: Text
    source_commit_sha: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
    procedure: Annotated[str, Field(min_length=1, max_length=8000)]
    observed_result: Annotated[str, Field(min_length=1, max_length=8000)]
    evidence_text: Annotated[str, Field(min_length=1, max_length=256 * 1024)]
    related_findings: Annotated[list[RelatedFinding], Field(max_length=100)] = Field(
        default_factory=list
    )
    actor_label: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    limitations: Annotated[list[Text], Field(max_length=20)] = Field(default_factory=list)

    @field_validator("environment", "procedure", "observed_result", "evidence_text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Evidence fields must contain text")
        return value

    @field_validator("evidence_text")
    @classmethod
    def bounded_bytes(cls, value):
        if len(value.encode("utf-8")) > 256 * 1024:
            raise ValueError("Evidence exceeds 256 KiB UTF-8")
        return value

    @model_validator(mode="after")
    def unique_references(self):
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("Duplicate finding reference")
        refs = [(item.report_revision_id, item.finding_id) for item in self.related_findings]
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate historical reference")
        return self


def target_relation(original, current):
    """Known mismatches dominate missing dimensions; missing is never false."""
    if original["api_version"] != current["api_version"]:
        return "different"
    missing = False
    for key in ("endpoint", "source_path"):
        if key in original and key in current:
            if original[key] != current[key]:
                return "different"
        elif (key in original) != (key in current):
            missing = True
    return "unresolved" if missing else "same"


def purpose_basis(frozen, target_id):
    target = next(item for item in frozen["target_manifest"] if item["target_id"] == target_id)

    def target_key(item):
        endpoint = item.get("endpoint")
        return (
            item["api_version"],
            (endpoint["method"].upper(), endpoint["path"]) if endpoint else None,
            item.get("source_path"),
        )

    original_target = next(
        (
            item
            for item in frozen["original_request"].get("targets", [])
            if target_key(item) == target_key(target)
        ),
        None,
    )
    if original_target is None:
        return None
    selectors = {
        item["key"]: sorted(item.get("rule_selectors", []), key=canonical)
        for item in original_target["checks"]
    }
    rules = [
        {
            **{
                key: rule.get(key)
                for key in ("body_hash", "disposition", "effective_scope_expression")
            },
            "purpose": rule.get("provenance", {}).get("purpose"),
        }
        for rule in frozen["adoption_records"]
        if rule["target_id"] == target_id
    ]
    checks = [
        {
            "key": item["key"],
            "behavior": item["behavior"],
            "rule_selectors": selectors.get(item["key"]),
        }
        for item in frozen["check_manifest"]
        if item["target_id"] == target_id
    ]
    return digest(
        {
            "rules": sorted(rules, key=canonical),
            "checks": sorted(checks, key=canonical),
            "request": frozen["original_request"]["request"],
            "resolutions": frozen.get("resolutions", []),
            "review_directives": frozen.get("review_directives", []),
        }
    )


def applicability(evidence, original, report, current):
    finding_ids = set(evidence["finding_ids"])
    target_ids = sorted(
        {
            target_id
            for finding in report["payload"]["findings"]
            if finding["id"] in finding_ids
            for target_id in finding["target_ids"]
        }
    )
    old_targets = {item["target_id"]: item for item in original["target_manifest"]}
    target_checks, comparisons = [], []
    for target in current["target_manifest"]:
        relations = [
            (identifier, target_relation(old_targets[identifier], target))
            for identifier in target_ids
        ]
        equal = [identifier for identifier, relation in relations if relation == "same"]
        current_basis = purpose_basis(current, target["target_id"])
        old_basis = {identifier: purpose_basis(original, identifier) for identifier in equal}
        if evidence["source_commit_sha"] != current["commit_sha"]:
            state, code, reason = "inapplicable", "BASELINE_MISMATCH", "源码提交不同。"
        elif current_basis is not None and any(
            value == current_basis for value in old_basis.values()
        ):
            state, code, reason = (
                "applicable",
                "SAME_BASELINE_AND_TARGET",
                "源码、目标与规则用途条件一致。",
            )
        elif relations and all(relation == "different" for _, relation in relations):
            state, code, reason = "inapplicable", "TARGET_MISMATCH", "该记录对应其他明确目标。"
        else:
            state, code, reason = (
                "unresolved",
                "MISSING_REQUIRED_CONTEXT",
                "缺少目标维度，或规则用途条件已变化。",
            )
        target_checks.append(
            {
                "target_id": target["target_id"],
                "origin_target_ids": target_ids,
                "applicability": state,
                "reason_code": code,
                "reason_text": reason,
            }
        )
        comparisons.append(
            {
                "target_id": target["target_id"],
                "current_target": target,
                "origin_target_ids": target_ids,
                "relations": relations,
                "current_purpose_fingerprint": current_basis,
                "origin_purpose_fingerprints": old_basis,
            }
        )
    return target_checks, {
        "origin_snapshot_id": original["snapshot_id"],
        "adopting_snapshot_id": current["snapshot_id"],
        "origin_commit_sha": original["commit_sha"],
        "adopting_commit_sha": current["commit_sha"],
        "origin_targets": [old_targets[item] for item in target_ids],
        "comparisons": comparisons,
        "evidence_body_hash": evidence["body_hash"],
        "checker_version": "verification-applicability.v1",
        "checked_at": now(),
    }


class VerificationService:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def input(self, conn, review_id, input_id):
        row = self.store.row(
            conn,
            "SELECT body FROM contract_review_inputs WHERE id=:id AND review_id=:review",
            id=input_id,
            review=review_id,
        )
        if row is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "输入不属于本审查。", 404)
        return json.loads(row["body"])

    def report(self, conn, review_id, report_id):
        row = self.store.row(
            conn,
            "SELECT body FROM contract_review_reports WHERE id=:id AND review_id=:review",
            id=report_id,
            review=review_id,
        )
        if row is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "报告不属于本审查。", 404)
        return json.loads(row["body"])

    def record(self, conn, review_id, evidence_id):
        row = self.store.row(
            conn,
            "SELECT body FROM contract_review_verification_evidence "
            "WHERE id=:id AND review_id=:review",
            id=evidence_id,
            review=review_id,
        )
        if row is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "核验记录不属于本审查。", 404)
        return json.loads(row["body"])

    def import_evidence(self, review_id, request, key):
        data = request.model_dump(exclude_none=True)
        key_hash, payload_hash = self.service.key_hash(key), digest(data)
        scope = "service:verification-import:" + review_id
        with self.store.transaction() as conn:
            prior = self.service.replay(conn, scope, key_hash, payload_hash)
            if prior:
                return prior
            review = self.service.require_review(conn, review_id)
            original = self.input(conn, review_id, request.input_revision_id)
            report = self.report(conn, review_id, request.report_revision_id)
            findings = {item["id"] for item in report["payload"]["findings"]}
            if (
                report["input_revision_id"] != request.input_revision_id
                or not set(request.finding_ids) <= findings
            ):
                raise ReviewError("RESOURCE_NOT_FOUND", "报告、输入或发现的关联不匹配。", 404)
            for related in request.related_findings:
                previous = self.report(conn, review_id, related.report_revision_id)
                if related.finding_id not in {
                    item["id"] for item in previous["payload"]["findings"]
                }:
                    raise ReviewError("RESOURCE_NOT_FOUND", "历史发现不存在。", 404)
            if request.expected_version != review["version"]:
                raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
            if (
                request.input_revision_id != review["current_input_id"]
                or request.report_revision_id != review["current_report_id"]
            ):
                raise ReviewError("VERIFICATION_TARGET_NOT_CURRENT", "核验必须绑定当前输入与报告。")
            if request.source_commit_sha != original["commit_sha"]:
                raise ReviewError("VERIFICATION_BASELINE_MISMATCH", "核验源码提交与报告基线不符。")
            if review["status"] in ("queued", "running"):
                raise ReviewError("REVIEW_BUSY", "当前审查仍在执行。")
            evidence_id, timestamp = identity("ev"), now()
            limitations = list(request.limitations)
            if len(limitations) < 20:
                limitations.append("提供者提交的记录尚未经过独立核验。")
            evidence = {
                "evidence_id": evidence_id,
                "review_id": review_id,
                **{
                    name: value
                    for name, value in data.items()
                    if name not in ("expected_version", "actor_label", "limitations")
                },
                "provider": {"actor_subject": "shared-service", "actor_label": request.actor_label},
                "status": STATUS,
                "limitations": limitations,
                "created_at": timestamp,
                "body_hash": digest(request.evidence_text.encode("utf-8")),
            }
            body = canonical(evidence)
            self.store.reserve_records(conn, len(body.encode("utf-8")))
            updated = self.store.execute(
                conn,
                "UPDATE contract_reviews SET version=version+1,updated_at=:at "
                "WHERE id=:id AND version=:expected",
                id=review_id,
                expected=request.expected_version,
                at=timestamp,
            )
            if updated.rowcount != 1:
                raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
            self.store.execute(
                conn,
                "INSERT INTO contract_review_verification_evidence VALUES "
                "(:id,:review,:input,:report,:body,:at)",
                id=evidence_id,
                review=review_id,
                input=request.input_revision_id,
                report=request.report_revision_id,
                body=body,
                at=timestamp,
            )
            response = {
                "evidence_id": evidence_id,
                "review_id": review_id,
                "version": request.expected_version + 1,
                "status": STATUS,
                "limitations": limitations,
            }
            self.store.event(
                conn,
                review_id,
                request.input_revision_id,
                None,
                "verification_evidence_imported",
                response,
            )
            return self.service.remember(conn, scope, key_hash, payload_hash, 201, response)

    def adopt(self, conn, review_id, frozen, evidence_ids):
        if len(evidence_ids) > 100 or len(evidence_ids) != len(set(evidence_ids)):
            raise ReviewError("INPUT_SCOPE_CONFLICT", "核验证据选择重复或过多。")
        bindings = []
        for evidence_id in evidence_ids:
            evidence = self.record(conn, review_id, evidence_id)
            if digest(evidence["evidence_text"].encode("utf-8")) != evidence["body_hash"]:
                raise ReviewError("INTERNAL_ERROR", "核验原文完整性校验失败。", 500)
            original = self.input(conn, review_id, evidence["input_revision_id"])
            report = self.report(conn, review_id, evidence["report_revision_id"])
            checks, basis = applicability(evidence, original, report, frozen)
            bindings.append(
                {
                    "verification_adoption_id": identity("ev_adopt"),
                    "evidence_id": evidence_id,
                    "adopting_input_revision_id": frozen["input_revision_id"],
                    "origin_input_revision_id": evidence["input_revision_id"],
                    "origin_report_revision_id": evidence["report_revision_id"],
                    "target_checks": checks,
                    "check_basis": basis,
                }
            )
        return bindings

    @staticmethod
    def view(record, current):
        adoption = next(
            (
                item
                for item in current["verification_evidence_adoptions"]
                if item["evidence_id"] == record["evidence_id"]
            ),
            None,
        )
        checks = adoption["target_checks"] if adoption else None
        states = {item["applicability"] for item in checks} if checks else set()
        summary = True if "applicable" in states else False if states == {"inapplicable"} else None
        return {
            **record,
            "origin": {
                key: record[key]
                for key in (
                    "review_id",
                    "input_revision_id",
                    "report_revision_id",
                    "finding_ids",
                    "source_commit_sha",
                )
            },
            "current_adoption": (
                {
                    key: adoption[key]
                    for key in ("verification_adoption_id", "adopting_input_revision_id")
                }
                if adoption
                else None
            ),
            "current_applicability": checks,
            "applicable_to_current_input": summary,
        }

    def get(self, review_id, evidence_id):
        with self.store.read() as conn:
            review = self.service.require_review(conn, review_id)
            current = self.input(conn, review_id, review["current_input_id"])
            return self.view(self.record(conn, review_id, evidence_id), current)

    def list(self, review_id, input_id=None, report_id=None, cursor=None, limit=20):
        filters = {"review": review_id, "input": input_id, "report": report_id}
        after_time, after_id = "", ""
        if cursor:
            try:
                value = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
                if (
                    set(value) != {"filters", "at", "id"}
                    or value["filters"] != filters
                    or not isinstance(value["at"], str)
                    or not isinstance(value["id"], str)
                ):
                    raise ValueError("Cursor mismatch")
                after_time, after_id = value["at"], value["id"]
            except (ValueError, TypeError, KeyError, UnicodeError) as error:
                raise ReviewError("INVALID_CURSOR", "游标无效或过滤条件已变化。", 422) from error
        with self.store.read() as conn:
            review = self.service.require_review(conn, review_id)
            current = self.input(conn, review_id, review["current_input_id"])
            if input_id:
                self.input(conn, review_id, input_id)
            if report_id:
                self.report(conn, review_id, report_id)
            rows = (
                conn.execute(
                    text(
                        "SELECT id,body,created_at FROM contract_review_verification_evidence "
                        "WHERE review_id=:review AND (:input IS NULL OR input_id=:input) "
                        "AND (:report IS NULL OR report_id=:report) "
                        "AND (created_at>:after OR (created_at=:after AND id>:last)) "
                        "ORDER BY created_at,id LIMIT :limit"
                    ),
                    {**filters, "after": after_time, "last": after_id, "limit": limit + 1},
                )
                .mappings()
                .all()
            )
            next_cursor = None
            if len(rows) > limit:
                last = rows[limit - 1]
                next_cursor = base64.urlsafe_b64encode(
                    canonical(
                        {"filters": filters, "at": last["created_at"], "id": last["id"]}
                    ).encode("utf-8")
                ).decode("ascii")
            return {
                "items": [self.view(json.loads(row["body"]), current) for row in rows[:limit]],
                "next_cursor": next_cursor,
            }

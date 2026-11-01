"""Review-local human answers and explicit revisions; no HTTP-side model calls."""

import json
from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator
from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.inputs import freeze_input
from specflow.contract_review.report_validation import question_checks
from specflow.contract_review.schemas import (
    ID,
    AuthorityBinding,
    CreateReview,
    GitSource,
    NoRuleset,
    StrictModel,
    Target,
    Text,
)

ExpectedVersion = Annotated[int, Field(ge=1, le=2**63 - 1)]
AnswerText = Annotated[str, Field(min_length=1, max_length=4000)]


class AnswerBase(StrictModel):
    question_id: ID
    scope: Literal["this_review"]


class SelectAnswer(AnswerBase):
    answer_type: Literal["select"]
    option_id: ID
    text: Annotated[str, Field(max_length=4000)] | None = None


class ClarifyAnswer(AnswerBase):
    answer_type: Literal["clarify"]
    text: AnswerText


class InsufficientAnswer(AnswerBase):
    answer_type: Literal["mark_insufficient"]
    reason: Text


Answer = Annotated[
    SelectAnswer | ClarifyAnswer | InsufficientAnswer, Field(discriminator="answer_type")
]


class ResolutionBatch(StrictModel):
    expected_version: ExpectedVersion
    input_revision_id: ID
    report_revision_id: ID
    answers: Annotated[list[Answer], Field(min_length=1, max_length=20)]
    actor_label: Annotated[str, Field(min_length=1, max_length=128)] | None = None

    @model_validator(mode="after")
    def unique_questions(self):
        if len({answer.question_id for answer in self.answers}) != len(self.answers):
            raise ValueError("Duplicate question ID")
        return self


class RevisionRequest(StrictModel):
    expected_version: ExpectedVersion
    base_input_revision_id: ID
    change_reason: Text
    request: Annotated[str, Field(min_length=1, max_length=16000)] | None = None
    targets: Annotated[list[Target], Field(min_length=1, max_length=100)] | None = None
    source: GitSource | None = None
    authority_bindings: (
        Annotated[list[AuthorityBinding], Field(min_length=1, max_length=100)] | None
    ) = None
    ruleset_usage: NoRuleset | None = None
    verification_evidence_ids: Annotated[list[ID], Field(max_length=100)] | None = None
    execution_profile_id: ID | None = None
    supersede_resolution_ids: Annotated[list[ID], Field(min_length=1, max_length=20)] | None = None
    review_directives: Annotated[list[AnswerText], Field(min_length=1, max_length=20)] | None = None

    @model_validator(mode="after")
    def declared_change(self):
        if not self.model_fields_set - {
            "expected_version",
            "base_input_revision_id",
            "change_reason",
        }:
            raise ValueError("A revision needs a declared input change")
        for values in (self.verification_evidence_ids, self.supersede_resolution_ids):
            if values is not None and len(set(values)) != len(values):
                raise ValueError("Duplicate reference")
        if self.supersede_resolution_ids and not self.review_directives:
            raise ValueError("Correcting an answer needs explicit review directives")
        return self


class CheckpointService:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def resolutions(self, conn, review_id, report_id):
        return [
            json.loads(row[0])
            for row in conn.execute(
                text(
                    "SELECT body FROM contract_review_resolutions "
                    "WHERE review_id=:review AND report_id=:report ORDER BY rowid"
                ),
                {"review": review_id, "report": report_id},
            )
        ]

    def remaining(self, conn, review_id, report):
        answered = {
            item["question_id"]
            for item in self.resolutions(conn, review_id, report["report_revision_id"])
        }
        return [
            question["id"]
            for question in report["payload"]["questions"]
            if question["blocking"] and question["id"] not in answered
        ]

    def _review(self, conn, review_id, version):
        review = self.service.require_review(conn, review_id)
        if review["version"] != version:
            raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
        if review["status"] in ("queued", "running"):
            raise ReviewError("REVIEW_BUSY", "当前审查仍在执行。")
        return review

    def answer(self, review_id, request, key):
        payload_hash, key_hash = (
            digest(request.model_dump(exclude_none=True)),
            self.service.key_hash(key),
        )
        scope = review_id + ":resolution-batches"
        with self.store.transaction() as conn:
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            self.service.require_review(conn, review_id)
            frozen = self.service.verifications.input(conn, review_id, request.input_revision_id)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_reports "
                "WHERE id=:id AND review_id=:review AND input_id=:input",
                id=request.report_revision_id,
                review=review_id,
                input=request.input_revision_id,
            )
            if row is None:
                raise ReviewError("RESOURCE_NOT_FOUND", "报告不属于指定审查输入。", 404)
            report = json.loads(row["body"])
            questions = {item["id"]: item for item in report["payload"]["questions"]}
            if any(answer.question_id not in questions for answer in request.answers):
                raise ReviewError("RESOURCE_NOT_FOUND", "问题不属于指定报告。", 404)
            review = self._review(conn, review_id, request.expected_version)
            if (
                review["status"] != "awaiting_decision"
                or review["current_input_id"] != request.input_revision_id
                or review["current_report_id"] != request.report_revision_id
            ):
                raise ReviewError("INVALID_STATE", "只能回答当前等待裁决报告中的问题。")
            saved = self.resolutions(conn, review_id, request.report_revision_id)
            answered = {item["question_id"] for item in saved}
            records = []
            for answer in request.answers:
                question = questions[answer.question_id]
                if answer.question_id in answered:
                    raise ReviewError("QUESTION_ALREADY_RESOLVED", "问题已有终局答案。")
                if answer.answer_type not in question["allowed_answer_types"]:
                    raise ReviewError("INVALID_ANSWER", "问题不接受该答案类型。", 422)
                selected = None
                if answer.answer_type == "select":
                    selected = next(
                        (item for item in question["options"] if item["id"] == answer.option_id),
                        None,
                    )
                    if selected is None:
                        raise ReviewError("INVALID_ANSWER", "选项不属于该问题。", 422)
                record = {
                    "resolution_id": identity("res"),
                    "review_id": review_id,
                    "input_revision_id": request.input_revision_id,
                    "report_revision_id": request.report_revision_id,
                    "question_id": answer.question_id,
                    "question": question,
                    "check_ids": sorted(question_checks(question, report["payload"])),
                    "answer": answer.model_dump(exclude_none=True),
                    "selected_option": selected,
                    "actor_subject": "shared-service",
                    "actor_label": request.actor_label,
                    "created_at": now(),
                }
                records.append(record)
            for record in records:
                body = canonical(record)
                self.store.reserve_records(conn, len(body.encode("utf-8")))
                self.store.execute(
                    conn,
                    "INSERT INTO contract_review_resolutions "
                    "VALUES (:id,:review,:input,:report,:question,:body,:created)",
                    id=record["resolution_id"],
                    review=review_id,
                    input=request.input_revision_id,
                    report=request.report_revision_id,
                    question=record["question_id"],
                    body=body,
                    created=record["created_at"],
                )
            remaining = self.remaining(conn, review_id, report)
            response = {
                "review_id": review_id,
                "version": request.expected_version + 1,
                "status": "awaiting_decision",
                "accepted_resolution_ids": [r["resolution_id"] for r in records],
                "remaining_blocking_question_ids": remaining,
                "job_id": None,
            }
            status = 200
            if remaining:
                self.store.execute(
                    conn,
                    "UPDATE contract_reviews SET version=version+1,updated_at=:at "
                    "WHERE id=:id AND version=:version",
                    id=review_id,
                    version=request.expected_version,
                    at=now(),
                )
            else:
                next_input = deepcopy(frozen)
                next_input.pop("input_hash", None)
                next_input["input_revision_id"] = identity("ir")
                next_input["resolutions"] = [*frozen["resolutions"], *saved, *records]
                next_input["revision_change"] = {
                    "kind": "human_answers",
                    "base_input_revision_id": request.input_revision_id,
                    "report_revision_id": request.report_revision_id,
                }
                self._bind_input(next_input)
                response.update(
                    self.service.enqueue_revision(
                        conn, review_id, request.expected_version, next_input
                    )
                )
                status = 202
            self.store.event(
                conn,
                review_id,
                request.input_revision_id,
                None,
                "resolutions_recorded",
                {
                    "records": records,
                    "remaining_blocking_question_ids": remaining,
                    "next_job_id": response["job_id"],
                },
            )
            return self.service.remember(conn, scope, key_hash, payload_hash, status, response)

    @staticmethod
    def _bind_input(frozen):
        for adoption in frozen["adoption_records"]:
            adoption["input_revision_id"] = frozen["input_revision_id"]

    def _snapshot(self, conn, frozen):
        row = self.store.row(
            conn,
            "SELECT manifest FROM contract_review_snapshots WHERE id=:id",
            id=frozen["snapshot_id"],
        )
        snapshot = json.loads(row["manifest"])
        files = []
        for item in snapshot["files"]:
            blob = self.store.row(
                conn,
                "SELECT raw_bytes,body_hash FROM contract_review_source_blobs "
                "WHERE id=:id AND snapshot_id=:snapshot",
                id=item["source_id"],
                snapshot=frozen["snapshot_id"],
            )
            if blob is None or digest(blob["raw_bytes"]) != item["body_hash"]:
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "密封快照字节损坏。")
            files.append({**item, "body": blob["raw_bytes"].decode("utf-8")})
        return {**snapshot, "files": files}

    def revise(self, review_id, request, key):
        patch = request.model_dump(exclude_none=True)
        payload_hash, key_hash = digest(patch), self.service.key_hash(key)
        scope = review_id + ":revisions"
        with self.store.read() as conn:
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            previous = self.service.verifications.input(
                conn, review_id, request.base_input_revision_id
            )
            review = self._review(conn, review_id, request.expected_version)
            if review["current_input_id"] != request.base_input_revision_id:
                raise ReviewError("INVALID_STATE", "只能基于当前输入显式修订。")
            previous["resolutions"] += self.resolutions(
                conn, review_id, review["current_report_id"]
            )
            project = self.store.row(
                conn, "SELECT repository_path FROM projects WHERE id=:id", id=review["project_id"]
            )
            repository = project["repository_path"]
            old_raw = CreateReview.model_validate(previous["original_request"]).model_dump(
                exclude_none=True
            )
            raw = deepcopy(old_raw)
            for field in (
                "request",
                "targets",
                "source",
                "authority_bindings",
                "ruleset_usage",
                "execution_profile_id",
            ):
                if field in patch:
                    raw[field] = patch[field]
            try:
                create = CreateReview.model_validate(raw)
            except ValidationError:
                raise ReviewError(
                    "INVALID_REVISION", "合并后的修订不符合输入 Schema。", 422
                ) from None
            raw = create.model_dump(exclude_none=True)
            profile_id = request.execution_profile_id or previous["execution_profile"]["profile_id"]
            profile = self.service.profiles.get(profile_id)
            if profile is None or (
                "execution_profile_id" not in patch and profile != previous["execution_profile"]
            ):
                raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "修订 profile 不可用。")
            source_changed = raw["source"] != old_raw["source"]
            snapshot = None if source_changed else self._snapshot(conn, previous)
        if source_changed:
            snapshot = self.service.snapshot_reader.prepare(repository, create.source)
        frozen = freeze_input(create, snapshot, profile, identity("ir"))
        self._preserve_ids(frozen, previous)
        self._bind_input(frozen)
        directives = patch.get("review_directives", previous.get("review_directives", []))
        frozen["review_directives"] = directives
        superseded = patch.get("supersede_resolution_ids", [])
        active = {item["resolution_id"]: item for item in previous["resolutions"]}
        if not set(superseded) <= set(active):
            raise ReviewError("RESOURCE_NOT_FOUND", "更正答案不属于当前输入的有效答案。", 404)
        changed_basis = any(
            raw[field] != old_raw[field] for field in ("source", "targets", "authority_bindings")
        )
        frozen["resolutions"] = [
            item for key, item in active.items() if key not in superseded and not changed_basis
        ]
        frozen["resolution_adoptions"] = [
            {
                "resolution_id": key,
                "status": "superseded"
                if key in superseded
                else "excluded"
                if changed_basis
                else "adopted",
                "reason": request.change_reason
                if key in superseded
                else "材料、目标或权威绑定变化，原答案不自动带入。"
                if changed_basis
                else "适用范围与密封材料保持一致。",
            }
            for key in active
        ]
        selected_before = [
            item["evidence_id"] for item in previous["verification_evidence_adoptions"]
        ]
        evidence_ids = patch.get("verification_evidence_ids", selected_before)
        if (
            {key: value for key, value in raw.items() if key != "execution_profile_id"}
            == {key: value for key, value in old_raw.items() if key != "execution_profile_id"}
            and profile == previous["execution_profile"]
            and directives == previous.get("review_directives", [])
            and set(evidence_ids) == set(selected_before)
            and not superseded
        ):
            raise ReviewError("INVALID_STATE", "修订没有实际输入或策略变化。")
        frozen["revision_change"] = {
            "kind": "explicit_revision",
            "base_input_revision_id": request.base_input_revision_id,
            "change_reason": request.change_reason,
            "declared_changes": patch,
            "supersede_resolution_ids": superseded,
        }
        with self.store.transaction() as conn:
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            self._review(conn, review_id, request.expected_version)
            current_project = self.store.row(
                conn, "SELECT repository_path FROM projects WHERE id=:id", id=review["project_id"]
            )
            if source_changed:
                if current_project is None or current_project["repository_path"] != repository:
                    raise ReviewError("PROJECT_NOT_FOUND", "项目来源已变化。", 404)
                self.service.snapshot_reader.validate_path(repository)
                self.service.capacity(conn, snapshot["byte_count"])
                self.service.save_snapshot(conn, review["project_id"], snapshot)
            response = self.service.enqueue_revision(
                conn, review_id, request.expected_version, frozen, evidence_ids
            )
            return self.service.remember(conn, scope, key_hash, payload_hash, 202, response)

    @staticmethod
    def _preserve_ids(frozen, previous):
        def target_key(target):
            return canonical({key: value for key, value in target.items() if key != "target_id"})

        old = {target_key(target): target["target_id"] for target in previous["target_manifest"]}
        mapping = {
            target["target_id"]: old.get(target_key(target), target["target_id"])
            for target in frozen["target_manifest"]
        }
        for target in frozen["target_manifest"]:
            target["target_id"] = mapping[target["target_id"]]
        old_checks = {
            canonical({key: value for key, value in check.items() if key != "check_id"}): check[
                "check_id"
            ]
            for check in previous["check_manifest"]
        }
        for check in frozen["check_manifest"]:
            check["target_id"] = mapping[check["target_id"]]
            check["check_id"] = old_checks.get(
                canonical({key: value for key, value in check.items() if key != "check_id"}),
                check["check_id"],
            )
        for adoption in frozen["adoption_records"]:
            adoption["target_id"] = mapping[adoption["target_id"]]

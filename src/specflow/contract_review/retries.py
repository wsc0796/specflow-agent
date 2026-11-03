"""Explicit same-input attempts; successful idempotency replay precedes mutable checks."""

import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.schemas import ID, StrictModel, Text


class RetryRequest(StrictModel):
    expected_version: Annotated[int, Field(ge=1)]
    failed_job_id: ID
    input_revision_id: ID
    reason: Text
    mode: Literal["fresh", "reuse_completed"]
    recovery_fallback: Literal["restart_fresh", "stop"] | None = None

    @model_validator(mode="after")
    def mode_contract(self):
        if self.mode == "fresh" and "recovery_fallback" in self.model_fields_set:
            raise ValueError("Fresh forbids recovery_fallback")
        if self.mode == "reuse_completed" and self.recovery_fallback is None:
            raise ValueError("Reuse requires an explicit recovery_fallback")
        return self


class RetryService:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def submit(self, review_id, request, key):
        scope = "retry:" + review_id
        key_hash = self.service.key_hash(key)
        payload_hash = digest(request.model_dump(exclude_none=True))
        with self.store.transaction() as conn:
            prior = self.service.replay(conn, scope, key_hash, payload_hash)
            if prior is not None:
                return prior
            review = self.service.require_review(conn, review_id)
            if review["version"] != request.expected_version:
                raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
            source = self.store.row(
                conn,
                "SELECT * FROM contract_review_jobs WHERE id=:id AND review_id=:review",
                id=request.failed_job_id,
                review=review_id,
            )
            if (
                source is None
                or source["input_id"] != request.input_revision_id
                or review["current_input_id"] != request.input_revision_id
                or review["active_job_id"] != source["id"]
            ):
                raise ReviewError("RETRY_TARGET_NOT_CURRENT", "重试必须指向当前输入的最近作业。")
            if review["status"] != "failed" or source["status"] not in ("failed", "interrupted"):
                raise ReviewError("RETRY_NOT_ALLOWED", "仅允许重试失败或中断的当前作业。")
            frozen = self.service.verifications.input(conn, review_id, request.input_revision_id)
            if (
                digest({k: v for k, v in frozen.items() if k != "input_hash"})
                != frozen["input_hash"]
            ):
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "冻结输入完整性校验失败。")
            profile = frozen["execution_profile"]
            if self.service.profiles.get(profile["profile_id"]) != profile:
                raise ReviewError(
                    "RETRY_PROFILE_UNAVAILABLE", "冻结 profile 已不可执行，请新建修订。"
                )
            if request.mode == "reuse_completed" and not profile["options"]["replay"]:
                raise ReviewError("OPTION_NOT_ENABLED", "冻结输入未启用前缀回放。")
            self.service.capacity(conn)
            account = json.loads(
                self.store.row(
                    conn,
                    "SELECT body FROM contract_review_budget_accounts WHERE review_id=:review",
                    review=review_id,
                )["body"]
            )
            if (
                account["model_calls"] >= account["grant"]["model_calls"]
                or account["tool_actions"] >= account["grant"]["tool_actions"]
                or account["execution_seconds_charged"] + account["execution_seconds_reserved"]
                >= account["grant"]["execution_seconds"]
            ):
                raise ReviewError("REVIEW_BUDGET_EXHAUSTED", "累计审查预算不足。")
            job_id = identity("job")
            attempt = source["attempt_no"] + 1
            body = {
                "requested_mode": request.mode,
                "effective_mode": request.mode,
                "retry_of_job_id": source["id"],
                "recovery_fallback": request.recovery_fallback,
                "replay_boundary": None,
                "reason": request.reason,
                "execution_mode": profile["execution_mode"],
            }
            encoded = canonical(body)
            self.store.reserve_records(conn, len(encoded.encode()))
            self.store.execute(
                conn,
                "INSERT INTO contract_review_jobs "
                "(id,review_id,input_id,attempt_no,status,body,created_at) "
                "VALUES (:id,:review,:input,:attempt,'queued',:body,:at)",
                id=job_id,
                review=review_id,
                input=request.input_revision_id,
                attempt=attempt,
                body=encoded,
                at=now(),
            )
            changed = self.store.execute(
                conn,
                "UPDATE contract_reviews SET active_job_id=:job,current_report_id=NULL,"
                "status='queued',version=version+1,updated_at=:at "
                "WHERE id=:review AND version=:version",
                job=job_id,
                at=now(),
                review=review_id,
                version=request.expected_version,
            )
            if changed.rowcount != 1:
                raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
            response = {
                "review_id": review_id,
                "input_revision_id": request.input_revision_id,
                "job_id": job_id,
                "attempt_no": attempt,
                "retry_of_job_id": source["id"],
                "requested_mode": request.mode,
                "effective_mode": request.mode,
                "status": "queued",
                "version": request.expected_version + 1,
                "accepted": True,
            }
            self.store.event(
                conn, review_id, request.input_revision_id, job_id, "retry_queued", body
            )
            return self.service.remember(conn, scope, key_hash, payload_hash, 202, response)

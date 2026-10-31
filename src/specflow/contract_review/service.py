"""Persistent intake/query service; no provider side effects in HTTP requests."""

from __future__ import annotations

import json
import re
from copy import deepcopy

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.inputs import freeze_input
from specflow.contract_review.schemas import ExecutionProfile
from specflow.contract_review.store import ReviewStore
from specflow.contract_review.verification import VerificationService


class ReviewService:
    def __init__(self, store: ReviewStore, snapshot_reader, profiles: dict | None = None):
        self.store = store
        self.snapshot_reader = snapshot_reader
        self.profiles = {}
        self.worker = None
        self.verifications = VerificationService(self)
        for name, value in (profiles or {}).items():
            try:
                profile = ExecutionProfile.model_validate(value)
                if name != profile.profile_id:
                    raise ValueError("Profile registration identity mismatch")
            except ValueError:
                raise RuntimeError("Invalid non-secret contract-review profile") from None
            self.profiles[name] = profile.frozen()

    @staticmethod
    def key_hash(key: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise ReviewError("INVALID_IDEMPOTENCY_KEY", "幂等键格式无效。", 422)
        return digest(key.encode("ascii"))

    def replay(self, conn, scope, key_hash, payload_hash):
        value = self.store.row(
            conn,
            "SELECT * FROM contract_review_idempotency WHERE scope=:scope AND key_digest=:key",
            scope=scope,
            key=key_hash,
        )
        if value is None:
            return None
        if value["payload_hash"] != payload_hash:
            raise ReviewError("IDEMPOTENCY_KEY_REUSED", "同一幂等键已用于不同请求。")
        return value["status_code"], json.loads(value["response"])

    def remember(self, conn, scope, key_hash, payload_hash, status_code, response):
        body = canonical(response)
        self.store.reserve_records(conn, len(body.encode("utf-8")))
        self.store.execute(
            conn,
            "INSERT INTO contract_review_idempotency VALUES "
            "(:scope,:key,:hash,:status,:body,:created)",
            scope=scope,
            key=key_hash,
            hash=payload_hash,
            status=status_code,
            body=body,
            created=now(),
        )
        return status_code, response

    def capacity(self, conn, snapshot_size=0):
        queued = self.store.row(
            conn, "SELECT count(*) AS count FROM contract_review_jobs WHERE status='queued'"
        )["count"]
        if queued >= 20:
            raise ReviewError("QUEUE_FULL", "审查队列已满。", 429)
        usage = self.store.row(conn, "SELECT * FROM contract_review_capacity WHERE id=1")
        if usage["snapshot_bytes"] + snapshot_size > self.store.snapshot_capacity:
            raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "快照保存容量不足。", 503)
        if usage["record_bytes"] >= self.store.record_capacity:
            raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "必要记录容量不足。", 503)

    def create(self, request, key, original_request=None):
        payload = request.model_dump(exclude_none=True)
        payload_hash, key_hash = digest(payload), self.key_hash(key)
        scope = "service:contract-review:create:" + request.project_id
        with self.store.read() as conn:
            prior = self.replay(conn, scope, key_hash, payload_hash)
            if prior:
                return prior
            project = self.store.row(
                conn,
                "SELECT repository_path FROM projects WHERE id=:id",
                id=request.project_id,
            )
            if project is None:
                raise ReviewError("PROJECT_NOT_FOUND", "项目不存在。", 404)
            self.capacity(conn)
            repository = project["repository_path"]
        profile_id = request.execution_profile_id
        if profile_id is None and len(self.profiles) == 1:
            profile_id = next(iter(self.profiles))
        profile = self.profiles.get(profile_id)
        if profile is None:
            raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "尚未配置可执行的审查 profile。")
        snapshot = self.snapshot_reader.prepare(repository, request.source)
        review_id, input_id, job_id = identity("cr"), identity("ir"), identity("job")
        frozen = freeze_input(request, snapshot, profile, input_id, original_request)
        created = now()
        grant = {"model_calls": 36, "tool_actions": 60, "execution_seconds": 900}
        response = {
            "review_id": review_id,
            "input_revision_id": input_id,
            "job_id": job_id,
            "attempt_no": 1,
            "status": "queued",
            "version": 1,
            "accepted": True,
            "budget_grant": grant,
            "links": {
                "status": f"/api/v1/contract-reviews/{review_id}",
                "report": f"/api/v1/contract-reviews/{review_id}/report",
                "events": f"/api/v1/contract-reviews/{review_id}/events?job_id={job_id}",
            },
        }
        with self.store.transaction() as conn:
            prior = self.replay(conn, scope, key_hash, payload_hash)
            if prior:
                return prior
            self.capacity(conn, snapshot["byte_count"])
            current_project = self.store.row(
                conn,
                "SELECT repository_path FROM projects WHERE id=:id",
                id=request.project_id,
            )
            if current_project is None or current_project["repository_path"] != repository:
                raise ReviewError("PROJECT_NOT_FOUND", "项目来源已变化。", 404)
            self.snapshot_reader.validate_path(repository)
            self.store.execute(
                conn,
                "INSERT INTO contract_reviews "
                "(id,project_id,status,version,current_input_id,active_job_id,"
                "created_at,updated_at) "
                "VALUES (:id,:project,'queued',1,:input,:job,:created,:created)",
                id=review_id,
                project=request.project_id,
                input=input_id,
                job=job_id,
                created=created,
            )
            self.save_snapshot(conn, request.project_id, snapshot)
            self.save_input(conn, review_id, frozen, 1)
            self.store.execute(
                conn,
                "INSERT INTO contract_review_jobs "
                "(id,review_id,input_id,attempt_no,status,body,created_at) "
                "VALUES (:id,:review,:input,1,'queued',:body,:created)",
                id=job_id,
                review=review_id,
                input=input_id,
                created=created,
                body=canonical(
                    {
                        "requested_mode": "fresh",
                        "effective_mode": "fresh",
                        "retry_of_job_id": None,
                        "execution_mode": profile["execution_mode"],
                    }
                ),
            )
            self.store.execute(
                conn,
                "INSERT INTO contract_review_budget_accounts VALUES (:id,:body,1)",
                id=review_id,
                body=canonical(
                    {
                        "grant": grant,
                        "model_calls": 0,
                        "tool_actions": 0,
                        "execution_seconds_charged": 0,
                        "execution_seconds_reserved": 0,
                        "input_tokens": None,
                        "output_tokens": None,
                        "usage_status": "unknown",
                    }
                ),
            )
            self.store.event(conn, review_id, input_id, job_id, "review_created", response)
            return self.remember(conn, scope, key_hash, payload_hash, 202, response)

    def save_snapshot(self, conn, project_id, snapshot):
        manifest = {key: value for key, value in snapshot.items() if key != "files"}
        manifest["project_id"] = project_id
        manifest["files"] = [
            {key: value for key, value in item.items() if key != "body"}
            for item in snapshot["files"]
        ]
        self.store.reserve_records(conn, len(canonical(manifest).encode("utf-8")))
        self.store.execute(
            conn,
            "UPDATE contract_review_capacity SET snapshot_bytes=snapshot_bytes+:size WHERE id=1",
            size=snapshot["byte_count"],
        )
        self.store.execute(
            conn,
            "INSERT INTO contract_review_snapshots VALUES (:id,:project,:commit,:manifest,:size)",
            id=snapshot["snapshot_id"],
            project=project_id,
            commit=snapshot["commit_sha"],
            manifest=canonical(manifest),
            size=snapshot["byte_count"],
        )
        for item in snapshot["files"]:
            self.store.execute(
                conn,
                "INSERT INTO contract_review_source_blobs VALUES "
                "(:id,:snapshot,:path,:roles,:raw,:hash)",
                id=item["source_id"],
                snapshot=snapshot["snapshot_id"],
                path=item["path"],
                roles=canonical(item["roles"]),
                raw=item["body"].encode("utf-8"),
                hash=item["body_hash"],
            )

    def save_input(self, conn, review_id, frozen, revision_no):
        body = canonical(frozen)
        self.store.reserve_records(conn, len(body.encode("utf-8")))
        self.store.execute(
            conn,
            "INSERT INTO contract_review_inputs VALUES "
            "(:id,:review,:no,:snapshot,:body,:hash,:created)",
            id=frozen["input_revision_id"],
            review=review_id,
            no=revision_no,
            snapshot=frozen["snapshot_id"],
            body=body,
            hash=frozen["input_hash"],
            created=now(),
        )

    def require_review(self, conn, review_id):
        row = self.store.row(conn, "SELECT * FROM contract_reviews WHERE id=:id", id=review_id)
        if row is None:
            raise ReviewError("REVIEW_NOT_FOUND", "审查不存在。", 404)
        return row

    def enqueue_revision(
        self, conn, review_id, expected_version, frozen, verification_evidence_ids=None
    ):
        """Atomic host operation used by later revision/resolution endpoints."""
        review = self.require_review(conn, review_id)
        if type(expected_version) is not int or review["version"] != expected_version:
            raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
        if review["status"] in ("queued", "running"):
            raise ReviewError("REVIEW_BUSY", "当前审查仍在执行。")
        self.capacity(conn)
        account = json.loads(
            self.store.row(
                conn,
                "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
                id=review_id,
            )["body"]
        )
        if (
            account["model_calls"] >= account["grant"]["model_calls"]
            or account["tool_actions"] >= account["grant"]["tool_actions"]
            or account["execution_seconds_charged"] + account["execution_seconds_reserved"]
            >= account["grant"]["execution_seconds"]
        ):
            raise ReviewError("REVIEW_BUDGET_EXHAUSTED", "累计审查预算不足。")
        profile = frozen["execution_profile"]
        if self.profiles.get(profile["profile_id"]) != profile:
            raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "冻结 profile 已不可用。")
        revision_no = (
            self.store.row(
                conn,
                "SELECT count(*) AS n FROM contract_review_inputs WHERE review_id=:id",
                id=review_id,
            )["n"]
            + 1
        )
        attempt_no = (
            self.store.row(
                conn,
                "SELECT count(*) AS n FROM contract_review_jobs WHERE review_id=:id",
                id=review_id,
            )["n"]
            + 1
        )
        previous = self.verifications.input(conn, review_id, review["current_input_id"])
        evidence_ids = (
            verification_evidence_ids
            if verification_evidence_ids is not None
            else [item["evidence_id"] for item in previous["verification_evidence_adoptions"]]
        )
        frozen = deepcopy(frozen)
        frozen["verification_evidence_adoptions"] = self.verifications.adopt(
            conn, review_id, frozen, evidence_ids
        )
        frozen.pop("input_hash", None)
        frozen["input_hash"] = digest(frozen)
        self.save_input(conn, review_id, frozen, revision_no)
        job_id = identity("job")
        updated = self.store.execute(
            conn,
            "UPDATE contract_reviews SET current_input_id=:input,current_report_id=NULL,"
            "active_job_id=:job,status='queued',version=version+1,updated_at=:at "
            "WHERE id=:id AND version=:expected",
            id=review_id,
            input=frozen["input_revision_id"],
            job=job_id,
            at=now(),
            expected=expected_version,
        )
        if updated.rowcount != 1:
            raise ReviewError("VERSION_CONFLICT", "审查版本已变化。")
        self.store.execute(
            conn,
            "INSERT INTO contract_review_jobs "
            "(id,review_id,input_id,attempt_no,status,body,created_at) "
            "VALUES (:id,:review,:input,:attempt,'queued',:body,:at)",
            id=job_id,
            review=review_id,
            input=frozen["input_revision_id"],
            attempt=attempt_no,
            body=canonical(
                {
                    "requested_mode": "fresh",
                    "effective_mode": "fresh",
                    "retry_of_job_id": None,
                    "execution_mode": profile["execution_mode"],
                }
            ),
            at=now(),
        )
        response = {
            "review_id": review_id,
            "input_revision_id": frozen["input_revision_id"],
            "job_id": job_id,
            "attempt_no": attempt_no,
            "status": "queued",
            "version": expected_version + 1,
            "accepted": True,
        }
        self.store.event(
            conn, review_id, frozen["input_revision_id"], job_id, "input_revised", response
        )
        return response

    def get(self, review_id):
        with self.store.read() as conn:
            row = self.require_review(conn, review_id)
            frozen = json.loads(
                self.store.row(
                    conn,
                    "SELECT body FROM contract_review_inputs WHERE id=:id",
                    id=row["current_input_id"],
                )["body"]
            )
            job = self.store.row(
                conn,
                "SELECT * FROM contract_review_jobs WHERE id=:id",
                id=row["active_job_id"],
            )
            account = self.store.row(
                conn,
                "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
                id=review_id,
            )
            quality = None
            if row["current_report_id"]:
                report = self.store.row(
                    conn,
                    "SELECT body,input_id FROM contract_review_reports "
                    "WHERE id=:id AND review_id=:review",
                    id=row["current_report_id"],
                    review=review_id,
                )
                if report is None or report["input_id"] != row["current_input_id"]:
                    raise ReviewError("INTERNAL_ERROR", "当前报告归属不完整。", 500)
                quality = json.loads(report["body"])["quality"]
            return {
                "review_id": review_id,
                "project_id": row["project_id"],
                "status": row["status"],
                "version": row["version"],
                "current_input_revision_id": row["current_input_id"],
                "current_report_revision_id": row["current_report_id"],
                "job_id": job["id"],
                "job_status": job["status"],
                "error_code": job["error_code"],
                "check_manifest": frozen["check_manifest"],
                "quality": quality,
                "report_available": row["current_report_id"] is not None,
                "execution_profile": frozen["execution_profile"],
                "input_hash": frozen["input_hash"],
                "budget": json.loads(account["body"]),
                "adopted_ruleset_version": None,
                "current_ruleset_version": None,
                "evidence_integrity": "incomplete"
                if self.worker and self.worker.faulted
                else "complete",
                "dispatch_gate": self.worker.dispatch_gate(conn)
                if self.worker
                else {
                    "can_claim": False,
                    "reason_codes": ["runtime_not_ready"],
                    "blocked_by": [],
                    "observed_at": now(),
                },
            }

    def report(self, review_id, report_id=None):
        with self.store.read() as conn:
            review = self.require_review(conn, review_id)
            current = report_id is None
            report_id = review["current_report_id"] if current else report_id
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_reports WHERE id=:id AND review_id=:review",
                id=report_id,
                review=review_id,
            )
            if row is None:
                raise ReviewError("REPORT_NOT_AVAILABLE", "指定输入尚无正式报告。", 404)
            if current and row["input_id"] != review["current_input_id"]:
                raise ReviewError("INTERNAL_ERROR", "当前报告归属不完整。", 500)
            return json.loads(row["body"])

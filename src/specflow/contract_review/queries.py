"""Read-only resource projections; no query changes authoritative records."""

import base64
import json

from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest


def event_view(row):
    try:
        metadata = json.loads(row["body"])
        if (
            not isinstance(metadata, dict)
            or metadata.get("event_id") != row["id"]
            or metadata.get("review_id") != row["review_id"]
            or metadata.get("event_seq") != row["event_seq"]
            or any(
                field not in metadata or metadata[field] != row[column]
                for field, column in (
                    ("job_id", "job_id"),
                    ("input_revision_id", "input_id"),
                    ("event_type", "event_type"),
                )
            )
            or "evidence_integrity" not in metadata
        ):
            raise ValueError("Event identity damaged")
    except (ValueError, TypeError):
        return {
            "event_id": row["id"],
            "review_id": row["review_id"],
            "event_seq": row["event_seq"],
            "input_revision_id": row["input_id"],
            "job_id": row["job_id"],
            "payload_available": False,
            "evidence_integrity": "incomplete",
            "missing_evidence": ["event_metadata_unavailable"],
        }, None
    payload, reason = None, None
    try:
        if len(row["payload"].encode("utf-8")) > 1024**2:
            reason = "payload_too_large"
        elif metadata.get("payload_ref") != row["id"]:
            reason = "payload_reference_mismatch"
        else:
            payload = json.loads(row["payload"])
            if digest(payload) != row["payload_hash"] or row["payload_hash"] != metadata.get(
                "payload_hash"
            ):
                reason = "payload_integrity_mismatch"
    except (ValueError, TypeError):
        reason = "payload_unavailable"
    return {
        **metadata,
        "payload_available": reason is None,
        "evidence_integrity": metadata["evidence_integrity"] if reason is None else "incomplete",
        "missing_evidence": [reason] if reason else [],
    }, payload


class ReviewQueries:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def report_record(self, conn, review_id, report_id=None):
        review = self.service.require_review(conn, review_id)
        current = report_id is None
        identifier = review["current_report_id"] if current else report_id
        row = self.store.row(
            conn,
            "SELECT * FROM contract_review_reports WHERE id=:id AND review_id=:review",
            id=identifier,
            review=review_id,
        )
        if row is None:
            raise ReviewError("REPORT_NOT_AVAILABLE", "指定输入尚无正式报告。", 404)
        if current and row["input_id"] != review["current_input_id"]:
            raise ReviewError("INTERNAL_ERROR", "当前报告归属不完整。", 500)
        return review, row, json.loads(row["body"])

    def questions(self, review_id, report_id=None):
        with self.store.read() as conn:
            review, row, report = self.report_record(conn, review_id, report_id)
            saved = {
                item["question_id"]: item
                for item in self.service.checkpoints.resolutions(conn, review_id, row["id"])
            }
            return {
                "review_id": review_id,
                "input_revision_id": row["input_id"],
                "report_revision_id": row["id"],
                "is_current_report": row["id"] == review["current_report_id"]
                and row["input_id"] == review["current_input_id"],
                "remaining_blocking_question_ids": [
                    q["id"]
                    for q in report["payload"]["questions"]
                    if q["blocking"] and q["id"] not in saved
                ],
                "items": [
                    {
                        **question,
                        "answer_status": "answered" if question["id"] in saved else "unanswered",
                        "resolution": saved.get(question["id"]),
                    }
                    for question in report["payload"]["questions"]
                ],
            }

    def list(self, project_id, cursor=None, limit=20):
        after_time, after_id = "", ""
        if cursor:
            try:
                value = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
                if (
                    set(value) != {"project", "at", "id"}
                    or value["project"] != project_id
                    or any(
                        type(value[key]) is not str or not 1 <= len(value[key]) <= 64
                        for key in ("at", "id")
                    )
                ):
                    raise ValueError("Cursor scope mismatch")
                after_time, after_id = value["at"], value["id"]
            except (ValueError, TypeError, KeyError, UnicodeError) as error:
                raise ReviewError("INVALID_CURSOR", "游标无效或项目不匹配。", 422) from error
        with self.store.read() as conn:
            self.service.decisions.require_project(conn, project_id)
            rows = (
                conn.execute(
                    text(
                        "SELECT r.*,j.status AS job_status,j.error_code FROM contract_reviews r "
                        "JOIN contract_review_jobs j ON j.id=r.active_job_id "
                        "WHERE r.project_id=:project AND (r.created_at>:at OR "
                        "(r.created_at=:at AND r.id>:id)) ORDER BY r.created_at,r.id LIMIT :count"
                    ),
                    {"project": project_id, "at": after_time, "id": after_id, "count": limit + 1},
                )
                .mappings()
                .all()
            )
            next_cursor = None
            if len(rows) > limit:
                last = rows[limit - 1]
                next_cursor = base64.urlsafe_b64encode(
                    canonical(
                        {"project": project_id, "at": last["created_at"], "id": last["id"]}
                    ).encode("utf-8")
                ).decode("ascii")
            return {
                "items": [
                    {
                        "review_id": row["id"],
                        "project_id": row["project_id"],
                        "status": row["status"],
                        "version": row["version"],
                        "current_input_revision_id": row["current_input_id"],
                        "current_report_revision_id": row["current_report_id"],
                        "job_id": row["active_job_id"],
                        "job_status": row["job_status"],
                        "error_code": row["error_code"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows[:limit]
                ],
                "next_cursor": next_cursor,
            }

    def diagnostics(self, conn, job):
        step = self.store.row(
            conn,
            "SELECT id,step_seq,role,logical_call_id FROM contract_review_steps "
            "WHERE job_id=:job ORDER BY step_seq DESC LIMIT 1",
            job=job["id"],
        )
        call = self.store.row(
            conn,
            "SELECT id,status,body FROM contract_review_calls WHERE job_id=:job "
            "ORDER BY rowid DESC LIMIT 1",
            job=job["id"],
        )
        last = None
        if call:
            body = json.loads(call["body"])
            last = {
                "call_id": call["id"],
                "status": call["status"],
                **{key: body[key] for key in ("local_io_state", "remote_outcome", "usage")},
            }
        return {
            "current_step": {
                "step_id": step["id"],
                **{key: step[key] for key in ("step_seq", "role", "logical_call_id")},
            }
            if step
            else None,
            "started_at": job["started_at"],
            "deadline": job["deadline"],
            "finished_at": job["finished_at"],
            "last_call": last,
        }

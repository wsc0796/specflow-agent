"""Fenced job/call ledger. All I/O happens after these short transactions commit."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.process_identity import (
    current_process_identity,
    original_process_exited,
)
from specflow.contract_review.sources import select_text


class ExecutionLedger:
    def __init__(self, service):
        self.service, self.store = service, service.store
        self.boot_id = identity("boot")
        self.process = current_process_identity()

    def start(self):
        with self.store.transaction() as conn:
            self.store.execute(
                conn,
                "UPDATE contract_review_runtime SET owner_boot_id=:boot WHERE id=1",
                boot=self.boot_id,
            )
            rows = (
                conn.exec_driver_sql("SELECT * FROM contract_review_jobs WHERE status='running'")
                .mappings()
                .all()
            )
            for row in rows:
                self._fail(conn, row, "INTERRUPTED", interrupted=True)
            calls = (
                conn.exec_driver_sql(
                    "SELECT * FROM contract_review_calls WHERE status IN "
                    "('intent_recorded','dispatch_started')"
                )
                .mappings()
                .all()
            )
            for call in calls:
                body = json.loads(call["body"])
                if body["local_io_state"] != "quiesced":
                    body["local_io_state"] = "unconfirmed"
                self.store.execute(
                    conn,
                    "UPDATE contract_review_calls SET "
                    "status='UNKNOWN',body=:body,version=version+1 WHERE id=:id",
                    id=call["id"],
                    body=canonical(body),
                )
        self.reconcile_dead_process()

    def owner(self, conn):
        runtime = self.store.row(conn, "SELECT * FROM contract_review_runtime WHERE id=1")
        if runtime["owner_boot_id"] != self.boot_id:
            raise ReviewError("STALE_EXECUTION", "当前宿主没有执行权。")
        return runtime

    def fence(self, conn, context):
        self.owner(conn)
        row = self.store.row(
            conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=context["job_id"]
        )
        review = self.service.require_review(conn, context["review_id"])
        if (
            row is None
            or row["status"] != "running"
            or row["owner_boot_id"] != self.boot_id
            or row["attempt_token"] != context["attempt_token"]
            or review["active_job_id"] != row["id"]
            or review["current_input_id"] != row["input_id"]
        ):
            raise ReviewError("STALE_EXECUTION", "作业执行权已失效。")
        if datetime.now(UTC) >= datetime.fromisoformat(row["deadline"].replace("Z", "+00:00")):
            raise ReviewError("DEADLINE_EXCEEDED", "作业期限已到。")
        return row

    def account(self, conn, review_id):
        return json.loads(
            self.store.row(
                conn,
                "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
                id=review_id,
            )["body"]
        )

    def save_account(self, conn, review_id, account):
        self.store.execute(
            conn,
            "UPDATE contract_review_budget_accounts SET body=:body,version=version+1 "
            "WHERE review_id=:id",
            id=review_id,
            body=canonical(account),
        )

    def claim(self):
        with self.store.transaction() as conn:
            runtime = self.owner(conn)
            if runtime["slot_call_id"] is not None:
                return None
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_jobs WHERE status='queued' ORDER BY "
                "created_at,id LIMIT 1",
            )
            if row is None:
                return None
            frozen = json.loads(
                self.store.row(
                    conn, "SELECT body FROM contract_review_inputs WHERE id=:id", id=row["input_id"]
                )["body"]
            )
            profile = frozen["execution_profile"]
            if self.service.profiles.get(profile["profile_id"]) != profile:
                self._fail(conn, row, "RETRY_PROFILE_UNAVAILABLE")
                return None
            account = self.account(conn, row["review_id"])
            remaining = (
                account["grant"]["execution_seconds"]
                - account["execution_seconds_charged"]
                - account["execution_seconds_reserved"]
            )
            if (
                remaining <= 0
                or account["model_calls"] >= account["grant"]["model_calls"]
                or account["tool_actions"] >= account["grant"]["tool_actions"]
            ):
                self._fail(conn, row, "REVIEW_BUDGET_EXHAUSTED")
                return None
            reserved = min(profile["attempt_seconds"], remaining)
            timestamp = datetime.now(UTC)
            started, deadline = (
                timestamp.isoformat().replace("+00:00", "Z"),
                (timestamp + timedelta(seconds=reserved)).isoformat().replace("+00:00", "Z"),
            )
            token = identity("attempt")
            body = json.loads(row["body"])
            body.update(model_calls=0, tool_actions=0, time_reserved=reserved, time_settled=False)
            updated = self.store.execute(
                conn,
                "UPDATE contract_review_jobs SET "
                "status='running',owner_boot_id=:boot,attempt_token=:token,"
                "started_at=:started,deadline=:deadline,body=:body "
                "WHERE id=:id AND status='queued'",
                id=row["id"],
                boot=self.boot_id,
                token=token,
                started=started,
                deadline=deadline,
                body=canonical(body),
            )
            if updated.rowcount != 1:
                return None
            account["execution_seconds_reserved"] += reserved
            self.save_account(conn, row["review_id"], account)
            self.store.execute(
                conn,
                "UPDATE contract_reviews SET "
                "status='running',version=version+1,updated_at=:at WHERE id=:id",
                id=row["review_id"],
                at=started,
            )
            self.store.event(
                conn,
                row["review_id"],
                row["input_id"],
                row["id"],
                "job_claimed",
                {"deadline": deadline, "time_reserved": reserved},
            )
            sources = {}
            for source in conn.execute(
                text("SELECT * FROM contract_review_source_blobs WHERE snapshot_id=:snapshot"),
                {"snapshot": frozen["snapshot_id"]},
            ).mappings():
                sources[source["id"]] = {
                    "source_id": source["id"],
                    "path": source["path"],
                    "roles": json.loads(source["roles"]),
                    "body": source["raw_bytes"].decode("utf-8"),
                    "body_hash": source["body_hash"],
                }
            return {
                "job_id": row["id"],
                "review_id": row["review_id"],
                "input_id": row["input_id"],
                "attempt_token": token,
                "frozen": frozen,
                "sources": sources,
                "verification_evidence": [
                    self.service.verifications.record(
                        conn, row["review_id"], binding["evidence_id"]
                    )
                    for binding in frozen["verification_evidence_adoptions"]
                ],
                "deadline": deadline,
            }

    def reserve_call(self, context, role, payload, material_entries):
        profile = context["frozen"]["execution_profile"]
        if (
            payload["model"] != profile["model"]
            or payload["max_tokens"] != profile["max_output_tokens"]
        ):
            raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "实际模型参数与冻结 profile 不符。")
        if (
            sum(len(message["content"]) for message in payload["messages"])
            > profile["context_characters"]
        ):
            raise ReviewError("BUDGET_EXHAUSTED", "必要请求正文超过上下文上限。")
        with self.store.transaction() as conn:
            row = self.fence(conn, context)
            runtime = self.owner(conn)
            if runtime["slot_call_id"] is not None:
                raise ReviewError("CALL_RESULT_UNKNOWN", "本地执行尚未收尾。")
            job_body = json.loads(row["body"])
            account = self.account(conn, context["review_id"])
            if (
                job_body["model_calls"] >= profile["model_call_limit"]
                or account["model_calls"] >= account["grant"]["model_calls"]
            ):
                raise ReviewError("BUDGET_EXHAUSTED", "模型请求预算耗尽。")
            sequence = (
                self.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_steps WHERE job_id=:job",
                    job=context["job_id"],
                )["n"]
                + 1
            )
            call_id, step_id, instance_id = identity("call"), identity("step"), identity("io")
            logical = digest(
                {
                    "input_hash": context["frozen"]["input_hash"],
                    "role": role,
                    "sequence": sequence,
                    "payload": payload,
                }
            )
            projection = {
                "projection_id": identity("projection"),
                "logical_call_id": logical,
                "role": role,
                "input_hash": context["frozen"]["input_hash"],
                "profile_hash": context["frozen"]["profile_hash"],
                "payload": payload,
                "material_entries": material_entries,
                "projection_hash": digest(payload),
                "content_integrity": "complete",
                "created_at": now(),
            }
            body = {
                "review_id": context["review_id"],
                "input_id": context["input_id"],
                "owner_boot_id": self.boot_id,
                "execution_instance_id": instance_id,
                "adapter_kind": "synchronous_in_process",
                "process": self.process,
                "local_io_state": "not_started",
                "remote_outcome": "unknown",
                "projection": projection,
                "result": None,
                "acceptance": None,
                "usage": {"input_tokens": None, "output_tokens": None},
                "usage_reserved": {
                    "input_tokens": len(canonical(payload).encode("utf-8")),
                    "output_tokens": profile["max_output_tokens"],
                },
                "maintenance_evidence": [],
                "logical_call_id": logical,
            }
            self.store.reserve_records(
                conn, len(canonical(body).encode("utf-8")), context["job_id"]
            )
            self.store.execute(
                conn,
                "INSERT INTO contract_review_steps (id,job_id,step_seq,role,logical_call_id) "
                "VALUES (:id,:job,:seq,:role,:logical)",
                id=step_id,
                job=context["job_id"],
                seq=sequence,
                role=role,
                logical=logical,
            )
            self.store.execute(
                conn,
                "INSERT INTO contract_review_calls VALUES "
                "(:id,:job,:step,0,'intent_recorded',:body,1)",
                id=call_id,
                job=context["job_id"],
                step=step_id,
                body=canonical(body),
            )
            self.store.execute(
                conn,
                "INSERT INTO contract_review_budget_entries VALUES (:id,:review,:job,:call,:body)",
                id=call_id + ":reserve",
                review=context["review_id"],
                job=context["job_id"],
                call=call_id,
                body=canonical({"model_calls": 1, "usage_reserved": body["usage_reserved"]}),
            )
            account["model_calls"] += 1
            job_body["model_calls"] += 1
            self.save_account(conn, context["review_id"], account)
            self.refresh_usage(conn, context["review_id"])
            self.store.execute(
                conn,
                "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
                id=context["job_id"],
                body=canonical(job_body),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_runtime SET "
                "slot_call_id=:call,slot_execution_instance_id=:instance WHERE id=1",
                call=call_id,
                instance=instance_id,
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "request_projected",
                projection,
                call_id=call_id,
                logical_call_id=logical,
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "dispatch_intent",
                {"execution_instance_id": instance_id},
                call_id=call_id,
                logical_call_id=logical,
            )
            return call_id, instance_id

    def dispatch_started(self, context, call_id):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            call = self.store.row(
                conn, "SELECT * FROM contract_review_calls WHERE id=:id", id=call_id
            )
            body = json.loads(call["body"])
            body["local_io_state"] = "running"
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET "
                "status='dispatch_started',body=:body,version=version+1 WHERE id=:id AND "
                "status='intent_recorded'",
                id=call_id,
                body=canonical(body),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "dispatch_started",
                {"execution_instance_id": body["execution_instance_id"]},
                call_id=call_id,
            )

    def abort_unstarted(self, call_id, instance_id):
        """Settle a revoked local start gate; never infer this from missing logs."""
        with self.store.transaction() as conn:
            self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_review_calls WHERE id=:id", id=call_id
            )
            if row is None:
                return False
            body = json.loads(row["body"])
            if (
                body["execution_instance_id"] != instance_id
                or body["owner_boot_id"] != self.boot_id
                or body.get("adapter_entered") is False
            ):
                return False
            if row["status"] not in ("intent_recorded", "dispatch_started", "UNKNOWN"):
                return False
            job = self.store.row(
                conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=row["job_id"]
            )
            job_body = json.loads(job["body"])
            account = self.account(conn, body["review_id"])
            released = int(body.get("kind", "model") == "model")
            account["model_calls"] -= released
            job_body["model_calls"] -= released
            if released and body.get("child_task_id"):
                child = self.store.row(
                    conn,
                    "SELECT body FROM contract_review_child_tasks WHERE id=:id",
                    id=body["child_task_id"],
                )
                child_body = json.loads(child["body"])
                child_body["model_calls"] -= 1
                self.store.execute(
                    conn,
                    "UPDATE contract_review_child_tasks SET body=:body WHERE id=:id",
                    id=body["child_task_id"],
                    body=canonical(child_body),
                )
            body.update(
                adapter_entered=False,
                local_io_state="quiesced",
                remote_outcome="not_applicable",
                usage={"input_tokens": 0, "output_tokens": 0},
                usage_reserved={"input_tokens": 0, "output_tokens": 0},
                acceptance={"accepted": False, "reason": "ADAPTER_NOT_ENTERED"},
            )
            body["maintenance_evidence"].append(
                {"kind": "start_gate_revoked", "owner_boot_id": self.boot_id, "at": now()}
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET status='failed',body=:body,version=version+1 "
                "WHERE id=:id AND version=:version",
                id=call_id,
                version=row["version"],
                body=canonical(body),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_runtime SET "
                "slot_call_id=NULL,slot_execution_instance_id=NULL "
                "WHERE id=1 AND slot_call_id=:call AND slot_execution_instance_id=:instance",
                call=call_id,
                instance=instance_id,
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
                id=row["job_id"],
                body=canonical(job_body),
            )
            self.save_account(conn, body["review_id"], account)
            self.refresh_usage(conn, body["review_id"])
            self.store.execute(
                conn,
                "INSERT INTO contract_review_budget_entries VALUES (:id,:review,:job,:call,:body)",
                id=call_id + ":not_started",
                review=body["review_id"],
                job=row["job_id"],
                call=call_id,
                body=canonical(
                    {
                        "model_calls": -released,
                        "usage": body["usage"],
                        "evidence": "start_gate_revoked",
                        "owner_boot_id": self.boot_id,
                    }
                ),
            )
            self.store.event(
                conn,
                body["review_id"],
                body["input_id"],
                row["job_id"],
                "call_quiesced",
                {
                    "evidence": "start_gate_revoked",
                    "adapter_entered": False,
                    "model_calls_released": released,
                },
                call_id=call_id,
            )
            return True

    def settle_call(
        self,
        call_id,
        instance_id,
        *,
        usage=None,
        quiesced=False,
        evidence=None,
        remote_outcome=None,
    ):
        """Current-owner maintenance only; terminal business state is never revived."""
        with self.store.transaction() as conn:
            runtime = self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_review_calls WHERE id=:id", id=call_id
            )
            if row is None:
                return False
            body = json.loads(row["body"])
            if body["execution_instance_id"] != instance_id:
                return False
            if quiesced and evidence not in (
                "wrapper_thread_exited",
                "original_process_exited",
                "adapter_not_entered",
            ):
                return False
            changed = False
            usage_changed = False
            if (
                remote_outcome in ("known", "not_applicable")
                and body["remote_outcome"] == "unknown"
            ):
                body["remote_outcome"] = remote_outcome
                changed = True
            for dimension in ("input_tokens", "output_tokens"):
                value = (usage or {}).get(dimension)
                old_value = body["usage"][dimension]
                if (
                    type(value) is int
                    and value >= 0
                    and old_value is not None
                    and value != old_value
                ):
                    conflict = {"dimension": dimension, "recorded": old_value, "received": value}
                    conflicts = body.setdefault("usage_conflicts", [])
                    if conflict not in conflicts and len(conflicts) < 20:
                        conflicts.append(conflict)
                        changed = True
                if type(value) is int and value >= 0 and body["usage"][dimension] is None:
                    body["usage"][dimension] = value
                    body["usage_reserved"][dimension] = 0
                    changed = True
                    usage_changed = True
                    self.store.execute(
                        conn,
                        "INSERT INTO contract_review_budget_entries VALUES "
                        "(:id,:review,:job,:call,:body)",
                        id=call_id + ":" + dimension,
                        review=body["review_id"],
                        job=row["job_id"],
                        call=call_id,
                        body=canonical(
                            {
                                dimension: value,
                                "evidence": "adapter_result",
                                "owner_boot_id": self.boot_id,
                            }
                        ),
                    )
            if quiesced and body["local_io_state"] != "quiesced":
                body["local_io_state"] = "quiesced"
                body["maintenance_evidence"].append(
                    {"kind": evidence, "owner_boot_id": self.boot_id, "at": now()}
                )
                changed = True
            if not changed:
                return False
            if (
                runtime["slot_call_id"] == call_id
                and runtime["slot_execution_instance_id"] == instance_id
                and body["local_io_state"] == "quiesced"
            ):
                self.store.execute(
                    conn,
                    "UPDATE contract_review_runtime SET "
                    "slot_call_id=NULL,slot_execution_instance_id=NULL WHERE id=1 AND "
                    "slot_call_id=:call AND slot_execution_instance_id=:instance",
                    call=call_id,
                    instance=instance_id,
                )
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET body=:body,version=version+1 WHERE "
                "id=:id AND version=:version",
                id=call_id,
                version=row["version"],
                body=canonical(body),
            )
            if usage_changed:
                self.refresh_usage(conn, body["review_id"])
                self.store.event(
                    conn,
                    body["review_id"],
                    body["input_id"],
                    row["job_id"],
                    "usage_settled",
                    {"usage": body["usage"], "usage_reserved": body["usage_reserved"]},
                    call_id=call_id,
                )
            self.store.event(
                conn,
                body["review_id"],
                body["input_id"],
                row["job_id"],
                "call_quiesced" if quiesced else "usage_settled",
                {
                    "execution_instance_id": instance_id,
                    "local_io_state": body["local_io_state"],
                    "usage": body["usage"],
                    "usage_reserved": body["usage_reserved"],
                    "evidence": evidence,
                },
                call_id=call_id,
            )
            return True

    def refresh_usage(self, conn, review_id):
        calls = [
            json.loads(row[0])
            for row in conn.execute(
                text(
                    "SELECT c.body FROM contract_review_calls c JOIN contract_review_jobs j "
                    "ON j.id=c.job_id WHERE j.review_id=:review"
                ),
                {"review": review_id},
            )
        ]
        calls = [call for call in calls if call.get("kind", "model") == "model"]
        account = self.account(conn, review_id)
        known_dimensions = 0
        account["token_ledger"] = {}
        for dimension in ("input_tokens", "output_tokens"):
            known = [
                call["usage"][dimension] for call in calls if call["usage"][dimension] is not None
            ]
            known_dimensions += len(known)
            account[dimension] = sum(known) if len(known) == len(calls) else None
            account["token_ledger"][dimension] = {
                "known": sum(known),
                "unknown_calls": len(calls) - len(known),
                "reserved": sum(call["usage_reserved"][dimension] for call in calls),
            }
        all_known = known_dimensions == 2 * len(calls)
        account["usage_status"] = (
            ("known_zero" if account["input_tokens"] == account["output_tokens"] == 0 else "known")
            if all_known
            else "partial"
            if known_dimensions
            else "unknown"
        )
        self.save_account(conn, review_id, account)

    def reconcile_dead_process(self):
        with self.store.read() as conn:
            runtime = self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_review_calls WHERE id=:id", id=runtime["slot_call_id"]
            )
        if row:
            body = json.loads(row["body"])
            if original_process_exited(body["process"]):
                self.settle_call(
                    row["id"],
                    body["execution_instance_id"],
                    quiesced=True,
                    evidence="original_process_exited",
                )

    def record_result(self, context, call_id, result, *, accepted, reason):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_calls WHERE id=:id AND job_id=:job",
                id=call_id,
                job=context["job_id"],
            )
            if row is None:
                raise ReviewError("STALE_EXECUTION", "调用不属于当前作业。")
            body = json.loads(row["body"])
            body.update(
                result=result,
                remote_outcome="not_applicable" if body.get("kind") == "tool" else "known",
                acceptance={
                    "accepted": accepted,
                    "reason": reason,
                    "result_hash": digest(result),
                    "owner_boot_id": self.boot_id,
                },
            )
            self.store.reserve_records(
                conn, len(canonical(result).encode("utf-8")), context["job_id"]
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET "
                "status=:status,body=:body,version=version+1 WHERE id=:id",
                id=call_id,
                status="accepted" if accepted else "rejected",
                body=canonical(body),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "result_accepted" if accepted else "result_rejected",
                {"result": result, "acceptance": body["acceptance"]},
                call_id=call_id,
            )

    def _fail(self, conn, row, code, interrupted=False):
        status = "interrupted" if interrupted else "failed"
        self.store.execute(
            conn,
            "UPDATE contract_review_jobs SET "
            "status=:status,error_code=:code,finished_at=:at WHERE id=:id",
            id=row["id"],
            status=status,
            code=code,
            at=now(),
        )
        self.store.execute(
            conn,
            "UPDATE contract_reviews SET "
            "status='failed',current_report_id=NULL,version=version+1,updated_at=:at "
            "WHERE id=:id AND active_job_id=:job AND current_input_id=:input",
            id=row["review_id"],
            job=row["id"],
            input=row["input_id"],
            at=now(),
        )
        self.store.event(
            conn,
            row["review_id"],
            row["input_id"],
            row["id"],
            "job_interrupted" if interrupted else "job_failed",
            {"error_code": code},
        )

    def fail(self, context, code, elapsed=None):
        with self.store.transaction() as conn:
            self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=context["job_id"]
            )
            if row["status"] != "running" or row["attempt_token"] != context["attempt_token"]:
                return
            self._fail(conn, row, code, interrupted=code == "INTERRUPTED")
            calls = (
                conn.execute(
                    text(
                        "SELECT * FROM contract_review_calls WHERE job_id=:job AND status "
                        "IN ('intent_recorded','dispatch_started')"
                    ),
                    {"job": row["id"]},
                )
                .mappings()
                .all()
            )
            for call in calls:
                body = json.loads(call["body"])
                body["remote_outcome"] = "unknown"
                if body["local_io_state"] != "quiesced":
                    body["local_io_state"] = "unconfirmed"
                self.store.execute(
                    conn,
                    "UPDATE contract_review_calls SET "
                    "status='UNKNOWN',body=:body,version=version+1 WHERE id=:id",
                    id=call["id"],
                    body=canonical(body),
                )
            if elapsed is not None and not self.owner(conn)["slot_call_id"]:
                self.settle_time(conn, row, elapsed)

    def settle_time(self, conn, row, elapsed):
        body = json.loads(row["body"])
        if body.get("time_settled"):
            return
        account = self.account(conn, row["review_id"])
        account["execution_seconds_reserved"] -= body["time_reserved"]
        account["execution_seconds_charged"] += max(0, elapsed)
        body["time_settled"] = True
        self.save_account(conn, row["review_id"], account)
        self.store.execute(
            conn,
            "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
            id=row["id"],
            body=canonical(body),
        )

    def commit_report(self, context, report, quality, elapsed):
        with self.store.transaction() as conn:
            row = self.fence(conn, context)
            frozen = context["frozen"]
            report_id = identity("report")
            number = (
                self.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_reports WHERE review_id=:id",
                    id=context["review_id"],
                )["n"]
                + 1
            )
            envelope = {
                "schema_version": "contract-review-report-envelope.v2.1",
                "review_id": context["review_id"],
                "input_revision_id": context["input_id"],
                "job_id": context["job_id"],
                "report_revision_id": report_id,
                "target_api_version": frozen["original_request"]["target_api_version"],
                "snapshot_id": frozen["snapshot_id"],
                "commit_sha": frozen["commit_sha"],
                "adopted_ruleset_version": None,
                "verification_mode": "static_only",
                "execution_mode": frozen["execution_profile"]["execution_mode"],
                "rules": [
                    {
                        **adoption,
                        "body": select_text(
                            context["sources"][adoption["body_ref"]["source_id"]]["body"],
                            adoption["body_ref"]["selector"],
                        ),
                        "report_usage": next(
                            (
                                item
                                for item in report["rule_uses"]
                                if item["adoption_id"] == adoption["adoption_id"]
                            ),
                            None,
                        ),
                    }
                    for adoption in frozen["adoption_records"]
                ],
                "check_manifest": frozen["check_manifest"],
                "payload": report,
                "quality": quality,
                "verification_evidence_summary": [
                    {
                        "evidence_id": record["evidence_id"],
                        "provider": record["provider"],
                        "status": record["status"],
                        "origin": view["origin"],
                        "current_adoption": view["current_adoption"],
                        "current_applicability": view["current_applicability"],
                        "applicable_to_current_input": view["applicable_to_current_input"],
                    }
                    for record in context["verification_evidence"]
                    for view in [self.service.verifications.view(record, frozen)]
                ],
                "created_at": now(),
            }
            status = (
                "awaiting_decision"
                if any(q["blocking"] for q in report["questions"])
                else "completed_degraded"
                if quality["level"] == "degraded"
                else "completed"
            )
            body = canonical(envelope)
            self.store.reserve_records(conn, len(body.encode("utf-8")), context["job_id"])
            self.store.execute(
                conn,
                "INSERT INTO contract_review_reports VALUES "
                "(:id,:review,:input,:job,:no,:body,:created)",
                id=report_id,
                review=context["review_id"],
                input=context["input_id"],
                job=context["job_id"],
                no=number,
                body=body,
                created=now(),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_jobs SET status='completed',finished_at=:at WHERE id=:id",
                id=context["job_id"],
                at=now(),
            )
            self.store.execute(
                conn,
                "UPDATE contract_reviews SET "
                "status=:status,current_report_id=:report,version=version+1,"
                "updated_at=:at WHERE id=:id",
                id=context["review_id"],
                status=status,
                report=report_id,
                at=now(),
            )
            self.settle_time(conn, row, elapsed)
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "report_committed",
                {"report_revision_id": report_id, "quality": quality},
            )
            return envelope

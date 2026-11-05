"""Discovery-owned calls sharing the existing worker boot and physical I/O fence."""

import json
import time
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.process_identity import original_process_exited


class ImpactLedger:
    def __init__(self, review_ledger):
        self.owner_ledger = review_ledger
        self.service, self.store = review_ledger.service.impacts, review_ledger.store

    @property
    def boot_id(self):
        return self.owner_ledger.boot_id

    def owner(self, conn):
        return self.owner_ledger.owner(conn)

    def start(self):
        with self.store.transaction() as conn:
            self.owner(conn)
            rows = conn.execute(
                text("SELECT * FROM contract_impact_discoveries WHERE status='running'")
            )
            for row in rows.mappings().all():
                body = json.loads(row["body"])
                body.update(error_code="INTERRUPTED", finished_at=now())
                self.service.put(conn, row, body, status="interrupted")
                self.service.event(conn, row["id"], "discovery_failed", dict(code="INTERRUPTED"))
            for row in (
                conn.execute(
                    text(
                        "SELECT * FROM contract_impact_calls WHERE status "
                        "IN ('intent_recorded','dispatch_started')"
                    )
                )
                .mappings()
                .all()
            ):
                body = json.loads(row["body"])
                if body["local_io_state"] != "quiesced":
                    body["local_io_state"] = "unconfirmed"
                self.call_put(conn, row, body, "UNKNOWN")
            terminal = (
                conn.execute(
                    text(
                        "SELECT * FROM contract_impact_discoveries "
                        "WHERE status IN ('failed','interrupted') "
                        "AND json_extract(body,'$.budget.execution_seconds_reserved')>0"
                    )
                )
                .mappings()
                .all()
            )
            for row in terminal:
                calls = conn.execute(
                    text("SELECT body FROM contract_impact_calls WHERE discovery_id=:id"),
                    dict(id=row["id"]),
                ).all()
                if all(json.loads(call[0])["local_io_state"] == "quiesced" for call in calls):
                    body = json.loads(row["body"])
                    elapsed = (
                        datetime.now(UTC) - datetime.fromisoformat(body["started_at"])
                    ).total_seconds()
                    self.settle_time(conn, row, elapsed)
        self.reconcile_dead_process()

    def fence(self, conn, context):
        self.owner(conn)
        row = self.service.require(conn, context["discovery_id"])
        body = json.loads(row["body"])
        if (
            row["status"] != "running"
            or body.get("owner_boot_id") != self.boot_id
            or body.get("attempt_token") != context["attempt_token"]
        ):
            raise ReviewError("STALE_EXECUTION", "发现执行权已失效。")
        if datetime.now(UTC) >= datetime.fromisoformat(body["deadline"].replace("Z", "+00:00")):
            raise ReviewError("DEADLINE_EXCEEDED", "发现执行期限已到。")
        return row, body

    def claim(self, *, _conn=None):
        with self.store.transaction() if _conn is None else nullcontext(_conn) as conn:
            runtime = self.owner(conn)
            if runtime["slot_call_id"] or runtime["slot_discovery_call_id"]:
                return None
            row = self.store.row(
                conn,
                "SELECT * FROM contract_impact_discoveries "
                "WHERE status='queued' ORDER BY created_at,id LIMIT 1",
            )
            if row is None:
                return None
            body = json.loads(row["body"])
            frozen = body["frozen"]
            profile = frozen["execution_profile"]
            if (
                digest({key: value for key, value in frozen.items() if key != "input_hash"})
                != frozen["input_hash"]
                or digest(profile) != frozen["profile_hash"]
            ):
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "发现冻结输入已损坏。")
            if self.service.profiles.get(profile["profile_id"]) != profile:
                body.update(error_code="RETRY_PROFILE_UNAVAILABLE", finished_at=now())
                self.service.put(conn, row, body, status="failed")
                self.service.event(
                    conn, row["id"], "discovery_failed", dict(code="RETRY_PROFILE_UNAVAILABLE")
                )
                return None
            snapshot = self.service.snapshot(conn, body)
            timestamp = datetime.now(UTC)
            body.update(
                owner_boot_id=self.boot_id,
                attempt_token=identity("iattempt"),
                started_at=timestamp.isoformat(),
                deadline=(timestamp + timedelta(seconds=profile["attempt_seconds"])).isoformat(),
            )
            body["budget"]["execution_seconds_reserved"] = profile["attempt_seconds"]
            self.service.put(conn, row, body, status="running")
            self.service.event(
                conn, row["id"], "discovery_claimed", dict(deadline=body["deadline"])
            )
            return dict(
                work_kind="impact",
                discovery_id=row["id"],
                frozen=frozen,
                attempt_token=body["attempt_token"],
                deadline=body["deadline"],
                started_monotonic=time.monotonic(),
                sources={source["source_id"]: source for source in snapshot["files"]},
            )

    def call_put(self, conn, row, body, status=None):
        raw = canonical(body)
        self.service.charge(
            conn, row["discovery_id"], max(0, len(raw.encode()) - len(row["body"].encode()))
        )
        self.store.execute(
            conn,
            "UPDATE contract_impact_calls SET body=:body,status=:status WHERE id=:id",
            id=row["id"],
            body=raw,
            status=status or row["status"],
        )

    def reserve_call(
        self, context, role, payload, material_entries, *, kind="model", retry_of=None
    ):
        if retry_of is not None:
            raise ReviewError("ACTION_NOT_ALLOWED", "发现阶段不重试物理调用。")
        profile = context["frozen"]["execution_profile"]
        if kind == "model" and (
            payload["model"] != profile["model"]
            or payload["max_tokens"] != profile["max_output_tokens"]
            or sum(len(message["content"]) for message in payload["messages"])
            > profile["context_characters"]
        ):
            raise ReviewError("BUDGET_EXHAUSTED", "发现请求超出冻结参数或上下文预算。")
        with self.store.transaction() as conn:
            row, body = self.fence(conn, context)
            runtime = self.owner(conn)
            if runtime["slot_call_id"] or runtime["slot_discovery_call_id"]:
                raise ReviewError("CALL_RESULT_UNKNOWN", "共享物理调用尚未收尾。")
            dimension = "model_calls" if kind == "model" else "tool_actions"
            limit = profile["model_call_limit" if kind == "model" else "tool_action_limit"]
            if body["budget"][dimension] >= limit:
                raise ReviewError("BUDGET_EXHAUSTED", "发现调用额度耗尽。")
            if kind == "model":
                # A retained denial traceback must not retain an active SQLite read cursor.
                calls = conn.execute(
                    text("SELECT body FROM contract_impact_calls WHERE discovery_id=:id"),
                    dict(id=row["id"]),
                ).all()
                if any(
                    value["kind"] == "model" and any(v is None for v in value["usage"].values())
                    for value in (json.loads(call[0]) for call in calls)
                ):
                    raise ReviewError("USAGE_UNKNOWN", "先前模型调用用量未知，不继续派发。")
            call_id, instance = identity("icall"), identity("io")
            projection = dict(
                projection_id=identity("iprojection"),
                role=role,
                input_hash=context["frozen"]["input_hash"],
                profile_hash=context["frozen"]["profile_hash"],
                payload=payload,
                material_entries=material_entries,
                projection_hash=digest(payload),
                logical_call_id=digest(dict(discovery=row["id"], call=call_id, payload=payload)),
            )
            call = dict(
                kind=kind,
                owner_boot_id=self.boot_id,
                execution_instance_id=instance,
                process=self.owner_ledger.process,
                local_io_state="not_started",
                remote_outcome="unknown",
                projection=projection,
                usage=dict(input_tokens=None, output_tokens=None) if kind == "model" else {},
                usage_reserved=dict(input_tokens=None, output_tokens=profile["max_output_tokens"])
                if kind == "model"
                else {},
                maintenance_evidence=[],
                result=None,
                acceptance=None,
            )
            self.service.charge(conn, row["id"], len(canonical(call).encode()))
            self.store.execute(
                conn,
                "INSERT INTO contract_impact_calls VALUES (:id,:discovery,'intent_recorded',:body)",
                id=call_id,
                discovery=row["id"],
                body=canonical(call),
            )
            body["budget"][dimension] += 1
            self.service.put(conn, row, body)
            updated = self.store.execute(
                conn,
                "UPDATE contract_review_runtime SET "
                "slot_discovery_call_id=:call,slot_execution_instance_id=:instance WHERE id=1 "
                "AND slot_call_id IS NULL AND slot_discovery_call_id IS NULL",
                call=call_id,
                instance=instance,
            )
            if updated.rowcount != 1:
                raise ReviewError("CALL_RESULT_UNKNOWN", "共享物理槽已被占用。")
            self.service.event(conn, row["id"], "request_projected", projection)
            self.service.event(
                conn,
                row["id"],
                "dispatch_intent",
                dict(call_id=call_id, execution_instance_id=instance),
            )
            return call_id, instance

    def dispatch_started(self, context, call_id):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_impact_calls WHERE id=:id AND discovery_id=:discovery",
                id=call_id,
                discovery=context["discovery_id"],
            )
            runtime = self.owner(conn)
            if row is None or row["status"] != "intent_recorded":
                raise ReviewError("STALE_EXECUTION", "发现调用不是未派发意图。")
            body = json.loads(row["body"])
            if (
                runtime["slot_discovery_call_id"] != call_id
                or runtime["slot_call_id"]
                or runtime["slot_execution_instance_id"] != body["execution_instance_id"]
            ):
                raise ReviewError("STALE_EXECUTION", "发现调用租约已变化。")
            body["local_io_state"] = "running"
            self.call_put(conn, row, body, "dispatch_started")
            self.service.event(
                conn, context["discovery_id"], "dispatch_started", dict(call_id=call_id)
            )

    def settle_call(
        self,
        call_id,
        instance_id,
        *,
        usage=None,
        quiesced=False,
        evidence=None,
        remote_outcome=None,
        _conn=None,
    ):
        with self.store.transaction() if _conn is None else nullcontext(_conn) as conn:
            runtime = self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_impact_calls WHERE id=:id", id=call_id
            )
            if row is None:
                return False
            body = json.loads(row["body"])
            if body["execution_instance_id"] != instance_id:
                return False
            if quiesced and evidence not in {
                "wrapper_thread_exited",
                "original_process_exited",
                "adapter_not_entered",
            }:
                return False
            before = canonical(body)
            for dimension in body["usage"]:
                value = (usage or {}).get(dimension)
                if type(value) is int and value >= 0:
                    old = body["usage"][dimension]
                    if old is None:
                        body["usage"][dimension] = value
                        body["usage_reserved"][dimension] = 0
                    elif old != value:
                        conflict = dict(dimension=dimension, recorded=old, received=value)
                        conflicts = body.setdefault("usage_conflicts", [])
                        if conflict not in conflicts and len(conflicts) < 20:
                            conflicts.append(conflict)
            if remote_outcome in {"known", "not_applicable"}:
                body["remote_outcome"] = remote_outcome
            if quiesced and body["local_io_state"] != "quiesced":
                body["local_io_state"] = "quiesced"
                body["maintenance_evidence"].append(dict(kind=evidence, at=now()))
            if canonical(body) == before:
                return False
            self.call_put(conn, row, body)
            if (
                body["local_io_state"] == "quiesced"
                and runtime["slot_discovery_call_id"] == call_id
                and runtime["slot_execution_instance_id"] == instance_id
            ):
                self.store.execute(
                    conn,
                    "UPDATE contract_review_runtime SET "
                    "slot_discovery_call_id=NULL,slot_execution_instance_id=NULL WHERE id=1 "
                    "AND slot_discovery_call_id=:call AND slot_execution_instance_id=:instance",
                    call=call_id,
                    instance=instance_id,
                )
            self.service.event(
                conn,
                row["discovery_id"],
                "call_quiesced" if quiesced else "usage_settled",
                dict(call_id=call_id, usage=body["usage"], local_io_state=body["local_io_state"]),
            )
            return True

    def abort_unstarted(self, call_id, instance_id):
        with self.store.transaction() as conn:
            self.owner(conn)
            row = self.store.row(
                conn, "SELECT * FROM contract_impact_calls WHERE id=:id", id=call_id
            )
            if row is None or row["status"] not in {
                "intent_recorded",
                "dispatch_started",
                "UNKNOWN",
            }:
                return False
            body = json.loads(row["body"])
            if (
                body["execution_instance_id"] != instance_id
                or body["owner_boot_id"] != self.boot_id
            ):
                return False
            body.update(
                adapter_entered=False, acceptance=dict(accepted=False, reason="ADAPTER_NOT_ENTERED")
            )
            self.call_put(conn, row, body, "failed")
            return self.settle_call(
                call_id,
                instance_id,
                usage=dict(input_tokens=0, output_tokens=0),
                quiesced=True,
                evidence="adapter_not_entered",
                remote_outcome="not_applicable",
                _conn=conn,
            )

    def record_result(self, context, call_id, result, *, accepted, reason):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_impact_calls WHERE id=:id AND discovery_id=:discovery",
                id=call_id,
                discovery=context["discovery_id"],
            )
            if row is None:
                raise ReviewError("STALE_EXECUTION", "调用不属于该发现。")
            body = json.loads(row["body"])
            if body["local_io_state"] != "quiesced" or row["status"] != "dispatch_started":
                raise ReviewError("STALE_EXECUTION", "调用不可重复接受或尚未收尾。")
            body.update(result=result, acceptance=dict(accepted=accepted, reason=reason))
            self.call_put(conn, row, body, "accepted" if accepted else "rejected")
            self.service.event(
                conn,
                context["discovery_id"],
                "result_accepted" if accepted else "result_rejected",
                dict(call_id=call_id, reason=reason, result=result),
            )

    def record_failure(self, context, call_id, error):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_impact_calls WHERE id=:id AND discovery_id=:discovery",
                id=call_id,
                discovery=context["discovery_id"],
            )
            if row:
                body = json.loads(row["body"])
                body["failure"] = dict(code=error.code, remote_outcome=error.remote_outcome)
                self.call_put(conn, row, body, "failed")
                self.service.event(
                    conn,
                    context["discovery_id"],
                    "dependency_failed",
                    dict(call_id=call_id, code=error.code),
                )

    def settle_time(self, conn, row, elapsed):
        body = json.loads(row["body"])
        reserved = body["budget"]["execution_seconds_reserved"]
        if reserved:
            body["budget"]["execution_seconds_charged"] += min(reserved, max(0, elapsed))
            body["budget"]["execution_seconds_reserved"] = 0
            self.service.put(conn, row, body)

    def finish(self, context, candidates, unresolved):
        with self.store.transaction() as conn:
            row, body = self.fence(conn, context)
            catalog = dict(candidates=candidates, unresolved=unresolved)
            catalog["catalog_hash"] = digest(catalog)
            body.update(catalog=catalog, finished_at=now())
            reserved = body["budget"]["execution_seconds_reserved"]
            body["budget"]["execution_seconds_charged"] = min(
                reserved, max(0, time.monotonic() - context["started_monotonic"])
            )
            body["budget"]["execution_seconds_reserved"] = 0
            self.service.put(conn, row, body, status="completed")
            self.service.event(conn, row["id"], "candidates_accepted", catalog)

    def fail(self, context, code, elapsed=None):
        with self.store.transaction() as conn:
            runtime = self.owner(conn)
            row = self.service.require(conn, context["discovery_id"])
            body = json.loads(row["body"])
            if row["status"] != "running" or body.get("attempt_token") != context["attempt_token"]:
                return
            body.update(error_code=code, finished_at=now())
            if not runtime["slot_discovery_call_id"]:
                reserved = body["budget"]["execution_seconds_reserved"]
                body["budget"]["execution_seconds_charged"] = min(reserved, max(0, elapsed or 0))
                body["budget"]["execution_seconds_reserved"] = 0
            self.service.put(
                conn, row, body, status="interrupted" if code == "INTERRUPTED" else "failed"
            )
            for call in (
                conn.execute(
                    text(
                        "SELECT * FROM contract_impact_calls "
                        "WHERE discovery_id=:id AND status IN "
                        "('intent_recorded','dispatch_started')"
                    ),
                    dict(id=row["id"]),
                )
                .mappings()
                .all()
            ):
                value = json.loads(call["body"])
                if value["local_io_state"] != "quiesced":
                    value["local_io_state"] = "unconfirmed"
                self.call_put(conn, call, value, "UNKNOWN")
            self.service.event(conn, row["id"], "discovery_failed", dict(code=code))

    def reconcile_dead_process(self):
        with self.store.read() as conn:
            runtime = self.owner(conn)
            call = self.store.row(
                conn,
                "SELECT * FROM contract_impact_calls WHERE id=:id",
                id=runtime["slot_discovery_call_id"],
            )
        if call:
            body = json.loads(call["body"])
            if original_process_exited(body["process"]):
                self.settle_call(
                    call["id"],
                    body["execution_instance_id"],
                    quiesced=True,
                    evidence="original_process_exited",
                )
                with self.store.transaction() as conn:
                    self.owner(conn)
                    row = self.service.require(conn, call["discovery_id"])
                    current = json.loads(row["body"])
                    if row["status"] in {"failed", "interrupted"} and current["started_at"]:
                        elapsed = (
                            datetime.now(UTC) - datetime.fromisoformat(current["started_at"])
                        ).total_seconds()
                        self.settle_time(conn, row, elapsed)

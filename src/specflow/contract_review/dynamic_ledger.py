"""Dynamic actions and one-level child records on the existing fenced ledger."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.execution import ExecutionLedger


class DynamicLedger(ExecutionLedger):
    def fence(self, conn, context):
        row = super().fence(conn, context)
        if context.get("child_id"):
            child = self.store.row(
                conn,
                "SELECT * FROM contract_review_child_tasks WHERE id=:id AND job_id=:job",
                id=context["child_id"],
                job=context["job_id"],
            )
            if child is None or child["status"] != "running":
                raise ReviewError("STALE_EXECUTION", "子任务执行权已失效。")
            if datetime.now(UTC) >= datetime.fromisoformat(
                json.loads(child["body"])["deadline"].replace("Z", "+00:00")
            ):
                raise ReviewError("CHILD_DEADLINE_EXCEEDED", "子任务期限已到。")
        return row

    def start(self):
        super().start()
        with self.store.transaction() as conn:
            self.owner(conn)
            conn.exec_driver_sql(
                "UPDATE contract_review_child_tasks SET status='interrupted' WHERE status='running'"
            )

    def reserve_call(
        self, context, role, payload, material_entries, *, kind="model", retry_of=None
    ):
        if context["frozen"]["execution_profile"]["engine_version"] == "contract-review-engine.v1":
            return super().reserve_call(context, role, payload, material_entries)
        profile = context["frozen"]["execution_profile"]
        if kind == "model":
            if (
                payload["model"] != profile["model"]
                or payload["max_tokens"] != profile["max_output_tokens"]
            ):
                raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "实际请求与冻结模型配置不符。")
            if (
                sum(len(message["content"]) for message in payload["messages"])
                > profile["context_characters"]
            ):
                raise ReviewError("BUDGET_EXHAUSTED", "实际请求超过冻结上下文上限。")
        with self.store.transaction() as conn:
            row = self.fence(conn, context)
            if self.owner(conn)["slot_call_id"] is not None:
                raise ReviewError("CALL_RESULT_UNKNOWN", "本地执行尚未收尾。")
            job = json.loads(row["body"])
            account = self.account(conn, context["review_id"])
            child = None
            if context.get("child_id"):
                child = json.loads(
                    self.store.row(
                        conn,
                        "SELECT body FROM contract_review_child_tasks WHERE id=:id",
                        id=context["child_id"],
                    )["body"]
                )
            if kind == "model":
                if (
                    job["model_calls"] >= profile["model_call_limit"]
                    or account["model_calls"] >= account["grant"]["model_calls"]
                ):
                    raise ReviewError("BUDGET_EXHAUSTED", "父子共享模型预算耗尽。")
                if child and child["model_calls"] >= profile["child_model_limit"]:
                    raise ReviewError("CHILD_BUDGET_EXHAUSTED", "子任务模型预算耗尽。")
            call_id, instance_id = identity("call"), identity("io")
            if retry_of:
                prior = self.store.row(
                    conn,
                    "SELECT * FROM contract_review_calls WHERE id=:id AND job_id=:job",
                    id=retry_of,
                    job=context["job_id"],
                )
                if prior is None:
                    raise ReviewError("ACTION_NOT_ALLOWED", "依赖重试归属无效。")
                previous = json.loads(prior["body"])
                if (
                    prior["physical_retry_no"] != 0
                    or previous["projection"]["payload"] != payload
                    or previous["local_io_state"] != "quiesced"
                    or previous.get("child_task_id") != context.get("child_id")
                    or previous.get("kind") != kind
                    or not previous.get("failure", {}).get("retryable")
                ):
                    raise ReviewError("ACTION_NOT_ALLOWED", "依赖重试条件不成立。")
                step_id, logical, retry_no = prior["step_id"], previous["logical_call_id"], 1
            else:
                sequence = (
                    self.store.row(
                        conn,
                        "SELECT count(*) AS n FROM contract_review_steps WHERE job_id=:job",
                        job=context["job_id"],
                    )["n"]
                    + 1
                )
                step_id, retry_no = identity("step"), 0
                logical = digest(
                    {
                        "input_hash": context["frozen"]["input_hash"],
                        "role": role,
                        "scope": context.get("scope_fingerprint"),
                        "sequence": sequence,
                        "payload": payload,
                    }
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
            projection = {
                "projection_id": identity("projection"),
                "logical_call_id": logical,
                "role": role,
                "child_task_id": context.get("child_id"),
                "input_hash": context["frozen"]["input_hash"],
                "profile_hash": context["frozen"]["profile_hash"],
                "payload": payload,
                "material_entries": material_entries,
                "projection_hash": digest(payload),
                "content_integrity": "complete",
                "created_at": now(),
            }
            body = {
                "kind": kind,
                "review_id": context["review_id"],
                "input_id": context["input_id"],
                "owner_boot_id": self.boot_id,
                "execution_instance_id": instance_id,
                "adapter_kind": "synchronous_in_process",
                "process": self.process,
                "local_io_state": "not_started",
                "remote_outcome": "unknown" if kind == "model" else "not_applicable",
                "projection": projection,
                "result": None,
                "acceptance": None,
                "usage": {
                    "input_tokens": None if kind == "model" else 0,
                    "output_tokens": None if kind == "model" else 0,
                },
                "usage_reserved": {
                    "input_tokens": len(canonical(payload).encode()) if kind == "model" else 0,
                    "output_tokens": profile["max_output_tokens"] if kind == "model" else 0,
                },
                "maintenance_evidence": [],
                "logical_call_id": logical,
                "child_task_id": context.get("child_id"),
                "parent_call_id": context.get("parent_call_id"),
            }
            self.store.reserve_records(conn, len(canonical(body).encode()), context["job_id"])
            self.store.execute(
                conn,
                "INSERT INTO contract_review_calls VALUES (:id,:job,:step,:retry,'intent_reco"
                "rded',:body,1)",
                id=call_id,
                job=context["job_id"],
                step=step_id,
                retry=retry_no,
                body=canonical(body),
            )
            if kind == "model":
                account["model_calls"] += 1
                job["model_calls"] += 1
                if child is not None:
                    child["model_calls"] += 1
                    self.store.execute(
                        conn,
                        "UPDATE contract_review_child_tasks SET body=:body WHERE id=:id",
                        id=context["child_id"],
                        body=canonical(child),
                    )
                self.save_account(conn, context["review_id"], account)
                self.refresh_usage(conn, context["review_id"])
                self.store.execute(
                    conn,
                    "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
                    id=context["job_id"],
                    body=canonical(job),
                )
            self.store.execute(
                conn,
                "INSERT INTO contract_review_budget_entries VALUES (:id,:review,:job,:call,:body)",
                id=call_id + ":reserve",
                review=context["review_id"],
                job=context["job_id"],
                call=call_id,
                body=canonical(
                    {"model_calls": int(kind == "model"), "usage_reserved": body["usage_reserved"]}
                ),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_runtime SET slot_call_id=:call,slot_execution_instanc"
                "e_id=:instance WHERE id=1",
                call=call_id,
                instance=instance_id,
            )
            projected = self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "request_projected",
                projection,
                call_id=call_id,
                logical_call_id=logical,
                child_task_id=context.get("child_id"),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "dispatch_intent",
                {"kind": kind, "execution_instance_id": instance_id, "physical_retry_no": retry_no},
                call_id=call_id,
                logical_call_id=logical,
                child_task_id=context.get("child_id"),
                caused_by_event_id=projected["event_id"],
            )
            return call_id, instance_id

    def record_failure(self, context, call_id, failure):
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT body FROM contract_review_calls WHERE id=:id AND job_id=:job",
                id=call_id,
                job=context["job_id"],
            )
            body = json.loads(row["body"])
            body["failure"] = {"code": failure.code, "retryable": failure.retryable}
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET status=:status,body=:body,version=version+1"
                " WHERE id=:id",
                id=call_id,
                status="UNKNOWN" if failure.remote_outcome == "unknown" else "failed",
                body=canonical(body),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "result_rejected",
                body["failure"],
                call_id=call_id,
                child_task_id=context.get("child_id"),
            )

    def propose(self, context, call_id, raw):
        blocked = None
        with self.store.transaction() as conn:
            row = self.fence(conn, context)
            route_id = identity("route")
            self.store.reserve_records(conn, len(canonical(raw).encode()), context["job_id"])
            self.store.execute(
                conn,
                "INSERT INTO contract_review_actions VALUES (:id,:job,:call,'proposed',:body)",
                id=route_id,
                job=context["job_id"],
                call=call_id,
                body=canonical(raw),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "action_proposed",
                raw,
                call_id=call_id,
                route_decision_id=route_id,
                child_task_id=context.get("child_id"),
            )
            if isinstance(raw, dict) and raw.get("action") == "tool_call":
                profile = context["frozen"]["execution_profile"]
                job, account = json.loads(row["body"]), self.account(conn, context["review_id"])
                child = (
                    json.loads(
                        self.store.row(
                            conn,
                            "SELECT body FROM contract_review_child_tasks WHERE id=:id",
                            id=context["child_id"],
                        )["body"]
                    )
                    if context.get("child_id")
                    else None
                )
                if (
                    job["tool_actions"] >= profile["tool_action_limit"]
                    or account["tool_actions"] >= account["grant"]["tool_actions"]
                ):
                    blocked = "BUDGET_EXHAUSTED"
                elif child and child["tool_actions"] >= profile["child_tool_limit"]:
                    blocked = "CHILD_BUDGET_EXHAUSTED"
                else:
                    job["tool_actions"] += 1
                    account["tool_actions"] += 1
                    self.save_account(conn, context["review_id"], account)
                    self.store.execute(
                        conn,
                        "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
                        id=context["job_id"],
                        body=canonical(job),
                    )
                    if child is not None:
                        child["tool_actions"] += 1
                        self.store.execute(
                            conn,
                            "UPDATE contract_review_child_tasks SET body=:body WHERE id=:id",
                            id=context["child_id"],
                            body=canonical(child),
                        )
                    self.store.execute(
                        conn,
                        "INSERT INTO contract_review_budget_entries VALUES (:id,:review,:job,"
                        ":call,:body)",
                        id=route_id,
                        review=context["review_id"],
                        job=context["job_id"],
                        call=call_id,
                        body=canonical({"tool_actions": 1, "route_decision_id": route_id}),
                    )
            if blocked:
                self.store.execute(
                    conn,
                    "UPDATE contract_review_actions SET status='rejected' WHERE id=:id",
                    id=route_id,
                )
                self.store.event(
                    conn,
                    context["review_id"],
                    context["input_id"],
                    context["job_id"],
                    "action_rejected",
                    {"code": blocked},
                    call_id=call_id,
                    route_decision_id=route_id,
                )
        if blocked:
            raise ReviewError(blocked, "工具动作预算耗尽。")
        return route_id

    def reject_action(self, context, call_id, result, route_id, code):
        self.record_result(context, call_id, result, accepted=False, reason=code)
        with self.store.transaction() as conn:
            self.fence(conn, context)
            self.store.execute(
                conn,
                "UPDATE contract_review_actions SET status='rejected' WHERE id=:id AND job_id=:job",
                id=route_id,
                job=context["job_id"],
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "action_rejected",
                {"code": code},
                call_id=call_id,
                route_decision_id=route_id,
                child_task_id=context.get("child_id"),
            )

    def child_rows(self, conn, context):
        return (
            conn.execute(
                text("SELECT * FROM contract_review_child_tasks WHERE job_id=:job ORDER BY rowid"),
                {"job": context["job_id"]},
            )
            .mappings()
            .all()
        )

    def check_reviews(self, context, call_id, reviews):
        with self.store.read() as conn:
            self.fence(conn, context)
            children = {
                row["result_ref"]: row
                for row in self.child_rows(conn, context)
                if row["status"] in ("accepted", "failed")
            }
            supplied = {item["child_result_ref"]: item for item in reviews}
            if len(supplied) != len(reviews) or not set(supplied) <= set(children):
                raise ReviewError("ACTION_SCHEMA_INVALID", "父验收重复或引用了未知子结果。")
            call = self.store.row(
                conn,
                "SELECT body FROM contract_review_calls WHERE id=:id AND job_id=:job",
                id=call_id,
                job=context["job_id"],
            )
            projected = json.loads(
                json.loads(call["body"])["projection"]["payload"]["messages"][1]["content"]
            )
            seen = {item["child_result_ref"] for item in projected.get("child_results", [])}
            projected_results = {
                item["child_result_ref"]: item["result"]
                for item in projected.get("child_results", [])
            }
            for reference, row in children.items():
                if (
                    reference not in seen
                    or row["latest_review"] is None
                    and reference not in supplied
                ):
                    raise ReviewError(
                        "ACTION_SCHEMA_INVALID", "父方必须先消费并验收每个返回的子结果。"
                    )
                if projected_results[reference] != json.loads(row["body"])["result"]:
                    raise ReviewError(
                        "ACTION_SCHEMA_INVALID", "父请求中的子结果不是完整已接受原文。"
                    )
            latest = {
                key: json.loads(row["latest_review"])
                for key, row in children.items()
                if row["latest_review"]
            }
            latest.update(supplied)
            return latest

    def accept_action(self, context, call_id, result, route_id, action):
        reviews = action.get("child_result_reviews", [])
        latest = (
            self.check_reviews(context, call_id, reviews) if not context.get("child_id") else {}
        )
        with self.store.transaction() as conn:
            self.fence(conn, context)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_calls WHERE id=:id AND job_id=:job",
                id=call_id,
                job=context["job_id"],
            )
            body = json.loads(row["body"])
            body.update(
                result=result,
                remote_outcome="known",
                acceptance={
                    "accepted": True,
                    "reason": "FORMAT_AND_SCOPE_VALID",
                    "result_hash": digest(result),
                },
            )
            self.store.reserve_records(
                conn,
                len(canonical(result).encode()) + len(canonical(action).encode()),
                context["job_id"],
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_calls SET status='accepted',body=:body,version=versio"
                "n+1 WHERE id=:id",
                id=call_id,
                body=canonical(body),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_actions SET status='accepted' WHERE id=:id AND job_id=:job",
                id=route_id,
                job=context["job_id"],
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_steps SET body=:body WHERE id=:id",
                id=row["step_id"],
                body=canonical(
                    {
                        "parent_response": result,
                        "action": action,
                        "child_result_reviews": reviews,
                        "accepted": True,
                    }
                ),
            )
            for review in reviews:
                self.store.execute(
                    conn,
                    "UPDATE contract_review_child_tasks SET latest_review=:body "
                    "WHERE job_id=:job AND result_ref=:ref AND status IN ('accepted','failed')",
                    body=canonical(review),
                    job=context["job_id"],
                    ref=review["child_result_ref"],
                )
                self.store.event(
                    conn,
                    context["review_id"],
                    context["input_id"],
                    context["job_id"],
                    "child_result_reviewed",
                    review,
                    call_id=call_id,
                    route_decision_id=route_id,
                )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "result_accepted",
                {"result": result, "acceptance": body["acceptance"]},
                call_id=call_id,
                route_decision_id=route_id,
                child_task_id=context.get("child_id"),
            )
        return latest

    def check_delegate(self, context):
        if not context["frozen"]["execution_profile"]["options"]["delegate"]:
            raise ReviewError("OPTION_NOT_ENABLED", "此输入未启用委派。")
        with self.store.read() as conn:
            self.fence(conn, context)
            children = self.child_rows(conn, context)
            if (
                context.get("child_id")
                or any(row["status"] == "running" for row in children)
                or len(children) >= 2
            ):
                raise ReviewError("ACTION_NOT_ALLOWED", "委派只允许一级顺序执行，每次最多两项。")

    def start_child(self, context, call_id, action):
        self.check_delegate(context)
        with self.store.transaction() as conn:
            self.fence(conn, context)
            child_id, result_ref = identity("child"), identity("child_result")
            deadline = min(
                datetime.fromisoformat(context["deadline"].replace("Z", "+00:00")),
                datetime.now(UTC)
                + timedelta(seconds=context["frozen"]["execution_profile"]["child_seconds"]),
            )
            body = {
                "input_id": context["input_id"],
                "snapshot_id": context["frozen"]["snapshot_id"],
                "action": action,
                "owner_boot_id": self.boot_id,
                "deadline": deadline.isoformat().replace("+00:00", "Z"),
                "model_calls": 0,
                "tool_actions": 0,
                "result": None,
            }
            self.store.reserve_records(conn, len(canonical(body).encode()), context["job_id"])
            self.store.execute(
                conn,
                "INSERT INTO contract_review_child_tasks VALUES (:id,:job,:parent,:ref,'runni"
                "ng',:body,NULL)",
                id=child_id,
                job=context["job_id"],
                parent=call_id,
                ref=result_ref,
                body=canonical(body),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "child_started",
                body,
                child_task_id=child_id,
                parent_call_id=call_id,
            )
            return child_id, result_ref, body["deadline"]

    def finish_child(self, context, child_id, payload, trace, *, failed=False):
        root = {key: value for key, value in context.items() if key != "child_id"}
        with self.store.transaction() as conn:
            self.fence(conn, root)
            row = self.store.row(
                conn,
                "SELECT * FROM contract_review_child_tasks WHERE id=:id AND job_id=:job",
                id=child_id,
                job=context["job_id"],
            )
            if row is None or row["status"] != "running":
                raise ReviewError("STALE_EXECUTION", "子任务已结束。")
            if not failed:
                self.fence(conn, context)
            body = json.loads(row["body"])
            body.update(result=payload, evidence_trace=trace)
            self.store.reserve_records(
                conn,
                len(canonical(payload).encode()) + len(canonical(trace).encode()),
                context["job_id"],
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_child_tasks SET status=:status,body=:body WHERE id=:id",
                id=child_id,
                status="failed" if failed else "accepted",
                body=canonical(body),
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "child_accepted",
                {"child_result_ref": row["result_ref"], "result": payload, "failed": failed},
                child_task_id=child_id,
            )
            return {
                "child_result_ref": row["result_ref"],
                "result": payload,
                "evidence_trace": trace,
            }

    def fail(self, context, code, elapsed=None):
        root = {key: value for key, value in context.items() if key != "child_id"}
        super().fail(root, code, elapsed)
        with self.store.transaction() as conn:
            self.owner(conn)
            self.store.execute(
                conn,
                "UPDATE contract_review_child_tasks SET status=:status "
                "WHERE job_id=:job AND status='running'",
                job=context["job_id"],
                status="interrupted" if code == "INTERRUPTED" else "failed",
            )

"""Ordered replay receipts. A reused step is never a new physical call."""

import json
import sys
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from specflow.contract_review.actions import parse_action
from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.sources import strict_json


class RestartFresh(Exception):
    """Explicit client-selected fallback, preserving the running attempt and its clock."""


@lru_cache(maxsize=1)
def compatibility():
    # Strict identity-only compatibility: upgrades need a new proven mapping.
    root = Path(__file__).parent
    return {
        "protocol": "contract-review-replay.v1",
        "python": list(sys.version_info[:2]),
        "build": digest({p.name: digest(p.read_bytes()) for p in sorted(root.glob("*.py"))}),
    }


def fingerprint(payload, result, kind, role):
    return digest({"payload": payload, "result": result, "kind": kind, "role": role})


def before_terminal(accepted, finished):
    try:
        start = datetime.fromisoformat(accepted.replace("Z", "+00:00"))
        end = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        return start.tzinfo is not None and end.tzinfo is not None and start <= end
    except (ValueError, TypeError, AttributeError):
        return False


class ReplayRecords:
    def __init__(self, store):
        self.store = store

    def growth(self, conn, context, previous, value):
        extra = len(canonical(value).encode()) - len(previous.encode())
        if extra > 0:
            self.store.reserve_records(conn, extra, context["job_id"])

    def history(self, conn, job_id, before_step_seq=2**63 - 1):
        result = []
        for row in conn.exec_driver_sql(
            "SELECT body FROM contract_review_steps WHERE job_id=? "
            "AND step_seq<? ORDER BY step_seq",
            (job_id, before_step_seq),
        ).mappings():
            body = json.loads(row["body"])
            if body.get("accepted"):
                result.extend(body.get("components", [body.get("fingerprint")]))
        return result

    def summary(self, conn, job_id):
        row = self.store.row(conn, "SELECT body FROM contract_review_jobs WHERE id=:id", id=job_id)
        body = json.loads(row["body"])
        value = {
            key: body.get(key)
            for key in (
                "retry_of_job_id",
                "requested_mode",
                "effective_mode",
                "recovery_fallback",
                "replay_boundary",
                "reason",
            )
        }
        if not body.get("retry_of_job_id"):
            return {**value, "reused_steps": []}
        value["reused_steps"] = [
            {
                "step_id": row["step_id"],
                "source_job_id": row["source_job_id"],
                "source_step_id": row["source_step_id"],
                "kind": row["kind"],
                "source_call_id": json.loads(row["body"])["source_call_id"],
            }
            for row in conn.exec_driver_sql(
                "SELECT * FROM contract_review_replay_bindings "
                "WHERE job_id=? AND status='accepted' ORDER BY rowid",
                (job_id,),
            ).mappings()
        ]
        return value

    def prepare(self, conn, context, step_id):
        if not context["frozen"]["execution_profile"]["options"]["replay"]:
            return
        row = self.store.row(
            conn, "SELECT body FROM contract_review_steps WHERE id=:id", id=step_id
        )
        body = json.loads(row["body"])
        if "compatibility" not in body:
            body.update(
                compatibility=compatibility(),
                predecessor=digest(self.history(conn, context["job_id"])),
                accepted=False,
            )
            self.growth(conn, context, row["body"], body)
            self.store.execute(
                conn,
                "UPDATE contract_review_steps SET body=:body WHERE id=:id",
                id=step_id,
                body=canonical(body),
            )

    def complete(self, conn, context, row, call, result, accepted, action=None):
        if not context["frozen"]["execution_profile"]["options"]["replay"]:
            return
        step = self.store.row(
            conn, "SELECT * FROM contract_review_steps WHERE id=:id", id=row["step_id"]
        )
        body = json.loads(step["body"])
        body.update(accepted=accepted)
        if accepted:
            body.update(
                accepted_at=now(),
                fingerprint=fingerprint(
                    call["projection"]["payload"], result, call["kind"], step["role"]
                ),
                result_hash=digest(result),
                projection_hash=digest(call["projection"]),
                parent_response=result,
            )
            if action is not None:
                body.update(
                    action=action, child_result_reviews=action.get("child_result_reviews", [])
                )
        self.growth(conn, context, step["body"], body)
        self.store.execute(
            conn,
            "UPDATE contract_review_steps SET body=:body WHERE id=:id",
            id=step["id"],
            body=canonical(body),
        )

    def binding(self, conn, context, handle):
        if not handle.startswith("reuse_"):
            return None
        row = self.store.row(
            conn,
            "SELECT * FROM contract_review_replay_bindings WHERE id=:id AND job_id=:job",
            id=handle,
            job=context["job_id"],
        )
        if row is None:
            raise ReviewError("STALE_EXECUTION", "回放步骤不属于当前作业。")
        return row

    def call_body(self, conn, context, handle):
        binding = self.binding(conn, context, handle)
        if binding is not None:
            return json.loads(binding["body"])
        row = self.store.row(
            conn,
            "SELECT body FROM contract_review_calls WHERE id=:id AND job_id=:job",
            id=handle,
            job=context["job_id"],
        )
        if row is None:
            raise ReviewError("STALE_EXECUTION", "调用不属于当前作业。")
        return json.loads(row["body"])

    def children(self, conn, context):
        rows = conn.exec_driver_sql(
            "SELECT body FROM contract_review_replay_bindings "
            "WHERE job_id=? AND kind='child' AND status='accepted' ORDER BY rowid",
            (context["job_id"],),
        ).mappings()
        return [json.loads(row["body"])["child_row"] for row in rows]

    def review_child(self, conn, context, review):
        for row in conn.exec_driver_sql(
            "SELECT id,body FROM contract_review_replay_bindings "
            "WHERE job_id=? AND kind='child' AND status='accepted'",
            (context["job_id"],),
        ).mappings():
            body = json.loads(row["body"])
            if body["child_row"]["result_ref"] == review["child_result_ref"]:
                body["child_row"]["latest_review"] = canonical(review)
                self.growth(conn, context, row["body"], body)
                self.store.execute(
                    conn,
                    "UPDATE contract_review_replay_bindings SET body=:body WHERE id=:id",
                    id=row["id"],
                    body=canonical(body),
                )

    def accept(self, fence, context, handle, result, *, accepted, reason, action=None):
        with self.store.transaction() as conn:
            fence(conn, context)
            row = self.binding(conn, context, handle)
            body = json.loads(row["body"])
            if body["result"] != result or (action is not None and body.get("action") != action):
                raise ReviewError("REPLAY_PREFIX_UNAVAILABLE", "回放正文与原接受记录不一致。")
            step = self.store.row(
                conn, "SELECT * FROM contract_review_steps WHERE id=:id", id=row["step_id"]
            )
            step_body = json.loads(step["body"])
            step_body.update(accepted=accepted, accepted_at=now())
            if action is not None:
                step_body.update(
                    parent_response=result,
                    action=action,
                    child_result_reviews=action.get("child_result_reviews", []),
                )
                for review in action.get("child_result_reviews", []):
                    self.store.execute(
                        conn,
                        "UPDATE contract_review_child_tasks SET latest_review=:body "
                        "WHERE job_id=:job AND result_ref=:ref",
                        job=context["job_id"],
                        ref=review["child_result_ref"],
                        body=canonical(review),
                    )
                    self.review_child(conn, context, review)
                    self.store.event(
                        conn,
                        context["review_id"],
                        context["input_id"],
                        context["job_id"],
                        "child_result_reviewed",
                        review,
                        reused_step_id=step["id"],
                    )
            self.growth(conn, context, step["body"], step_body)
            self.store.execute(
                conn,
                "UPDATE contract_review_steps SET body=:body WHERE id=:id",
                id=step["id"],
                body=canonical(step_body),
            )
            self.store.execute(
                conn,
                "UPDATE contract_review_replay_bindings SET status=:status WHERE id=:id",
                id=handle,
                status="accepted" if accepted else "rejected",
            )
            self.store.event(
                conn,
                context["review_id"],
                context["input_id"],
                context["job_id"],
                "result_reused" if accepted else "result_rejected",
                {
                    "reused_from_job_id": row["source_job_id"],
                    "reused_from_step_id": row["source_step_id"],
                    "reused_from_call_id": body["source_call_id"],
                    "result_hash": digest(result),
                    "step_id": step["id"],
                    "reason": reason,
                },
            )

    def make(
        self,
        conn,
        fence,
        context,
        source,
        kind,
        payload=None,
        entries=None,
        child=None,
        components=None,
    ):
        fence(conn, context)
        sequence = conn.exec_driver_sql(
            "SELECT coalesce(max(step_seq),0)+1 FROM contract_review_steps WHERE job_id=?",
            (context["job_id"],),
        ).scalar_one()
        step_id, handle = identity("step"), identity("reuse")
        old = source["step"]
        result = source["call"]["result"]
        step_body = {
            "compatibility": compatibility(),
            "predecessor": digest(self.history(conn, context["job_id"])),
            "fingerprint": source["body"]["fingerprint"],
            "result_hash": digest(result),
            "parent_response": result,
            "accepted": kind == "child",
            "accepted_at": now() if kind == "child" else None,
            "reused_from_step": old["id"],
            "reused_from_call": source["call_id"],
        }
        if components is not None:
            step_body["components"] = components
        body = {
            "source_call_id": source["call_id"],
            "result": result,
            "action": source["body"].get("action"),
            "kind": kind,
            "projection": {
                "projection_id": identity("projection"),
                "logical_call_id": old["logical_call_id"],
                "input_hash": context["frozen"]["input_hash"],
                "profile_hash": context["frozen"]["profile_hash"],
                "role": old["role"],
                "payload": payload,
                "material_entries": entries or [],
                "projection_hash": digest(payload),
                "content_integrity": "complete",
                "created_at": now(),
            },
        }
        if child is not None:
            body["child_row"] = child
        encoded = canonical(body)
        self.store.reserve_records(
            conn, len(encoded.encode()) + len(canonical(step_body).encode()), context["job_id"]
        )
        self.store.execute(
            conn,
            "INSERT INTO contract_review_steps (id,job_id,step_seq,role,logical_call_id,body) "
            "VALUES (:id,:job,:seq,:role,:logical,:body)",
            id=step_id,
            job=context["job_id"],
            seq=sequence,
            role="child_bundle" if kind == "child" else old["role"],
            logical=old["logical_call_id"],
            body=canonical(step_body),
        )
        self.store.execute(
            conn,
            "INSERT INTO contract_review_replay_bindings "
            "VALUES (:id,:job,:step,:source_job,:source_step,:kind,:status,:body,:at)",
            id=handle,
            job=context["job_id"],
            step=step_id,
            source_job=old["job_id"],
            source_step=old["id"],
            kind=kind,
            status="accepted" if kind == "child" else "pending",
            body=encoded,
            at=now(),
        )
        self.store.event(
            conn,
            context["review_id"],
            context["input_id"],
            context["job_id"],
            "result_reused" if kind == "child" else "request_projected",
            {
                "step_id": step_id,
                "reused_from_step": old["id"],
                "reused_from_call": source["call_id"],
                "kind": kind,
                "projection": body["projection"],
            },
        )
        return handle, deepcopy(result)


class ReplaySession:
    def __init__(self, records, fence, context):
        self.context, self.fence = context, fence
        self.records = records
        self.store = self.records.store
        self.cursor, self.steps, self.units = 0, [], {}
        with self.store.read() as conn:
            current = self.store.row(
                conn, "SELECT body FROM contract_review_jobs WHERE id=:id", id=context["job_id"]
            )
            job = json.loads(current["body"])
            self.active = job.get("requested_mode") == "reuse_completed"
            self.source_id, self.fallback = job.get("retry_of_job_id"), job.get("recovery_fallback")
            if self.active:
                source = self.store.row(
                    conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=self.source_id
                )
                if (
                    source is None
                    or source["review_id"] != context["review_id"]
                    or source["input_id"] != context["input_id"]
                    or source["status"] not in ("failed", "interrupted")
                ):
                    raise ReviewError("RETRY_TARGET_NOT_CURRENT", "回放源归属或状态不合法。")
                self.source = dict(source)
                self.steps = [
                    dict(row)
                    for row in conn.exec_driver_sql(
                        "SELECT * FROM contract_review_steps WHERE job_id=? ORDER BY step_seq",
                        (self.source_id,),
                    ).mappings()
                ]
                source_body = json.loads(source["body"])
                self.integrity_problem = self.check_source_inventory(conn, source_body)
                fresh_after = source_body.get("fresh_start_after_step_seq", 0)
                self.steps = [step for step in self.steps if step["step_seq"] > fresh_after]

    def check_source_inventory(self, conn, source_body):
        """Detect missing accepted tails as well as a gap exposed by the next predecessor."""
        try:
            calls = list(
                conn.exec_driver_sql(
                    "SELECT id,step_id FROM contract_review_calls "
                    "WHERE job_id=? AND status='accepted'",
                    (self.source_id,),
                ).mappings()
            )
            bindings = list(
                conn.exec_driver_sql(
                    "SELECT step_id FROM contract_review_replay_bindings "
                    "WHERE job_id=? AND status='accepted'",
                    (self.source_id,),
                ).mappings()
            )
            call_events, reuse_events, child_events = set(), set(), set()
            abandoned = set(source_body.get("abandoned_step_ids", []))
            for row in conn.exec_driver_sql(
                "SELECT * FROM contract_review_events WHERE job_id=? "
                "AND event_type IN ('result_accepted','result_reused','child_accepted')",
                (self.source_id,),
            ).mappings():
                metadata, payload = json.loads(row["body"]), json.loads(row["payload"])
                if (
                    digest(payload) != row["payload_hash"]
                    or metadata["payload_hash"] != row["payload_hash"]
                ):
                    return True
                if row["event_type"] == "result_accepted":
                    call_events.add(metadata["call_id"])
                elif row["event_type"] == "child_accepted":
                    if not payload["failed"]:
                        child_events.add(metadata["child_task_id"])
                elif payload["step_id"] not in abandoned:
                    reuse_events.add(payload["step_id"])
            accepted = {
                step["id"] for step in self.steps if json.loads(step["body"]).get("accepted")
            }
            return (
                call_events != {row["id"] for row in calls}
                or reuse_events != {row["step_id"] for row in bindings}
                or accepted
                != {row["step_id"] for row in calls} | {row["step_id"] for row in bindings}
                or child_events
                != {
                    row["id"]
                    for row in conn.exec_driver_sql(
                        "SELECT id FROM contract_review_child_tasks "
                        "WHERE job_id=? AND status='accepted'",
                        (self.source_id,),
                    ).mappings()
                }
            )
        except (ValueError, KeyError, TypeError):
            return True

    def source_step(self, conn, index, seen=None):
        step = self.steps[index]
        body = json.loads(step["body"])
        if not body.get("accepted"):
            # Intent-only and rejected work are an ordinary unfinished suffix.
            return None
        if body.get("predecessor") != digest(
            self.records.history(conn, step["job_id"], step["step_seq"])
        ):
            raise ValueError("source step predecessor differs from its own accepted prefix")
        if body.get("compatibility") != compatibility() or not before_terminal(
            body.get("accepted_at"), self.source["finished_at"]
        ):
            raise ValueError("accepted step compatibility or terminal boundary")
        binding = self.store.row(
            conn,
            "SELECT * FROM contract_review_replay_bindings WHERE step_id=:step",
            step=step["id"],
        )
        if binding is not None:
            if binding["status"] != "accepted":
                raise ValueError("accepted replay receipt is missing")
            call = json.loads(binding["body"])
            call_id = call["source_call_id"]
            # Validate every provenance hop; source records may not be substituted.
            seen = set() if seen is None else seen
            if step["id"] in seen:
                raise ValueError("cyclic replay provenance")
            seen.add(step["id"])
            origin = self.store.row(
                conn,
                "SELECT * FROM contract_review_steps WHERE id=:id",
                id=binding["source_step_id"],
            )
            owner = self.store.row(
                conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=binding["source_job_id"]
            )
            if (
                origin is None
                or owner is None
                or owner["review_id"] != self.context["review_id"]
                or owner["input_id"] != self.context["input_id"]
                or owner["status"] not in ("failed", "interrupted")
                or origin["job_id"] != owner["id"]
                or owner["attempt_no"] >= self.source["attempt_no"]
            ):
                raise ReviewError("ACTION_PERMISSION_DENIED", "回放来源超出当前输入或审查。")
            nested = object.__new__(ReplaySession)
            origin_steps = [
                dict(row)
                for row in conn.exec_driver_sql(
                    "SELECT * FROM contract_review_steps WHERE job_id=? ORDER BY step_seq",
                    (owner["id"],),
                ).mappings()
            ]
            origin_index = next(
                i for i, item in enumerate(origin_steps) if item["id"] == origin["id"]
            )
            nested.__dict__.update(
                self.__dict__,
                source=dict(owner),
                source_id=owner["id"],
                steps=origin_steps,
                units={},
            )
            original = nested.source_step(conn, origin_index, seen)
            if (
                original is None
                or original["call_id"] != call_id
                or original["call"]["result"] != call["result"]
            ):
                raise ValueError("replay provenance differs from original")
            kind = binding["kind"]
            if kind == "child":
                unit = nested.delegation(conn, origin_index, original)
                bound = call.get("child_row", {})
                if (
                    unit is None
                    or body.get("components") != unit["components"]
                    or bound.get("job_id") != step["job_id"]
                    or any(
                        bound.get(key) != unit["row"].get(key)
                        for key in ("id", "body", "result_ref")
                    )
                ):
                    raise ValueError(
                        "replayed child unit differs from its complete original prefix"
                    )
            elif body.get("predecessor") != original["body"].get("predecessor"):
                raise ValueError("replay receipt predecessor differs from original source")
        else:
            calls = list(
                conn.exec_driver_sql(
                    "SELECT * FROM contract_review_calls WHERE step_id=? AND status='accepted'",
                    (step["id"],),
                ).mappings()
            )
            if len(calls) != 1:
                raise ValueError("accepted physical result missing or ambiguous")
            call_id = calls[0]["id"]
            call = json.loads(calls[0]["body"])
            acceptance = call.get("acceptance") or {}
            if not acceptance.get("accepted") or acceptance.get("result_hash") != digest(
                call["result"]
            ):
                raise ValueError("result hash or acceptance")
            if body.get("projection_hash") != digest(call["projection"]):
                raise ValueError("projection record damaged")
            kind = call["kind"]
        projection = call["projection"]
        if body.get("parent_response") != call["result"]:
            raise ValueError("complete accepted response differs from physical result")
        if kind == "model" and step["role"] != "review":
            action = parse_action(
                strict_json(call["result"]["content"]),
                child=bool(call.get("child_task_id")),
                delegation=self.context["frozen"]["execution_profile"]["options"]["delegate"],
            ).model_dump(exclude_none=True)
            if body.get("action") != action or body.get("child_result_reviews", []) != action.get(
                "child_result_reviews", []
            ):
                raise ValueError("accepted action or parent review differs from full response")
        if (
            projection["input_hash"] != self.context["frozen"]["input_hash"]
            or projection["profile_hash"] != self.context["frozen"]["profile_hash"]
        ):
            raise ReviewError("ACTION_PERMISSION_DENIED", "回放投影不属于当前冻结输入。")
        if projection.get("content_integrity") != "complete" or projection[
            "projection_hash"
        ] != digest(projection["payload"]):
            raise ValueError("incomplete projection")
        if body.get("result_hash") != digest(call["result"]) or (
            kind != "child"
            and body.get("fingerprint")
            != fingerprint(projection["payload"], call["result"], kind, step["role"])
        ):
            raise ValueError("logical result fingerprint")
        return {"step": step, "body": body, "call": call, "call_id": call_id, "kind": kind}

    def boundary(self, reason, *, broken=False):
        with self.store.transaction() as conn:
            self.fence(conn, self.context)
            row = self.store.row(
                conn,
                "SELECT body FROM contract_review_jobs WHERE id=:id",
                id=self.context["job_id"],
            )
            body = json.loads(row["body"])
            body["replay_boundary"] = {
                "source_job_id": self.source_id,
                "step_index": self.cursor,
                "reason": reason,
            }
            event = "recovery_fallback" if broken else "replay_boundary"
            if broken and self.fallback == "restart_fresh":
                body["effective_mode"] = "fresh"
                body["abandoned_step_ids"] = []
                body["fresh_start_after_step_seq"] = 0
                for step in conn.exec_driver_sql(
                    "SELECT id,body,step_seq FROM contract_review_steps WHERE job_id=?",
                    (self.context["job_id"],),
                ).mappings():
                    prior = json.loads(step["body"])
                    prior["accepted"] = False
                    body["abandoned_step_ids"].append(step["id"])
                    body["fresh_start_after_step_seq"] = max(
                        body["fresh_start_after_step_seq"], step["step_seq"]
                    )
                    self.store.execute(
                        conn,
                        "UPDATE contract_review_steps SET body=:body WHERE id=:id",
                        id=step["id"],
                        body=canonical(prior),
                    )
                self.store.execute(
                    conn,
                    "UPDATE contract_review_replay_bindings SET status='abandoned' "
                    "WHERE job_id=:job",
                    job=self.context["job_id"],
                )
            self.store.execute(
                conn,
                "UPDATE contract_review_jobs SET body=:body WHERE id=:id",
                id=self.context["job_id"],
                body=canonical(body),
            )
            self.store.event(
                conn,
                self.context["review_id"],
                self.context["input_id"],
                self.context["job_id"],
                event,
                body["replay_boundary"],
            )
        self.active = False
        if broken:
            if self.fallback == "restart_fresh":
                raise RestartFresh()
            raise ReviewError("REPLAY_PREFIX_UNAVAILABLE", "完整前缀无法核对，已按请求停止。")

    def delegation(self, conn, index, source):
        action = source["body"].get("action", {})
        if action.get("action") != "delegate_task":
            return None
        if index in self.units:
            return self.units[index]
        native = self.store.row(
            conn,
            "SELECT * FROM contract_review_child_tasks WHERE job_id=:job AND parent_call_id=:call",
            job=self.source_id,
            call=source["call_id"],
        )
        end, components = index + 1, []
        if native is None and end < len(self.steps):
            binding = self.store.row(
                conn,
                "SELECT body FROM contract_review_replay_bindings "
                "WHERE step_id=:step AND kind='child' AND status='accepted'",
                step=self.steps[end]["id"],
            )
            if binding:
                native = json.loads(binding["body"])["child_row"]
                bundle = self.source_step(conn, end)
                components = bundle["body"]["components"]
                end += 1
        elif native is not None:
            native = dict(native)
            while end < len(self.steps):
                item = self.source_step(conn, end)
                if item is None:
                    return None
                if item["call"].get("child_task_id") is None:
                    break
                components.extend(item["body"].get("components", [item["body"]["fingerprint"]]))
                end += 1
        if native is None or native["status"] != "accepted" or end >= len(self.steps):
            return None
        child = json.loads(native["body"])
        if child.get("replay_package_hash") != digest(
            {
                "result": child["result"],
                "evidence_trace": child.get("evidence_trace"),
                "action": child.get("action"),
            }
        ) or not before_terminal(child.get("accepted_at"), self.source["finished_at"]):
            raise ValueError("accepted child package damaged or late")
        if child.get("result", {}).get("status") not in ("completed", "insufficient"):
            return None
        parent = self.source_step(conn, end)
        if parent is None:
            return None
        reviews = parent["body"].get("child_result_reviews", [])
        if not any(r["child_result_ref"] == native["result_ref"] for r in reviews):
            return None
        projected = json.loads(parent["call"]["projection"]["payload"]["messages"][1]["content"])
        if not any(
            r["child_result_ref"] == native["result_ref"] and r["result"] == child["result"]
            for r in projected.get("child_results", [])
        ):
            raise ValueError("complete parent acceptance payload missing")
        if (
            parent["body"].get("action", {}).get("action") == "delegate_task"
            and self.delegation(conn, end, parent) is None
        ):
            return None
        if not components or "evidence_trace" not in child:
            raise ValueError("child bundle incomplete")
        value = {"row": dict(native), "end": end, "components": components, "child": child}
        self.units[index] = value
        return value

    def take(self, context, role, payload, entries, *, kind="model"):
        if not self.active:
            return None
        if self.integrity_problem:
            self.boundary("accepted_record_inventory_incomplete", broken=True)
        try:
            with self.store.transaction() as conn:
                self.fence(conn, context)
                if self.cursor >= len(self.steps):
                    source = None
                else:
                    source = self.source_step(conn, self.cursor)
                if source is not None:
                    if (
                        source["kind"] != kind
                        or source["step"]["role"] != role
                        or source["call"]["projection"]["payload"] != payload
                        or source["call"]["projection"]["material_entries"] != entries
                        or source["body"].get("predecessor")
                        != digest(self.records.history(conn, context["job_id"]))
                    ):
                        raise ValueError("request, material or predecessor differs")
                    action = source["body"].get("action", {})
                    if (
                        action.get("action") == "delegate_task"
                        and self.delegation(conn, self.cursor, source) is None
                    ):
                        source = None
                if source is not None:
                    result = self.records.make(
                        conn, self.fence, context, source, kind, payload, entries
                    )
                    self.cursor += 1
                    return result
            self.boundary("unfinished_suffix")
            return None
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            self.boundary("invalid_or_incompatible_prefix", broken=True)

    def child(self, action, parent_handle, specification):
        if not parent_handle.startswith("reuse_"):
            return None
        index = self.cursor - 1
        unit = self.units.get(index)
        if unit is None:
            self.boundary("incomplete_delegation_unit", broken=True)
        grants, explicit_rules, initial_observations, _ = specification
        child = unit["child"]
        if child["action"] != action:
            raise ReviewError("ACTION_PERMISSION_DENIED", "子任务委派与原范围不一致。")
        with self.store.transaction() as conn:
            source = self.source_step(conn, index)
            row = {**unit["row"], "job_id": self.context["job_id"], "latest_review": None}
            # Consuming an explicitly granted, already projected fragment does
            # not grant a tool the right to read any new source fragment.
            consumable = deepcopy(grants)
            fragments = [
                rule["body_ref"]
                for rule in self.context["frozen"]["adoption_records"]
                if rule["adoption_id"] in explicit_rules and "source_id" in rule["body_ref"]
            ]
            projected = {
                item["observation_id"]: item for item in child["evidence_trace"]["observations"]
            }
            fragments.extend(
                reference
                for identifier, observation in initial_observations.items()
                if projected.get(identifier) == observation
                for reference in observation["source_refs"]
            )
            for reference in fragments:
                consumable.setdefault(reference["source_id"], []).append(reference["selector"])
            # Binding changes ownership, never the original result or evidence handles.
            for ref in child["evidence_trace"]["published_source_refs"]:
                from specflow.contract_review.tool_protocol import covers_selector

                source_body = self.context["sources"][ref["source_id"]]["body"]
                if not covers_selector(
                    consumable.get(ref["source_id"], []),
                    ref["selector"],
                    len(source_body.splitlines()),
                ):
                    raise ReviewError("ACTION_PERMISSION_DENIED", "回放子证据超出当前授权片段。")
            self.records.make(
                conn,
                self.fence,
                self.context,
                source,
                "child",
                child=row,
                components=unit["components"],
            )
        self.cursor = unit["end"]
        return {
            "child_result_ref": row["result_ref"],
            "result": deepcopy(child["result"]),
            "evidence_trace": deepcopy(child["evidence_trace"]),
        }

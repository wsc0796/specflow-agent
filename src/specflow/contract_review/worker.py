"""One persistent-queue worker with a synchronous adapter and independent cleanup."""

import json
import threading
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from specflow.contract_review.common import ReviewError, canonical, digest, now
from specflow.contract_review.inputs import project_rule_material
from specflow.contract_review.protocol import ReviewResult, SubmitReport
from specflow.contract_review.provider import OpenAIReviewAdapter, ProviderFailure
from specflow.contract_review.report_validation import (
    require,
    validate_material_refs,
    validate_report,
)
from specflow.contract_review.shared_ledger import SharedLedger
from specflow.contract_review.sources import strict_json


class ReviewWorker:
    def __init__(self, service, adapter):
        if getattr(adapter, "execution_mode", None) != "test" and not isinstance(
            adapter, OpenAIReviewAdapter
        ):
            raise RuntimeError(
                "Register a controlled test adapter or the supported synchronous HTTP adapter"
            )
        self.service, self.adapter = service, adapter
        self.ledger = SharedLedger(service)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.pending = None
        self.faulted = False
        self.recovery = None

    def start(self):
        self.ledger.start()
        self.thread = threading.Thread(target=self._loop, name="contract-review-worker")
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.wake_event.set()
        if self.thread:
            self.thread.join()
        if self.pending:
            thread, _, _, _, _ = self.pending
            if thread.ident is not None:
                thread.join()
                self._maintain_pending()

        if self.recovery:
            context, _ = self.recovery
            self.ledger.fail(
                context, "INTERRUPTED", time.monotonic() - context["started_monotonic"]
            )
            self.recovery = None

    def _loop(self):
        while not self.stop_event.is_set():
            context = None
            try:
                if self.recovery:
                    recovering, code = self.recovery
                    self.ledger.fail(
                        recovering, code, time.monotonic() - recovering["started_monotonic"]
                    )
                    self.recovery = None
                self._maintain_pending()
                self.faulted = False
                if self.pending is None:
                    context = self.ledger.claim()
                    if context:
                        self._run_job(context)
                        continue
            except ReviewError as error:
                if error.code not in {
                    "DATABASE_BUSY",
                    "DEPENDENCY_UNAVAILABLE",
                    "STORAGE_CAPACITY_EXCEEDED",
                    "EVIDENCE_PERSISTENCE_FAILED",
                }:
                    self.faulted = True
                    return
                if context is not None:
                    self.recovery = (context, "EVIDENCE_PERSISTENCE_FAILED")
                self.faulted = True
            except Exception:
                # Publish the stopped dispatch state before the failure commit
                # becomes visible to concurrent HTTP readers.
                self.faulted = True
                if context is not None:
                    try:
                        elapsed = (
                            time.monotonic() - context["started_monotonic"]
                            if "started_monotonic" in context
                            else None
                        )
                        self.ledger.fail(context, "INTERNAL_ERROR", elapsed)
                    except Exception:
                        pass  # Storage or execution ownership may itself be unavailable.
                # If required storage is unavailable, no new dispatch is safe.
                # Unknown programming failures require an explicit subsequent startup.
                return
            self.wake_event.wait(0.1 if self.faulted else 0.02)
            self.wake_event.clear()

    def _maintain_pending(self):
        if self.pending is None:
            return
        thread, box, call_id, instance_id, context = self.pending
        if thread.is_alive() or not box.get("finished"):
            return
        result = box.get("result")
        failure = box.get("failure")
        usage = (
            failure.usage
            if failure
            else result.get("usage", {})
            if isinstance(result, dict)
            else {}
        )
        outcome = (
            failure.remote_outcome
            if failure
            else "not_applicable"
            if box.get("kind") == "tool"
            else "known"
        )
        if box.get("not_entered"):
            self.ledger.abort_unstarted(call_id, instance_id)
        else:
            self.ledger.settle_call(
                call_id,
                instance_id,
                usage=usage if isinstance(usage, dict) else {},
                quiesced=True,
                evidence="wrapper_thread_exited",
                remote_outcome=outcome,
            )
        with self.service.store.transaction() as conn:
            self.ledger.owner(conn)
            if context.get("work_kind") == "impact":
                row = self.service.impacts.require(conn, context["discovery_id"])
                if row["status"] in ("failed", "interrupted"):
                    self.ledger.impact.settle_time(
                        conn, row, time.monotonic() - context["started_monotonic"]
                    )
            else:
                row = self.service.store.row(
                    conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=context["job_id"]
                )
                if row["status"] in ("failed", "interrupted"):
                    self.ledger.settle_time(
                        conn, row, time.monotonic() - context["started_monotonic"]
                    )
        self.pending = None

    def perform_io(self, context, call_id, instance_id, operation, timeout, *, kind="model"):
        if self.stop_event.is_set():
            raise ReviewError("INTERRUPTED", "宿主正在关闭。")
        box = {"kind": kind}
        start_gate, aborted = threading.Event(), threading.Event()

        def run():
            start_gate.wait()
            if aborted.is_set():
                box.update(not_entered=True, finished=True)
                return
            try:
                box["result"] = operation()
            except ProviderFailure as error:
                box["failure"] = error
            except ReviewError as error:
                box["failure"] = ProviderFailure(
                    error.code, remote_outcome="not_applicable" if kind == "tool" else "unknown"
                )
            except BaseException:
                box["failure"] = ProviderFailure(
                    "TOOL_ERROR" if kind == "tool" else "PROVIDER_ERROR",
                    remote_outcome="not_applicable" if kind == "tool" else "unknown",
                )
            finally:
                box["finished"] = True

        thread = threading.Thread(target=run, name="contract-review-io")
        self.pending = (thread, box, call_id, instance_id, context)
        start_error = None
        try:
            thread.start()
            if self.stop_event.is_set():
                raise ReviewError("INTERRUPTED", "宿主正在关闭。")
            self.ledger.dispatch_started(context, call_id)
        except BaseException as error:
            start_error = error.code if isinstance(error, ReviewError) else "IO_START_FAILED"
        if start_error:
            aborted.set()
            start_gate.set()
            if thread.ident is not None:
                thread.join()
            box.update(not_entered=True, finished=True)
            self.ledger.abort_unstarted(call_id, instance_id)
            self.pending = None
            raise ReviewError(start_error, "调用在进入 adapter 前终止。")
        start_gate.set()
        deadlines = [context["deadline"]]
        if context.get("child_deadline"):
            deadlines.append(context["child_deadline"])
        remaining_scope = min(
            (
                datetime.fromisoformat(value.replace("Z", "+00:00")) - datetime.now(UTC)
            ).total_seconds()
            for value in deadlines
        )
        deadline = time.monotonic() + min(timeout, remaining_scope)
        while thread.is_alive():
            if self.stop_event.is_set():
                raise ReviewError("INTERRUPTED", "宿主正在关闭。")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReviewError("CALL_RESULT_UNKNOWN", "等待超时，本地调用仍未收尾。")
            thread.join(min(0.02, remaining))
        self._maintain_pending()
        if box.get("failure"):
            raise box["failure"]
        return box.get("result")

    def model_call(self, context, role, data, material_entries):
        profile = context["frozen"]["execution_profile"]
        if profile["execution_mode"] != self.adapter.execution_mode:
            raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "Adapter 与冻结执行模式不符。")
        payload = {
            "model": profile["model"],
            "temperature": 0.0,
            "max_tokens": profile["max_output_tokens"],
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": profile[role + "_prompt"]},
                {"role": "user", "content": canonical(data)},
            ],
        }
        if isinstance(self.adapter, OpenAIReviewAdapter):
            payload = self.adapter.prepare(payload, profile)
        replay = context.get("replay_session")
        if replay is not None:
            reused = replay.take(context, role, payload, material_entries)
            if reused is not None:
                return reused
        retries = profile.get("dependency_retry_limit", 0)
        retry_of = None
        for attempt in range(retries + 1):
            call_id, instance_id = self.ledger.reserve_call(
                context, role, payload, material_entries, retry_of=retry_of
            )
            operation = (
                (lambda: self.adapter.complete(payload, profile=profile))
                if isinstance(self.adapter, OpenAIReviewAdapter)
                else (lambda: self.adapter.complete(payload))
            )
            try:
                result = self.perform_io(
                    context, call_id, instance_id, operation, profile["model_timeout_seconds"]
                )
                if not isinstance(result, dict) or not isinstance(result.get("content"), str):
                    raise ProviderFailure("PROVIDER_RESPONSE_INVALID", remote_outcome="known")
                try:
                    if len(result["content"].encode("utf-8")) > 128 * 1024:
                        raise ProviderFailure("PROVIDER_RESPONSE_TOO_LARGE", remote_outcome="known")
                except UnicodeError:
                    raise ProviderFailure(
                        "PROVIDER_RESPONSE_INVALID", remote_outcome="known"
                    ) from None
                usage = result.get("usage", {})
                if not isinstance(usage, dict) or any(
                    type(value) is not int or value < 0 for value in usage.values()
                ):
                    raise ProviderFailure("PROVIDER_RESPONSE_INVALID", remote_outcome="known")
                if usage.get("output_tokens", 0) > profile["max_output_tokens"]:
                    raise ProviderFailure("BUDGET_EXHAUSTED", usage=usage, remote_outcome="known")
            except ProviderFailure as error:
                self.ledger.record_failure(context, call_id, error)
                if error.retryable and attempt < retries:
                    retry_of = call_id
                    continue
                raise ReviewError(error.code, "模型依赖失败。") from None
            return call_id, result
        raise ReviewError("PROVIDER_ERROR", "依赖请求没有结果。")

    def _invoke(self, context, role, data, material_entries):
        call_id, result = self.model_call(context, role, data, material_entries)
        try:
            parsed = strict_json(result["content"])
            read_refs = [entry["source_ref"] for entry in material_entries if "source_ref" in entry]
            if role == "analysis":
                action = SubmitReport.model_validate(parsed)
                validate_material_refs(
                    [ref.model_dump() for ref in action.reason.evidence_refs],
                    context["frozen"],
                    context["sources"],
                    read_refs,
                )
                historical = {}
                report_ids = {
                    ref.report_revision_id
                    for finding in action.report.findings
                    for ref in finding.related_findings
                }
                if report_ids:
                    with self.service.store.read() as conn:
                        for report_id in report_ids:
                            row = self.service.store.row(
                                conn,
                                "SELECT body FROM contract_review_reports "
                                "WHERE id=:id AND review_id=:review",
                                id=report_id,
                                review=context["review_id"],
                            )
                            if row:
                                historical[report_id] = {
                                    item["id"]
                                    for item in json.loads(row["body"])["payload"]["findings"]
                                }
                value = validate_report(
                    action.report.model_dump(exclude_none=True),
                    context["frozen"],
                    context["sources"],
                    read_refs,
                    historical_reports=historical,
                    projected_evidence_ids=[
                        entry["evidence_id"] for entry in material_entries if "evidence_id" in entry
                    ],
                )
            else:
                value = ReviewResult.model_validate(parsed)
                if value.candidate_report_hash != data["candidate_report_hash"]:
                    raise ValueError("Fixed review candidate mismatch")
                fields = {
                    "finding": "findings",
                    "question": "questions",
                    "work_item": "work_items",
                    "acceptance": "acceptance_items",
                }
                for issue in value.issues:
                    if issue.subject_kind == "report":
                        require(issue.subject_id == "", "Report issue needs an empty subject ID")
                    else:
                        require(
                            issue.subject_id
                            in {
                                item["id"]
                                for item in data["candidate_report"][fields[issue.subject_kind]]
                            },
                            "Fixed review subject belongs to another report",
                        )
                    validate_material_refs(
                        [ref.model_dump() for ref in issue.evidence_refs],
                        context["frozen"],
                        context["sources"],
                        read_refs,
                    )
        except ValueError:
            self.ledger.record_result(
                context, call_id, result, accepted=False, reason="ACTION_SCHEMA_INVALID"
            )
            if role == "review":
                raise ReviewError("REPORT_REVIEW_FAILED", "固定复核协议或候选归属非法。") from None
            raise
        self.ledger.record_result(
            context, call_id, result, accepted=True, reason="FORMAT_AND_SCOPE_VALID"
        )
        return value

    def _run_job(self, context):
        if context.get("work_kind") == "impact":
            from specflow.contract_review.impact_runner import ImpactRunner

            return ImpactRunner(self, context).run()
        context["started_monotonic"] = time.monotonic()
        frozen = context["frozen"]
        if frozen["execution_profile"]["engine_version"] == "contract-review-engine.v2":
            from specflow.contract_review.dynamic_runner import DynamicRunner
            from specflow.contract_review.replay import ReplaySession

            if frozen["execution_profile"]["options"]["replay"]:
                context["replay_session"] = ReplaySession(
                    self.service.replay_records, self.ledger.fence, context
                )
            DynamicRunner(self, context).run()
            return
        reads = [
            {"source_id": source_id, "selector": {"kind": "full"}}
            for source_id in context["sources"]
        ]
        entries = [
            {
                "source_ref": ref,
                "body_hash": context["sources"][ref["source_id"]]["body_hash"],
                "body": context["sources"][ref["source_id"]]["body"],
                "message_index": 1,
                "disposition": "retained",
            }
            for ref in reads
        ]
        data = {
            "request": frozen["original_request"]["request"],
            "targets": frozen["target_manifest"],
            "check_manifest": frozen["check_manifest"],
            "adoption_records": frozen["adoption_records"],
            "resolutions": frozen["resolutions"],
            "review_directives": frozen.get("review_directives", []),
            "sources": list(context["sources"].values()),
        }
        entries.extend(
            project_rule_material(rule)
            for rule in frozen["adoption_records"]
            if rule["origin"]["kind"] == "project_decision"
        )
        if context["verification_evidence"]:
            data["verification_evidence"] = context["verification_evidence"]
            data["verification_evidence_adoptions"] = frozen["verification_evidence_adoptions"]
            entries.extend(
                {
                    "evidence_id": record["evidence_id"],
                    "body_hash": record["body_hash"],
                    "body": record,
                    "message_index": 1,
                    "disposition": "retained",
                }
                for record in context["verification_evidence"]
            )
        try:
            corrections, reworks = 0, 0
            while True:
                try:
                    report, quality = self._invoke(context, "analysis", data, entries)
                except (ValueError, ValidationError) as error:
                    if corrections >= 1:
                        raise ReviewError(
                            "ACTION_PROTOCOL_ERROR", "候选报告未通过结构校验。"
                        ) from error
                    corrections += 1
                    data["protocol_feedback"] = "候选结构或引用不符合冻结协议；请修正后重新提交。"
                    continue
                candidate_hash = digest(report)
                verdict = self._invoke(
                    context,
                    "review",
                    {**data, "candidate_report_hash": candidate_hash, "candidate_report": report},
                    entries,
                )
                if verdict.outcome == "accept":
                    self.ledger.commit_report(
                        context, report, quality, time.monotonic() - context["started_monotonic"]
                    )
                    return
                if reworks >= 1:
                    raise ReviewError("REPORT_REVIEW_FAILED", "固定复核在返工后仍未接受。")
                reworks += 1
                data["revision_feedback"] = verdict.model_dump()
        except ReviewError as error:
            self.ledger.fail(context, error.code, time.monotonic() - context["started_monotonic"])
        except (ValueError, ValidationError):
            self.ledger.fail(
                context, "ACTION_PROTOCOL_ERROR", time.monotonic() - context["started_monotonic"]
            )

    def dispatch_gate(self, conn):
        runtime = self.service.store.row(conn, "SELECT * FROM contract_review_runtime WHERE id=1")
        reasons, blocked = [], []
        if self.faulted or self.stop_event.is_set() or self.thread is None:
            reasons.append("runtime_not_ready")
        if runtime["slot_call_id"]:
            row = self.service.store.row(
                conn,
                "SELECT body FROM contract_review_calls WHERE id=:id",
                id=runtime["slot_call_id"],
            )
            body = json.loads(row["body"])
            reasons.append("local_io_unconfirmed")
            blocked.append(
                {
                    "kind": "analysis_call",
                    "call_id": runtime["slot_call_id"],
                    "execution_instance_id": body["execution_instance_id"],
                    "local_io_state": body["local_io_state"],
                    "evidence_refs": body["maintenance_evidence"],
                    "missing_evidence": "同步 adapter 尚未返回或其进程实例尚未确认退出。",
                }
            )
        if runtime["slot_discovery_call_id"]:
            row = self.service.store.row(
                conn,
                "SELECT body FROM contract_impact_calls WHERE id=:id",
                id=runtime["slot_discovery_call_id"],
            )
            body = json.loads(row["body"])
            reasons.append("local_io_unconfirmed")
            blocked.append(
                dict(
                    kind="discovery_call",
                    call_id=runtime["slot_discovery_call_id"],
                    execution_instance_id=body["execution_instance_id"],
                    local_io_state=body["local_io_state"],
                    evidence_refs=body["maintenance_evidence"],
                    missing_evidence="同步发现调用尚未确认退出。",
                )
            )
        return {
            "can_claim": not reasons,
            "reason_codes": reasons,
            "blocked_by": blocked,
            "observed_at": now(),
        }

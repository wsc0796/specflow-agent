"""One persistent-queue worker with a synchronous adapter and independent cleanup."""

import json
import threading
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from specflow.contract_review.common import ReviewError, canonical, digest, now
from specflow.contract_review.execution import ExecutionLedger
from specflow.contract_review.protocol import ReviewResult, SubmitReport
from specflow.contract_review.report_validation import (
    require,
    validate_material_refs,
    validate_report,
)
from specflow.contract_review.sources import strict_json


class ReviewWorker:
    def __init__(self, service, adapter):
        if getattr(adapter, "execution_mode", None) != "test":
            raise RuntimeError("This vertical slice requires an explicitly controlled test adapter")
        self.service, self.adapter = service, adapter
        self.ledger = ExecutionLedger(service)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.pending = None
        self.faulted = False

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

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                self._maintain_pending()
                if self.pending is None:
                    context = self.ledger.claim()
                    if context:
                        self._run_job(context)
                        continue
            except Exception:
                # If required storage is unavailable, no new dispatch is safe.
                # Recovery is an explicit subsequent startup, not hidden retry.
                self.faulted = True
                return
            self.wake_event.wait(0.02)
            self.wake_event.clear()

    def _maintain_pending(self):
        if self.pending is None:
            return
        thread, box, call_id, instance_id, context = self.pending
        if thread.is_alive() or not box.get("finished"):
            return
        result = box.get("result")
        usage = result.get("usage", {}) if isinstance(result, dict) else {}
        self.ledger.settle_call(
            call_id,
            instance_id,
            usage=usage if isinstance(usage, dict) else {},
            quiesced=True,
            evidence="wrapper_thread_exited",
        )
        with self.service.store.transaction() as conn:
            self.ledger.owner(conn)
            row = self.service.store.row(
                conn, "SELECT * FROM contract_review_jobs WHERE id=:id", id=context["job_id"]
            )
            if row["status"] in ("failed", "interrupted"):
                self.ledger.settle_time(conn, row, time.monotonic() - context["started_monotonic"])
        self.pending = None

    def _invoke(self, context, role, data, material_entries):
        if self.stop_event.is_set():
            raise ReviewError("INTERRUPTED", "宿主正在关闭。")
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
        call_id, instance_id = self.ledger.reserve_call(context, role, payload, material_entries)
        self.ledger.dispatch_started(context, call_id)
        box = {}

        def run():
            try:
                box["result"] = self.adapter.complete(payload)
            except BaseException:
                box["error"] = "PROVIDER_ERROR"
            finally:
                box["finished"] = True

        thread = threading.Thread(target=run, name="contract-review-io")
        self.pending = (thread, box, call_id, instance_id, context)
        thread.start()
        deadline = min(
            time.monotonic() + profile["model_timeout_seconds"],
            time.monotonic()
            + (
                datetime.fromisoformat(context["deadline"].replace("Z", "+00:00"))
                - datetime.now(UTC)
            ).total_seconds(),
        )
        while thread.is_alive():
            if self.stop_event.is_set():
                raise ReviewError("INTERRUPTED", "宿主正在关闭。")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReviewError("CALL_RESULT_UNKNOWN", "等待超时，本地调用仍未收尾。")
            thread.join(min(0.02, remaining))
        self._maintain_pending()
        if box.get("error"):
            raise ReviewError(box["error"], "模型依赖失败。")
        result = box.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("content"), str):
            raise ReviewError("PROVIDER_RESPONSE_INVALID", "模型响应结构非法。")
        if len(result["content"].encode("utf-8")) > 128 * 1024:
            raise ReviewError("PROVIDER_RESPONSE_INVALID", "模型响应超过读取上限。")
        usage = result.get("usage", {})
        if not isinstance(usage, dict) or any(
            type(value) is not int or value < 0 for value in usage.values()
        ):
            raise ReviewError("PROVIDER_RESPONSE_INVALID", "模型用量类型非法。")
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
        context["started_monotonic"] = time.monotonic()
        frozen = context["frozen"]
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
            "sources": list(context["sources"].values()),
        }
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
        return {
            "can_claim": not reasons,
            "reason_codes": reasons,
            "blocked_by": blocked,
            "observed_at": now(),
        }

"""One worker owner and queue, with explicit business-ledger routing."""

from specflow.contract_review.dynamic_ledger import DynamicLedger
from specflow.contract_review.impact_ledger import ImpactLedger


class SharedLedger(DynamicLedger):
    def __init__(self, service):
        super().__init__(service)
        self.impact = ImpactLedger(self)

    def start(self):
        super().start()
        self.impact.start()

    def claim(self):
        with self.store.transaction() as conn:
            row = self.store.row(
                conn,
                "SELECT kind FROM ("
                "SELECT 'review' AS kind,created_at,id FROM contract_review_jobs "
                "WHERE status='queued' "
                "UNION ALL SELECT 'impact' AS kind,created_at,id FROM contract_impact_discoveries "
                "WHERE status='queued') ORDER BY created_at,id LIMIT 1",
            )
            if row is None:
                return None
            return (
                self.impact.claim(_conn=conn)
                if row["kind"] == "impact"
                else super().claim(_conn=conn)
            )

    def reserve_call(self, context, *args, **kwargs):
        if context.get("work_kind") == "impact":
            return self.impact.reserve_call(context, *args, **kwargs)
        return super().reserve_call(context, *args, **kwargs)

    def dispatch_started(self, context, call_id):
        if context.get("work_kind") == "impact":
            return self.impact.dispatch_started(context, call_id)
        return super().dispatch_started(context, call_id)

    def settle_call(self, call_id, *args, **kwargs):
        if call_id.startswith("icall_"):
            return self.impact.settle_call(call_id, *args, **kwargs)
        return super().settle_call(call_id, *args, **kwargs)

    def abort_unstarted(self, call_id, instance_id):
        if call_id.startswith("icall_"):
            return self.impact.abort_unstarted(call_id, instance_id)
        return super().abort_unstarted(call_id, instance_id)

    def record_result(self, context, *args, **kwargs):
        if context.get("work_kind") == "impact":
            return self.impact.record_result(context, *args, **kwargs)
        return super().record_result(context, *args, **kwargs)

    def record_failure(self, context, *args, **kwargs):
        if context.get("work_kind") == "impact":
            return self.impact.record_failure(context, *args, **kwargs)
        return super().record_failure(context, *args, **kwargs)

    def fail(self, context, code, elapsed=None):
        if context.get("work_kind") == "impact":
            return self.impact.fail(context, code, elapsed)
        return super().fail(context, code, elapsed)

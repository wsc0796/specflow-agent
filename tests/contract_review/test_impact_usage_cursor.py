"""Unknown-usage denial must not retain a read cursor through its traceback."""

import json
from contextlib import ExitStack

import pytest
from sqlalchemy import event
from test_impact_discovery import URL, post
from test_impact_discovery import impact_app as impact_app

from specflow.contract_review import impact_ledger
from specflow.contract_review.common import ReviewError
from specflow.contract_review.shared_ledger import SharedLedger


def test_usage_denial_releases_cursor_before_failure_is_persisted(impact_app, monkeypatch):
    with impact_app(worker=False) as (client, service, body, _, _):
        original_identity = impact_ledger.identity
        call_ids = iter(["icall_000", "icall_999"])
        monkeypatch.setattr(
            impact_ledger,
            "identity",
            lambda prefix: next(call_ids) if prefix == "icall" else original_identity(prefix),
        )
        readers, writers = [], []
        engine = service.store.database.engine

        def capture(connection, cursor, statement, parameters, context, executemany):
            normalized = " ".join(statement.split())
            physical = id(connection.connection.driver_connection)
            if normalized.startswith("SELECT body FROM contract_impact_calls WHERE discovery_id"):
                readers.append(physical)
            if normalized.startswith("UPDATE contract_impact_discoveries SET"):
                writers.append(physical)

        event.listen(engine, "before_cursor_execute", capture)
        ledger = SharedLedger(service)
        ledger.start()
        discovery_id = post(client, URL, body).json()["discovery_id"]
        context = ledger.claim()
        profile = context["frozen"]["execution_profile"]
        payload = dict(model=profile["model"], max_tokens=profile["max_output_tokens"], messages=[])
        model, instance = ledger.reserve_call(context, "analysis", payload, [])
        ledger.dispatch_started(context, model)
        ledger.settle_call(
            model,
            instance,
            usage={},
            quiesced=True,
            evidence="wrapper_thread_exited",
            remote_outcome="known",
        )
        ledger.record_result(context, model, dict(content="{}"), accepted=True, reason="controlled")
        tool, instance = ledger.reserve_call(
            context, "tool", dict(tool="list_sources"), [], kind="tool"
        )
        ledger.dispatch_started(context, tool)
        ledger.settle_call(
            tool,
            instance,
            usage={},
            quiesced=True,
            evidence="wrapper_thread_exited",
            remote_outcome="not_applicable",
        )
        ledger.record_result(context, tool, {}, accepted=True, reason="controlled")
        # Keep the original exception/traceback alive and force the failure commit
        # onto a second physical SQLite connection, as concurrent status polls do.
        with pytest.raises(ReviewError) as denied:
            ledger.reserve_call(context, "analysis", payload, [])
        assert denied.value.code == "USAGE_UNKNOWN"
        reader_id = readers[-1]
        with ExitStack() as holds:
            for _ in range(10):
                reader = holds.enter_context(engine.connect())
                if id(reader.connection.driver_connection) == reader_id:
                    break
            else:
                raise AssertionError("Original physical reader connection was not checked out")
            with engine.connect() as writer:
                writer.exec_driver_sql("PRAGMA busy_timeout=50")
            writers.clear()
            try:
                ledger.fail(context, denied.value.code, 0.1)
            finally:
                assert writers and writers[-1] != reader_id
        with service.store.read() as conn:
            row = service.impacts.require(conn, discovery_id)
        assert row["status"] == "failed"
        assert json.loads(row["body"])["error_code"] == "USAGE_UNKNOWN"

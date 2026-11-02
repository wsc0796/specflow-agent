"""Regressions for the three independently reproduced Astra findings."""

import copy
import json

import pytest
from test_impact_discovery import URL, counts, post, terminal
from test_impact_discovery import impact_app as impact_app

from specflow.contract_review.shared_ledger import SharedLedger


def test_restart_preserves_quiesced_proof_and_settles_time_once(impact_app):
    with impact_app(worker=False) as (client, service, body, _, _):
        old = SharedLedger(service)
        old.start()
        discovery_id = post(client, URL, body).json()["discovery_id"]
        context = old.claim()
        profile = context["frozen"]["execution_profile"]
        wire = dict(model=profile["model"], max_tokens=profile["max_output_tokens"], messages=[])
        call, instance = old.reserve_call(context, "analysis", wire, [])
        old.dispatch_started(context, call)
        old.settle_call(
            call,
            instance,
            usage=dict(input_tokens=3, output_tokens=4),
            quiesced=True,
            evidence="wrapper_thread_exited",
            remote_outcome="known",
        )
        fresh = SharedLedger(service)
        fresh.start()
        state = service.impacts.get(discovery_id)
        assert state["status"] == "interrupted"
        assert state["budget"]["execution_seconds_reserved"] == 0
        assert 0 < state["budget"]["execution_seconds_charged"] <= profile["attempt_seconds"]
        with service.store.read() as conn:
            raw = service.store.row(
                conn, "SELECT * FROM contract_impact_calls WHERE id=:id", id=call
            )
            value = json.loads(raw["body"])
            runtime = service.store.row(conn, "SELECT * FROM contract_review_runtime WHERE id=1")
        assert value["local_io_state"] == "quiesced" and value["result"] is None
        assert value["maintenance_evidence"][0]["kind"] == "wrapper_thread_exited"
        assert raw["status"] == "UNKNOWN"
        assert runtime["slot_discovery_call_id"] is None
        again = SharedLedger(service)
        again.start()
        assert service.impacts.get(discovery_id)["budget"] == state["budget"]


@pytest.mark.parametrize("fabricated", ["version", "path", "method", "path_prefix"])
def test_candidate_identity_without_basis_is_rejected(impact_app, fabricated):
    def transform(action, data):
        if action["action"] == "submit_candidates":
            candidate = action["candidates"][0]
            if fabricated == "version":
                candidate["api_version"] = "v999"
            elif fabricated == "method":
                candidate["endpoint"]["method"] = "DELETE"
            else:
                candidate["endpoint"]["path"] = (
                    "/export" if fabricated == "path_prefix" else "/not-supported-by-any-source"
                )
        return action

    with impact_app(transform=transform) as (client, service, body, _, _):
        discovery_id = post(client, URL, body).json()["discovery_id"]
        state = terminal(client, URL + "/" + discovery_id)
        assert state["status"] == "failed" and state["error_code"] == "ACTION_PROTOCOL_ERROR"
        assert state["catalog"] is None and counts(service) == (0, 0, 0, 0)


def test_replay_does_not_depend_on_current_profile(impact_app):
    with impact_app(worker=False) as (client, service, body, _, _):
        first = post(client, URL, body, "frozen-command")
        assert first.status_code == 202
        service.impacts.profiles.clear()
        repeated = post(client, URL, body, "frozen-command")
        assert repeated.status_code == 202 and repeated.json() == first.json()
        changed = copy.deepcopy(body)
        changed["change_request"] = "变更后的命令不能复用同一键"
        conflict = post(client, URL, changed, "frozen-command")
        assert conflict.status_code == 409 and "IDEMPOTENCY_KEY_REUSED" in conflict.text
        with service.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_impact_discoveries"
                ).scalar_one()
                == 1
            )

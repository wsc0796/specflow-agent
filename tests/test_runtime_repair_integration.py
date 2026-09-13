"""Cross-PR contracts: typed failures remain shared and fail closed."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_runs import client_for, register_project

import specflow.runner_multi as runner
import specflow.runs as runs
from specflow.api_security import ApiSecurity
from specflow.db import Database, Project, WorkflowRun
from specflow.runs import RunCreate, RunRepository, RunService
from specflow.single_flight import Flight, SingleFlightCoordinator


@pytest.mark.parametrize(
    "fault, expected",
    [
        ("no-evidence", "EVIDENCE_NOT_FOUND"),
        ("invalid-output", "MULTI_AGENT_RUN_FAILED"),
        ("handoff-tamper", "HANDOFF_INTEGRITY_FAILED"),
        ("handoff-inplace", "HANDOFF_INTEGRITY_FAILED"),
        ("handoff-agent-id", "HANDOFF_INTEGRITY_FAILED"),
        ("handoff-role", "HANDOFF_INTEGRITY_FAILED"),
        ("handoff-output", "HANDOFF_INTEGRITY_FAILED"),
        ("handoff-unhashable", "MULTI_AGENT_RUN_FAILED"),
        ("handoff-cycle", "MULTI_AGENT_RUN_FAILED"),
        ("handoff-mixed-keys", "MULTI_AGENT_RUN_FAILED"),
    ],
)
def test_equivalent_api_requests_share_classified_failures(tmp_path, monkeypatch, fault, expected):
    repo = tmp_path / "repo"
    repo.mkdir()
    content = (
        "def unrelated(): return 0\n" if fault == "no-evidence" else "def feature(): return 1\n"
    )
    (repo / "app.py").write_text(content, encoding="utf-8")
    coordinator = SingleFlightCoordinator()
    monkeypatch.setattr(runs, "DEFAULT_COORDINATOR", coordinator)
    entered, joined, release = Event(), Event(), Event()
    original_collect, original_wait = runner.EvidenceCollector.collect, Flight.wait
    original_complete = runner.MockLLMClient.complete
    collections, completions, receivers = [], [], []
    recorded_hashes = []

    def collect(self, **kwargs):
        collections.append(1)
        entered.set()
        assert release.wait(5)
        return original_collect(self, **kwargs)

    def wait(self, timeout):
        joined.set()
        return original_wait(self, timeout)

    def complete(self, request):
        completions.append(1)
        return original_complete(self, request)

    def receiver(self, context):
        receivers.append(1)
        pytest.fail("invalid upstream data reached its receiver")

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", wait)
    monkeypatch.setattr(runner.MockLLMClient, "complete", complete)
    monkeypatch.setattr(runner.DesignAgent, "execute", receiver)
    if fault == "invalid-output":
        monkeypatch.setattr(
            runner.RepositoryAnalystAgent,
            "execute",
            lambda self, ctx: {
                "agent_id": "repository-analyst-agent-v1",
                "role": "repository_analyst",
                "success": True,
                "schema_validated": True,
                "output": {},
            },
        )
    elif fault.startswith("handoff-"):
        original_validate = runner.HandoffValidator.validate_payload

        def tamper(self, handoff, sender, payloads):
            changed = deepcopy(payloads) if fault == "handoff-tamper" else payloads
            key = handoff.payload_ref.removeprefix("agent-outputs.json#")
            recorded_hashes.append(handoff.output_hash)
            if fault == "handoff-agent-id":
                changed[key]["agent_id"] = "test-private-payload"
            elif fault == "handoff-role":
                changed[key]["role"] = {"untrusted": "test-private-payload"}
            elif fault == "handoff-output":
                changed[key]["output"] = "test-private-payload"
            elif fault == "handoff-unhashable":
                changed[key]["role"] = {"test-private-payload"}
            elif fault == "handoff-cycle":
                changed[key]["output"]["test-private-payload"] = changed[key]
            elif fault == "handoff-mixed-keys":
                changed[key]["output"] = {
                    1: "test-private-payload",
                    "summary": "test-private-payload",
                }
            else:
                changed[key]["output"]["summary"] = "test-private-payload"
            return original_validate(self, handoff, sender, changed)

        monkeypatch.setattr(runner.HandoffValidator, "validate_payload", tamper)

    with client_for(tmp_path) as client, ThreadPoolExecutor(2) as pool:
        project_id = register_project(client, repo)
        payload = {"project_id": project_id, "requirement": "feature"}
        owner = pool.submit(client.post, "/api/v1/runs", json=payload)
        try:
            assert entered.wait(5)
            follower = pool.submit(client.post, "/api/v1/runs", json=payload)
            assert joined.wait(5)
            assert not owner.done() and not follower.done()
            assert collections == [1] and coordinator.active_count == 1
        finally:
            release.set()
        responses = [owner.result(5), follower.result(5)]
        assert all(response.status_code == 201 for response in responses)
        first, second = [response.json() for response in responses]
        assert first["id"] != second["id"]
        assert first["single_flight"]["role"] == "owner"
        assert second["single_flight"] == {"role": "follower", "owner_run_id": first["id"]}
        for body in (first, second):
            assert body["status"] == body["result_status"] == "failed_runtime"
            assert body["error_code"] == expected
            assert body["artifact_available"]
            assert client.get(f"/api/v1/runs/{body['id']}/review-package").status_code == 409
            assert "test-private-payload" not in str(body)
        indexes = [
            client.get(f"/api/v1/runs/{body['id']}/artifacts").json() for body in (first, second)
        ]
        assert indexes[0]["files"] == indexes[1]["files"]
        assert "_COMPLETE" in indexes[0]["files"]
        owner_directory = next((tmp_path / "run-artifacts" / first["id"]).glob("run-multi-*"))
        if fault.startswith("handoff-"):
            manifest = json.loads((owner_directory / "manifest.json").read_text(encoding="utf-8"))
            assert set(manifest["failure_context"]) == {
                "handoff_id",
                "from_agent_id",
                "to_agent_id",
                "payload_ref",
            }
            for artifact in owner_directory.iterdir():
                if artifact.is_file():
                    contents = artifact.read_text(encoding="utf-8")
                    assert "test-private-payload" not in contents
                    assert all(digest not in contents for digest in recorded_hashes)
        assert not (tmp_path / "run-artifacts" / second["id"]).exists()
    assert coordinator.active_count == 0
    assert not receivers
    assert len(completions) == (0 if fault == "no-evidence" else 6)


@pytest.mark.parametrize(
    "failure, expected",
    [
        ("budget", "CALL_BUDGET_EXCEEDED"),
        ("runtime", "MULTI_AGENT_RUN_FAILED"),
    ],
)
def test_unrelated_failures_keep_trusted_stage_diagnostics(
    service_context, monkeypatch, failure, expected
):
    from specflow.policy import SpecFlowError

    repo, db, security, coordinator, service, create = service_context

    def fail_design(self, context):
        if failure == "budget":
            raise SpecFlowError("CALL_BUDGET_EXCEEDED", "safe budget failure")
        raise RuntimeError("test-runtime-failure")

    monkeypatch.setattr(runner.DesignAgent, "execute", fail_design)
    result = create()
    assert result.current_state == "failed_runtime"
    assert result.error_code == expected
    assert result.artifact_directory is not None
    directory = service.artifact_root / result.artifact_directory
    outputs = json.loads((directory / "agent-outputs.json").read_text(encoding="utf-8"))
    assert outputs["stage-0/repository-analyst-agent-v1"]["output"]["summary"]
    assert (directory / "_COMPLETE").is_file()
    assert coordinator.active_count == 0


# Promote the verified independent cancellation/cross-entry probes into regression coverage.
@pytest.fixture
def service_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text("def feature(): return 1\n")
    db = Database(f"sqlite:///{(tmp_path / 'state.db').as_posix()}")
    db.create_schema()
    with db.factory() as session:
        project = Project(name="demo", repository_path=str(repo))
        session.add(project)
        session.commit()
        payload = RunCreate(project_id=project.id, requirement="feature")
    security = ApiSecurity(api_key="synthetic", allowed_repository_roots=(str(repo),))
    coordinator = SingleFlightCoordinator()
    service = RunService(
        RunRepository(),
        tmp_path / "artifacts",
        security.validate_repository_path,
        admit=security.admit_single_flight,
        coordinator=coordinator,
    )

    def create():
        with db.factory() as session:
            return service.create(session, payload)

    try:
        yield repo, db, security, coordinator, service, create
    finally:
        db.engine.dispose()


def test_actual_worker_cancellation_waits_for_peer_and_keeps_permit(service_context, monkeypatch):
    repo, db, security, coordinator, service, create = service_context
    entered, release, unwinding, joined = Event(), Event(), Event(), Event()
    real_design, real_risk = runner.DesignAgent.execute, runner.RiskReviewAgent.execute
    real_shutdown, real_wait = ThreadPoolExecutor.shutdown, Flight.wait

    def design(self, context):
        assert entered.wait(5)
        raise KeyboardInterrupt()

    def risk(self, context):
        entered.set()
        assert release.wait(5)
        return real_risk(self, context)

    def shutdown(self, *args, **kwargs):
        if entered.is_set() and not release.is_set():
            unwinding.set()
        return real_shutdown(self, *args, **kwargs)

    def wait(self, timeout):
        joined.set()
        return real_wait(self, timeout)

    monkeypatch.setattr(runner.DesignAgent, "execute", design)
    monkeypatch.setattr(runner.RiskReviewAgent, "execute", risk)
    monkeypatch.setattr(ThreadPoolExecutor, "shutdown", shutdown)
    monkeypatch.setattr(Flight, "wait", wait)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(create)
        try:
            assert unwinding.wait(5)
            follower = pool.submit(create)
            assert joined.wait(5)
            assert coordinator.active_count == 1
            assert not owner.done() and not follower.done()
            with pytest.raises(HTTPException) as rejected:
                security.admit_single_flight(True)
            assert rejected.value.status_code == 429
        finally:
            release.set()
        with pytest.raises(KeyboardInterrupt):
            owner.result(5)
        followed = follower.result(5)
        assert followed.current_state == "cancelled"
        assert followed.error_code == "RUN_CANCELLED"
    assert coordinator.active_count == 0
    with db.factory() as session:
        rows = list(session.scalars(select(WorkflowRun)))
        assert len(rows) == 2
        assert all(row.current_state == "cancelled" and row.finished_at for row in rows)
    monkeypatch.setattr(runner.DesignAgent, "execute", real_design)
    monkeypatch.setattr(runner.RiskReviewAgent, "execute", real_risk)
    retried = create()
    assert retried.current_state == "completed"
    assert retried.state_payload["single_flight"]["role"] == "owner"
    assert coordinator.active_count == 0


@pytest.mark.parametrize("api_is_owner", [True, False])
def test_cross_entry_same_safe_outcome_with_artifacts_inside_api_root(
    service_context, monkeypatch, api_is_owner
):
    repo, db, security, coordinator, service, create = service_context
    entered, release, joined = Event(), Event(), Event()
    real_collect, real_wait = runner.EvidenceCollector.collect, Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return real_collect(self, **kwargs)

    def wait(self, timeout):
        joined.set()
        return real_wait(self, timeout)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", wait)

    def direct():
        return runner.run_multi_agent(
            repo=repo,
            requirement="feature",
            output=service.artifact_root / "direct",
            mock=True,
            _coordinator=coordinator,
        )

    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(create if api_is_owner else direct)
        try:
            assert entered.wait(5)
            follower = pool.submit(direct if api_is_owner else create)
            assert joined.wait(5)
            assert len(calls) == 1
        finally:
            release.set()
        first, second = owner.result(5), follower.result(5)
    api_result, direct_result = (first, second) if api_is_owner else (second, first)
    assert api_result.current_state == "completed"
    assert direct_result == 0
    assert api_result.state_payload["single_flight"]["role"] == (
        "owner" if api_is_owner else "follower"
    )
    assert (
        api_result.state_payload["single_flight"]["owner_run_id"]
        == direct_result.single_flight["owner_run_id"]
    )
    assert service.artifact_root / api_result.artifact_directory == direct_result.artifact_directory
    assert coordinator.active_count == 0

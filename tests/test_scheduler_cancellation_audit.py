"""Deadline cancellation records Future facts without accepting aborted output."""

import json
import time
from concurrent.futures import CancelledError
from threading import Barrier, Event, Timer

import pytest

from specflow import runner_multi
from specflow.coordinator.exceptions import (
    ScheduleExecutionError,
    SchedulerAbortAgent,
    SchedulerAbortAudit,
)
from specflow.coordinator.scheduler import MultiAgentScheduler
from specflow.policy import ExecutionPolicy
from specflow.policy.models import ArtifactPolicy


def _timeout_error(action):
    with pytest.raises(ScheduleExecutionError) as raised:
        action()
    assert str(raised.value).startswith("TIME_BUDGET_EXCEEDED")
    return raised.value


def test_timeout_audits_running_and_queued_future_after_cleanup(monkeypatch):
    import specflow.coordinator.scheduler as scheduler_module

    started = Event()
    release = Event()
    queued_called = Event()

    def running(_):
        started.set()
        assert release.wait(2)
        return {"agent_id": "running"}

    def queued(_):
        queued_called.set()
        return {"agent_id": "queued"}

    original = scheduler_module.as_completed
    timers = []

    def controlled(futures, timeout):
        assert started.wait(1)
        timer = Timer(0.02, release.set)
        timer.start()
        timers.append(timer)
        return original(futures, timeout=0)

    monkeypatch.setattr(scheduler_module, "as_completed", controlled)
    error = _timeout_error(
        lambda: MultiAgentScheduler(max_parallel_workers=1).execute(
            (("running", "queued"),),
            {"running": running, "queued": queued},
            {},
            deadline=time.monotonic() + 5,
        )
    )
    for timer in timers:
        timer.join(1)
    assert queued_called.is_set() is False
    assert error.scheduler_abort == SchedulerAbortAudit(
        reason="deadline_exceeded",
        stage_index=0,
        agents=(
            SchedulerAbortAgent("running", True, False, "running", "finished_unvalidated"),
            SchedulerAbortAgent(
                "queued",
                True,
                True,
                "cancelled_before_start",
                "cancelled_before_start",
            ),
        ),
        cleanup_completed=True,
    )


def test_timeout_records_finished_future_without_claiming_business_success(monkeypatch):
    import specflow.coordinator.scheduler as scheduler_module

    finished = Event()
    release = Event()

    def done(_):
        finished.set()
        return {"agent_id": "done", "success": True, "output": {"private": "never-persist"}}

    def slow(_):
        assert release.wait(2)
        return {"agent_id": "slow"}

    original = scheduler_module.as_completed
    timers = []

    def controlled(futures, timeout):
        assert finished.wait(1)
        timer = Timer(0.02, release.set)
        timer.start()
        timers.append(timer)
        return original(futures, timeout=0)

    monkeypatch.setattr(scheduler_module, "as_completed", controlled)
    error = _timeout_error(
        lambda: MultiAgentScheduler(max_parallel_workers=1).execute(
            (("done", "slow"),),
            {"done": done, "slow": slow},
            {},
            deadline=time.monotonic() + 5,
        )
    )
    for timer in timers:
        timer.join(1)
    assert error.scheduler_abort.agents[0] == SchedulerAbortAgent(
        "done", True, False, "finished_unvalidated", "finished_unvalidated"
    )
    assert "success" not in error.scheduler_abort.as_dict()["agents"][0]


def test_timeout_when_all_tasks_started_never_invents_cancelled_before_start(monkeypatch):
    import specflow.coordinator.scheduler as scheduler_module

    started = Barrier(3)
    release = Event()

    def slow(_):
        started.wait(1)
        assert release.wait(2)
        return {"agent_id": "slow"}

    original = scheduler_module.as_completed
    timers = []

    def controlled(futures, timeout):
        started.wait(1)
        timer = Timer(0.02, release.set)
        timer.start()
        timers.append(timer)
        return original(futures, timeout=0)

    monkeypatch.setattr(scheduler_module, "as_completed", controlled)
    error = _timeout_error(
        lambda: MultiAgentScheduler(max_parallel_workers=2).execute(
            (("one", "two"),), {"one": slow, "two": slow}, {}, deadline=time.monotonic() + 5
        )
    )
    for timer in timers:
        timer.join(1)
    assert all(agent.cancel_succeeded is False for agent in error.scheduler_abort.agents)
    assert all(agent.state_during_abort == "running" for agent in error.scheduler_abort.agents)


def test_executor_cancelled_error_is_not_future_cancellation_audit():
    def cancelled(_):
        raise CancelledError("executor chose to stop")

    with pytest.raises(ScheduleExecutionError) as raised:
        MultiAgentScheduler().execute((("agent",),), {"agent": cancelled}, {})
    assert raised.value.scheduler_abort is None


def test_expired_deadline_has_no_future_audit_agents():
    called = []
    error = _timeout_error(
        lambda: MultiAgentScheduler().execute(
            (("agent",),),
            {"agent": lambda _: called.append(True)},
            {},
            deadline=time.monotonic() - 1,
        )
    )
    assert called == []
    assert error.scheduler_abort == SchedulerAbortAudit(
        reason="deadline_exceeded", stage_index=0, agents=(), cleanup_completed=True
    )


def test_runner_uses_logical_stage_and_keeps_abort_out_of_outputs(tmp_path, monkeypatch):
    import specflow.coordinator.scheduler as scheduler_module

    stage_one_started = Event()
    release = Event()
    sentinels = []
    original_as_completed = scheduler_module.as_completed
    timers = []

    def controlled_as_completed(futures, timeout):
        if stage_one_started.is_set():
            timer = Timer(0.02, release.set)
            timer.start()
            timers.append(timer)
            return original_as_completed(futures, timeout=0)
        return original_as_completed(futures, timeout=timeout)

    monkeypatch.setattr(scheduler_module, "as_completed", controlled_as_completed)

    class StageOneTimeoutScheduler:
        def __init__(self, *args, **kwargs):
            self._delegate = MultiAgentScheduler(max_parallel_workers=1)

        def execute(self, stages, executors, context, *, deadline=None):
            if stages[0][0] == "repository-analyst-agent-v1":
                return self._delegate.execute(stages, executors, context, deadline=deadline)
            return self._delegate.execute(stages, executors, context, deadline=time.monotonic() + 5)

    monkeypatch.setattr(runner_multi, "MultiAgentScheduler", StageOneTimeoutScheduler)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# Explain cancellation audit\n", encoding="utf-8")
    output = tmp_path / "output"
    downstream = []

    def slow_design(_):
        stage_one_started.set()
        assert release.wait(2)
        return {
            "agent_id": "design-agent-v1",
            "success": True,
            "output": {"summary": "never-persist"},
        }

    def queued_sentinel(_):
        sentinels.append(True)
        raise AssertionError("Queued Stage1 executor must not run")

    def forbidden(_):
        downstream.append(True)
        raise AssertionError("Synthesis/Review must not run")

    assert (
        runner_multi.run_multi_agent(
            repo=repo,
            requirement="Explain cancellation audit",
            output=output,
            mock=True,
            policy=ExecutionPolicy(max_llm_calls=12),
            _executor_overrides={
                "synthesis-agent-v1": forbidden,
                "review-agent-v1": forbidden,
                "design-agent-v1": slow_design,
                "test-strategy-agent-v1": queued_sentinel,
                "risk-review-agent-v1": queued_sentinel,
            },
        )
        == 3
    )
    for timer in timers:
        timer.join(1)
    assert downstream == []
    assert sentinels == []
    run_dir = next(output.glob("run-multi-*"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
    outputs = json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8"))
    assert manifest["error"] == "TIME_BUDGET_EXCEEDED"
    assert manifest["stages_completed"] == 1
    assert manifest["scheduler_abort"]["stage_index"] == 1
    assert manifest["scheduler_abort"]["cleanup_completed"] is True
    assert manifest["scheduler_abort"]["agents"][0]["agent_id"] == "design-agent-v1"
    assert manifest["scheduler_abort"]["agents"][0]["cancel_succeeded"] is False
    assert manifest["scheduler_abort"] == next(
        trace["scheduler_abort"] for trace in traces if trace["kind"] == "run"
    )
    assert set(outputs) == {"stage-0/repository-analyst-agent-v1"}
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.iterdir())
    assert "never-persist" not in serialized
    assert (run_dir / "_COMPLETE").is_file()


@pytest.mark.parametrize("failure", ["write", "size"])
def test_abort_artifact_failure_never_marks_run_complete(tmp_path, monkeypatch, failure):
    abort = SchedulerAbortAudit(
        reason="deadline_exceeded", stage_index=0, agents=(), cleanup_completed=True
    )
    if failure == "write":
        original = runner_multi._safe_write

        def fail_manifest(run_dir, filename, data, guard, **kwargs):
            if filename == "manifest.json":
                raise OSError("synthetic persistence failure")
            return original(run_dir, filename, data, guard, **kwargs)

        monkeypatch.setattr(runner_multi, "_safe_write", fail_manifest)
    else:

        def oversized_trace(*args, **kwargs):
            return [{"payload": "x" * 100_000, "scheduler_abort": abort.as_dict()}]

        monkeypatch.setattr(
            runner_multi,
            "_build_trace_tree",
            oversized_trace,
        )
    engine = type("Engine", (), {"state": "failed", "history": ()})()
    coordinator = type("Coordinator", (), {"engine": engine})()
    guard = runner_multi.RuntimeGuard(
        ExecutionPolicy(
            artifacts=ArtifactPolicy(max_artifact_bytes=64)
            if failure == "size"
            else ArtifactPolicy()
        )
    )
    run_dir = tmp_path / "output" / "run"
    runner_multi._persist_failed_run(
        output=tmp_path / "output",
        run_id="run",
        coordinator=coordinator,
        registry=runner_multi._build_registry(),
        model="mock",
        stages=[],
        plan=None,
        discovered_files=0,
        guard=guard,
        error="TIME_BUDGET_EXCEEDED",
        scheduler_abort=abort,
    )
    assert not (run_dir / "_COMPLETE").exists()

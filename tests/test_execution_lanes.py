"""Deterministic contracts for bounded local/provider resource admission."""

import importlib
from concurrent.futures import CancelledError, ThreadPoolExecutor, wait
from threading import Barrier, Event

import pytest


def _module():
    return importlib.import_module("specflow.coordinator.execution_lanes")


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def _manager(active=1, queued=1, **kwargs):
    from specflow.policy import models

    config = models.ExecutionLanePolicy(
        local_tool=models.LaneLimits(max_active=active, queue_capacity=queued),
        provider=models.LaneLimits(max_active=active, queue_capacity=queued),
    )
    return _module().LaneManager(config, **kwargs)


@pytest.mark.parametrize("lane", ["local_tool", "provider"])
def test_active_and_queue_bounds_reject_without_exposing_or_later_running_work(lane):
    entered, release = Event(), Event()
    ran = []

    def held():
        entered.set()
        assert release.wait(5)
        return "first"

    with _manager() as manager:
        first = manager.submit(lane, held)
        try:
            assert entered.wait(5)
            second = manager.submit(lane, lambda: ran.append("second"))
            before = manager.snapshot(lane)
            assert (before.active, before.queued, before.submitted) == (1, 1, 2)
            with pytest.raises(_module().LaneAdmissionError) as rejected:
                manager.submit(lane, lambda: ran.append("rejected"))
            assert rejected.value.code == "LANE_SATURATED"
            assert rejected.value.details["lane"] == lane
            assert not rejected.value.retryable
            assert manager.snapshot(lane).rejected == 1
            assert ran == []
        finally:
            release.set()
        assert manager.wait_for(first) == "first"
        assert manager.wait_for(second) is None
        assert ran == ["second"]
        after = manager.snapshot(lane)
        assert (after.active, after.queued, after.completed, after.started) == (0, 0, 2, 2)


@pytest.mark.parametrize("full,other", [("local_tool", "provider"), ("provider", "local_tool")])
def test_lane_capacity_is_independent(full, other):
    entered, release = Event(), Event()

    def held():
        entered.set()
        assert release.wait(5)

    with _manager() as manager:
        first = manager.submit(full, held)
        try:
            assert entered.wait(5)
            second = manager.submit(full, lambda: None)
            with pytest.raises(_module().LaneAdmissionError):
                manager.submit(full, lambda: None)
            assert manager.call(other, lambda: 17) == 17
            assert manager.snapshot(other).active == manager.snapshot(other).queued == 0
        finally:
            release.set()
        manager.wait_for(first)
        manager.wait_for(second)


@pytest.mark.parametrize("failure", [RuntimeError, SystemExit, KeyboardInterrupt])
def test_accepted_exception_settles_future_and_releases_capacity(failure):
    def fail():
        raise failure("test failure")

    with _manager() as manager:
        future = manager.submit("local_tool", fail)
        with pytest.raises(failure):
            manager.wait_for(future)
        assert future.done()
        assert manager.snapshot("local_tool").active == 0
        assert manager.call("local_tool", lambda: 23) == 23
        assert manager.snapshot("local_tool").completed == 2


def test_queued_cancellation_is_removed_and_does_not_grow_executor_queue():
    entered, release = Event(), Event()
    ran = []

    def held():
        entered.set()
        assert release.wait(5)

    with _manager() as manager:
        first = manager.submit("provider", held)
        try:
            assert entered.wait(5)
            for _ in range(100):
                future = manager.submit("provider", lambda: ran.append("bad"))
                assert future.cancel()
                assert future.cancelled()
                assert wait([future], timeout=1).not_done == set()
                assert manager.snapshot("provider").queued == 0
            queued = manager.submit("provider", lambda: "next")
            snapshot = manager.snapshot("provider")
            assert snapshot.cancelled == 100
            assert snapshot.active == snapshot.queued == 1
        finally:
            release.set()
        manager.wait_for(first)
        assert manager.wait_for(queued) == "next"
        assert ran == []


def test_queue_deadline_is_checked_before_work_starts():
    clock = Clock()
    entered, release = Event(), Event()
    ran = []

    def held():
        entered.set()
        assert release.wait(5)

    with _manager(clock=clock) as manager:
        first = manager.submit("local_tool", held)
        try:
            assert entered.wait(5)
            second = manager.submit("local_tool", lambda: ran.append("bad"), deadline=10)
            clock.now = 10
        finally:
            release.set()
        manager.wait_for(first)
        with pytest.raises(CancelledError):
            second.result(timeout=5)
        manager.drain([second])
        assert second.cancelled()
        assert ran == []
        assert manager.snapshot("local_tool").cancelled == 1
        assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0


def test_deadline_waits_for_started_work_before_releasing_capacity():
    clock = Clock()
    started, release, waiting, returned = Event(), Event(), Event(), Event()
    failures = []

    def held():
        started.set()
        assert release.wait(5)

    with _manager(clock=clock) as manager:
        future = manager.submit("provider", held, deadline=10)
        assert started.wait(5)
        clock.now = 10

        def observer():
            waiting.set()
            try:
                manager.wait_for(future, deadline=10)
            except Exception as error:
                failures.append(error.code)
            finally:
                returned.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(observer)
            try:
                assert waiting.wait(5)
                assert not returned.is_set()
                assert manager.snapshot("provider").active == 1
                assert not future.cancel()
            finally:
                release.set()
            pending.result(timeout=5)
        assert failures == ["TIME_BUDGET_EXCEEDED"]
        assert manager.snapshot("provider").active == 0


def test_submission_failure_rolls_back_and_exposes_no_future():
    class FailOnceExecutor(ThreadPoolExecutor):
        failed = False

        def submit(self, *args, **kwargs):
            if not type(self).failed:
                type(self).failed = True
                raise RuntimeError("private executor error")
            return super().submit(*args, **kwargs)

    with _manager(executor_factory=FailOnceExecutor) as manager:
        with pytest.raises(_module().LaneAdmissionError) as error:
            manager.submit("local_tool", lambda: 1)
        assert "private" not in str(error.value)
        snapshot = manager.snapshot("local_tool")
        assert (snapshot.active, snapshot.queued, snapshot.submitted) == (0, 0, 0)
        assert manager.call("local_tool", lambda: 2) == 2


def test_already_accepted_queued_submission_failure_settles_future():
    class FailAfterFirstExecutor(ThreadPoolExecutor):
        calls = 0

        def submit(self, *args, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("test submit failure")
            return super().submit(*args, **kwargs)

    entered, release = Event(), Event()

    def held():
        entered.set()
        assert release.wait(5)

    with _manager(executor_factory=FailAfterFirstExecutor) as manager:
        first = manager.submit("provider", held)
        try:
            assert entered.wait(5)
            queued = manager.submit("provider", lambda: pytest.fail("submission failed work ran"))
        finally:
            release.set()
        manager.wait_for(first)
        with pytest.raises(_module().LaneAdmissionError):
            manager.wait_for(queued)
        assert queued.done()
        snapshot = manager.snapshot("provider")
        assert (snapshot.submitted, snapshot.completed, snapshot.active, snapshot.queued) == (
            2,
            2,
            0,
            0,
        )


def test_thread_start_failure_cannot_execute_the_rejected_operation_later(monkeypatch):
    from threading import Thread

    original = Thread.start
    failed = []
    ran = []

    def fail_once(thread):
        if thread.name.startswith("specflow-local_tool") and not failed:
            failed.append(True)
            raise RuntimeError("test thread resource unavailable")
        return original(thread)

    monkeypatch.setattr(Thread, "start", fail_once)
    with _manager() as manager:
        with pytest.raises(_module().LaneAdmissionError):
            manager.submit("local_tool", lambda: ran.append("rejected"))
        manager.call("local_tool", lambda: ran.append("accepted"))
        assert ran == ["accepted"]
        snapshot = manager.snapshot("local_tool")
        assert (snapshot.submitted, snapshot.started, snapshot.completed, snapshot.rejected) == (
            1,
            1,
            1,
            1,
        )


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_thread_start_interruption_rolls_back_before_propagating(monkeypatch, interruption):
    from threading import Thread

    original = Thread.start
    interrupted = []

    def start(thread):
        if thread.name.startswith("specflow-local_tool") and not interrupted:
            interrupted.append(True)
            raise interruption("test interruption")
        return original(thread)

    monkeypatch.setattr(Thread, "start", start)
    with _manager() as manager:
        with pytest.raises(interruption):
            manager.submit("local_tool", lambda: pytest.fail("interrupted submission ran"))
        assert manager.snapshot("local_tool").active == 0
        assert manager.snapshot("local_tool").submitted == 0
        assert manager.call("local_tool", lambda: 17) == 17


def test_queued_dispatch_interruption_settles_all_accepted_futures():
    class InterruptSecondSubmit(ThreadPoolExecutor):
        calls = 0

        def submit(self, *args, **kwargs):
            type(self).calls += 1
            future = super().submit(*args, **kwargs)
            if type(self).calls == 2:
                raise KeyboardInterrupt("test queued dispatch interruption")
            return future

    started, release = Event(), Event()

    def held():
        started.set()
        assert release.wait(5)

    with _manager(executor_factory=InterruptSecondSubmit) as manager:
        first = manager.submit("local_tool", held)
        try:
            assert started.wait(5)
            queued = manager.submit("local_tool", lambda: pytest.fail("interrupted dispatch ran"))
        finally:
            release.set()
        first.result(timeout=5)
        with pytest.raises(KeyboardInterrupt):
            queued.result(timeout=5)
        manager.drain([first, queued])
        assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0


def test_failed_thread_start_cannot_accumulate_unbounded_native_submissions(monkeypatch):
    from threading import Thread

    original = Thread.start
    started, release = Event(), Event()
    failing = [False]
    native_calls = []
    ran = []

    class CountingExecutor(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            native_calls.append(1)
            return super().submit(*args, **kwargs)

    def start(thread):
        if failing[0] and thread.name.startswith("specflow-local_tool"):
            raise RuntimeError("test thread resource unavailable")
        return original(thread)

    def held():
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(Thread, "start", start)
    with _manager(active=2, queued=1, executor_factory=CountingExecutor) as manager:
        active = manager.submit("local_tool", held)
        try:
            assert started.wait(5)
            failing[0] = True
            for _ in range(20):
                with pytest.raises(_module().LaneAdmissionError):
                    manager.submit("local_tool", lambda: ran.append("rejected"))
            assert len(native_calls) == 2
            assert manager.snapshot("local_tool").active == 1
        finally:
            failing[0] = False
            release.set()
        manager.wait_for(active)
        assert manager.call("local_tool", lambda: 7) == 7
        assert ran == []
        assert manager.snapshot("local_tool").rejected == 20


@pytest.mark.parametrize("status", [200, 429, 503])
def test_deadline_does_not_hide_real_attempt_health_from_breaker(status):
    import httpx

    from specflow.llm import (
        LLMMessage,
        LLMRequest,
        OpenAICompatibleConfig,
        OpenAICompatibleLLMClient,
    )
    from specflow.llm.exceptions import LLMError
    from specflow.llm.resilience import (
        ProviderResilienceGuard,
        ResilienceSettings,
        resource_identity,
    )

    clock = Clock()
    config = OpenAICompatibleConfig("https://lane.example.test/v1", "test-lane-key", "model")
    guard = ProviderResilienceGuard(
        ResilienceSettings(failure_threshold=1, open_seconds=5), clock=clock
    )
    request = LLMRequest("model", [LLMMessage("user", "feature")])
    if status == 200:
        with pytest.raises(LLMError):
            OpenAICompatibleLLMClient(
                config,
                resilience_guard=guard,
                transport=httpx.MockTransport(lambda _: httpx.Response(429)),
            ).complete(request)
        clock.now = 5
    entered, expired, release = Event(), Event(), Event()

    def transport(_):
        entered.set()
        assert release.wait(5)
        return httpx.Response(
            status,
            json={
                "model": "model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with _manager(clock=clock) as manager:

        def dispatch(operation):
            future = manager.submit("provider", operation, deadline=10)
            assert entered.wait(5)
            clock.now = 10
            expired.set()
            return manager.wait_for(future, deadline=10)

        client = OpenAICompatibleLLMClient(
            config,
            transport=httpx.MockTransport(transport),
            resilience_guard=guard,
            attempt_executor=dispatch,
        )
        with ThreadPoolExecutor(max_workers=1) as observer:
            call = observer.submit(client.complete, request)
            try:
                assert expired.wait(5)
                assert not call.done()
                assert guard.snapshot(resource_identity(config)).active_calls == 1
            finally:
                release.set()
            with pytest.raises(LLMError) as error:
                call.result(timeout=5)
            assert error.value.code.value == "BUDGET_WALL_TIME"
        snapshot = guard.snapshot(resource_identity(config))
        assert snapshot.failure_count == 1
        assert snapshot.state == ("CLOSED" if status == 200 else "OPEN")
        assert snapshot.active_calls == snapshot.active_probes == 0


def test_scheduler_deadline_cancels_queued_and_drains_started_with_injected_clock(monkeypatch):
    import specflow.coordinator.scheduler as scheduling

    clock = Clock()
    entered, expired, release = Event(), Event(), Event()
    ran = []

    def held(_):
        entered.set()
        assert release.wait(5)
        return {"ok": True}

    def expire(futures, **kwargs):
        assert entered.wait(5)
        clock.now = 10
        expired.set()
        return set(), set(futures)

    with _manager(clock=clock) as manager:
        scheduler = scheduling.MultiAgentScheduler(max_parallel_workers=2, lane_manager=manager)
        monkeypatch.setattr(scheduling, "wait", expire)
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                scheduler.execute,
                (("active", "queued"),),
                {"active": held, "queued": lambda _: ran.append("bad")},
                {},
                deadline=10,
            )
            try:
                assert expired.wait(5)
                assert not result.done()
                assert manager.snapshot("local_tool").active == 1
            finally:
                release.set()
            with pytest.raises(scheduling.ScheduleExecutionError, match="TIME_BUDGET_EXCEEDED"):
                result.result(timeout=5)
        assert ran == []
        assert manager.snapshot("local_tool").cancelled == 1
        assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0


def test_shutdown_cancels_queue_waits_running_and_rejects_new_work():
    started, release, shutting_down = Event(), Event(), Event()
    manager = _manager()

    def held():
        started.set()
        assert release.wait(5)

    first = manager.submit("local_tool", held)
    assert started.wait(5)
    queued = manager.submit("local_tool", lambda: pytest.fail("shutdown queued work executed"))

    def close():
        shutting_down.set()
        manager.shutdown()

    with ThreadPoolExecutor(max_workers=1) as pool:
        closing = pool.submit(close)
        try:
            assert shutting_down.wait(5)
            with pytest.raises(CancelledError):
                queued.result(timeout=5)
            assert not closing.done()
            assert manager.snapshot("local_tool").active == 1
        finally:
            release.set()
        closing.result(timeout=5)
    assert first.done() and queued.cancelled()
    assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0
    with pytest.raises(_module().LaneAdmissionError):
        manager.submit("local_tool", lambda: None)


def test_no_silent_discard_under_concurrent_admission():
    barrier = Barrier(13)
    release = Event()
    manager = _manager(active=2, queued=3)

    def submit():
        barrier.wait(timeout=5)
        try:
            return manager.submit("provider", lambda: release.wait(5))
        except _module().LaneAdmissionError:
            return None

    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            callers = [pool.submit(submit) for _ in range(12)]
            barrier.wait(timeout=5)
            accepted = [future.result(timeout=5) for future in callers]
        accepted = [future for future in accepted if future is not None]
        assert len(accepted) == 5
        assert manager.snapshot("provider").rejected == 7
        release.set()
        assert all(manager.wait_for(future) for future in accepted)
        assert manager.snapshot("provider").completed == 5
    finally:
        release.set()
        manager.shutdown()


def test_shutdown_stops_both_lanes_before_waiting_for_started_work():
    started, release = Event(), Event()
    manager = _manager()

    def held():
        started.set()
        assert release.wait(5)

    first = manager.submit("local_tool", held)
    assert started.wait(5)
    queued = manager.submit("local_tool", lambda: None)
    with ThreadPoolExecutor(max_workers=1) as pool:
        closing = pool.submit(manager.shutdown)
        try:
            with pytest.raises(CancelledError):
                queued.result(timeout=5)
            with pytest.raises(_module().LaneAdmissionError):
                manager.submit("provider", lambda: None)
        finally:
            release.set()
            closing.result(timeout=5)
    assert first.done()


def test_same_lane_reentry_is_rejected_instead_of_deadlocking():
    with _manager() as manager:
        with pytest.raises(_module().LaneAdmissionError):
            manager.call("local_tool", lambda: manager.call("local_tool", lambda: 1))
        assert manager.snapshot("local_tool").active == 0


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_policy_rejects_non_positive_or_non_integer_lane_limits(value):
    from specflow.policy.models import LaneLimits

    with pytest.raises(ValueError):
        LaneLimits(max_active=value)
    with pytest.raises(ValueError):
        LaneLimits(queue_capacity=value)


def test_lane_policy_affects_single_flight_policy_identity_and_hard_limits():
    from dataclasses import replace

    from specflow.policy.models import ExecutionLanePolicy, ExecutionPolicy, LaneLimits
    from specflow.policy.validator import PolicyValidator

    base = ExecutionPolicy(lanes=ExecutionLanePolicy(provider=LaneLimits(1, 1)))
    changed = replace(base, lanes=ExecutionLanePolicy(provider=LaneLimits(2, 1)))
    assert base.policy_hash() != changed.policy_hash()
    with pytest.raises(ValueError):
        PolicyValidator(system_hard_limit=base).validate(changed)


def test_scheduler_rejection_drains_accepted_work_and_preserves_saturation_cause():
    from specflow.coordinator.exceptions import ScheduleExecutionError
    from specflow.coordinator.scheduler import MultiAgentScheduler

    release, entered = Event(), Event()
    rejected = Event()
    with _manager(active=1, queued=1) as manager:

        def held(_):
            entered.set()
            assert release.wait(5)
            return {"ok": True}

        scheduler = MultiAgentScheduler(max_parallel_workers=3, lane_manager=manager)
        original_submit = manager.submit
        submitted = []

        def controlled_submit(*args, **kwargs):
            try:
                future = original_submit(*args, **kwargs)
            except _module().LaneAdmissionError:
                rejected.set()
                raise
            submitted.append(future)
            if len(submitted) == 1:
                assert entered.wait(5)
            return future

        manager.submit = controlled_submit
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(
                scheduler.execute, (("a", "b", "c"),), {name: held for name in ("a", "b", "c")}, {}
            )
            try:
                assert rejected.wait(5)
                assert not running.done()
            finally:
                release.set()
            with pytest.raises(ScheduleExecutionError) as error:
                running.result(timeout=5)
            assert error.value.__cause__.code == "LANE_SATURATED"
        assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0


def test_provider_open_has_zero_lane_submissions_and_saturation_does_not_count_health():
    import httpx

    from specflow.llm import (
        LLMMessage,
        LLMRequest,
        OpenAICompatibleConfig,
        OpenAICompatibleLLMClient,
    )
    from specflow.llm.exceptions import LLMCircuitError, LLMError
    from specflow.llm.resilience import (
        ProviderResilienceGuard,
        ResilienceSettings,
        resource_identity,
    )

    config = OpenAICompatibleConfig("https://lane.example.test/v1", "test-lane-key", "model")
    guard = ProviderResilienceGuard(ResilienceSettings(failure_threshold=1))
    request = LLMRequest("model", [LLMMessage("user", "feature")])
    release, entered = Event(), Event()
    with _manager() as manager:

        def held():
            entered.set()
            assert release.wait(5)

        active = manager.submit("provider", held)
        try:
            assert entered.wait(5)
            queued = manager.submit("provider", lambda: None)
            client = OpenAICompatibleLLMClient(
                config,
                resilience_guard=guard,
                transport=httpx.MockTransport(lambda _: httpx.Response(429)),
                attempt_executor=lambda operation: manager.call("provider", operation),
            )
            with pytest.raises(LLMError) as error:
                client.complete(request)
            assert error.value.code.value == "LANE_SATURATED"
            snapshot = guard.snapshot(resource_identity(config))
            assert snapshot.failure_count == snapshot.active_calls == 0
        finally:
            release.set()
        manager.wait_for(active)
        manager.wait_for(queued)
        with pytest.raises(LLMError):
            client.complete(request)
        submitted = manager.snapshot("provider").submitted
        with pytest.raises(LLMCircuitError):
            client.complete(request)
        assert manager.snapshot("provider").submitted == submitted
        assert guard.snapshot(resource_identity(config)).state == "OPEN"


def test_single_flight_follower_uses_no_second_lane_and_different_owner_is_rejected(
    tmp_path, monkeypatch
):
    from specflow.evidence import EvidenceCollector
    from specflow.policy.models import ExecutionPolicy
    from specflow.runner_multi import run_multi_agent

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# feature\ndef feature(): pass\n")
    entered, release, follower_joined = Event(), Event(), Event()
    original_collect = EvidenceCollector.collect
    count = []

    def held_collect(self, **kwargs):
        count.append(1)
        entered.set()
        assert release.wait(5)
        return original_collect(self, **kwargs)

    monkeypatch.setattr(EvidenceCollector, "collect", held_collect)
    with _manager(queued=2) as manager:
        policy = ExecutionPolicy(lanes=manager.policy)

        def run(label, requirement="feature", on_join=None):
            return run_multi_agent(
                repo=repo,
                requirement=requirement,
                output=tmp_path / label,
                mock=True,
                policy=policy,
                _lane_manager=manager,
                _on_join=on_join,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            owner = pool.submit(run, "owner")
            try:
                assert entered.wait(5)
                queued = [manager.submit("local_tool", lambda: None) for _ in range(2)]
                follower = pool.submit(
                    run, "follower", "feature", lambda meta: follower_joined.set()
                )
                assert follower_joined.wait(5)
                assert manager.snapshot("local_tool").submitted == 3
                rejected = run("different", "different feature")
                assert rejected.error_code == "LANE_SATURATED"
                assert not follower.done()
                assert count == [1]
            finally:
                release.set()
            first = owner.result(timeout=10)
            second = follower.result(timeout=10)
        for future in queued:
            manager.wait_for(future)
        assert first == second == 0
        assert first.artifact_directory == second.artifact_directory
        assert second.single_flight["role"] == "follower"
        assert manager.snapshot("local_tool").active == manager.snapshot("local_tool").queued == 0


def test_real_multi_agent_provider_saturation_is_not_provider_health_or_retry(
    tmp_path, monkeypatch
):
    import specflow.llm.providers.openai_compatible as provider
    from specflow.llm import OpenAICompatibleConfig
    from specflow.llm.resilience import ProviderResilienceGuard, resource_identity
    from specflow.policy.models import ExecutionPolicy
    from specflow.runner_multi import run_multi_agent

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# feature\ndef feature(): pass\n")
    config = OpenAICompatibleConfig("https://lane.example.test/v1", "test-lane-key", "model")
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", config.base_url)
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", config.api_key)
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", config.model)
    breaker = ProviderResilienceGuard()
    monkeypatch.setattr(provider, "DEFAULT_RESILIENCE_GUARD", breaker)
    entered, release = Event(), Event()

    def held():
        entered.set()
        assert release.wait(5)

    with _manager() as manager:
        active = manager.submit("provider", held)
        try:
            assert entered.wait(5)
            queued = manager.submit("provider", lambda: None)
            result = run_multi_agent(
                repo=repo,
                requirement="feature",
                output=tmp_path / "out",
                mock=False,
                provider="openai-compatible",
                model="model",
                policy=ExecutionPolicy(lanes=manager.policy),
                _lane_manager=manager,
            )
            assert result == 3
            assert result.error_code == "LANE_SATURATED"
            assert result.artifact_directory is not None
            assert manager.snapshot("provider").submitted == 2
            assert breaker.snapshot(resource_identity(config)).failure_count == 0
            assert breaker.snapshot(resource_identity(config)).active_calls == 0
        finally:
            release.set()
        manager.wait_for(active)
        manager.wait_for(queued)

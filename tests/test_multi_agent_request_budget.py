"""Request-level budgets cover planning, failed parsing and concurrent requests."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest

from specflow import runner_multi
from specflow.agents.adapter import AgentRunner
from specflow.llm import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.llm.providers.openai_compatible import OpenAICompatibleLLMClient
from specflow.policy import ExecutionPolicy, RuntimeGuard, SpecFlowError
from specflow.policy.models import TokenPolicy
from specflow.schema import build_schema_registry


class FakeProvider:
    def __init__(self, analyst_content=None, usage=LLMUsage(3, 2)):
        self.requests = []
        self.analyst_content = analyst_content
        self.usage = usage

    def complete(self, request):
        self.requests.append(request)
        first = request.messages[0]
        usage = LLMUsage(3, 2)
        if first.role != "system":
            content = '{"task_description":"synthetic brief"}'
        elif "**repository_analyst**" in first.content:
            content = self.analyst_content or '{"summary":"synthetic analysis"}'
            usage = self.usage
        elif "**review**" in first.content:
            content = '{"summary":"synthetic review","decision":"PASS"}'
        else:
            content = '{"summary":"synthetic output"}'
        return _response(content, usage)


def _response(content='{"summary":"synthetic"}', usage=LLMUsage(3, 2)):
    return LLMResponse(
        content=content, model="fake", usage=usage, latency_ms=1, finish_reason="stop"
    )


def _request(**kwargs):
    return LLMRequest(model="fake", messages=[LLMMessage("user", "synthetic")], **kwargs)


def _budget(policy=None, clock=None):
    from specflow.llm.budgeted import LLMCallBudget

    policy = policy or ExecutionPolicy(max_llm_calls=12)
    guard = RuntimeGuard(policy, time_source=lambda: clock[0]) if clock else RuntimeGuard(policy)
    return LLMCallBudget(guard, policy)


def _run(tmp_path, monkeypatch, provider, cap, observer=None):
    monkeypatch.setattr(runner_multi, "_create_real_llm_client", lambda *a, **k: provider)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# explain health endpoint\n", encoding="utf-8")
    output = tmp_path / "out"
    observations = []

    def observe(value):
        observations.append(value)
        if observer is not None:
            observer(value)

    exit_code = runner_multi.run_multi_agent(
        repo=repo,
        requirement="explain health endpoint",
        output=output,
        provider="openai-compatible",
        model="fake",
        policy=ExecutionPolicy(max_llm_calls=cap),
        request_observer=observe,
    )
    run = next(output.glob("run-multi-*"))

    def read(name):
        return json.loads((run / name).read_text(encoding="utf-8"))

    return exit_code, read, observations


@pytest.mark.parametrize("cap", [1, 3, 10])
def test_shared_cap_stops_planning_or_agents_before_extra_request(tmp_path, monkeypatch, cap):
    provider = FakeProvider()
    exit_code, read, observations = _run(tmp_path, monkeypatch, provider, cap)
    assert len(provider.requests) == len(observations) == cap
    assert exit_code == 3
    manifest = read("manifest.json")
    assert manifest["error"] == "CALL_BUDGET_EXCEEDED"
    assert manifest["workflow_state"] == "failed"
    assert manifest["budget_usage"]["llm_calls"] == cap
    assert manifest["budget_usage"]["observed_input_tokens"] == cap * 3
    if cap < 6:
        assert manifest["stages_completed"] == 0


def test_success_metrics_and_observer_cover_all_twelve_requests(tmp_path, monkeypatch):
    provider = FakeProvider()
    exit_code, read, observations = _run(tmp_path, monkeypatch, provider, 12)
    assert exit_code == 0
    assert len(provider.requests) == len(observations) == 12
    assert [o.max_tokens for o in observations] == [r.max_tokens for r in provider.requests]
    metrics = read("metrics.json")
    assert (metrics["llm_call_count"], metrics["input_tokens"], metrics["output_tokens"]) == (
        12,
        36,
        24,
    )
    assert read("manifest.json")["budget_usage"]["usage_complete"] is True


@pytest.mark.parametrize("content", ["not json PRIVATE_SYNTHETIC_BODY", '{"summary":42}'])
def test_failed_agent_parsing_keeps_response_usage(tmp_path, monkeypatch, caplog, content):
    provider = FakeProvider(analyst_content=content, usage=LLMUsage(11, 7))
    exit_code, read, _ = _run(tmp_path, monkeypatch, provider, 12)
    assert exit_code == 3
    manifest = read("manifest.json")
    assert manifest["error"] == "MULTI_AGENT_RUN_FAILED"
    usage = manifest["budget_usage"]
    assert (usage["llm_calls"], usage["usage_observed_calls"]) == (7, 7)
    assert (usage["observed_input_tokens"], usage["observed_output_tokens"]) == (29, 19)
    assert usage["usage_complete"] is True
    assert "PRIVATE_SYNTHETIC_BODY" not in json.dumps(manifest) + caplog.text
    assert read("agent-outputs.json")["stage-0/repository-analyst-agent-v1"]["audit_only"] is True


def test_missing_usage_fails_closed_without_claiming_zero_cost(tmp_path, monkeypatch):
    provider = FakeProvider(usage=None)
    exit_code, read, _ = _run(tmp_path, monkeypatch, provider, 12)
    assert exit_code == 3
    assert len(provider.requests) == 7
    manifest = read("manifest.json")
    assert manifest["error"] == "TOKEN_USAGE_UNAVAILABLE"
    usage = manifest["budget_usage"]
    assert usage["usage_observed_calls"] == 6
    assert usage["usage_unknown_calls"] == 1
    assert usage["usage_complete"] is False


def test_adapter_does_not_reclassify_budget_error_as_provider_failure():
    policy = ExecutionPolicy(max_llm_calls=1)
    provider = FakeProvider()
    client = _budget(policy).wrap(provider)
    adapter = AgentRunner(
        runner_multi._build_registry().get("repository-analyst-agent-v1").identity,
        client,
        schema_registry=build_schema_registry(),
    )
    adapter.execute({"requirement": "synthetic"})
    with pytest.raises(SpecFlowError) as error:
        adapter.execute({"requirement": "synthetic"})
    assert error.value.code == "CALL_BUDGET_EXCEEDED"
    assert len(provider.requests) == 1


def test_concurrent_requests_reserve_output_before_sending():
    policy = ExecutionPolicy(
        tokens=TokenPolicy(
            max_run_input_tokens=100,
            max_run_output_tokens=10,
            max_run_total_tokens=100,
            max_agent_output_tokens=8,
            reserved_retry_tokens=0,
        )
    )
    budget = _budget(policy)
    first_started = Event()
    release = Event()
    sent = []

    class Provider:
        def complete(self, request):
            sent.append(request.max_tokens)
            if request.max_tokens == 8:
                first_started.set()
                assert release.wait(5)
            return _response(usage=LLMUsage(1, 1))

    client = budget.wrap(Provider())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.complete, _request(max_tokens=8))
        try:
            assert first_started.wait(5)
            second = pool.submit(client.complete, _request(max_tokens=8))
            assert second.result(timeout=5).usage.output_tokens == 1
        finally:
            release.set()
        assert first.result(timeout=5).usage.output_tokens == 1
    assert sent == [8, 2]
    assert budget.snapshot()["usage_complete"] is True


def test_over_budget_response_is_recorded_and_prevents_later_requests():
    policy = ExecutionPolicy(tokens=TokenPolicy(max_agent_output_tokens=1))
    provider = FakeProvider()
    budget = _budget(policy)
    client = budget.wrap(provider)
    for _ in range(2):
        with pytest.raises(SpecFlowError) as error:
            client.complete(_request())
        assert error.value.code == "TOKEN_BUDGET_EXCEEDED"
    assert len(provider.requests) == 1
    assert budget.snapshot()["observed_output_tokens"] == 2


@pytest.mark.parametrize("usage", [None, LLMUsage(True, 2), LLMUsage(1.5, 2)])
def test_unknown_or_malformed_usage_blocks_next_request(usage):
    calls = []

    class Provider:
        def complete(self, request):
            calls.append(True)
            return _response(usage=usage)

    budget = _budget()
    client = budget.wrap(Provider())
    for _ in range(2):
        with pytest.raises(SpecFlowError) as error:
            client.complete(_request())
        assert error.value.code == "TOKEN_USAGE_UNAVAILABLE"
    assert len(calls) == 1
    assert budget.snapshot()["usage_unknown_calls"] == 1


def test_provider_exception_stays_original_but_unknown_usage_stops_further_calls():
    original = RuntimeError("synthetic provider error")

    class Provider:
        def complete(self, request):
            raise original

    budget = _budget()
    client = budget.wrap(Provider())
    with pytest.raises(RuntimeError) as error:
        client.complete(_request())
    assert error.value is original
    with pytest.raises(SpecFlowError, match="usage"):
        client.complete(_request())
    assert budget.snapshot()["llm_calls"] == 1


def test_deadline_caps_requests_and_rejects_late_response():
    clock = [100.0]
    budget = _budget(ExecutionPolicy(max_wall_time_seconds=10), clock)
    received = []

    class Provider:
        def complete(self, request):
            received.append(request.timeout_seconds)
            if len(received) == 2:
                clock[0] = 111.0
            return _response()

    client = budget.wrap(Provider())
    client.complete(_request())
    clock[0] = 108.0
    with pytest.raises(SpecFlowError) as error:
        client.complete(_request())
    assert error.value.code == "TIME_BUDGET_EXCEEDED"
    with pytest.raises(SpecFlowError):
        client.complete(_request())
    assert received == [10.0, 2.0]
    assert budget.snapshot()["usage_observed_calls"] == 2


def test_already_expired_request_never_reaches_provider():
    clock = [100.0]
    budget = _budget(ExecutionPolicy(max_wall_time_seconds=1), clock)
    provider = FakeProvider()
    clock[0] = 101.0
    with pytest.raises(SpecFlowError) as error:
        budget.wrap(provider).complete(_request())
    assert error.value.code == "TIME_BUDGET_EXCEEDED"
    assert provider.requests == []


def test_slow_observer_cannot_send_after_deadline(tmp_path, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(
        runner_multi,
        "RuntimeGuard",
        lambda policy: RuntimeGuard(policy, time_source=lambda: clock[0]),
    )
    provider = FakeProvider()

    def slow_observer(observation):
        clock[0] += 301

    code, read, _ = _run(tmp_path, monkeypatch, provider, 12, observer=slow_observer)
    assert code == 3
    assert provider.requests == []
    manifest = read("manifest.json")
    assert manifest["error"] == "TIME_BUDGET_EXCEEDED"
    assert manifest["budget_usage"]["llm_calls"] == 0
    assert manifest["budget_usage"]["usage_unknown_calls"] == 0
    assert manifest["workflow_history"][-1][1] == "failed"


def test_observer_delay_is_deducted_before_http_send():
    clock = [100.0]
    budget = _budget(ExecutionPolicy(max_wall_time_seconds=10), clock)
    provider = FakeProvider()

    def observer(request):
        clock[0] = 106.0

    budget.wrap(provider, on_request=observer).complete(_request())
    assert provider.requests[0].timeout_seconds == 4.0


def test_sibling_failure_cancels_request_waiting_in_observer():
    entered = Event()
    release = Event()
    budget = _budget()
    blocked_provider = FakeProvider()

    def observer(request):
        entered.set()
        assert release.wait(5)

    class MissingUsageProvider:
        def complete(self, request):
            return _response(usage=None)

    client = budget.wrap(blocked_provider, on_request=observer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting = pool.submit(client.complete, _request())
        try:
            assert entered.wait(5)
            with pytest.raises(SpecFlowError):
                budget.wrap(MissingUsageProvider()).complete(_request())
        finally:
            release.set()
        with pytest.raises(SpecFlowError) as error:
            waiting.result(timeout=5)
    assert error.value.code == "TOKEN_USAGE_UNAVAILABLE"
    assert blocked_provider.requests == []
    assert budget.snapshot()["llm_calls"] == 1


@pytest.mark.parametrize(("configured", "requested", "expected"), [(30, 2.5, 2.5), (2, 30, 2)])
def test_provider_uses_smaller_request_timeout(configured, requested, expected):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(
            base_url="https://synthetic.invalid/v1",
            api_key="synthetic",
            model="fake",
            timeout_seconds=configured,
        ),
        transport=httpx.MockTransport(handler),
    )
    client.complete(_request(timeout_seconds=requested))
    assert len(seen) == 1
    assert set(seen[0].extensions["timeout"].values()) == {expected}
    assert "timeout_seconds" not in json.loads(seen[0].content)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_request_rejects_invalid_timeout(timeout):
    from specflow.llm.exceptions import LLMResponseError

    with pytest.raises(LLMResponseError):
        _request(timeout_seconds=timeout)

"""Offline provider-attempt contracts for T-071; clocks/events replace sleeps."""

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from hashlib import sha256
from threading import Barrier, Event

import httpx
import pytest

from specflow.llm import LLMMessage, LLMRequest, OpenAICompatibleConfig, OpenAICompatibleLLMClient
from specflow.llm.exceptions import LLMResponseError
from specflow.policy.errors import ErrorCode


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def _module():
    return importlib.import_module("specflow.llm.resilience")


def _guard(clock=None, **settings):
    return _module().ProviderResilienceGuard(
        _module().ResilienceSettings(**settings), clock=clock or Clock()
    )


def _config(**changes):
    config = OpenAICompatibleConfig(
        base_url="https://private-provider.example.test/v1",
        api_key="test-private-provider-credential-A",
        model="private-model",
    )
    return replace(config, **changes)


def _request():
    return LLMRequest(model="requested-model", messages=[LLMMessage("user", "Return JSON")])


def _response(status=200):
    return httpx.Response(
        status,
        json={
            "model": "private-model",
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        },
    )


def _client(guard, handler, config=None):
    return OpenAICompatibleLLMClient(
        config or _config(), transport=httpx.MockTransport(handler), resilience_guard=guard
    )


def _snapshot(guard, config=None):
    return guard.snapshot(_module().resource_identity(config or _config()))


def _circuit_error():
    return importlib.import_module("specflow.llm.exceptions").LLMCircuitError


def test_closed_success_and_read_only_safe_observation():
    guard = _guard()
    assert _snapshot(guard) is None
    assert guard.entry_count == 0
    response = _client(guard, lambda _: _response()).complete(_request())
    assert response.content == '{"ok":true}'
    state = _snapshot(guard)
    assert state.state == "CLOSED"
    assert state.failure_count == state.active_calls == state.active_probes == 0
    assert guard.entry_count == 1
    with pytest.raises(AttributeError):
        state.state = "OPEN"


def test_threshold_open_rejects_without_transport_then_probe_recovers():
    clock = Clock()
    guard = _guard(clock, failure_threshold=2, open_seconds=10)
    calls = []

    def transport(request):
        calls.append(request)
        return _response(429 if len(calls) <= 2 else 200)

    client = _client(guard, transport)
    for expected in (1, 2):
        with pytest.raises(LLMResponseError):
            client.complete(_request())
        assert _snapshot(guard).failure_count == expected
    assert _snapshot(guard).state == "OPEN"
    with pytest.raises(_circuit_error()) as rejected:
        client.complete(_request())
    assert rejected.value.code.value == "PROVIDER_CIRCUIT_REJECTED"
    assert rejected.value.reason == "open"
    assert len(calls) == 2
    clock.now = 9.99
    with pytest.raises(_circuit_error()):
        client.complete(_request())
    assert len(calls) == 2
    clock.now = 10
    client.complete(_request())
    assert len(calls) == 3
    assert _snapshot(guard).state == "CLOSED"
    assert _snapshot(guard).active_probes == 0
    assert _snapshot(guard).transition_count == 3


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (429, "PROVIDER_RATE_LIMITED"),
        (500, "PROVIDER_SERVER_ERROR"),
        (503, "PROVIDER_SERVER_ERROR"),
        (504, "PROVIDER_SERVER_ERROR"),
        (httpx.ReadTimeout("private raw timeout"), "PROVIDER_TIMEOUT"),
        (httpx.ConnectError("private raw network"), "PROVIDER_CONNECTION_ERROR"),
    ],
)
def test_only_classified_availability_failures_open_the_circuit(failure, code):
    guard = _guard(failure_threshold=1)

    def transport(_):
        if isinstance(failure, Exception):
            raise failure
        return _response(failure)

    with pytest.raises(Exception) as caught:
        _client(guard, transport).complete(_request())
    assert caught.value.code.value == code
    assert caught.value.__context__ is None
    assert _snapshot(guard).state == "OPEN"
    assert _snapshot(guard).failure_count == 1


@pytest.mark.parametrize("status", [401, 403, 404, 400])
def test_permanent_http_failure_never_opens_breaker(status):
    guard = _guard(failure_threshold=1)
    client = _client(guard, lambda _: _response(status))
    for _ in range(3):
        with pytest.raises(LLMResponseError) as caught:
            client.complete(_request())
        if status in (401, 403):
            assert caught.value.code == ErrorCode.PROVIDER_AUTH_FAILURE
        if status == 404:
            assert caught.value.code == ErrorCode.PROVIDER_MODEL_NOT_FOUND
    assert _snapshot(guard).state == "CLOSED"
    assert _snapshot(guard).failure_count == 0


@pytest.mark.parametrize("failure", ["json", "structure", "coding"])
def test_invalid_response_or_transport_coding_error_is_not_health_failure(failure):
    guard = _guard(failure_threshold=1)

    def transport(_):
        if failure == "coding":
            raise RuntimeError("server 500 rate limit private internal failure")
        if failure == "json":
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(200, json={"choices": []})

    client = _client(guard, transport)
    for _ in range(2):
        with pytest.raises(LLMResponseError):
            client.complete(_request())
    assert _snapshot(guard).failure_count == 0
    assert _snapshot(guard).active_calls == 0


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.PROVIDER_AUTH_FAILURE,
        ErrorCode.PROVIDER_MODEL_NOT_FOUND,
        ErrorCode.JSON_PARSE_FAILED,
        ErrorCode.SCHEMA_VALIDATION_FAILED,
        ErrorCode.SECURITY_PATH_TRAVERSAL,
        ErrorCode.BUDGET_LLM_CALLS,
        ErrorCode.INTERNAL_UNEXPECTED,
    ],
)
def test_excluded_classified_errors_never_count_even_with_misleading_text(code):
    guard = _guard(failure_threshold=1)
    key = _module().resource_identity(_config())
    for _ in range(2):
        with pytest.raises(LLMResponseError):
            with guard.attempt(key):
                raise LLMResponseError("server 500 rate timeout", code=code)
    assert _snapshot(guard).failure_count == 0
    assert _snapshot(guard).state == "CLOSED"


@pytest.mark.parametrize(
    "changes",
    [
        {"base_url": "https://other-provider.example.test/v1"},
        {"model": "other-model"},
        {"api_key": "test-private-provider-credential-B"},
    ],
)
def test_endpoint_model_and_tenancy_isolation(changes):
    guard = _guard(failure_threshold=1)
    failed = _client(guard, lambda _: _response(429))
    with pytest.raises(LLMResponseError):
        failed.complete(_request())
    other = _config(**changes)
    healthy = _client(guard, lambda _: _response(), other)
    assert healthy.complete(_request()).content == '{"ok":true}'
    assert _snapshot(guard).state == "OPEN"
    assert _snapshot(guard, other).state == "CLOSED"
    assert guard.entry_count == 2


def test_same_actual_resource_and_tenancy_share_across_client_instances():
    guard = _guard(failure_threshold=1)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())

    def forbidden(_):
        pytest.fail("open shared resource must not reach transport")

    same = _config(base_url="https://private-provider.example.test/v1/")
    with pytest.raises(_circuit_error()):
        _client(guard, forbidden, same).complete(_request())
    assert guard.entry_count == 1


def test_half_open_failure_restarts_cooldown_and_releases_probe():
    clock = Clock()
    guard = _guard(clock, failure_threshold=1, open_seconds=10)
    client = _client(guard, lambda _: _response(503))
    with pytest.raises(LLMResponseError):
        client.complete(_request())
    clock.now = 10
    with pytest.raises(LLMResponseError):
        client.complete(_request())
    assert _snapshot(guard).state == "OPEN"
    assert _snapshot(guard).active_probes == 0
    clock.now = 19
    with pytest.raises(_circuit_error()):
        client.complete(_request())
    clock.now = 20
    assert _client(guard, lambda _: _response()).complete(_request())
    assert _snapshot(guard).state == "CLOSED"


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_unclassified_half_open_exception_releases_exactly_once(failure):
    clock = Clock()
    guard = _guard(clock, failure_threshold=1, open_seconds=10)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())
    clock.now = 10
    key = _module().resource_identity(_config())
    with pytest.raises(failure):
        with guard.attempt(key):
            raise failure("private local error")
    assert _snapshot(guard).state == "HALF_OPEN"
    assert _snapshot(guard).active_probes == _snapshot(guard).active_calls == 0
    with guard.attempt(key):
        pass
    assert _snapshot(guard).state == "CLOSED"


def test_half_open_probe_bound_with_real_overlapping_transport():
    clock = Clock()
    guard = _guard(clock, failure_threshold=1, open_seconds=10, half_open_max_probes=2)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())
    clock.now = 10
    entered = Barrier(3)
    release = Event()

    def transport(_):
        entered.wait(timeout=5)
        assert release.wait(timeout=5)
        return _response()

    client = _client(guard, transport)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.complete, _request()) for _ in range(2)]
        try:
            entered.wait(timeout=5)
            assert _snapshot(guard).active_probes == 2
            with pytest.raises(_circuit_error()) as caught:
                client.complete(_request())
            assert caught.value.reason == "probe_limit"
        finally:
            release.set()
        for future in futures:
            assert future.result(timeout=5).content == '{"ok":true}'
    assert _snapshot(guard).active_calls == _snapshot(guard).active_probes == 0
    assert _snapshot(guard).state == "CLOSED"


def test_late_success_cannot_close_a_newer_open_circuit():
    guard = _guard(failure_threshold=1)
    started, release = Event(), Event()

    def transport(_):
        started.set()
        assert release.wait(timeout=5)
        return _response()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_client(guard, transport).complete, _request())
        try:
            assert started.wait(timeout=5)
            with pytest.raises(LLMResponseError):
                _client(guard, lambda _: _response(429)).complete(_request())
        finally:
            release.set()
        future.result(timeout=5)
    assert _snapshot(guard).state == "OPEN"
    assert _snapshot(guard).active_calls == 0


def test_half_open_does_not_close_while_another_probe_can_still_fail():
    clock = Clock()
    guard = _guard(clock, failure_threshold=1, open_seconds=10, half_open_max_probes=2)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())
    clock.now = 10
    entered, release = Event(), Event()

    def slow_failure(_):
        entered.set()
        assert release.wait(timeout=5)
        return _response(503)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(_client(guard, slow_failure).complete, _request())
        try:
            assert entered.wait(timeout=5)
            _client(guard, lambda _: _response()).complete(_request())
            assert _snapshot(guard).state == "HALF_OPEN"
        finally:
            release.set()
        with pytest.raises(LLMResponseError):
            pending.result(timeout=5)
    assert _snapshot(guard).state == "OPEN"
    assert _snapshot(guard).active_calls == _snapshot(guard).active_probes == 0


def test_half_open_auth_error_releases_without_counting_or_closing():
    clock = Clock()
    guard = _guard(clock, failure_threshold=1, open_seconds=10)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())
    clock.now = 10
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(401)).complete(_request())
    assert _snapshot(guard).state == "HALF_OPEN"
    assert _snapshot(guard).failure_count == 1
    assert _snapshot(guard).active_calls == _snapshot(guard).active_probes == 0
    _client(guard, lambda _: _response()).complete(_request())
    assert _snapshot(guard).state == "CLOSED"


def test_concurrent_failures_count_each_real_attempt_once_without_duplicate_entry():
    guard = _guard(failure_threshold=2)
    entered = Barrier(9)

    def transport(_):
        entered.wait(timeout=5)
        return _response(429)

    client = _client(guard, transport)
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = [pool.submit(client.complete, _request()) for _ in range(8)]
        entered.wait(timeout=5)
        for future in pending:
            with pytest.raises(LLMResponseError):
                future.result(timeout=5)
    assert guard.entry_count == 1
    assert _snapshot(guard).failure_count == 8
    assert _snapshot(guard).consecutive_failures == 2
    assert _snapshot(guard).active_calls == 0
    assert _snapshot(guard).state == "OPEN"


def test_registry_keeps_failed_or_active_entries_and_recycles_only_healthy_idle():
    guard = _guard(failure_threshold=1, max_entries=1)
    key = _module().resource_identity(_config())
    other = _config(api_key="test-other-tenancy")
    with guard.attempt(key):
        with pytest.raises(_circuit_error()) as rejected:
            _client(guard, lambda _: _response(), other).complete(_request())
        assert rejected.value.reason == "registry_capacity"
    assert _client(guard, lambda _: _response(), other).complete(_request())
    assert guard.entry_count == 1
    assert _snapshot(guard) is None
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429), other).complete(_request())
    with pytest.raises(_circuit_error()):
        _client(guard, lambda _: _response()).complete(_request())
    assert _snapshot(guard, other).state == "OPEN"


def test_key_is_bounded_private_and_public_snapshot_does_not_publish_fingerprints(caplog):
    config = _config()
    key = _module().resource_identity(config)
    assert all(len(value) == 64 for value in asdict(key).values())
    guard = _guard(failure_threshold=1)
    with pytest.raises(LLMResponseError):
        _client(guard, lambda _: _response(429)).complete(_request())
    with pytest.raises(_circuit_error()) as error:
        _client(guard, lambda _: _response()).complete(_request())
    public = json.dumps(asdict(_snapshot(guard))) + repr(key) + str(error.value) + caplog.text
    for secret in (
        config.api_key,
        sha256(config.api_key.encode()).hexdigest(),
        config.base_url,
        config.model,
        *asdict(key).values(),
    ):
        assert secret not in public


@pytest.mark.parametrize(
    "values",
    [
        {"failure_threshold": 0},
        {"failure_threshold": True},
        {"failure_threshold": 1.5},
        {"open_seconds": 0},
        {"open_seconds": float("nan")},
        {"open_seconds": float("inf")},
        {"half_open_max_probes": 0},
        {"max_entries": -1},
    ],
)
def test_invalid_bounds_cannot_create_a_guard(values):
    with pytest.raises(ValueError):
        _guard(**values)


def test_fallback_retries_remain_owned_by_existing_manager():
    from specflow.fallback import FallbackManager, RetryStrategy

    guard = _guard(failure_threshold=5)
    attempts = []

    def transport(_):
        attempts.append(1)
        return _response(503 if len(attempts) < 3 else 200)

    client = _client(guard, transport)
    manager = FallbackManager(RetryStrategy(max_retries=2, base_backoff_seconds=0))
    result = manager.execute(lambda: client.complete(_request()).content, expect_json=True)
    assert result.status == "success"
    assert result.retry_count == 2
    assert len(attempts) == 3
    assert _snapshot(guard).failure_count == 2
    assert _snapshot(guard).consecutive_failures == 0


def test_open_circuit_stops_existing_fallback_retries_and_remains_degraded():
    from specflow.fallback import FallbackManager, RetryStrategy

    guard = _guard(failure_threshold=1)
    attempts = []

    def transport(_):
        attempts.append(1)
        return _response(429)

    client = _client(guard, transport)
    manager = FallbackManager(RetryStrategy(max_retries=4, base_backoff_seconds=0))
    first = manager.execute(lambda: client.complete(_request()).content)
    second = manager.execute(lambda: client.complete(_request()).content)
    assert first.retry_count == 1
    assert second.retry_count == 0
    assert len(attempts) == 1
    assert _snapshot(guard).failure_count == 1
    for result in (first, second):
        assert result.status == "degraded"
        assert result.requires_review is True
        assert result.confidence == 0
        assert result.error_type == "LLMCircuitError"


def _agent_runner(client, **kwargs):
    from specflow.agents.adapter import AgentRunner
    from specflow.runner_multi import _build_registry
    from specflow.schema import build_schema_registry

    identity = next(
        item for item in _build_registry().list_agents() if item.agent_id == "design-agent-v1"
    )
    return AgentRunner(identity, client, schema_registry=build_schema_registry(), **kwargs)


def test_agent_runner_preserves_circuit_code_and_does_not_retry_rejection(monkeypatch):
    import specflow.agents.adapter as adapter

    guard = _guard(failure_threshold=1)
    calls, backoffs = [], []

    def transport(_):
        calls.append(1)
        return _response(429)

    monkeypatch.setattr(adapter.time, "sleep", backoffs.append)
    client = _client(guard, transport)
    runner = _agent_runner(client, max_retries=3)
    result = runner.execute({"requirement": "Add feature"})
    assert result["output"]["error_code"] == "PROVIDER_CIRCUIT_REJECTED"
    assert result["success"] is False
    assert result["schema_validated"] is False
    assert len(calls) == 1
    assert len(backoffs) == 1
    assert _snapshot(guard).failure_count == 1
    runner.execute({"requirement": "Add feature"})
    assert len(calls) == len(backoffs) == 1


@pytest.mark.parametrize(
    "status,expected", [(401, "PROVIDER_AUTH_FAILURE"), (404, "PROVIDER_MODEL_NOT_FOUND")]
)
def test_agent_runner_keeps_permanent_failure_classification(status, expected, monkeypatch):
    import specflow.agents.adapter as adapter

    guard = _guard(failure_threshold=1)
    monkeypatch.setattr(adapter.time, "sleep", lambda _: pytest.fail("permanent failure retried"))
    result = _agent_runner(_client(guard, lambda _: _response(status)), max_retries=2).execute(
        {"requirement": "Add feature"}
    )
    assert result["output"]["error_code"] == expected
    assert _snapshot(guard).failure_count == 0


@pytest.mark.parametrize(
    "content,expected",
    [("not-json", "JSON_PARSE_FAILED"), ('{"summary":""}', "SCHEMA_VALIDATION_FAILED")],
)
def test_agent_output_validation_is_outside_breaker_health(content, expected):
    guard = _guard(failure_threshold=1)

    def transport(_):
        body = _response().json()
        body["choices"][0]["message"]["content"] = content
        return httpx.Response(200, json=body)

    result = _agent_runner(_client(guard, transport)).execute({"requirement": "Add feature"})
    assert result["output"]["error_code"] == expected
    assert _snapshot(guard).failure_count == 0
    assert _snapshot(guard).state == "CLOSED"


@pytest.mark.parametrize("mode", ["legacy", "multi-agent"])
def test_mock_cli_never_constructs_or_consults_live_guard(mode, tmp_path, monkeypatch):
    import specflow.llm.providers.openai_compatible as provider
    from specflow.cli import main

    class ForbiddenGuard:
        def attempt(self, *args):
            pytest.fail("mock touched live breaker")

    monkeypatch.setattr(provider, "DEFAULT_RESILIENCE_GUARD", ForbiddenGuard())
    monkeypatch.setattr(
        provider, "resource_identity", lambda _: pytest.fail("mock derived live key")
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# Add feature\ndef feature(): pass\n", encoding="utf-8")
    with pytest.raises(SystemExit) as result:
        main(
            [
                "run",
                "--mode",
                mode,
                "--mock",
                "--repo",
                str(repo),
                "--requirement",
                "Add feature",
                "--output",
                str(tmp_path / "out"),
            ]
        )
    assert result.value.code == 0


def test_both_live_cli_pipelines_share_guard_and_never_publish_internal_identity(
    tmp_path, monkeypatch, caplog
):
    import specflow.fallback.strategies as fallback
    import specflow.llm.providers.openai_compatible as provider
    from specflow.cli import main

    guard = _guard(failure_threshold=1)
    config = _config()
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", config.base_url)
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", config.api_key)
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", config.model)
    monkeypatch.setattr(provider, "DEFAULT_RESILIENCE_GUARD", guard)
    monkeypatch.setattr(fallback.time, "sleep", lambda _: None)
    calls = []

    def transport(_):
        calls.append(1)
        return _response(429)

    original_client = httpx.Client

    def offline_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(transport)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(provider.httpx, "Client", offline_client)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# Add feature\ndef feature(): pass\n", encoding="utf-8")
    outputs = []
    for mode, expected in [("legacy", 4), ("multi-agent", 3)]:
        output = tmp_path / mode
        outputs.append(output)
        with pytest.raises(SystemExit) as result:
            main(
                [
                    "run",
                    "--mode",
                    mode,
                    "--provider",
                    "openai-compatible",
                    "--model",
                    "audit-model",
                    "--repo",
                    str(repo),
                    "--requirement",
                    "Add feature",
                    "--output",
                    str(output),
                ]
            )
        assert result.value.code == expected
    assert len(calls) == 1
    assert _snapshot(guard).failure_count == 1
    assert _snapshot(guard).active_calls == 0
    artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for output in outputs
        for path in output.rglob("*")
        if path.is_file()
    )
    assert "LLMCircuitError" in artifacts
    assert "PROVIDER_CIRCUIT_REJECTED" in artifacts
    for secret in (
        config.api_key,
        config.base_url,
        *asdict(_module().resource_identity(config)).values(),
    ):
        assert secret not in artifacts + caplog.text

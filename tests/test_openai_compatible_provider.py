from collections.abc import Callable

import httpx
import pytest

from specflow.llm import (
    LLMConfigurationError,
    LLMMessage,
    LLMRequest,
    LLMResponseError,
    LLMTimeoutError,
    MockLLMClient,
    OpenAICompatibleConfig,
    OpenAICompatibleLLMClient,
)
from specflow.llm.resilience import ProviderResilienceGuard
from specflow.policy.errors import ErrorCategory, error_category, is_retryable

_TEST_CREDENTIAL = "test-credential-not-a-real-key"


def _config(**overrides: object) -> OpenAICompatibleConfig:
    values = {
        "base_url": "https://llm.example.test/v1",
        "api_key": _TEST_CREDENTIAL,
        "model": "example-model",
        "timeout_seconds": 30.0,
    }
    values.update(overrides)
    return OpenAICompatibleConfig(**values)


def _request(model: str = "example-model") -> LLMRequest:
    return LLMRequest(
        model=model,
        messages=[
            LLMMessage(role="system", content="Return JSON."),
            LLMMessage(role="user", content="Analyze the requirement."),
        ],
        temperature=0.2,
        max_tokens=256,
        response_format="json",
    )


def _response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "completion-1",
            "model": "example-model-2026",
            "choices": [
                {
                    "message": {"role": "assistant", "content": '{"ok":true}'},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
        },
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        _config(),
        transport=httpx.MockTransport(handler),
        resilience_guard=ProviderResilienceGuard(),
    )


def test_explicit_configuration_is_valid() -> None:
    config = _config()

    assert config.base_url == "https://llm.example.test/v1"
    assert config.model == "example-model"
    assert config.timeout_seconds == 30.0


def test_configuration_loads_from_environment_mapping() -> None:
    config = OpenAICompatibleConfig.from_env(
        {
            "SPECFLOW_LLM_BASE_URL": "https://llm.example.test/v1/",
            "SPECFLOW_LLM_API_KEY": _TEST_CREDENTIAL,
            "SPECFLOW_LLM_MODEL": "environment-model",
            "SPECFLOW_LLM_TIMEOUT_SECONDS": "45",
        }
    )

    assert config.base_url == "https://llm.example.test/v1"
    assert config.model == "environment-model"
    assert config.timeout_seconds == 45.0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"base_url": ""}, "base URL"),
        ({"api_key": ""}, "API key"),
        ({"model": ""}, "model"),
        ({"timeout_seconds": 0}, "timeout"),
        ({"base_url": "file:///tmp/model"}, "HTTP"),
        ({"base_url": "https://user:pass@llm.example.test/v1"}, "credentials"),
    ],
)
def test_invalid_configuration_fails(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(LLMConfigurationError, match=message):
        _config(**overrides)


def test_successful_response_is_normalized() -> None:
    result = _client(lambda _: _response()).complete(_request())

    assert result.content == '{"ok":true}'
    assert result.model == "example-model-2026"
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 17
    assert result.latency_ms >= 0


def test_request_uses_configured_model_and_openai_shape() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _response()

    _client(handler).complete(_request(model="caller-placeholder"))

    assert len(captured) == 1
    assert captured[0].url == "https://llm.example.test/v1/chat/completions"
    payload = captured[0].read().decode("utf-8")
    assert '"model":"example-model"' in payload
    assert '"max_tokens":256' in payload
    assert '"response_format":{"type":"json_object"}' in payload
    assert captured[0].headers["authorization"] == f"Bearer {_TEST_CREDENTIAL}"


def test_timeout_is_mapped_without_raw_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("server included sensitive body", request=request)

    with pytest.raises(LLMTimeoutError, match="timed out") as exc_info:
        _client(handler).complete(_request())

    assert "sensitive body" not in str(exc_info.value)
    assert exc_info.value.__context__ is None


def test_network_error_is_mapped_without_raw_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("host secret detail", request=request)

    with pytest.raises(LLMResponseError, match="network request failed") as exc_info:
        _client(handler).complete(_request())

    assert "host secret detail" not in str(exc_info.value)
    assert exc_info.value.__context__ is None


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "authentication"), (403, "authentication"), (429, "rate limited"), (500, "unavailable")],
)
def test_http_errors_are_safely_mapped(status: int, message: str) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=f"server body {_TEST_CREDENTIAL}")

    with pytest.raises(LLMResponseError, match=message) as exc_info:
        _client(handler).complete(_request())

    assert _TEST_CREDENTIAL not in str(exc_info.value)
    assert "server body" not in str(exc_info.value)


def test_invalid_json_response_fails_safely() -> None:
    with pytest.raises(LLMResponseError, match="invalid JSON") as exc_info:
        _client(lambda _: httpx.Response(200, content=b"not-json")).complete(_request())

    assert exc_info.value.__context__ is None
    assert exc_info.value.code == "PROVIDER_RESPONSE_INVALID"
    assert exc_info.value.diagnostics.as_dict() == {
        "failure_stage": "response_normalization",
        "finish_reason": None,
        "usage": {"input_tokens": None, "output_tokens": None},
        "usage_status": "unknown",
        "content_empty": None,
        "schema_validation": "not_run",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": []},
    ],
)
def test_invalid_response_structure_fails(payload: object) -> None:
    with pytest.raises(LLMResponseError, match="invalid response structure"):
        _client(lambda _: httpx.Response(200, json=payload)).complete(_request())


def test_api_key_does_not_enter_config_or_client_repr() -> None:
    config = _config()
    client = OpenAICompatibleLLMClient(config, transport=httpx.MockTransport(lambda _: _response()))

    assert _TEST_CREDENTIAL not in repr(config)
    assert _TEST_CREDENTIAL not in repr(client)


def test_api_key_does_not_enter_transport_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError(
            f"transport saw {request.headers['authorization']} {request.read().decode()}"
        )

    with pytest.raises(LLMResponseError) as exc_info:
        _client(handler).complete(_request())

    assert _TEST_CREDENTIAL not in str(exc_info.value)
    assert exc_info.value.__context__ is None


def test_provider_performs_exactly_one_http_attempt() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, text="fail")

    with pytest.raises(LLMResponseError):
        _client(handler).complete(_request())

    assert calls == 1


def test_mock_client_remains_available() -> None:
    response = MockLLMClient(response_content="still mock").complete(_request())

    assert response.content == "still mock"


def _empty_content_payload(usage: object = None, finish_reason: object = "length") -> dict:
    payload = {
        "choices": [{"message": {"content": ""}, "finish_reason": finish_reason}],
    }
    if usage is not None:
        payload["usage"] = usage
    return payload


def test_empty_final_content_retains_known_diagnostics_without_retry() -> None:
    calls = 0
    payload = _empty_content_payload({"prompt_tokens": 2528, "completion_tokens": 3000})

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    with pytest.raises(LLMResponseError) as exc_info:
        _client(handler).complete(_request())

    error = exc_info.value
    assert error.code == "PROVIDER_EMPTY_CONTENT"
    assert error_category(error.code) == ErrorCategory.PERMANENT_PROVIDER
    assert not is_retryable(error.code)
    assert error.diagnostics.as_dict() == {
        "failure_stage": "response_normalization",
        "finish_reason": "length",
        "usage": {"input_tokens": 2528, "output_tokens": 3000},
        "usage_status": "known",
        "content_empty": True,
        "schema_validation": "not_run",
    }
    assert calls == 1


@pytest.mark.parametrize(
    ("usage", "expected_usage", "status"),
    [
        (None, {"input_tokens": None, "output_tokens": None}, "unknown"),
        ({}, {"input_tokens": None, "output_tokens": None}, "unknown"),
        ([], {"input_tokens": None, "output_tokens": None}, "unknown"),
        (
            {"prompt_tokens": True, "completion_tokens": -1},
            {"input_tokens": None, "output_tokens": None},
            "unknown",
        ),
        (
            {"prompt_tokens": "2528", "completion_tokens": 3.0},
            {"input_tokens": None, "output_tokens": None},
            "unknown",
        ),
        (
            {"prompt_tokens": 2528, "completion_tokens": False},
            {"input_tokens": 2528, "output_tokens": None},
            "partial",
        ),
        (
            {"prompt_tokens": None, "completion_tokens": 3000},
            {"input_tokens": None, "output_tokens": 3000},
            "partial",
        ),
        (
            {"prompt_tokens": 0, "completion_tokens": 0},
            {"input_tokens": 0, "output_tokens": 0},
            "known",
        ),
    ],
)
def test_failed_usage_retains_only_known_counts(usage, expected_usage, status) -> None:
    with pytest.raises(LLMResponseError) as exc_info:
        _client(lambda _: httpx.Response(200, json=_empty_content_payload(usage))).complete(
            _request()
        )

    diagnostics = exc_info.value.diagnostics.as_dict()
    assert diagnostics["usage"] == expected_usage
    assert diagnostics["usage_status"] == status
    assert diagnostics["finish_reason"] == "length"
    assert diagnostics["content_empty"] is True


def test_invalid_structure_preserves_facts_before_validation_exit() -> None:
    payload = {
        "choices": [{"message": None, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2528, "completion_tokens": 3000},
    }
    with pytest.raises(LLMResponseError) as exc_info:
        _client(lambda _: httpx.Response(200, json=payload)).complete(_request())

    error = exc_info.value
    assert error.code == "PROVIDER_RESPONSE_INVALID"
    assert error_category(error.code) == ErrorCategory.PERMANENT_PROVIDER
    assert not is_retryable(error.code)
    assert error.diagnostics.as_dict() == {
        "failure_stage": "response_normalization",
        "finish_reason": "stop",
        "usage": {"input_tokens": 2528, "output_tokens": 3000},
        "usage_status": "known",
        "content_empty": None,
        "schema_validation": "not_run",
    }


def test_failure_diagnostics_drop_arbitrary_provider_strings() -> None:
    sensitive = "provider-private-text-and-credential"
    payload = _empty_content_payload(
        {"prompt_tokens": 2528, "completion_tokens": 3000, "private": sensitive},
        sensitive,
    )
    payload["id"] = sensitive
    payload["choices"][0]["message"]["reasoning_content"] = sensitive
    with pytest.raises(LLMResponseError) as exc_info:
        _client(lambda _: httpx.Response(200, json=payload)).complete(_request())

    diagnostics = exc_info.value.diagnostics
    assert diagnostics.finish_reason == "unknown"
    assert sensitive not in repr(diagnostics)
    assert sensitive not in str(diagnostics.as_dict())
    assert sensitive not in str(exc_info.value)


def test_successful_response_keeps_existing_finish_reason_contract() -> None:
    payload = _response().json()
    payload["choices"][0]["finish_reason"] = "provider-specific-success-reason"
    response = _client(lambda _: httpx.Response(200, json=payload)).complete(_request())

    assert response.finish_reason == "provider-specific-success-reason"
    assert response.content == '{"ok":true}'
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 5


@pytest.mark.parametrize(
    ("content", "code", "content_empty"),
    [(" \n\t", "PROVIDER_EMPTY_CONTENT", True), (None, "PROVIDER_RESPONSE_INVALID", None)],
)
def test_absent_content_is_distinguished_from_empty_text(content, code, content_empty) -> None:
    payload = _response().json()
    payload["choices"][0]["message"]["content"] = content
    with pytest.raises(LLMResponseError) as exc_info:
        _client(lambda _: httpx.Response(200, json=payload)).complete(_request())

    assert exc_info.value.code == code
    assert exc_info.value.diagnostics.content_empty is content_empty


def test_invalid_usage_does_not_become_a_successful_response() -> None:
    payload = _response().json()
    payload["usage"]["prompt_tokens"] = False
    with pytest.raises(LLMResponseError) as exc_info:
        _client(lambda _: httpx.Response(200, json=payload)).complete(_request())

    assert exc_info.value.code == "PROVIDER_RESPONSE_INVALID"
    assert exc_info.value.diagnostics.as_dict()["usage"] == {
        "input_tokens": None,
        "output_tokens": 5,
    }
    assert exc_info.value.diagnostics.content_empty is False

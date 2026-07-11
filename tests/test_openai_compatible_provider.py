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
    return OpenAICompatibleLLMClient(_config(), transport=httpx.MockTransport(handler))


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

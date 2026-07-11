import pytest

from specflow.llm import (
    LLMClient,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
    MockLLMClient,
)


def test_mock_llm_returns_response_for_normal_request() -> None:
    client: LLMClient = MockLLMClient(response_content="mock response")
    request = LLMRequest(
        model="mock-model",
        messages=[LLMMessage(role="user", content="hello")],
        temperature=0.0,
        max_tokens=128,
    )

    response = client.complete(request)

    assert response.content == "mock response"
    assert response.model == "mock-model"
    assert response.finish_reason == "stop"


def test_invalid_request_model_fails() -> None:
    with pytest.raises(LLMResponseError):
        LLMRequest(model="", messages=[LLMMessage(role="user", content="hello")])


def test_response_structure_is_stable() -> None:
    response = MockLLMClient().complete(
        LLMRequest(model="mock-model", messages=[LLMMessage(role="user", content="hello")])
    )

    assert isinstance(response, LLMResponse)
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0
    assert response.usage.total_tokens == response.usage.input_tokens + response.usage.output_tokens
    assert response.latency_ms >= 0
    assert response.model == "mock-model"


def test_mock_failures_are_converted_to_llm_response_error() -> None:
    client = MockLLMClient(fail_with=RuntimeError("boom"))
    request = LLMRequest(model="mock-model", messages=[LLMMessage(role="user", content="hello")])

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete(request)

    assert "RuntimeError" in str(exc_info.value)

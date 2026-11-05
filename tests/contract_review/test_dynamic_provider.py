"""Wire-level provider checks through MockTransport, never a real provider."""

import json

import httpx
import pytest

from specflow.contract_review.common import ReviewError
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.provider import OpenAIReviewAdapter, ProviderFailure
from specflow.llm.providers.config import OpenAICompatibleConfig


def configured(handler, *, model="fixture-model"):
    adapter = OpenAIReviewAdapter(
        OpenAICompatibleConfig("https://offline.invalid/v1", "synthetic-secret", model, 5),
        transport=httpx.MockTransport(handler),
        execution_mode="test",
    )
    profile = dynamic_profile("http-test", model, provider_binding=adapter.binding)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "controlled input"}],
        "temperature": 0.0,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    return adapter, profile, payload


def success(usage=None):
    result = {"model": "fixture-model", "choices": [{"message": {"content": '{"ok":true}'}}]}
    if usage is not None:
        result["usage"] = usage
    return result


def test_exact_semantic_payload_and_partial_usage_and_hidden_credential():
    received = []

    def handle(request):
        received.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer synthetic-secret"
        assert request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(200, json=success({"prompt_tokens": 0}))

    adapter, profile, payload = configured(handle)
    response = adapter.complete(payload, profile=profile)
    assert received == [payload]
    assert response["usage"] == {"input_tokens": 0}
    assert "synthetic-secret" not in repr(adapter) + json.dumps(profile) + json.dumps(response)


@pytest.mark.parametrize("field", ["model", "base_url", "timeout", "max_tokens"])
def test_profile_mismatch_has_zero_http_dispatch(field):
    adapter, profile, payload = configured(lambda _: pytest.fail("HTTP must not dispatch"))
    if field == "model":
        payload["model"] = "another-model"
    elif field == "base_url":
        profile["provider_binding"]["base_url"] = "https://another.invalid/v1"
    elif field == "timeout":
        profile["provider_binding"]["timeout_seconds"] = 4
    else:
        payload["max_tokens"] = 10
    with pytest.raises(ReviewError) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.code == "RETRY_PROFILE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (404, False), (429, True), (503, True), (302, False)],
)
def test_status_classification_does_not_hide_automatic_retries(status, retryable):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, text="sensitive upstream diagnostics")

    adapter, profile, payload = configured(handle)
    with pytest.raises(ProviderFailure) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.retryable is retryable
    assert len(requests) == 1
    assert "sensitive upstream" not in str(caught.value)


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": True},
        {"prompt_tokens": -1},
        {"completion_tokens": "3"},
        {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 9},
    ],
)
def test_invalid_usage_is_not_coerced_or_accepted(usage):
    adapter, profile, payload = configured(lambda _: httpx.Response(200, json=success(usage)))
    with pytest.raises(ProviderFailure) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"


def test_missing_usage_remains_unknown():
    adapter, profile, payload = configured(lambda _: httpx.Response(200, json=success()))
    assert adapter.complete(payload, profile=profile)["usage"] == {}


def test_stream_is_closed_as_soon_as_body_limit_is_exceeded():
    class Stream(httpx.SyncByteStream):
        yielded = 0
        closed = False

        def __iter__(self):
            for _ in range(100):
                self.yielded += 1
                yield b"x" * 8192

        def close(self):
            self.closed = True

    stream = Stream()
    adapter, profile, payload = configured(lambda _: httpx.Response(200, stream=stream))
    with pytest.raises(ProviderFailure) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.code == "PROVIDER_RESPONSE_TOO_LARGE"
    assert stream.closed and stream.yielded == 17


@pytest.mark.parametrize("failure", ["timeout", "connection", "unexpected"])
def test_transport_failure_is_safe_and_locally_closed(failure):
    def handle(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret diagnostic", request=request)
        if failure == "connection":
            raise httpx.ConnectError("secret diagnostic", request=request)
        raise RuntimeError("synthetic-secret")

    adapter, profile, payload = configured(handle)
    with pytest.raises(ProviderFailure) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.remote_outcome == "unknown"
    assert caught.value.retryable is (failure != "unexpected")
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("body", [b"not json", b'{"choices":[]}', b'{"choices":[],"choices":[]}'])
def test_invalid_outer_response_is_not_a_model_action(body):
    adapter, profile, payload = configured(lambda _: httpx.Response(200, content=body))
    with pytest.raises(ProviderFailure) as caught:
        adapter.complete(payload, profile=profile)
    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"

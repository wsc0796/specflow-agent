"""Synchronous OpenAI-compatible implementation of the existing LLMClient."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from specflow.llm.exceptions import LLMResponseError, LLMTimeoutError
from specflow.llm.models import LLMRequest, LLMResponse, LLMUsage
from specflow.llm.providers.config import OpenAICompatibleConfig


class OpenAICompatibleLLMClient:
    """Perform exactly one configured OpenAI-compatible completion request."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not isinstance(config, OpenAICompatibleConfig):
            raise TypeError("config must be an OpenAICompatibleConfig")
        self._config = config
        self._transport = transport

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleLLMClient("
            f"base_url={self._config.base_url!r}, "
            f"model={self._config.model!r}, "
            f"timeout_seconds={self._config.timeout_seconds!r})"
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Map one provider-neutral request to one safe HTTP request and response."""
        if not isinstance(request, LLMRequest):
            raise LLMResponseError("OpenAI-compatible Provider requires an LLMRequest")
        started = perf_counter()
        response: httpx.Response | None = None
        transport_failure: str | None = None
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self._config.timeout_seconds),
                transport=self._transport,
            ) as client:
                response = client.post(
                    self._config.completions_url,
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._request_payload(request),
                )
        except httpx.TimeoutException:
            transport_failure = "timeout"
        except httpx.RequestError:
            transport_failure = "network"
        except Exception:
            # Custom transports can raise arbitrary errors containing headers or
            # message bodies. Keep only a safe category and raise after leaving
            # the except scope so no sensitive original remains as __context__.
            transport_failure = "transport"

        if transport_failure == "timeout":
            raise LLMTimeoutError("LLM provider request timed out")
        if transport_failure == "network":
            raise LLMResponseError("LLM provider network request failed")
        if transport_failure == "transport":
            raise LLMResponseError("LLM provider transport failed")
        if response is None:
            raise LLMResponseError("LLM provider transport returned no response")

        self._raise_for_status(response.status_code)
        payload: Any = None
        invalid_json = False
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            invalid_json = True
        if invalid_json:
            raise LLMResponseError("LLM provider returned invalid JSON")

        content, model, usage, finish_reason = self._parse_response(payload)
        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            finish_reason=finish_reason,
        )

    def _request_payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format:
            response_type = (
                "json_object"
                if request.response_format in {"json", "json_object"}
                else request.response_format
            )
            payload["response_format"] = {"type": response_type}
        return payload

    def _parse_response(self, payload: Any) -> tuple[str, str, LLMUsage, str]:
        if not isinstance(payload, dict):
            self._invalid_response()
        choices = payload.get("choices")
        usage_payload = payload.get("usage")
        if not isinstance(choices, list) or not choices or not isinstance(usage_payload, dict):
            self._invalid_response()
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            self._invalid_response()
        message = first["message"]
        content = message.get("content")
        finish_reason = first.get("finish_reason")
        model = payload.get("model") or self._config.model
        input_tokens = self._token_count(usage_payload, "prompt_tokens")
        output_tokens = self._token_count(usage_payload, "completion_tokens")
        if (
            not isinstance(content, str)
            or not content.strip()
            or not isinstance(model, str)
            or not model.strip()
            or not isinstance(finish_reason, str)
            or not finish_reason.strip()
        ):
            self._invalid_response()
        return (
            content,
            model,
            LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            finish_reason,
        )

    @staticmethod
    def _token_count(usage: dict[str, Any], key: str) -> int:
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            OpenAICompatibleLLMClient._invalid_response()
        return value

    @staticmethod
    def _invalid_response() -> None:
        raise LLMResponseError("LLM provider returned invalid response structure")

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code < 400:
            return
        if status_code in {401, 403}:
            raise LLMResponseError(f"LLM provider authentication failed (HTTP {status_code})")
        if status_code == 429:
            raise LLMResponseError("LLM provider rate limited the request (HTTP 429)")
        raise LLMResponseError(f"LLM provider is unavailable (HTTP {status_code})")

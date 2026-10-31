"""Single-request synchronous OpenAI-compatible adapter with bounded streaming reads."""

import httpx

from specflow.contract_review.common import ReviewError
from specflow.contract_review.sources import strict_json
from specflow.llm.providers.config import OpenAICompatibleConfig


class ProviderFailure(ReviewError):
    def __init__(self, code, *, retryable=False, usage=None, remote_outcome="unknown"):
        super().__init__(code, "模型依赖未产生可接受响应。")
        self.retryable = retryable
        self.usage = usage or {}
        self.remote_outcome = remote_outcome


class OpenAIReviewAdapter:
    def __init__(self, config: OpenAICompatibleConfig, *, transport=None, execution_mode="live"):
        if not isinstance(config, OpenAICompatibleConfig):
            raise TypeError("Expected validated provider configuration")
        if execution_mode not in ("test", "live"):
            raise ValueError("Unknown execution mode")
        if execution_mode == "test" and not isinstance(transport, httpx.MockTransport):
            raise ValueError("Test HTTP adapter requires MockTransport")
        self._config, self._transport = config, transport
        self.execution_mode = execution_mode

    def __repr__(self):
        return "OpenAIReviewAdapter(synchronous, credentials_hidden=True)"

    @property
    def binding(self):
        return {
            "adapter_version": "openai-compatible.sync.v1",
            "base_url": self._config.base_url,
            "timeout_seconds": self._config.timeout_seconds,
        }

    def prepare(self, payload, profile):
        if (
            profile.get("provider_binding") != self.binding
            or profile["model"] != self._config.model
            or profile["execution_mode"] != self.execution_mode
            or payload["model"] != self._config.model
            or payload["max_tokens"] != profile["max_output_tokens"]
            or payload.get("temperature") != 0.0
            or payload.get("response_format") != {"type": "json_object"}
            or set(payload) != {"model", "messages", "temperature", "max_tokens", "response_format"}
        ):
            raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "实际 Provider 配置与冻结输入不符。")
        return {**payload, "model": self._config.model}

    def complete(self, payload, *, profile):
        wire = self.prepare(payload, profile)
        failure, body = None, bytearray()
        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds,
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                with client.stream(
                    "POST",
                    self._config.completions_url,
                    json=wire,
                    headers={
                        "Authorization": "Bearer " + self._config.api_key,
                        "Accept-Encoding": "identity",
                    },
                ) as response:
                    status = response.status_code
                    if status != 200:
                        code = (
                            "PROVIDER_AUTH_FAILURE"
                            if status in (401, 403)
                            else "PROVIDER_RATE_LIMITED"
                            if status == 429
                            else "PROVIDER_SERVER_ERROR"
                            if status >= 500
                            else "PROVIDER_REQUEST_REJECTED"
                        )
                        failure = (code, status == 429 or status >= 500, "known")
                    elif response.headers.get("content-encoding", "identity").lower() != "identity":
                        failure = ("PROVIDER_RESPONSE_ENCODING_UNSUPPORTED", False, "known")
                    else:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if len(body) + len(chunk) > 128 * 1024:
                                failure = ("PROVIDER_RESPONSE_TOO_LARGE", False, "known")
                                break
                            body.extend(chunk)
        except httpx.TimeoutException:
            failure = ("PROVIDER_TIMEOUT", True, "unknown")
        except httpx.RequestError:
            failure = ("PROVIDER_CONNECTION_ERROR", True, "unknown")
        except Exception:
            failure = ("PROVIDER_ERROR", False, "unknown")
        if failure:
            raise ProviderFailure(failure[0], retryable=failure[1], remote_outcome=failure[2])
        invalid, usage, content, model = False, {}, None, None
        try:
            parsed = strict_json(bytes(body).decode("utf-8"))
            content = parsed["choices"][0]["message"]["content"]
            model = parsed.get("model") or self._config.model
            raw_usage = parsed.get("usage", {})
            if raw_usage is None:
                raw_usage = {}
            if not isinstance(raw_usage, dict):
                raise ValueError("Invalid usage")
            for name, key in (
                ("prompt_tokens", "input_tokens"),
                ("completion_tokens", "output_tokens"),
            ):
                if name in raw_usage and raw_usage[name] is not None:
                    value = raw_usage[name]
                    if type(value) is not int or value < 0:
                        raise ValueError("Invalid token count")
                    usage[key] = value
            total = raw_usage.get("total_tokens")
            if total is not None and (
                type(total) is not int
                or total < 0
                or len(usage) == 2
                and total != sum(usage.values())
            ):
                usage = {}
                raise ValueError("Inconsistent total usage")
            if not isinstance(content, str) or not content.strip() or not isinstance(model, str):
                raise ValueError("Missing content")
        except (ValueError, UnicodeError, KeyError, IndexError, TypeError, AttributeError):
            invalid = True
        if invalid:
            raise ProviderFailure("PROVIDER_RESPONSE_INVALID", usage=usage, remote_outcome="known")
        return {"content": content, "model": model, "usage": usage}

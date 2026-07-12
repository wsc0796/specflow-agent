import json

import pytest

from specflow.fallback import FallbackLevel, FallbackManager, RetryStrategy
from specflow.trace import LLMTrace


def test_normal_success_has_no_fallback() -> None:
    result = FallbackManager().execute(lambda: "success")

    assert result.status == "success"
    assert result.fallback_level == FallbackLevel.NONE
    assert result.content == "success"
    assert result.retry_count == 0
    assert not result.requires_review


def test_first_failure_then_success_uses_retry() -> None:
    calls = {"count": 0}

    def operation() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("temporary")
        return "success"

    result = FallbackManager(RetryStrategy(max_retries=2)).execute(operation)

    assert result.status == "success"
    assert result.fallback_level == FallbackLevel.RETRY
    assert result.retry_count == 1
    assert result.content == "success"


def test_json_repair_extracts_valid_json() -> None:
    result = FallbackManager().execute(
        lambda: 'Here is result:\n{"name":"test"}',
        expect_json=True,
    )

    assert result.status == "success"
    assert result.fallback_level == FallbackLevel.JSON_REPAIR
    assert json.loads(result.content) == {"name": "test"}
    assert result.confidence == 0.8


def test_full_failure_uses_rule_baseline() -> None:
    def operation() -> str:
        raise TimeoutError("down")

    result = FallbackManager(RetryStrategy(max_retries=1)).execute(operation, expect_json=True)

    assert result.status == "degraded"
    assert result.fallback_level == FallbackLevel.RULE_BASELINE
    assert result.requires_review
    assert result.confidence == 0
    assert result.error_type == "TimeoutError"
    assert result.retry_count == 1


def test_security_and_auth_failures_are_not_retried() -> None:
    for message in ("401 unauthorized", "403 forbidden", "path traversal blocked"):
        calls = 0

        def operation() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError(message)

        result = FallbackManager(RetryStrategy(max_retries=2)).execute(operation)
        assert result.status == "degraded"
        assert calls == 1


def test_invalid_json_uses_rule_baseline() -> None:
    result = FallbackManager().execute(lambda: "not json", expect_json=True)

    assert result.status == "degraded"
    assert result.fallback_level == FallbackLevel.RULE_BASELINE
    assert result.requires_review


def test_sensitive_data_is_redacted_from_fallback_result() -> None:
    result = FallbackManager().execute(
        lambda: "api_key=sk-abc123def456ghi789jkl012 token=raw-secret password=hunter2"
    )

    assert "sk-abc123" not in result.content
    assert "raw-secret" not in result.content
    assert "hunter2" not in result.content
    assert "api_key=<redacted>" in result.content
    assert "token=<redacted>" in result.content
    assert "password=<redacted>" in result.content


def test_trace_can_carry_fallback_metadata_without_content() -> None:
    trace = LLMTrace(
        run_id="run-001",
        prompt_name="analyze_requirement",
        prompt_version="1.0.0",
        prompt_hash="prompt-hash",
        context_hash="context-hash",
        model="mock-model",
        latency_ms=1,
        input_tokens=1,
        output_tokens=0,
        status="degraded",
        error_type="TimeoutError",
        fallback_level="rule_baseline",
        retry_count=2,
    )

    payload = trace.as_dict()
    raw = json.dumps(payload)
    assert payload["fallback_level"] == "rule_baseline"
    assert payload["retry_count"] == 2
    assert "api_key" not in raw
    assert "password" not in raw
    assert "token=" not in raw


def test_negative_retry_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        RetryStrategy(max_retries=-1)

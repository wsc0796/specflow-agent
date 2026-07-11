import json

import pytest

from specflow.llm import LLMMessage, LLMRequest, LLMResponseError, MockLLMClient
from specflow.trace import JsonTraceStorage, TraceRecorder


def _request() -> LLMRequest:
    return LLMRequest(
        model="mock-model",
        messages=[LLMMessage(role="user", content="hello with api_key=secret")],
    )


def test_successful_llm_call_writes_trace_json(tmp_path) -> None:
    recorder = TraceRecorder(JsonTraceStorage(tmp_path))

    response = recorder.complete_with_trace(
        client=MockLLMClient(response_content="mock response"),
        request=_request(),
        prompt_name="analyze_requirement",
        prompt_version="1.0.0",
        prompt_hash="prompt-hash",
        context_hash="context-hash",
        run_id="run-001",
    )

    trace_file = tmp_path / "run-001.json"
    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert response.content == "mock response"
    assert payload["prompt_hash"] == "prompt-hash"
    assert payload["context_hash"] == "context-hash"
    assert payload["status"] == "success"
    assert payload["latency_ms"] >= 0
    assert payload["input_tokens"] > 0
    assert payload["output_tokens"] > 0


def test_failed_llm_call_writes_failed_trace(tmp_path) -> None:
    recorder = TraceRecorder(JsonTraceStorage(tmp_path))

    with pytest.raises(LLMResponseError):
        recorder.complete_with_trace(
            client=MockLLMClient(fail_with=RuntimeError("boom")),
            request=_request(),
            prompt_name="analyze_requirement",
            prompt_version="1.0.0",
            prompt_hash="prompt-hash",
            context_hash="context-hash",
            run_id="run-failed",
        )

    payload = json.loads((tmp_path / "run-failed.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error_type"] == "LLMResponseError"
    assert payload["input_tokens"] == 0
    assert payload["output_tokens"] == 0


def test_trace_json_does_not_store_sensitive_content(tmp_path) -> None:
    recorder = TraceRecorder(JsonTraceStorage(tmp_path))

    recorder.complete_with_trace(
        client=MockLLMClient(response_content="mock response"),
        request=_request(),
        prompt_name="analyze_requirement",
        prompt_version="1.0.0",
        prompt_hash="prompt-hash",
        context_hash="context-hash",
        run_id="run-safe",
    )

    raw = (tmp_path / "run-safe.json").read_text(encoding="utf-8")
    assert "api_key" not in raw
    assert "secret" not in raw
    assert "hello" not in raw
    assert "mock response" not in raw


def test_run_id_controls_trace_filename(tmp_path) -> None:
    recorder = TraceRecorder(JsonTraceStorage(tmp_path))

    recorder.complete_with_trace(
        client=MockLLMClient(),
        request=_request(),
        prompt_name="analyze_requirement",
        prompt_version="1.0.0",
        prompt_hash="prompt-hash",
        context_hash="context-hash",
        run_id="stable-run",
    )

    assert (tmp_path / "stable-run.json").exists()

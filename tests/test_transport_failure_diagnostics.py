"""Offline transport faults through the real Provider, Adapter and Runner."""

import json

import httpx
import pytest

from specflow.agents.adapter import AgentRunner
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.llm.providers.openai_compatible import OpenAICompatibleLLMClient
from specflow.llm.resilience import ProviderResilienceGuard, ResilienceSettings
from specflow.runner_multi import _build_registry, run_multi_agent
from specflow.schema import build_schema_registry

_SENSITIVE = "PRIVATE_TRANSPORT_DIAGNOSTIC_MARKER"
_CREDENTIAL = "offline-transport-fixture-credential"
_PRIVATE_HOST = "private-transport.example.invalid"
_FAULTS = [("timeout", "PROVIDER_TIMEOUT"), ("503", "PROVIDER_SERVER_ERROR")]


def _response(content):
    return httpx.Response(
        200,
        json={
            "model": "offline-transport-model",
            "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        },
    )


def _transport_failure(fault, request):
    private_text = (
        f"{_SENSITIVE} https://{_PRIVATE_HOST}/private Authorization: Bearer {_CREDENTIAL}"
    )
    if fault == "timeout":
        raise httpx.ReadTimeout(private_text, request=request)
    return httpx.Response(503, text=private_text)


def _client(config, handler):
    # Keep the breaker above the explicit three-attempt test budget.
    return OpenAICompatibleLLMClient(
        config,
        transport=httpx.MockTransport(handler),
        resilience_guard=ProviderResilienceGuard(ResilienceSettings(failure_threshold=5)),
    )


def _unknown_transport_diagnostics():
    return {
        "failure_stage": "provider_transport",
        "finish_reason": None,
        "usage": {"input_tokens": None, "output_tokens": None},
        "usage_status": "unknown",
        "content_empty": None,
        "schema_validation": "not_run",
    }


@pytest.mark.parametrize("fault,expected_code", _FAULTS)
def test_transport_fault_reaches_native_artifacts_without_product_retry(
    tmp_path, monkeypatch, caplog, capsys, fault, expected_code
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def login(username):\n    return bool(username)\n", encoding="utf-8"
    )
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", f"https://{_PRIVATE_HOST}/v1")
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", _CREDENTIAL)
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", "offline-transport-model")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        text = "\n".join(item["content"] for item in body["messages"])
        planning = text.startswith("Generate a task brief")
        calls.append("planning" if planning else "execution")
        if planning:
            return _response({"task_description": "Inspect login."})
        return _transport_failure(fault, request)

    def client_factory(*args, config, **kwargs):
        return _client(config, handler)

    monkeypatch.setattr("specflow.runner_multi._create_real_llm_client", client_factory)
    output = tmp_path / "out"
    result = run_multi_agent(
        repo=repo,
        requirement="Add login failure protection",
        output=output,
        provider="openai-compatible",
        model="offline-transport-model",
    )

    assert int(result) == 3
    assert calls == ["planning"] * 6 + ["execution"]
    run_dir = result.artifact_directory
    assert run_dir is not None
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == expected_code
    assert manifest["workflow_state"] == "failed"
    assert manifest["stages_completed"] == 0
    assert manifest["failure_context"] == {
        "agent_id": "repository-analyst-agent-v1",
        "agent_role": "repository_analyst",
        "failure_stage": "provider_transport",
        "stage_index": "0",
    }
    assert manifest["failure_diagnostics"] == [
        {
            "agent_id": "repository-analyst-agent-v1",
            "agent_role": "repository_analyst",
            "stage_index": 0,
            "error_code": expected_code,
            **_unknown_transport_diagnostics(),
        }
    ]
    traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
    assert traces
    assert all(trace["error_code"] == expected_code for trace in traces)
    assert all(trace["failure_context"] == manifest["failure_context"] for trace in traces)
    assert json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8")) == {}
    assert not (run_dir / "metrics.json").exists()
    captured = capsys.readouterr()
    observed = caplog.text + captured.out + captured.err
    observed += "\n".join(path.read_text(encoding="utf-8") for path in run_dir.glob("*.json"))
    for secret in (_SENSITIVE, _CREDENTIAL, _PRIVATE_HOST):
        assert secret not in observed


@pytest.mark.parametrize("fault,expected_code", _FAULTS)
@pytest.mark.parametrize("failures_before_success", [None, 0, 1, 2])
def test_explicit_adapter_retry_is_bounded_and_success_can_pass(
    monkeypatch, fault, expected_code, failures_before_success
):
    calls, backoffs = [], []
    valid_output = {
        "summary": "Preserve the existing login contract.",
        "implementation_steps": ["Add an atomic username failure counter."],
    }

    def handler(request):
        calls.append(request)
        if failures_before_success is not None and len(calls) > failures_before_success:
            return _response(valid_output)
        return _transport_failure(fault, request)

    config = OpenAICompatibleConfig(
        base_url=f"https://{_PRIVATE_HOST}/v1",
        api_key=_CREDENTIAL,
        model="offline-transport-model",
    )
    monkeypatch.setattr("specflow.agents.adapter.time.sleep", backoffs.append)
    identity = _build_registry().get("design-agent-v1").identity
    result = AgentRunner(
        identity,
        _client(config, handler),
        model=config.model,
        schema_registry=build_schema_registry(),
        max_retries=2,
    ).execute({"requirement": "Add login failure protection"})

    expected_attempts = 3 if failures_before_success is None else failures_before_success + 1
    assert len(calls) == expected_attempts
    assert backoffs == [0.5, 1.0][: expected_attempts - 1]
    if failures_before_success is None:
        assert result["success"] is False
        assert result["schema_validated"] is False
        assert result["output"]["error_code"] == expected_code
        assert result["failure_diagnostics"] == _unknown_transport_diagnostics()
    else:
        assert result["success"] is True
        assert result["schema_validated"] is True
        assert result["output"]["summary"] == valid_output["summary"]
        assert result["output"]["implementation_steps"] == valid_output["implementation_steps"]
        assert "failure_diagnostics" not in result
    serialized = json.dumps(result)
    for secret in (_SENSITIVE, _CREDENTIAL, _PRIVATE_HOST):
        assert secret not in serialized

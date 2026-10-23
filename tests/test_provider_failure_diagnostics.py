"""Offline regressions for native failure artifacts, never live-model tests."""

import json

import httpx
import pytest

from specflow.llm.providers.openai_compatible import OpenAICompatibleLLMClient
from specflow.runner_multi import run_multi_agent


@pytest.mark.parametrize(
    "fault,expected_code,expected_stage,expected_schema",
    [
        ("empty", "PROVIDER_EMPTY_CONTENT", "response_normalization", "not_run"),
        ("json", "JSON_PARSE_FAILED", "json_parse", "not_run"),
        ("schema", "SCHEMA_VALIDATION_FAILED", "schema_validation", "failed"),
    ],
)
def test_native_failure_keeps_safe_response_facts(
    tmp_path, monkeypatch, fault, expected_code, expected_stage, expected_schema
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def login(username):\n    return bool(username)\n")
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", "https://offline.invalid/v1")
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", "offline-fixture-only")
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", "offline-diagnostics-model")
    calls = []
    sensitive_marker = "SENSITIVE_FAILURE_MARKER"

    def handler(request):
        body = json.loads(request.content)
        text = "\n".join(item["content"] for item in body["messages"])
        planning = text.startswith("Generate a task brief")
        calls.append("planning" if planning else "repository_analyst")
        if planning:
            content = json.dumps({"task_description": "Inspect login."})
        elif fault == "empty":
            content = ""
        elif fault == "json":
            content = "{invalid-json-" + sensitive_marker
        else:
            content = json.dumps({"summary": " ", "untrusted": sensitive_marker})
        return httpx.Response(
            200,
            json={
                "model": "offline-diagnostics-model",
                "choices": [
                    {
                        "message": {
                            "content": content,
                            "reasoning_content": sensitive_marker,
                        },
                        "finish_reason": "stop" if planning else "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10 if planning else 2528,
                    "completion_tokens": 10 if planning else 3000,
                },
            },
        )

    def client_factory(*args, config, **kwargs):
        return OpenAICompatibleLLMClient(config, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("specflow.runner_multi._create_real_llm_client", client_factory)
    output = tmp_path / "out"
    result = run_multi_agent(
        repo=repo,
        requirement="Add login failure protection",
        output=output,
        provider="openai-compatible",
        model="offline-diagnostics-model",
    )
    assert int(result) == 3
    assert calls == ["planning"] * 6 + ["repository_analyst"]
    run_dir = next(output.iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["error"] == expected_code
    assert manifest["workflow_state"] == "failed"
    assert manifest["stages_completed"] == 0
    assert len(manifest["failure_diagnostics"]) == 1
    diagnostic = manifest["failure_diagnostics"][0]
    assert diagnostic["agent_id"] == "repository-analyst-agent-v1"
    assert diagnostic["agent_role"] == "repository_analyst"
    assert diagnostic["stage_index"] == 0
    assert diagnostic["failure_stage"] == expected_stage
    assert diagnostic["schema_validation"] == expected_schema
    assert diagnostic["finish_reason"] == "length"
    assert diagnostic["usage_status"] == "known"
    assert diagnostic["usage"] == {"input_tokens": 2528, "output_tokens": 3000}
    assert json.loads((run_dir / "agent-outputs.json").read_text()) == {}
    traces = json.loads((run_dir / "traces.json").read_text())
    assert all(trace["error_code"] == expected_code for trace in traces)
    assert all(trace["failure_context"]["agent_id"] == diagnostic["agent_id"] for trace in traces)
    assert not (run_dir / "metrics.json").exists()
    for artifact in run_dir.glob("*.json"):
        assert sensitive_marker not in artifact.read_text()


def test_untrusted_diagnostic_fields_are_not_serialized(tmp_path):
    from specflow.runner_multi import _build_registry

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return True\n")
    identity = next(
        identity
        for identity in _build_registry().list_agents()
        if identity.role.value == "repository_analyst"
    )
    payload = {
        "agent_id": identity.agent_id,
        "success": False,
        "schema_validated": False,
        "output": {"error_code": "PROVIDER_EMPTY_CONTENT"},
        "failure_diagnostics": {
            "failure_stage": "response_normalization",
            "finish_reason": "SENSITIVE_FINISH_MARKER",
            "usage": {"input_tokens": None, "output_tokens": None},
            "usage_status": "known",
            "raw_response": "SENSITIVE_BODY_MARKER",
            "content_empty": True,
        },
    }
    output = tmp_path / "out"
    result = run_multi_agent(
        repo=repo,
        requirement="Review health",
        output=output,
        mock=True,
        _executor_overrides={identity.agent_id: lambda _: payload},
    )
    assert int(result) == 3
    run_dir = next(output.iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    diagnostic = manifest["failure_diagnostics"][0]
    assert diagnostic["finish_reason"] == "unknown"
    assert diagnostic["usage_status"] == "unknown"
    assert diagnostic["usage"] == {"input_tokens": None, "output_tokens": None}
    assert "raw_response" not in diagnostic
    for artifact in run_dir.glob("*.json"):
        assert "SENSITIVE_" not in artifact.read_text()

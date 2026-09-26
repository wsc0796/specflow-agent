"""Accepted upstream fields must reach actual receiver requests within a bound."""

import json
from dataclasses import replace

import pytest
from test_multi_agent_request_budget import FakeProvider

from specflow import runner_multi
from specflow.policy import ExecutionPolicy, TokenPolicy

ANALYST_MARKER = "src/critical_fact_marker.py"
DESIGN_MARKER = "IMPLEMENTATION_STEP_MARKER"
TEST_MARKER = "REQUIRED_TEST_MARKER"
RISK_MARKER = "RISK_CONDITION_MARKER"


class LongPayloadProvider(FakeProvider):
    def __init__(self, summary_size=700):
        super().__init__()
        self.summary_size = summary_size

    def complete(self, request):
        response = super().complete(request)
        first = request.messages[0]
        if first.role != "system":
            return response
        payload = {"summary": "s" * self.summary_size}
        if "**repository_analyst**" in first.content:
            payload.update(key_files=[ANALYST_MARKER], evidence_count=1)
        elif "**design**" in first.content:
            payload["implementation_steps"] = [DESIGN_MARKER]
        elif "**test_strategy**" in first.content:
            payload["test_scenarios"] = [TEST_MARKER]
        elif "**risk_review**" in first.content:
            payload["risks"] = [RISK_MARKER]
        else:
            return response
        return replace(response, content=json.dumps(payload))


def _run(tmp_path, monkeypatch, provider, *, input_tokens=10000):
    monkeypatch.setattr(runner_multi, "_create_real_llm_client", lambda *a, **k: provider)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health RAW_EVIDENCE_ONLY_MARKER\n", encoding="utf-8")
    output = tmp_path / "out"
    code = runner_multi.run_multi_agent(
        repo=repo,
        requirement="explain health",
        output=output,
        provider="openai-compatible",
        model="fake",
        policy=ExecutionPolicy(
            max_llm_calls=12, tokens=TokenPolicy(max_agent_input_tokens=input_tokens)
        ),
    )
    run = next(output.glob("run-multi-*"))
    return code, run


def _message(provider, role):
    request = next(r for r in provider.requests if f"**{role}**" in r.messages[0].content)
    return request.messages[-1].content


def test_long_upstream_fields_reach_every_declared_receiver(tmp_path, monkeypatch):
    provider = LongPayloadProvider()
    code, run = _run(tmp_path, monkeypatch, provider)
    assert code == 0
    assert len(provider.requests) == 12
    outputs = json.loads((run / "agent-outputs.json").read_text(encoding="utf-8"))
    assert outputs["stage-0/repository-analyst-agent-v1"]["schema_validated"] is True
    for role in ("design", "test_strategy", "risk_review"):
        user = _message(provider, role)
        assert ANALYST_MARKER in user
        assert "RAW_EVIDENCE_ONLY_MARKER" not in user
        assert "...(truncated)" not in user
        payload = user.split("### repository_analysis\n", 1)[1].split("\n\nReturn", 1)[0]
        parsed = json.loads(payload)
        assert parsed["summary"] == "s" * 700
        assert parsed["key_files"] == [ANALYST_MARKER]
    synthesis = _message(provider, "synthesis")
    for marker in (DESIGN_MARKER, TEST_MARKER, RISK_MARKER):
        assert marker in synthesis
    assert ANALYST_MARKER not in synthesis
    assert "RAW_EVIDENCE_ONLY_MARKER" not in synthesis


def test_oversized_required_input_stops_before_receiver_request(tmp_path, monkeypatch):
    provider = LongPayloadProvider(summary_size=5000)
    code, run = _run(tmp_path, monkeypatch, provider, input_tokens=1024)
    assert code == 3
    assert len(provider.requests) == 7  # six briefs + Analyst; no Specialist request
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == "TOKEN_BUDGET_EXCEEDED"
    assert manifest["stages_completed"] == 1
    outputs = json.loads((run / "agent-outputs.json").read_text(encoding="utf-8"))
    assert set(outputs) == {"stage-0/repository-analyst-agent-v1"}


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_adapter_input_budget_is_rejected(limit):
    from specflow.agents.adapter import AgentRunner

    with pytest.raises(ValueError):
        AgentRunner(
            runner_multi._build_registry().get("design-agent-v1").identity,
            FakeProvider(),
            max_input_tokens=limit,
        )

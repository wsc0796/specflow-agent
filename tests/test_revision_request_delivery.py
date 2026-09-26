"""Revision must change the actual target request, within its input budget."""

import json
from dataclasses import replace

import pytest
from test_multi_agent_request_budget import FakeProvider

from specflow import runner_multi
from specflow.policy import ExecutionPolicy, TokenPolicy


class RevisionProvider(FakeProvider):
    def __init__(
        self, role="design", finding="REVIEW_CORRECTION_MARKER", summary="Review needs changes"
    ):
        super().__init__()
        self.role = role
        self.finding = finding
        self.reviews = 0
        self.summary = summary

    def complete(self, request):
        response = super().complete(request)
        first = request.messages[0].content
        if request.messages[0].role != "system":
            return response
        if f"**{self.role}**" in first:
            return replace(response, content='{"summary":"PREVIOUS_TARGET_OUTPUT_MARKER"}')
        if "**review**" in first:
            self.reviews += 1
            if self.reviews == 1:
                payload = {
                    "summary": self.summary,
                    "decision": "REJECT",
                    "findings": [self.finding],
                    "target_agent_id": self.role.replace("_", "-") + "-agent-v1",
                }
                return replace(response, content=json.dumps(payload))
        return response


def run_revision(tmp_path, monkeypatch, provider, input_tokens=10000):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health RAW_REPOSITORY_ONLY\n", encoding="utf-8")
    monkeypatch.setattr(runner_multi, "_create_real_llm_client", lambda *a, **k: provider)
    output = tmp_path / "out"
    code = runner_multi.run_multi_agent(
        repo=repo,
        requirement="health",
        output=output,
        provider="openai-compatible",
        model="fake",
        policy=ExecutionPolicy(
            max_llm_calls=15, tokens=TokenPolicy(max_agent_input_tokens=input_tokens)
        ),
    )
    return code, next(output.glob("run-multi-*"))


@pytest.mark.parametrize("role", ["design", "test_strategy", "risk_review"])
def test_revision_request_delivers_instruction_review_and_previous_output(
    tmp_path, monkeypatch, role
):
    provider = RevisionProvider(role)
    code, run = run_revision(tmp_path, monkeypatch, provider)
    assert code == 0
    assert len(provider.requests) == 15
    requests = [r for r in provider.requests if f"**{role}**" in r.messages[0].content]
    initial, revised = [r.messages[-1].content for r in requests]
    assert "## Revision Context" not in initial
    assert "## Revision Context" in revised
    assert "REVIEW_CORRECTION_MARKER" in revised
    assert "PREVIOUS_TARGET_OUTPUT_MARKER" in revised
    assert "Revise the output" in revised
    assert "RAW_REPOSITORY_ONLY" not in revised
    for request in provider.requests:
        if request not in requests:
            assert "REVIEW_CORRECTION_MARKER" not in request.messages[-1].content
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["revision_count"] == 1


def test_revision_context_is_checked_before_spending_another_call(tmp_path, monkeypatch):
    provider = RevisionProvider(finding="x" * 6000)
    code, run = run_revision(tmp_path, monkeypatch, provider, input_tokens=1024)
    assert code == 3
    assert len(provider.requests) == 12
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == "TOKEN_BUDGET_EXCEEDED"
    assert manifest["stages_completed"] == 4


def test_revision_dlp_preserves_findings_and_previous_output(tmp_path, monkeypatch):
    provider = RevisionProvider(summary="authorization=synthetic-front-value")
    code, _ = run_revision(tmp_path, monkeypatch, provider)
    assert code == 0
    request = [r for r in provider.requests if "**design**" in r.messages[0].content][-1]
    block = request.messages[-1].content.split("## Revision Context\n", 1)[1].splitlines()[1]
    parsed = json.loads(block)
    assert parsed["review_output"]["findings"] == ["REVIEW_CORRECTION_MARKER"]
    assert parsed["previous_output"]["summary"] == "PREVIOUS_TARGET_OUTPUT_MARKER"
    assert "synthetic-front-value" not in block

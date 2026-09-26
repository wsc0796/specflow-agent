"""Semantic briefs must reach their own receiver's actual request."""

import json
import re
from dataclasses import replace

import pytest
from test_revision_request_delivery import RevisionProvider, run_revision


class BriefProvider(RevisionProvider):
    def __init__(self, *, degraded=False, size=0):
        super().__init__()
        self.degraded = degraded
        self.size = size

    def complete(self, request):
        response = super().complete(request)
        if request.messages[0].role == "system":
            return response
        agent_id = re.search(r'agent "([^"]+)"', request.messages[0].content).group(1)
        brief = {
            "task_description": f"TASK::{agent_id}" + "x" * self.size,
            "analysis_focus": [f"FOCUS::{agent_id}"],
            "evaluation_hints": [f"EVAL::{agent_id}"],
            "repository_scope_hint": f"SCOPE::{agent_id} authorization=synthetic-only",
        }
        return replace(response, content="not json" if self.degraded else json.dumps(brief))


@pytest.mark.parametrize("degraded", [False, True])
def test_briefs_reach_only_their_receiver_including_revision(tmp_path, monkeypatch, degraded):
    provider = BriefProvider(degraded=degraded)
    code, run = run_revision(tmp_path, monkeypatch, provider)
    assert code == 0
    assert len(provider.requests) == 15
    agents = [r for r in provider.requests if r.messages[0].role == "system"]
    assert len(agents) == 9
    for request in agents:
        role = request.messages[0].content.split("**")[1]
        agent_id = role.replace("_", "-") + "-agent-v1"
        user = request.messages[-1].content
        assert "## Task Brief" in user
        if degraded:
            assert f"Execute {role} analysis for the given requirement." in user
        else:
            for field in ("TASK", "FOCUS", "EVAL", "SCOPE"):
                assert f"{field}::{agent_id}" in user
                assert user.count(f"{field}::") == 1
            assert "synthetic-only" not in user
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["enriched"] is (not degraded)


def test_oversized_brief_is_rejected_before_first_agent_call(tmp_path, monkeypatch):
    provider = BriefProvider(size=6000)
    code, run = run_revision(tmp_path, monkeypatch, provider, input_tokens=1024)
    assert code == 3
    assert len(provider.requests) == 6
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == "TOKEN_BUDGET_EXCEEDED"
    assert manifest["stages_completed"] == 0

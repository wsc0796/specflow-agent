"""H04: observe real request assembly with a deterministic offline provider."""

import json
import re

import httpx
import pytest
from pydantic import ValidationError

from specflow.llm.providers.openai_compatible import OpenAICompatibleLLMClient
from specflow.runner_multi import _build_registry, _validated_inputs, run_multi_agent
from specflow.schema import build_schema_registry
from specflow.schema.models import DesignInput, ReviewInput, RiskReviewInput
from specflow.schema.models import TestStrategyInput as StrategyInput


@pytest.mark.parametrize("target_role", ["design", "test_strategy", "risk_review"])
@pytest.mark.parametrize("empty_findings", [False, True])
def test_review_feedback_reaches_only_revised_role(
    tmp_path, monkeypatch, target_role, empty_findings
):
    target_id = {
        "design": "design-agent-v1",
        "test_strategy": "test-strategy-agent-v1",
        "risk_review": "risk-review-agent-v1",
    }[target_role]
    requirement = "Analyze login protection without changing repository files."
    summary = "REVIEW_ONLY_SUMMARY: explain the locked-account decision."
    finding = "Boundary explanation. " * 50 + "REVIEW_ONLY_TAIL: preserve the active lock."
    findings = [] if empty_findings else [finding, "REVIEW_ONLY_SECOND: retain JWT fields."]
    requests = {}
    payloads = {
        "repository_analyst": {"summary": "Existing login checks and JWT generation."},
        "design": {"summary": "Design proposal.", "implementation_steps": ["Preserve login."]},
        "test_strategy": {"summary": "Tests.", "test_scenarios": ["Check active lock."]},
        "risk_review": {"summary": "Assess lock risks."},
        "synthesis": {"summary": "Combined plan.", "consolidated_design": "Preserve login."},
    }
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "login.py").write_text("def login(user):\n    return bool(user)\n", encoding="utf-8")
    for name, value in {
        "SPECFLOW_LLM_BASE_URL": "https://offline.invalid/v1",
        "SPECFLOW_LLM_API_KEY": "offline-fixture-only",
        "SPECFLOW_LLM_MODEL": "offline-feedback-model",
    }.items():
        monkeypatch.setenv(name, value)

    def handler(request):
        body = json.loads(request.content)
        text = "\n".join(message["content"] for message in body["messages"])
        if text.startswith("Generate a task brief"):
            content = {"task_description": "Analyze login."}
        else:
            role = re.search(r"You are the \*\*(\w+)\*\* agent", text).group(1)
            requests.setdefault(role, []).append(text)
            if role == "review":
                first = len(requests[role]) == 1
                content = {
                    "decision": "REJECT" if first else "PASS",
                    "summary": summary if first else "Offline fixture accepts revision.",
                    "findings": findings if first else [],
                    "target_agent_id": target_id if first else "",
                }
            else:
                content = payloads[role]
        return httpx.Response(
            200,
            json={
                "model": "offline-feedback-model",
                "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        )

    def factory(*args, config, **kwargs):
        return OpenAICompatibleLLMClient(config, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("specflow.runner_multi._create_real_llm_client", factory)
    output = tmp_path / "out"
    result = run_multi_agent(
        repo=repo,
        requirement=requirement,
        output=output,
        provider="openai-compatible",
        model="offline-feedback-model",
    )
    assert int(result) == 0
    assert len(requests[target_role]) == 2
    revised_message = requests[target_role][1]
    assert summary in revised_message
    for item in findings:
        assert item in revised_message
    assert "## Revision Feedback" in revised_message
    assert requirement in revised_message
    assert "Existing login checks and JWT generation." in revised_message
    for role, messages in requests.items():
        for index, message in enumerate(messages):
            if role == target_role and index == 1:
                continue
            assert "REVIEW_ONLY_" not in message
            assert "## Revision Feedback" not in message
    run_dir = next(output.iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["revision_count"] == 1
    assert manifest["revision_exhausted"] is False
    assert len(requests["review"]) == 2
    outputs = json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8"))
    assert f"stage-1/{target_id}" in outputs
    assert f"stage-4/{target_id}" in outputs


def _feedback():
    return {
        "target_agent_id": "design-agent-v1",
        "round_number": 1,
        "summary": "Revise lock behavior.",
        "findings": [],
    }


@pytest.mark.parametrize("model", [DesignInput, StrategyInput, RiskReviewInput])
def test_revisable_input_accepts_typed_optional_feedback(model):
    assert model.model_validate({"revision_feedback": _feedback()}).revision_feedback is not None
    assert model().revision_feedback is None


@pytest.mark.parametrize(
    "changes",
    [{"round_number": 0}, {"summary": " "}, {"findings": "not-a-list"}, {"extra": "not-allowed"}],
)
def test_revision_feedback_rejects_malformed_fields(changes):
    with pytest.raises(ValidationError):
        DesignInput.model_validate({"revision_feedback": {**_feedback(), **changes}})


def test_non_revisable_input_rejects_feedback():
    with pytest.raises(ValidationError):
        ReviewInput.model_validate({"revision_feedback": _feedback()})


def test_revision_projection_rejects_mismatched_review_target():
    registry = _build_registry()
    context = {
        "requirement": "Analyze login.",
        "revision_task": {
            "target_agent_id": "design-agent-v1",
            "round_number": 1,
        },
    }
    prior = {
        "review-agent-v1": {
            "output": {
                "decision": "REJECT",
                "summary": "Revise tests.",
                "findings": [],
                "target_agent_id": "test-strategy-agent-v1",
            }
        }
    }
    with pytest.raises(ValueError, match="REVISION_FEEDBACK_TARGET_MISMATCH"):
        _validated_inputs(("design-agent-v1",), registry, build_schema_registry(), context, prior)

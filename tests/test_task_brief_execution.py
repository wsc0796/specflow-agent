"""Execution-contract tests proving task briefs reach real LLM requests."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

import pytest
from pydantic import ValidationError
from task_brief_test_helpers import (
    controlled_evidence,
    evidence_reference,
    execution_input,
    task_brief,
)

from specflow.agents.adapter import AgentRunner
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.plan.models import (
    EnrichmentStatus,
    SemanticTaskBrief,
    TaskBriefArtifact,
    TaskBriefDraft,
)
from specflow.schema.agent_payloads import DesignPayload
from specflow.schema.models import AgentExecutionInput
from specflow.schema.registry import SchemaRegistry
from specflow.trace.models import TaskBriefTraceEvent

SECTION_NAMES = (
    "Original Requirement",
    "Verified Repository Evidence",
    "Role Task Brief",
    "Validated Prior Stage Outputs",
    "Role-specific Output Contract",
)


class CapturingClient:
    def __init__(self, *, before_return=None) -> None:
        self.requests = []
        self._before_return = before_return

    def complete(self, request):
        self.requests.append(request)
        if self._before_return is not None:
            self._before_return()

        class Response:
            content = json.dumps({"summary": "valid"})
            input_tokens = 10
            output_tokens = 5

        return Response()


def _identity(
    agent_id: str = "test-agent-v1",
    role: AgentRole = AgentRole.DESIGN,
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        role=role,
        version="1.0.0",
        description="Fixed role description",
        prompt_id="prompts/test/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/test/v1/input",
        output_schema_id="agent/test/v1/output",
        tool_permissions=frozenset({"read_file"}),
    )


def _registry() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register("agent/test/v1/output", DesignPayload)
    registry.freeze()
    return registry


def _run_request(identity: AgentIdentity, execution: AgentExecutionInput) -> str:
    client = CapturingClient()
    result = AgentRunner(
        identity,
        client,
        model="test-model",
        schema_registry=_registry(),
    ).execute({"validated_input": execution})
    assert result["success"] is True
    return client.requests[-1].messages[-1].content


def _sections(message: str) -> dict[str, str]:
    positions = [(name, message.index(f"[{name}]")) for name in SECTION_NAMES]
    result: dict[str, str] = {}
    for index, (name, start) in enumerate(positions):
        content_start = start + len(name) + 2
        end = positions[index + 1][1] if index + 1 < len(positions) else len(message)
        result[name] = message[content_start:end].strip()
    return result


def test_task_brief_change_changes_only_target_real_llm_request_section() -> None:
    evidence = controlled_evidence(content="Evidence remains byte-identical")
    prior = {"repository-analyst-agent-v1": {"summary": "same validated output"}}
    design_identity = _identity("design-agent-v1", AgentRole.DESIGN)
    design_a = task_brief(
        agent_id=design_identity.agent_id,
        role=design_identity.role,
        task_description="Focus on API boundaries",
    )
    design_b = task_brief(
        agent_id=design_identity.agent_id,
        role=design_identity.role,
        task_description="Focus on persistence boundaries",
    )

    request_a = _run_request(
        design_identity,
        execution_input(brief=design_a, evidence=evidence, prior_outputs=prior),
    )
    request_b = _run_request(
        design_identity,
        execution_input(brief=design_b, evidence=evidence, prior_outputs=prior),
    )
    sections_a = _sections(request_a)
    sections_b = _sections(request_b)

    assert request_a != request_b
    assert sections_a["Role Task Brief"] != sections_b["Role Task Brief"]
    for name in set(SECTION_NAMES) - {"Role Task Brief"}:
        assert sections_a[name] == sections_b[name]

    other_identity = _identity("risk-agent-v1", AgentRole.RISK_REVIEW)
    other_brief = task_brief(
        agent_id=other_identity.agent_id,
        role=other_identity.role,
    )
    other_input = execution_input(brief=other_brief, evidence=evidence, prior_outputs=prior)
    assert _run_request(other_identity, other_input) == _run_request(other_identity, other_input)


def test_brief_text_is_not_promoted_to_verified_evidence() -> None:
    identity = _identity()
    brief = task_brief(task_description="UNVERIFIED_BRIEF_CLAIM")
    message = _run_request(identity, execution_input(brief=brief))
    sections = _sections(message)
    assert "UNVERIFIED_BRIEF_CLAIM" in sections["Role Task Brief"]
    assert "UNVERIFIED_BRIEF_CLAIM" not in sections["Verified Repository Evidence"]


@pytest.mark.parametrize("field", ["agent_id", "role", "output_schema_id"])
def test_execution_identity_mismatch_fails_closed(field: str) -> None:
    values = execution_input().model_dump()
    if field == "agent_id":
        values[field] = "another-agent"
    elif field == "role":
        values[field] = AgentRole.REVIEW
    else:
        values[field] = "agent/another/v1/output"
    with pytest.raises(ValidationError, match="does not match"):
        AgentExecutionInput.model_validate(values)


def test_runner_rejects_input_for_another_valid_agent_without_provider_call() -> None:
    client = CapturingClient()
    runner = AgentRunner(_identity(), client, model="test", schema_registry=_registry())
    other_brief = task_brief(agent_id="other-agent-v1")
    result = runner.execute({"validated_input": execution_input(brief=other_brief)})
    assert result["output"]["error_code"] == "AGENT_INPUT_IDENTITY_MISMATCH"
    assert client.requests == []


def test_missing_execution_brief_fails_closed_without_consumed_event() -> None:
    events: list[TaskBriefTraceEvent] = []
    client = CapturingClient()
    result = AgentRunner(
        _identity(),
        client,
        model="test",
        schema_registry=_registry(),
        task_brief_event_sink=events.append,
    ).execute({"validated_input": None})
    assert result["output"]["error_code"] == "AGENT_INPUT_VALIDATION_FAILED"
    assert client.requests == []
    assert events == []


def test_execution_input_without_task_brief_is_rejected_before_runner() -> None:
    values = execution_input().model_dump()
    values.pop("task_brief")
    with pytest.raises(ValidationError, match="task_brief"):
        AgentExecutionInput.model_validate(values)


def test_consumed_event_exists_when_provider_receives_request() -> None:
    events: list[TaskBriefTraceEvent] = []

    def assert_event_recorded_before_provider_returns() -> None:
        assert len(events) == 1

    client = CapturingClient(before_return=assert_event_recorded_before_provider_returns)
    execution = execution_input()
    result = AgentRunner(
        _identity(),
        client,
        model="test",
        schema_registry=_registry(),
        task_brief_event_sink=events.append,
    ).execute({"validated_input": execution})
    assert result["success"] is True
    assert [event.event_type for event in events] == ["TASK_BRIEF_CONSUMED"]
    assert events[0].brief_hash == execution.task_brief.brief_hash()
    assert "Add a search API" not in json.dumps(events[0].as_dict())


def test_degraded_brief_remains_visible_in_real_request() -> None:
    brief = task_brief(status=EnrichmentStatus.DEGRADED)
    message = _run_request(_identity(), execution_input(brief=brief))
    assert '"status": "degraded"' in _sections(message)["Role Task Brief"]


def test_schema_rejects_extra_fields_empty_briefs_and_tool_permission_override() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TaskBriefDraft.model_validate(
            {"task_description": "valid", "tool_permissions": ["write_file"]}
        )
    values = task_brief().model_dump()
    values["task_description"] = ""
    with pytest.raises(ValidationError, match="at least 1 character"):
        SemanticTaskBrief.model_validate(values)
    values = task_brief().model_dump()
    values["requirement"] = "brief tries to replace requirement"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SemanticTaskBrief.model_validate(values)


def test_unknown_evidence_reference_is_rejected_at_execution_boundary() -> None:
    unknown = evidence_reference("evidence-unknown")
    brief = task_brief(evidence_refs=(unknown,))
    with pytest.raises(ValidationError, match="unknown evidence references"):
        execution_input(brief=brief, evidence=controlled_evidence())


def test_task_brief_artifact_hash_is_reproducible_and_self_verifying() -> None:
    artifact = TaskBriefArtifact.build("run-test", (task_brief(),))
    reloaded = TaskBriefArtifact.model_validate(artifact.model_dump(mode="json"))
    expected = sha256(canonical_json_bytes(reloaded.hash_payload())).hexdigest()
    assert reloaded.canonical_hash == expected
    assert reloaded.brief_hashes["test-agent-v1"] == reloaded.briefs[0].brief_hash()


def test_task_brief_artifact_rejects_tampered_status_indexes_with_recomputed_hash() -> None:
    artifact = TaskBriefArtifact.build("run-test", (task_brief(),))
    values = artifact.model_dump(mode="json")
    values["enriched_agents"] = []
    values["degraded_agents"] = ["test-agent-v1"]
    hash_payload = dict(values)
    hash_payload.pop("canonical_hash")
    values["canonical_hash"] = sha256(canonical_json_bytes(hash_payload)).hexdigest()
    with pytest.raises(ValidationError, match="status indexes are inconsistent"):
        TaskBriefArtifact.model_validate(values)


def test_trace_event_rejects_unapproved_fields() -> None:
    data: dict[str, Any] = {
        "event_type": "TASK_BRIEF_CONSUMED",
        "run_id": "run-test",
        "agent_id": "test-agent-v1",
        "role": AgentRole.DESIGN,
        "brief_hash": "a" * 64,
        "schema_version": "task_brief/v1",
        "status": EnrichmentStatus.ENRICHED,
        "stage": 1,
        "trace_id": "trace-consumed",
        "prompt": "secret prompt",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TaskBriefTraceEvent.model_validate(data)

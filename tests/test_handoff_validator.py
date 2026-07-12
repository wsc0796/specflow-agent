"""Tests for HandoffValidator — runtime schema compatibility checks."""

from __future__ import annotations

import json
from hashlib import sha256

import pytest

from specflow.agents.models import AgentIdentity, AgentRole
from specflow.handoff.exceptions import HandoffValidationError
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator


def _make_identity(
    agent_id: str,
    role: AgentRole = AgentRole.DESIGN,
    *,
    input_schema_id: str | None = None,
    output_schema_id: str | None = None,
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        role=role,
        version="1.0.0",
        description=f"Test {role.value} agent",
        prompt_id="test/v1",
        prompt_version="1.0.0",
        input_schema_id=input_schema_id or f"{agent_id}/input",
        output_schema_id=output_schema_id or f"{agent_id}/output",
    )


def _make_handoff(
    *,
    source_output_schema_id: str = "sender/output",
    target_input_schema_id: str = "receiver/input",
) -> AgentHandoff:
    return AgentHandoff(
        handoff_id="h1",
        from_agent_id="sender",
        to_agent_id="receiver",
        source_output_schema_id=source_output_schema_id,
        target_input_schema_id=target_input_schema_id,
        payload_ref="ref://payload",
        input_hash="in-hash",
    )


class TestHandoffValidator:
    def test_matching_schemas_pass(self) -> None:
        """Sender output matches handoff source, receiver input matches handoff target."""
        sender = _make_identity(
            "sender",
            AgentRole.REPOSITORY_ANALYST,
            output_schema_id="sender/output",
        )
        receiver = _make_identity(
            "receiver",
            AgentRole.DESIGN,
            input_schema_id="receiver/input",
        )
        handoff = _make_handoff(
            source_output_schema_id="sender/output",
            target_input_schema_id="receiver/input",
        )
        HandoffValidator().validate(handoff, sender, receiver)  # should not raise

    def test_mismatched_source_output_schema_raises(self) -> None:
        """Handoff source_output_schema_id != sender.output_schema_id."""
        sender = _make_identity(
            "sender",
            AgentRole.REPOSITORY_ANALYST,
            output_schema_id="sender/output",
        )
        receiver = _make_identity(
            "receiver",
            AgentRole.DESIGN,
            input_schema_id="receiver/input",
        )
        handoff = _make_handoff(
            source_output_schema_id="WRONG/output",
            target_input_schema_id="receiver/input",
        )
        with pytest.raises(HandoffValidationError, match="source_output_schema_id"):
            HandoffValidator().validate(handoff, sender, receiver)

    def test_mismatched_target_input_schema_raises(self) -> None:
        """Handoff target_input_schema_id != receiver.input_schema_id."""
        sender = _make_identity(
            "sender",
            AgentRole.REPOSITORY_ANALYST,
            output_schema_id="sender/output",
        )
        receiver = _make_identity(
            "receiver",
            AgentRole.DESIGN,
            input_schema_id="receiver/input",
        )
        handoff = _make_handoff(
            source_output_schema_id="sender/output",
            target_input_schema_id="WRONG/input",
        )
        with pytest.raises(HandoffValidationError, match="target_input_schema_id"):
            HandoffValidator().validate(handoff, sender, receiver)

    def test_payload_must_exist_match_sender_and_hash(self) -> None:
        sender = _make_identity(
            "sender", AgentRole.REPOSITORY_ANALYST, output_schema_id="sender/output"
        )
        payload = {"agent_id": "sender", "role": "repository_analyst", "output": {"x": 1}}
        output_hash = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        handoff = AgentHandoff(
            **{
                **_make_handoff(source_output_schema_id="sender/output").__dict__,
                "payload_ref": "agent-outputs.json#stage-0/sender",
                "output_hash": output_hash,
            }
        )
        HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})

        with pytest.raises(HandoffValidationError, match="output_hash"):
            HandoffValidator().validate_payload(
                AgentHandoff(**{**handoff.__dict__, "output_hash": "wrong"}),
                sender,
                {"stage-0/sender": payload},
            )

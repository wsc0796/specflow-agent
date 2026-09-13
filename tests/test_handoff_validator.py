"""Tests for HandoffValidator — runtime schema compatibility checks."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from specflow.agents.models import AgentIdentity, AgentRole
from specflow.handoff.exceptions import HandoffIntegrityError, HandoffValidationError
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator
from specflow.plan.hash_utils import canonical_json_bytes


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
        output_hash = sha256(canonical_json_bytes(payload)).hexdigest()
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

    def test_payload_mutated_after_hash_raises_integrity_error(self) -> None:
        """A post-hash payload change must fail with a classified handoff error."""
        sender = _make_identity(
            "sender", AgentRole.REPOSITORY_ANALYST, output_schema_id="sender/output"
        )
        payload = {
            "agent_id": "sender",
            "role": "repository_analyst",
            "output": {"summary": "Original"},
        }
        handoff = AgentHandoff(
            **{
                **_make_handoff(source_output_schema_id="sender/output").__dict__,
                "payload_ref": "agent-outputs.json#stage-0/sender",
                "output_hash": sha256(canonical_json_bytes(payload)).hexdigest(),
            }
        )

        payload["output"]["summary"] = "Tampered"

        with pytest.raises(HandoffValidationError, match="output_hash") as exc_info:
            HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})

        assert type(exc_info.value).__name__ == "HandoffIntegrityError"
        assert exc_info.value.audit_context == {
            "handoff_id": "h1",
            "from_agent_id": "sender",
            "to_agent_id": "receiver",
            "payload_ref": "agent-outputs.json#stage-0/sender",
        }


def _payload_case():
    sender = _make_identity("sender", AgentRole.REPOSITORY_ANALYST)
    payload = {
        "agent_id": "sender",
        "role": "repository_analyst",
        "output": {"summary": "Original"},
    }
    handoff = AgentHandoff(
        **{
            **_make_handoff().__dict__,
            "payload_ref": "agent-outputs.json#stage-0/sender",
            "output_hash": sha256(canonical_json_bytes(payload)).hexdigest(),
        }
    )
    return sender, payload, handoff


@pytest.mark.parametrize("field", ["summary", "agent_id", "role", "output", "container", "null"])
def test_hash_changes_take_precedence_over_envelope_validation(field):
    sender, payload, handoff = _payload_case()
    if field == "summary":
        payload["output"]["summary"] = "test-tampered"
    elif field == "agent_id":
        payload["agent_id"] = "test-tampered"
    elif field == "role":
        payload["role"] = {"untrusted": "test-tampered"}
    elif field == "output":
        payload["output"] = "test-tampered"
    elif field == "container":
        payload = ["test-tampered"]
    else:
        payload = None
    assert sha256(canonical_json_bytes(payload)).hexdigest() != handoff.output_hash
    with pytest.raises(HandoffIntegrityError) as failure:
        HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})
    assert failure.value.audit_context["handoff_id"] == handoff.handoff_id
    assert "test-tampered" not in str(failure.value)


@pytest.mark.parametrize("field", ["agent_id", "role", "output", "container", "null"])
def test_matching_hash_does_not_reclassify_invalid_envelopes_as_integrity_failure(field):
    sender, payload, handoff = _payload_case()
    if field == "agent_id":
        payload["agent_id"] = "wrong-sender"
    elif field == "role":
        payload["role"] = {"not": "a string"}
    elif field == "output":
        payload["output"] = "not a dict"
    elif field == "container":
        payload = ["not", "an", "envelope"]
    else:
        payload = None
    handoff = AgentHandoff(
        **{**handoff.__dict__, "output_hash": sha256(canonical_json_bytes(payload)).hexdigest()}
    )
    with pytest.raises(HandoffValidationError) as failure:
        HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})
    assert type(failure.value) is HandoffValidationError


@pytest.mark.parametrize("kind", ["set", "cycle", "mixed-keys"])
def test_unverifiable_payload_is_safe_without_claiming_hash_mismatch(kind):
    sender, payload, handoff = _payload_case()
    if kind == "set":
        payload["role"] = {"test-untrusted"}
    elif kind == "cycle":
        payload["output"]["cycle"] = payload
    else:
        payload["output"] = {1: "test-untrusted", "summary": "test-untrusted"}
    with pytest.raises(HandoffValidationError) as failure:
        HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})
    assert not isinstance(failure.value, HandoffIntegrityError)
    assert type(failure.value).__name__ == "HandoffPayloadError"
    assert "test-untrusted" not in str(failure.value)
    assert failure.value.audit_context["payload_ref"] == handoff.payload_ref


def test_missing_payload_reference_retains_ordinary_validation_error():
    sender, payload, handoff = _payload_case()
    with pytest.raises(HandoffValidationError) as failure:
        HandoffValidator().validate_payload(handoff, sender, {})
    assert type(failure.value) is HandoffValidationError
    unchanged = deepcopy(payload)
    HandoffValidator().validate_payload(handoff, sender, {"stage-0/sender": payload})
    assert payload == unchanged

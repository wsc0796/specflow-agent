"""Runtime handoff validator — checks schema compatibility.

Unlike :class:`specflow.plan.validator.PlanValidator` which performs
static structural checks, this validator has access to **runtime**
information (actual :class:`AgentIdentity` instances) and verifies
that the schema IDs recorded in a handoff match the identities of the
sender and receiver agents.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from specflow.agents.models import AgentIdentity
from specflow.handoff.exceptions import HandoffValidationError
from specflow.handoff.models import AgentHandoff
from specflow.plan.hash_utils import canonical_json_bytes


class HandoffValidator:
    """Validates that a handoff's schema IDs match sender/receiver identities."""

    def validate(
        self,
        handoff: AgentHandoff,
        sender: AgentIdentity,
        receiver: AgentIdentity,
    ) -> None:
        """Check *handoff* schema compatibility.

        Parameters
        ----------
        handoff:
            The handoff record to validate.
        sender:
            The sending agent's identity (must match ``handoff.from_agent_id``).
        receiver:
            The receiving agent's identity (must match ``handoff.to_agent_id``).

        Raises
        ------
        HandoffValidationError
            If ``source_output_schema_id`` does not match the sender's
            ``output_schema_id``, or ``target_input_schema_id`` does not
            match the receiver's ``input_schema_id``.
        """
        if handoff.source_output_schema_id != sender.output_schema_id:
            raise HandoffValidationError(
                f"Handoff source_output_schema_id={handoff.source_output_schema_id!r} "
                f"does not match sender output_schema_id={sender.output_schema_id!r}"
            )
        if handoff.target_input_schema_id != receiver.input_schema_id:
            raise HandoffValidationError(
                f"Handoff target_input_schema_id={handoff.target_input_schema_id!r} "
                f"does not match receiver input_schema_id={receiver.input_schema_id!r}"
            )

    def validate_payload(
        self,
        handoff: AgentHandoff,
        sender: AgentIdentity,
        payloads: Mapping[str, Mapping[str, object]],
    ) -> None:
        """Validate the concrete, immutable payload referenced by a handoff.

        The runner calls this before a receiver executes.  ``payload_ref`` is
        deliberately an artifact-relative reference, so it cannot name an
        arbitrary local file.
        """
        prefix = "agent-outputs.json#"
        if not handoff.payload_ref.startswith(prefix):
            raise HandoffValidationError("Handoff payload_ref must reference agent-outputs.json")
        payload_key = handoff.payload_ref.removeprefix(prefix)
        payload = payloads.get(payload_key)
        if payload is None:
            raise HandoffValidationError(f"Handoff payload is missing: {payload_key}")
        if payload.get("agent_id") != sender.agent_id:
            raise HandoffValidationError("Handoff payload agent_id does not match sender")
        if not isinstance(payload.get("role"), str) or not isinstance(payload.get("output"), dict):
            raise HandoffValidationError("Handoff payload does not match the agent output envelope")
        expected_hash = sha256(canonical_json_bytes(dict(payload))).hexdigest()
        if handoff.output_hash != expected_hash:
            raise HandoffValidationError("Handoff output_hash does not match payload")

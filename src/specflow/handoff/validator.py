"""Runtime handoff validator — checks schema compatibility.

Unlike :class:`specflow.plan.validator.PlanValidator` which performs
static structural checks, this validator has access to **runtime**
information (actual :class:`AgentIdentity` instances) and verifies
that the schema IDs recorded in a handoff match the identities of the
sender and receiver agents.
"""

from __future__ import annotations

from specflow.agents.models import AgentIdentity
from specflow.handoff.exceptions import HandoffValidationError
from specflow.handoff.models import AgentHandoff


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

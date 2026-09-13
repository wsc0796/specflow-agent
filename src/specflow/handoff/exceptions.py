"""Handoff-specific exceptions."""


class HandoffError(Exception):
    """Base exception for handoff-related errors."""


class HandoffValidationError(HandoffError):
    """A handoff failed runtime validation."""


class HandoffPayloadError(HandoffValidationError):
    """A referenced payload cannot be trusted; its contents must be quarantined.

    Canonicalization failure does not establish a hash mismatch. The dedicated
    integrity subclass below is reserved for an actual comparison mismatch.
    """

    def __init__(
        self,
        message: str,
        *,
        handoff_id: str,
        from_agent_id: str,
        to_agent_id: str,
        payload_ref: str,
    ) -> None:
        super().__init__(message)
        self._audit_context = {
            "handoff_id": handoff_id,
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "payload_ref": payload_ref,
        }

    @property
    def audit_context(self) -> dict[str, str]:
        """Return bounded identifiers safe for failure artifacts and traces."""
        return dict(self._audit_context)


class HandoffIntegrityError(HandoffPayloadError):
    """A referenced handoff payload no longer matches its recorded hash."""

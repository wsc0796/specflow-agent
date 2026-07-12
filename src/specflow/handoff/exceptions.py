"""Handoff-specific exceptions."""


class HandoffError(Exception):
    """Base exception for handoff-related errors."""


class HandoffValidationError(HandoffError):
    """A handoff failed runtime validation."""

"""Immutable data models for inter-agent handoffs and messages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentHandoff:
    """Records a data handoff between two agents.

    Binds the source agent's output schema to the target agent's input
    schema so that runtime validation can verify schema compatibility
    before passing data.
    """

    handoff_id: str
    from_agent_id: str
    to_agent_id: str
    source_output_schema_id: str
    target_input_schema_id: str
    payload_ref: str
    input_hash: str
    output_hash: str | None = None


@dataclass(frozen=True)
class AgentMessage:
    """A concrete message exchanged between two agents.

    References the :class:`AgentHandoff` it belongs to and carries
    content metadata plus a payload reference.
    """

    message_id: str
    handoff_id: str
    sender_agent_id: str
    receiver_agent_id: str
    content_type: str
    payload_ref: str
    created_at: str

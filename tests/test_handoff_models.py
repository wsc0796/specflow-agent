"""Tests for AgentHandoff and AgentMessage models."""

from __future__ import annotations

import pytest

from specflow.handoff.models import AgentHandoff, AgentMessage


class TestAgentHandoff:
    def test_create_minimal(self) -> None:
        handoff = AgentHandoff(
            handoff_id="h1",
            from_agent_id="sender-agent",
            to_agent_id="receiver-agent",
            source_output_schema_id="schema/output/v1",
            target_input_schema_id="schema/input/v1",
            payload_ref="ref://payload-1",
            input_hash="abc123",
        )
        assert handoff.handoff_id == "h1"
        assert handoff.from_agent_id == "sender-agent"
        assert handoff.to_agent_id == "receiver-agent"
        assert handoff.source_output_schema_id == "schema/output/v1"
        assert handoff.target_input_schema_id == "schema/input/v1"
        assert handoff.payload_ref == "ref://payload-1"
        assert handoff.input_hash == "abc123"
        assert handoff.output_hash is None

    def test_create_with_output_hash(self) -> None:
        handoff = AgentHandoff(
            handoff_id="h2",
            from_agent_id="sender",
            to_agent_id="receiver",
            source_output_schema_id="s/src",
            target_input_schema_id="s/dst",
            payload_ref="ref://p2",
            input_hash="in-hash",
            output_hash="out-hash",
        )
        assert handoff.output_hash == "out-hash"

    def test_frozen_dataclass(self) -> None:
        handoff = AgentHandoff(
            handoff_id="h3",
            from_agent_id="sender",
            to_agent_id="receiver",
            source_output_schema_id="s/src",
            target_input_schema_id="s/dst",
            payload_ref="ref://p3",
            input_hash="h3-in",
        )
        with pytest.raises(AttributeError):
            handoff.handoff_id = "new-id"  # type: ignore[misc]


class TestAgentMessage:
    def test_create(self) -> None:
        msg = AgentMessage(
            message_id="m1",
            handoff_id="h1",
            sender_agent_id="sender-agent",
            receiver_agent_id="receiver-agent",
            content_type="application/json",
            payload_ref="ref://msg-1",
            created_at="2026-07-12T10:00:00Z",
        )
        assert msg.message_id == "m1"
        assert msg.handoff_id == "h1"
        assert msg.sender_agent_id == "sender-agent"
        assert msg.receiver_agent_id == "receiver-agent"
        assert msg.content_type == "application/json"
        assert msg.payload_ref == "ref://msg-1"
        assert msg.created_at == "2026-07-12T10:00:00Z"

    def test_frozen_dataclass(self) -> None:
        msg = AgentMessage(
            message_id="m2",
            handoff_id="h1",
            sender_agent_id="sender",
            receiver_agent_id="receiver",
            content_type="text/plain",
            payload_ref="ref://m2",
            created_at="now",
        )
        with pytest.raises(AttributeError):
            msg.message_id = "new-id"  # type: ignore[misc]

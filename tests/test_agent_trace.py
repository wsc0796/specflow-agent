"""Tests for AgentTraceSpan model."""

from specflow.trace.models import AgentTraceSpan


class TestAgentTraceSpan:
    def test_create_minimal_span(self):
        span = AgentTraceSpan(
            span_id="s1",
            agent_id="a1",
            agent_role="design",
            agent_version="1.0.0",
            parent_span_id="coord",
        )
        assert span.span_id == "s1"
        assert span.stage == 0

    def test_create_full_span(self):
        span = AgentTraceSpan(
            span_id="span-001",
            agent_id="design-agent-v1",
            agent_role="design",
            agent_version="1.0.0",
            parent_span_id="coordinator-span",
            stage=1,
            stage_started_at="2026-07-12T00:00:00Z",
            agent_submitted_at="2026-07-12T00:00:01Z",
            agent_completed_at="2026-07-12T00:00:05Z",
            stage_completed_at="2026-07-12T00:00:06Z",
            model="test",
            latency_ms=5000,
            input_tokens=500,
            output_tokens=300,
            status="success",
            tool_calls=("c1", "c2"),
            revision_round=0,
        )
        assert span.latency_ms == 5000

    def test_as_dict(self):
        span = AgentTraceSpan(
            span_id="s1",
            agent_id="a1",
            agent_role="design",
            agent_version="1.0.0",
            parent_span_id="p1",
            stage=1,
            model="m",
            latency_ms=100,
        )
        d = span.as_dict()
        assert d["span_id"] == "s1"
        assert d["agent_role"] == "design"
        assert d["tool_calls"] == []

    def test_parallel_agents_share_parent(self):
        design = AgentTraceSpan(
            span_id="d1",
            agent_id="design-agent-v1",
            agent_role="design",
            agent_version="1.0.0",
            parent_span_id="coord",
            stage=1,
        )
        test = AgentTraceSpan(
            span_id="t1",
            agent_id="test-agent-v1",
            agent_role="test_strategy",
            agent_version="1.0.0",
            parent_span_id="coord",
            stage=1,
        )
        assert design.parent_span_id == test.parent_span_id
        assert design.stage == test.stage

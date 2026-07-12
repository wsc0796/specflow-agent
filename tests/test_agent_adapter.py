"""Tests for AgentRunner — bridges Agent identity to LLM execution."""

import json

from specflow.agents.adapter import AgentRunner
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.schema import build_schema_registry


def _make_identity(role: AgentRole = AgentRole.DESIGN) -> AgentIdentity:
    return AgentIdentity(
        agent_id="test-agent-v1",
        role=role,
        version="1.0.0",
        description="Test agent",
        prompt_id="prompts/test/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/test/v1/input",
        output_schema_id="agent/test/v1/output",
        tool_permissions=frozenset(),
    )


class FakeLLMClient:
    def __init__(self, content: str = "") -> None:
        self.content = content or json.dumps({"summary": "A valid design response."})
        self.last_request = None

    def complete(self, request):
        self.last_request = request

        class Response:
            content = self.content
            input_tokens = 100
            output_tokens = 50

        return Response()


class TestAgentRunner:
    def test_runner_passes_agent_id(self):
        ident = _make_identity()
        runner = AgentRunner(
            ident, FakeLLMClient(), model="test", schema_registry=build_schema_registry()
        )
        result = runner.execute({"requirement": "Add feature X"})
        assert result["agent_id"] == "test-agent-v1"
        assert result["success"] is True
        assert result["output"]["summary"] == "A valid design response."

    def test_runner_includes_role_in_user_message(self):
        ident = _make_identity(AgentRole.RISK_REVIEW)
        client = FakeLLMClient()
        runner = AgentRunner(
            ident, client, model="test", schema_registry=build_schema_registry()
        )
        runner.execute({"requirement": "Test"})
        user_msg = client.last_request.messages[-1].content.lower()
        assert "risk_review" in user_msg

    def test_runner_includes_requirement(self):
        ident = _make_identity()
        client = FakeLLMClient()
        runner = AgentRunner(
            ident, client, model="test", schema_registry=build_schema_registry()
        )
        runner.execute({"requirement": "Build a search API"})
        msgs = client.last_request.messages
        user_msg = msgs[-1].content  # last message is always the user message
        assert "Build a search API" in user_msg

    def test_runner_includes_prior_outputs(self):
        ident = _make_identity()
        client = FakeLLMClient()
        runner = AgentRunner(
            ident, client, model="test", schema_registry=build_schema_registry()
        )
        runner.execute({
            "requirement": "Test",
            "prior_outputs": {"repo-analyst-agent-v1": {"output": {"files": ["a.py"]}}},
        })
        user_msg = client.last_request.messages[-1].content
        assert "repo-analyst-agent-v1" in user_msg

    def test_runner_degraded_on_llm_failure(self):
        ident = _make_identity()

        class FailingClient:
            def complete(self, request):
                raise RuntimeError("API down")

        runner = AgentRunner(
            ident, FailingClient(), model="test", schema_registry=build_schema_registry()
        )
        result = runner.execute({"requirement": "Test"})
        assert result["success"] is False
        assert result["degraded"] is True
        assert "output" in result  # must carry output for downstream compat
        assert result["output"]["degraded"] is True
        assert result["output"]["error_code"] == "INTERNAL_UNEXPECTED"
        assert "API down" not in str(result)

    def test_runner_uses_json_response_format(self):
        ident = _make_identity()
        client = FakeLLMClient()
        runner = AgentRunner(
            ident, client, model="test", schema_registry=build_schema_registry()
        )
        runner.execute({"requirement": "Test"})
        assert client.last_request.response_format == "json"

    def test_runner_fails_closed_without_schema_registry(self):
        result = AgentRunner(_make_identity(), FakeLLMClient(), model="test").execute({})
        assert result["success"] is False
        assert result["output"]["error_code"] == "SCHEMA_REGISTRY_UNAVAILABLE"

    def test_security_error_is_not_retried(self):
        calls = 0

        class SecurityFailingClient:
            def complete(self, request):
                nonlocal calls
                calls += 1
                raise RuntimeError("security path traversal")

        result = AgentRunner(
            _make_identity(),
            SecurityFailingClient(),
            model="test",
            schema_registry=build_schema_registry(),
            max_retries=2,
        ).execute({})
        assert calls == 1
        assert result["output"]["error_code"] == "SECURITY_PATH_TRAVERSAL"

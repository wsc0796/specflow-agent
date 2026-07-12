import pytest

from specflow.agents.exceptions import AgentModelValidationError
from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)


class TestAgentRole:
    def test_all_roles_defined(self):
        assert AgentRole.REPOSITORY_ANALYST == "repository_analyst"
        assert AgentRole.DESIGN == "design"
        assert AgentRole.TEST_STRATEGY == "test_strategy"
        assert AgentRole.RISK_REVIEW == "risk_review"
        assert AgentRole.SYNTHESIS == "synthesis"
        assert AgentRole.REVIEW == "review"


class TestAgentIdentity:
    def test_valid_identity(self):
        ident = AgentIdentity(
            agent_id="design-agent-v1",
            role=AgentRole.DESIGN,
            version="1.0.0",
            description="Designs technical solutions",
            prompt_id="prompts/design/v1",
            prompt_version="1.0.0",
            input_schema_id="agent/design/v1/input",
            output_schema_id="agent/design/v1/output",
            tool_permissions=frozenset({"list_files", "read_file"}),
        )
        assert ident.agent_id == "design-agent-v1"
        assert ident.role == AgentRole.DESIGN

    def test_empty_agent_id_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentIdentity(
                agent_id="",
                role=AgentRole.DESIGN,
                version="1.0.0",
                description="test",
                prompt_id="p/v1",
                prompt_version="1.0.0",
                input_schema_id="a/d/v1/input",
                output_schema_id="a/d/v1/output",
                tool_permissions=frozenset(),
            )

    def test_empty_version_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentIdentity(
                agent_id="agent-v1",
                role=AgentRole.DESIGN,
                version="",
                description="test",
                prompt_id="p/v1",
                prompt_version="1.0.0",
                input_schema_id="a/d/v1/input",
                output_schema_id="a/d/v1/output",
                tool_permissions=frozenset(),
            )


class TestAgentDependency:
    def test_valid_dependency(self):
        dep = AgentDependency(
            agent_id="design-agent-v1",
            depends_on=frozenset({"repo-analyst-v1"}),
        )
        assert dep.agent_id == "design-agent-v1"
        assert "repo-analyst-v1" in dep.depends_on

    def test_self_dependency_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentDependency(
                agent_id="design-agent-v1",
                depends_on=frozenset({"design-agent-v1"}),
            )


class TestAgentConstraints:
    def test_valid_constraints(self):
        c = AgentConstraints(
            agent_id="design-agent-v1",
            max_execution_seconds=60,
            max_token_budget=4096,
            max_revision_rounds=1,
            allowed_paths=(),
            denied_paths=(),
        )
        assert c.max_execution_seconds == 60

    def test_negative_timeout_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentConstraints(
                agent_id="design-agent-v1",
                max_execution_seconds=-1,
                max_token_budget=4096,
                max_revision_rounds=1,
                allowed_paths=(),
                denied_paths=(),
            )

    def test_empty_allowed_path_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentConstraints(
                agent_id="design-agent-v1",
                max_execution_seconds=60,
                max_token_budget=4096,
                allowed_paths=("",),
            )

    def test_empty_denied_path_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentConstraints(
                agent_id="design-agent-v1",
                max_execution_seconds=60,
                max_token_budget=4096,
                denied_paths=("/safe", ""),
            )


class TestRevisionPolicy:
    def test_defaults(self):
        policy = RevisionPolicy()
        assert policy.max_total_rounds == 1
        assert AgentRole.DESIGN in policy.revisable_roles
        assert AgentRole.TEST_STRATEGY in policy.revisable_roles
        assert AgentRole.RISK_REVIEW in policy.revisable_roles
        assert policy.final_authority_role == AgentRole.REVIEW

    def test_is_role_revisable(self):
        policy = RevisionPolicy()
        assert policy.is_revisable(AgentRole.DESIGN) is True
        assert policy.is_revisable(AgentRole.SYNTHESIS) is False
        assert policy.is_revisable(AgentRole.REVIEW) is False

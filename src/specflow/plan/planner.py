from __future__ import annotations

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.models import StructuralDelegationSpec

FIXED_TOPOLOGY_AGENTS: tuple[AgentIdentity, ...] = (
    AgentIdentity(
        agent_id="repository-analyst-agent-v1",
        role=AgentRole.REPOSITORY_ANALYST,
        version="1.0.0",
        description="Analyzes repository structure and maps requirements to code evidence",
        prompt_id="prompts/repository-analyst/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/repository-analyst/v1/input",
        output_schema_id="agent/repository-analyst/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="design-agent-v1",
        role=AgentRole.DESIGN,
        version="1.0.0",
        description="Generates architecture, interface, data, and implementation plans",
        prompt_id="prompts/design/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/design/v1/input",
        output_schema_id="agent/design/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="test-strategy-agent-v1",
        role=AgentRole.TEST_STRATEGY,
        version="1.0.0",
        description="Independently generates comprehensive test strategies",
        prompt_id="prompts/test-strategy/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/test-strategy/v1/input",
        output_schema_id="agent/test-strategy/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="risk-review-agent-v1",
        role=AgentRole.RISK_REVIEW,
        version="1.0.0",
        description=(
            "Independently identifies security, concurrency, consistency,"
            " migration, and rollback risks"
        ),
        prompt_id="prompts/risk-review/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/risk-review/v1/input",
        output_schema_id="agent/risk-review/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="synthesis-agent-v1",
        role=AgentRole.SYNTHESIS,
        version="1.0.0",
        description="Merges outputs from multiple specialist agents, resolves conflicts",
        prompt_id="prompts/synthesis/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/synthesis/v1/input",
        output_schema_id="agent/synthesis/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="review-agent-v1",
        role=AgentRole.REVIEW,
        version="1.0.0",
        description="Performs final review and issues PASS/REJECT with structured findings",
        prompt_id="prompts/review/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/review/v1/input",
        output_schema_id="agent/review/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
)


class DeterministicPlanner:
    """Produces a StructuralDelegationSpec from the fixed topology."""

    def generate(self, plan_id: str = "plan-v1") -> StructuralDelegationSpec:
        agents = FIXED_TOPOLOGY_AGENTS
        agent_ids = {a.agent_id for a in agents}

        repo_id = "repository-analyst-agent-v1"
        design_id = "design-agent-v1"
        test_id = "test-strategy-agent-v1"
        risk_id = "risk-review-agent-v1"
        synthesis_id = "synthesis-agent-v1"
        review_id = "review-agent-v1"

        dependencies = (
            AgentDependency(agent_id=design_id, depends_on=frozenset({repo_id})),
            AgentDependency(agent_id=test_id, depends_on=frozenset({repo_id})),
            AgentDependency(agent_id=risk_id, depends_on=frozenset({repo_id})),
            AgentDependency(
                agent_id=synthesis_id,
                depends_on=frozenset({design_id, test_id, risk_id}),
            ),
            AgentDependency(agent_id=review_id, depends_on=frozenset({synthesis_id})),
        )

        _required = {
            repo_id,
            synthesis_id,
            review_id,
        }

        constraints = tuple(
            AgentConstraints(
                agent_id=a_id,
                max_execution_seconds=120,
                max_token_budget=8192,
                max_revision_rounds=1,
                criticality="required" if a_id in _required else "optional",
                fallback_allowed=(a_id not in _required),
            )
            for a_id in sorted(agent_ids)
        )

        # Agents with no upstream dependency (repo-analyst) get no explicit dependency.
        # We add an empty dependency for repo-analyst so its constraints are included.
        all_deps = list(dependencies)
        dep_agent_ids = {d.agent_id for d in all_deps}
        if repo_id not in dep_agent_ids:
            all_deps.append(AgentDependency(agent_id=repo_id, depends_on=frozenset()))

        return StructuralDelegationSpec(
            plan_id=plan_id,
            agents=agents,
            dependencies=tuple(all_deps),
            constraints=constraints,
            revision_policy=RevisionPolicy(),
        )

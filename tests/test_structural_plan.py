import pytest

from specflow.agents.models import (
    AgentDependency,
    AgentRole,
)
from specflow.plan.compiler import PlanCompiler
from specflow.plan.exceptions import PlanCompilationError
from specflow.plan.models import CompiledStructuralPlan, StructuralDelegationSpec
from specflow.plan.planner import FIXED_TOPOLOGY_AGENTS, DeterministicPlanner


def _make_spec() -> StructuralDelegationSpec:
    return DeterministicPlanner().generate()


def _agent_id_for_role(spec, role):
    for a in spec.agents:
        if a.role == role:
            return a.agent_id
    raise ValueError(f"No agent with role {role}")


class TestStructuralDelegationSpec:
    def test_spec_has_no_compiled_fields(self):
        spec = _make_spec()
        assert not hasattr(spec, "execution_stages")
        assert not hasattr(spec, "structure_hash")

    def test_spec_has_all_agents(self):
        spec = _make_spec()
        roles = {a.role for a in spec.agents}
        assert AgentRole.REPOSITORY_ANALYST in roles
        assert AgentRole.DESIGN in roles
        assert AgentRole.TEST_STRATEGY in roles
        assert AgentRole.RISK_REVIEW in roles
        assert AgentRole.SYNTHESIS in roles
        assert AgentRole.REVIEW in roles

    def test_spec_has_correct_dependencies(self):
        spec = _make_spec()
        dep_map = {d.agent_id: d.depends_on for d in spec.dependencies}
        repo_id = _agent_id_for_role(spec, AgentRole.REPOSITORY_ANALYST)
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        test_id = _agent_id_for_role(spec, AgentRole.TEST_STRATEGY)
        risk_id = _agent_id_for_role(spec, AgentRole.RISK_REVIEW)
        synthesis_id = _agent_id_for_role(spec, AgentRole.SYNTHESIS)
        review_id = _agent_id_for_role(spec, AgentRole.REVIEW)

        assert dep_map[design_id] == frozenset({repo_id})
        assert dep_map[test_id] == frozenset({repo_id})
        assert dep_map[risk_id] == frozenset({repo_id})
        assert dep_map[synthesis_id] == frozenset({design_id, test_id, risk_id})
        assert dep_map[review_id] == frozenset({synthesis_id})

    def test_fixed_topology_has_six_agents(self):
        assert len(FIXED_TOPOLOGY_AGENTS) == 6


class TestCompiledStructuralPlan:
    def test_compiler_produces_compiled_plan(self):
        spec = _make_spec()
        compiled = PlanCompiler().compile(spec)
        assert isinstance(compiled, CompiledStructuralPlan)
        assert len(compiled.structure_hash) == 64

    def test_execution_stages_correct_order(self):
        compiled = PlanCompiler().compile(_make_spec())
        assert len(compiled.execution_stages) == 4
        assert len(compiled.execution_stages[0]) == 1  # repo-analyst
        assert len(compiled.execution_stages[1]) == 3  # design/test/risk
        assert len(compiled.execution_stages[2]) == 1  # synthesis
        assert len(compiled.execution_stages[3]) == 1  # review

    def test_parallel_agents_same_stage(self):
        spec = _make_spec()
        compiled = PlanCompiler().compile(spec)
        stage2 = compiled.execution_stages[1]
        assert _agent_id_for_role(spec, AgentRole.DESIGN) in stage2
        assert _agent_id_for_role(spec, AgentRole.TEST_STRATEGY) in stage2
        assert _agent_id_for_role(spec, AgentRole.RISK_REVIEW) in stage2

    def test_rejects_cyclic_dependency(self):
        spec = _make_spec()
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        test_id = _agent_id_for_role(spec, AgentRole.TEST_STRATEGY)
        # Create a mutual dependency cycle: design <-> test
        deps = list(spec.dependencies) + [
            AgentDependency(agent_id=design_id, depends_on=frozenset({test_id})),
            AgentDependency(agent_id=test_id, depends_on=frozenset({design_id})),
        ]
        bad_spec = StructuralDelegationSpec(
            plan_id=spec.plan_id, agents=spec.agents,
            dependencies=tuple(deps), constraints=spec.constraints,
            revision_policy=spec.revision_policy,
        )
        with pytest.raises(PlanCompilationError):
            PlanCompiler().compile(bad_spec)

    def test_rejects_missing_agent_dependency(self):
        spec = _make_spec()
        deps = list(spec.dependencies) + [
            AgentDependency(agent_id="nonexistent-agent", depends_on=frozenset()),
        ]
        bad_spec = StructuralDelegationSpec(
            plan_id=spec.plan_id, agents=spec.agents,
            dependencies=tuple(deps), constraints=spec.constraints,
            revision_policy=spec.revision_policy,
        )
        with pytest.raises(PlanCompilationError):
            PlanCompiler().compile(bad_spec)

    def test_rejects_dependency_on_missing_agent(self):
        spec = _make_spec()
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        deps = list(spec.dependencies) + [
            AgentDependency(agent_id=design_id, depends_on=frozenset({"ghost-agent"})),
        ]
        bad_spec = StructuralDelegationSpec(
            plan_id=spec.plan_id, agents=spec.agents,
            dependencies=tuple(deps), constraints=spec.constraints,
            revision_policy=spec.revision_policy,
        )
        with pytest.raises(PlanCompilationError):
            PlanCompiler().compile(bad_spec)

    def test_compiler_deterministic_hash(self):
        compiled1 = PlanCompiler().compile(_make_spec())
        compiled2 = PlanCompiler().compile(_make_spec())
        assert compiled1.structure_hash == compiled2.structure_hash


class TestDeterministicPlanner:
    def test_generate_returns_valid_spec(self):
        spec = DeterministicPlanner().generate()
        assert isinstance(spec, StructuralDelegationSpec)
        assert spec.plan_id == "plan-v1"

    def test_generate_custom_plan_id(self):
        spec = DeterministicPlanner().generate(plan_id="my-plan")
        assert spec.plan_id == "my-plan"

"""Tests for PlanValidator — static structural plan validation."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.exceptions import PlanValidationError
from specflow.plan.models import CompiledStructuralPlan
from specflow.plan.validator import PlanValidator


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_identity(
    agent_id: str,
    role: AgentRole = AgentRole.DESIGN,
    *,
    input_schema_id: str | None = None,
    output_schema_id: str | None = None,
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        role=role,
        version="1.0.0",
        description=f"Test {role.value} agent",
        prompt_id="test/v1",
        prompt_version="1.0.0",
        input_schema_id=input_schema_id or f"{agent_id}/input",
        output_schema_id=output_schema_id or f"{agent_id}/output",
    )


def _make_constraints(agent_id: str) -> AgentConstraints:
    return AgentConstraints(
        agent_id=agent_id,
        max_execution_seconds=120,
        max_token_budget=8192,
    )


def _valid_plan(**overrides: Any) -> CompiledStructuralPlan:
    """Build a structurally valid 2-agent 2-stage plan."""
    defaults: dict[str, Any] = dict(
        plan_id="valid-plan",
        agents=(
            _make_identity("a1", AgentRole.REPOSITORY_ANALYST),
            _make_identity("a2", AgentRole.DESIGN),
        ),
        dependencies=(
            AgentDependency(agent_id="a2", depends_on=frozenset({"a1"})),
            AgentDependency(agent_id="a1", depends_on=frozenset()),
        ),
        execution_stages=(("a1",), ("a2",)),
        constraints=(
            _make_constraints("a1"),
            _make_constraints("a2"),
        ),
        revision_policy=RevisionPolicy(),
        structure_hash="abc123",
    )
    defaults.update(overrides)
    return CompiledStructuralPlan(**defaults)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestPlanValidator:
    def test_valid_compiled_plan_passes(self) -> None:
        plan = _valid_plan()
        PlanValidator().validate(plan)  # should not raise

    def test_missing_agent_in_stages_raises(self) -> None:
        """Agent in plan.agents but not in any execution stage."""
        plan = _valid_plan(
            agents=(
                _make_identity("a1", AgentRole.REPOSITORY_ANALYST),
                _make_identity("a2", AgentRole.DESIGN),
            ),
            execution_stages=(("a1",),),  # a2 missing
        )
        with pytest.raises(PlanValidationError, match="missing from execution"):
            PlanValidator().validate(plan)

    def test_extra_agent_in_stages_raises(self) -> None:
        """Agent in execution stages but not in plan.agents."""
        plan = _valid_plan(
            agents=(
                _make_identity("a1", AgentRole.REPOSITORY_ANALYST),
            ),
            execution_stages=(("a1",), ("a2",)),  # a2 not in plan.agents
        )
        with pytest.raises(PlanValidationError, match="not declared in plan"):
            PlanValidator().validate(plan)

    def test_duplicate_agent_across_stages_raises(self) -> None:
        """Same agent_id appears in two different stages."""
        plan = _valid_plan(
            agents=(_make_identity("a1", AgentRole.REPOSITORY_ANALYST),),
            execution_stages=(("a1",), ("a1",)),
            dependencies=(),
            constraints=(_make_constraints("a1"),),
        )
        with pytest.raises(
            PlanValidationError, match="appears in multiple execution stages"
        ):
            PlanValidator().validate(plan)

    def test_intra_stage_dependency_raises(self) -> None:
        """Two agents in the same stage with a dependency edge between them."""
        plan = _valid_plan(
            agents=(
                _make_identity("a1", AgentRole.REPOSITORY_ANALYST),
                _make_identity("a2", AgentRole.DESIGN),
            ),
            dependencies=(
                AgentDependency(agent_id="a2", depends_on=frozenset({"a1"})),
            ),
            execution_stages=(("a1", "a2"),),  # same stage, but a2 depends on a1
        )
        with pytest.raises(
            PlanValidationError, match="Intra-stage dependency"
        ):
            PlanValidator().validate(plan)

    def test_with_schema_registry_all_exist(self) -> None:
        """All schema IDs are registered -> passes."""
        from specflow.schema.registry import SchemaRegistry

        registry = SchemaRegistry()

        class FakeInput(BaseModel):
            pass

        class FakeOutput(BaseModel):
            pass

        registry.register("a1/input", FakeInput)
        registry.register("a1/output", FakeOutput)

        plan = _valid_plan(
            agents=(
                _make_identity(
                    "a1",
                    AgentRole.REPOSITORY_ANALYST,
                    input_schema_id="a1/input",
                    output_schema_id="a1/output",
                ),
            ),
            execution_stages=(("a1",),),
            dependencies=(),
            constraints=(_make_constraints("a1"),),
        )
        PlanValidator().validate(plan, schema_registry=registry)  # should not raise

    def test_with_schema_registry_missing_input_raises(self) -> None:
        """Input schema ID not registered -> PlanValidationError."""
        from specflow.schema.registry import SchemaRegistry

        registry = SchemaRegistry()

        class FakeOutput(BaseModel):
            pass

        registry.register("a1/output", FakeOutput)
        # a1/input is NOT registered

        plan = _valid_plan(
            agents=(
                _make_identity(
                    "a1",
                    AgentRole.REPOSITORY_ANALYST,
                    input_schema_id="a1/input",
                    output_schema_id="a1/output",
                ),
            ),
            execution_stages=(("a1",),),
            dependencies=(),
            constraints=(_make_constraints("a1"),),
        )
        with pytest.raises(
            PlanValidationError, match="unknown input_schema_id"
        ):
            PlanValidator().validate(plan, schema_registry=registry)

    def test_with_schema_registry_missing_output_raises(self) -> None:
        """Output schema ID not registered -> PlanValidationError."""
        from specflow.schema.registry import SchemaRegistry

        registry = SchemaRegistry()

        class FakeInput(BaseModel):
            pass

        registry.register("a1/input", FakeInput)
        # a1/output is NOT registered

        plan = _valid_plan(
            agents=(
                _make_identity(
                    "a1",
                    AgentRole.REPOSITORY_ANALYST,
                    input_schema_id="a1/input",
                    output_schema_id="a1/output",
                ),
            ),
            execution_stages=(("a1",),),
            dependencies=(),
            constraints=(_make_constraints("a1"),),
        )
        with pytest.raises(
            PlanValidationError, match="unknown output_schema_id"
        ):
            PlanValidator().validate(plan, schema_registry=registry)

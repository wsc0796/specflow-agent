"""Tests for schema model validation and registry wiring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from specflow.schema.factory import build_schema_registry
from specflow.schema.models import (
    DesignOutput,
    RepositoryAnalystOutput,
    ReviewOutput,
    RiskReviewOutput,
    SynthesisOutput,
    TestStrategyOutput,
)


class TestSchemaRegistry:
    def test_registry_has_all_12_schemas(self) -> None:
        """build_schema_registry() registers 6 input + 6 output schemas."""
        registry = build_schema_registry()
        assert registry.frozen
        schemas = registry.list_schemas()
        assert len(schemas) == 12

    def test_all_output_schemas_are_registered(self) -> None:
        """Each agent's output_schema_id must be resolvable."""
        registry = build_schema_registry()
        schema_ids = [
            "agent/repository-analyst/v1/output",
            "agent/design/v1/output",
            "agent/test-strategy/v1/output",
            "agent/risk-review/v1/output",
            "agent/synthesis/v1/output",
            "agent/review/v1/output",
        ]
        for sid in schema_ids:
            registry.get(sid)  # must not raise

    def test_all_input_schemas_are_registered(self) -> None:
        """Each agent's input_schema_id must be resolvable."""
        registry = build_schema_registry()
        schema_ids = [
            "agent/repository-analyst/v1/input",
            "agent/design/v1/input",
            "agent/test-strategy/v1/input",
            "agent/risk-review/v1/input",
            "agent/synthesis/v1/input",
            "agent/review/v1/input",
        ]
        for sid in schema_ids:
            registry.get(sid)  # should not raise

    def test_registry_is_frozen_after_build(self) -> None:
        """Frozen registry must reject new registrations."""
        registry = build_schema_registry()
        from pydantic import BaseModel

        from specflow.schema.exceptions import RegistryFrozenError

        class Foo(BaseModel):
            x: int

        with pytest.raises(RegistryFrozenError):
            registry.register("test/foo", Foo)

    def test_nonexistent_schema_id_raises(self) -> None:
        """Looking up an unregistered schema must raise SchemaNotFoundError."""
        registry = build_schema_registry()
        from specflow.schema.exceptions import SchemaNotFoundError

        with pytest.raises(SchemaNotFoundError):
            registry.get("nonexistent/schema/id")


class TestAgentOutputValidation:
    """Valid output must pass; structurally invalid output must fail."""

    def test_valid_repository_analyst_output_passes(self) -> None:
        output = RepositoryAnalystOutput(
            agent_id="repo-1", role="repository_analyst", output={"files": []}
        )
        assert output.agent_id == "repo-1"

    def test_valid_review_output_passes(self) -> None:
        output = ReviewOutput(
            agent_id="rev-1",
            role="review",
            output={"findings": []},
            decision="PASS",
        )
        assert output.decision == "PASS"

    def test_valid_synthesis_output_passes(self) -> None:
        output = SynthesisOutput(agent_id="syn-1", role="synthesis", output={"proposal": {}})
        assert output.role == "synthesis"

    def test_missing_agent_id_fails(self) -> None:
        with pytest.raises(PydanticValidationError):
            DesignOutput(role="design", output={})

    def test_missing_output_field_fails(self) -> None:
        with pytest.raises(PydanticValidationError):
            RepositoryAnalystOutput(agent_id="r1", role="repository_analyst")

    def test_output_with_non_dict_output_fails(self) -> None:
        with pytest.raises(PydanticValidationError):
            RepositoryAnalystOutput(agent_id="r1", role="repository_analyst", output="not_a_dict")

    def test_all_output_models_accept_valid_minimal_payload(self) -> None:
        """Every output model must accept a minimal-envelope payload."""
        envelope = {"agent_id": "a1", "output": {}}
        models: list[tuple[type, dict[str, object]]] = [
            (RepositoryAnalystOutput, {**envelope, "role": "repository_analyst"}),
            (DesignOutput, {**envelope, "role": "design"}),
            (TestStrategyOutput, {**envelope, "role": "test_strategy"}),
            (RiskReviewOutput, {**envelope, "role": "risk_review"}),
            (SynthesisOutput, {**envelope, "role": "synthesis"}),
            (ReviewOutput, {**envelope, "role": "review", "decision": "PASS"}),
        ]
        for model_cls, payload in models:
            instance = model_cls(**payload)
            assert instance.agent_id == "a1"


class TestSchemaRegistryWiring:
    """The registry must reject plans referencing unknown schema IDs."""

    def test_valid_plan_passes_schema_check(self) -> None:
        """A plan whose agent schema IDs are all registered must pass."""
        registry = build_schema_registry()
        from specflow.plan.compiler import PlanCompiler
        from specflow.plan.planner import DeterministicPlanner
        from specflow.plan.validator import PlanValidator

        planner = DeterministicPlanner()
        spec = planner.generate()
        compiler = PlanCompiler()
        compiled = compiler.compile(spec)

        validator = PlanValidator()
        validator.validate(compiled, schema_registry=registry)  # must not raise

    def test_unknown_schema_id_rejected(self) -> None:
        """A plan with an unregistered schema ID must fail validation."""
        from dataclasses import replace

        from specflow.plan.exceptions import PlanValidationError
        from specflow.plan.validator import PlanValidator

        registry = build_schema_registry()
        from specflow.plan.compiler import PlanCompiler
        from specflow.plan.planner import DeterministicPlanner

        planner = DeterministicPlanner()
        spec = planner.generate()
        # Replace one agent with a copy that has an unknown input_schema_id.
        tampered = replace(spec.agents[0], input_schema_id="nonexistent/schema/v99")
        tampered_agents = tuple(tampered if i == 0 else a for i, a in enumerate(spec.agents))
        tampered_spec = replace(spec, agents=tampered_agents)
        compiler = PlanCompiler()
        compiled = compiler.compile(tampered_spec)

        validator = PlanValidator()
        with pytest.raises(PlanValidationError, match="input_schema_id"):
            validator.validate(compiled, schema_registry=registry)

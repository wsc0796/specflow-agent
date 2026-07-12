"""Schema Registry factory — wires all 12 agent schemas into a frozen registry."""

from __future__ import annotations

from specflow.schema.models import (
    DesignInput,
    DesignOutput,
    RepositoryAnalystInput,
    RepositoryAnalystOutput,
    ReviewInput,
    ReviewOutput,
    RiskReviewInput,
    RiskReviewOutput,
    SynthesisInput,
    SynthesisOutput,
    TestStrategyInput,
    TestStrategyOutput,
)
from specflow.schema.registry import SchemaRegistry


def build_schema_registry() -> SchemaRegistry:
    """Build and freeze the production SchemaRegistry with all 12 agent schemas.

    Returns a frozen registry that can be passed to Coordinator,
    PlanValidator, and AgentRunner for runtime schema enforcement.
    """
    registry = SchemaRegistry()

    # Repository Analyst
    registry.register("agent/repository-analyst/v1/input", RepositoryAnalystInput)
    registry.register("agent/repository-analyst/v1/output", RepositoryAnalystOutput)

    # Design
    registry.register("agent/design/v1/input", DesignInput)
    registry.register("agent/design/v1/output", DesignOutput)

    # Test Strategy
    registry.register("agent/test-strategy/v1/input", TestStrategyInput)
    registry.register("agent/test-strategy/v1/output", TestStrategyOutput)

    # Risk Review
    registry.register("agent/risk-review/v1/input", RiskReviewInput)
    registry.register("agent/risk-review/v1/output", RiskReviewOutput)

    # Synthesis
    registry.register("agent/synthesis/v1/input", SynthesisInput)
    registry.register("agent/synthesis/v1/output", SynthesisOutput)

    # Review
    registry.register("agent/review/v1/input", ReviewInput)
    registry.register("agent/review/v1/output", ReviewOutput)

    registry.freeze()
    return registry

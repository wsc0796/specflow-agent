"""Schema Registry factory — wires all 12 agent schemas into a frozen registry."""

from __future__ import annotations

from specflow.schema.agent_payloads import (
    DesignPayload,
    RepositoryAnalysisPayload,
    ReviewPayload,
    RiskReviewPayload,
    SynthesisPayload,
    TestStrategyPayload,
)
from specflow.schema.models import (
    DesignInput,
    RepositoryAnalystInput,
    ReviewInput,
    RiskReviewInput,
    SynthesisInput,
    TestStrategyInput,
)
from specflow.schema.registry import SchemaRegistry


def build_schema_registry() -> SchemaRegistry:
    """Build and freeze the production SchemaRegistry with all 12 agent schemas.

    Output schemas use strict business payloads (from agent_payloads).
    Input schemas validate what each agent receives.

    Returns a frozen registry for Coordinator, PlanValidator, and AgentRunner.
    """
    registry = SchemaRegistry()

    # Repository Analyst
    registry.register("agent/repository-analyst/v1/input", RepositoryAnalystInput)
    registry.register("agent/repository-analyst/v1/output", RepositoryAnalysisPayload)

    # Design
    registry.register("agent/design/v1/input", DesignInput)
    registry.register("agent/design/v1/output", DesignPayload)

    # Test Strategy
    registry.register("agent/test-strategy/v1/input", TestStrategyInput)
    registry.register("agent/test-strategy/v1/output", TestStrategyPayload)

    # Risk Review
    registry.register("agent/risk-review/v1/input", RiskReviewInput)
    registry.register("agent/risk-review/v1/output", RiskReviewPayload)

    # Synthesis
    registry.register("agent/synthesis/v1/input", SynthesisInput)
    registry.register("agent/synthesis/v1/output", SynthesisPayload)

    # Review
    registry.register("agent/review/v1/input", ReviewInput)
    registry.register("agent/review/v1/output", ReviewPayload)

    registry.freeze()
    return registry

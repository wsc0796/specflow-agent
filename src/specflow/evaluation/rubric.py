"""Manual rubric definitions; content quality is never auto-scored as Live quality."""

from dataclasses import dataclass


@dataclass
class RubricDimension:
    """A scoring dimension in the A/B evaluation rubric."""

    key: str
    label: str
    max_score: int = 2


RUBRIC_DIMENSIONS = (
    "repository_grounding",
    "affected_component_relevance",
    "requirement_coverage",
    "risk_coverage",
    "implementation_feasibility",
    "test_completeness",
    "review_usefulness",
    "evidence_integrity",
    "artifact_completeness",
    "security",
)

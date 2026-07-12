class PlanError(Exception):
    """Base exception for plan-related errors."""


class PlanCompilationError(PlanError):
    """PlanCompiler failed to compile the structural plan."""


class PlanValidationError(PlanError):
    """PlanValidator found an invalid plan."""


class PlanEnrichmentError(PlanError):
    """SemanticPlanEnricher failed."""

"""Workflow State Machine exceptions."""


class WorkflowError(Exception):
    """Base error for workflow state handling."""


class WorkflowTransitionError(WorkflowError):
    """Raised when a workflow transition is not allowed."""

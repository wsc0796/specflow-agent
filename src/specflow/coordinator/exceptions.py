class CoordinatorError(Exception):
    """Base exception for coordinator-related errors."""


class StateTransitionError(CoordinatorError):
    """Illegal state transition in the workflow state machine."""


class ScheduleExecutionError(CoordinatorError):
    """Scheduler execution failed."""


class RevisionError(CoordinatorError):
    """Revision operation failed."""

"""Worker Framework exceptions."""


class WorkerError(Exception):
    """Base error for Worker Framework failures."""


class WorkerValidationError(WorkerError):
    """Raised when Worker Framework data violates its contract."""


class WorkerRegistrationError(WorkerError):
    """Raised when worker registration fails."""


class DuplicateWorkerError(WorkerRegistrationError):
    """Raised when a worker role or name is registered twice."""


class WorkerNotFoundError(WorkerError):
    """Raised when a worker lookup cannot be satisfied."""


class WorkerExecutionError(WorkerError):
    """Raised when a worker returns failure or raises unexpectedly."""

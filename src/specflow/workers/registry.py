"""Deterministic Worker Registry."""

from __future__ import annotations

from specflow.workers.base import Worker
from specflow.workers.exceptions import DuplicateWorkerError, WorkerNotFoundError
from specflow.workers.models import WorkerMetadata, WorkerRole


class WorkerRegistry:
    """Explicit, deterministic worker registry."""

    def __init__(self) -> None:
        self._workers_by_role: dict[WorkerRole, Worker] = {}
        self._names: set[str] = set()

    def register(self, worker: Worker) -> None:
        """Register one worker by role and name."""
        metadata = worker_metadata(worker)
        if metadata.role in self._workers_by_role:
            raise DuplicateWorkerError(f"Worker role already registered: {metadata.role}")
        if metadata.name in self._names:
            raise DuplicateWorkerError(f"Worker name already registered: {metadata.name}")
        self._workers_by_role[metadata.role] = worker
        self._names.add(metadata.name)

    def get(self, role: WorkerRole) -> Worker:
        """Return the worker registered for a role."""
        try:
            return self._workers_by_role[role]
        except KeyError as exc:
            raise WorkerNotFoundError(f"No worker registered for role: {role}") from exc

    def metadata(self) -> tuple[WorkerMetadata, ...]:
        """Return registered worker metadata in deterministic role order."""
        return tuple(
            worker_metadata(self._workers_by_role[role])
            for role in sorted(self._workers_by_role, key=lambda item: item.value)
        )


def worker_metadata(worker: Worker) -> WorkerMetadata:
    """Build validated metadata from a worker."""
    return WorkerMetadata(
        name=worker.name,
        role=worker.role,
        version=worker.version,
        description=worker.description,
    )

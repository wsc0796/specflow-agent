"""Worker Framework base protocol."""

from __future__ import annotations

from typing import Protocol

from specflow.workers.models import WorkerContext, WorkerMetadata, WorkerResult, WorkerRole


class Worker(Protocol):
    """Protocol implemented by future business workers."""

    @property
    def name(self) -> str:
        """Stable worker name."""
        ...

    @property
    def role(self) -> WorkerRole:
        """Worker role."""
        ...

    @property
    def version(self) -> str:
        """Stable worker version."""
        ...

    @property
    def description(self) -> str:
        """Human-readable worker description."""
        ...

    def execute(self, context: WorkerContext) -> WorkerResult:
        """Execute one worker step."""
        ...


class BaseWorker:
    """Minimal base class for fake and future concrete workers."""

    def __init__(self, metadata: WorkerMetadata) -> None:
        self._metadata = metadata

    @property
    def name(self) -> str:
        return self._metadata.name

    @property
    def role(self) -> WorkerRole:
        return self._metadata.role

    @property
    def version(self) -> str:
        return self._metadata.version

    @property
    def description(self) -> str:
        return self._metadata.description

    @property
    def metadata(self) -> WorkerMetadata:
        """Return stable worker metadata."""
        return self._metadata

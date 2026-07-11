"""Worker Framework models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from specflow.context import _redact_secrets, _strip_control
from specflow.workers.exceptions import WorkerValidationError


class WorkerRole(StrEnum):
    """Supported future worker roles."""

    ANALYZE = "analyze"
    GENERATE = "generate"
    REVIEW = "review"


@dataclass(frozen=True)
class WorkerMetadata:
    """Stable worker identity metadata."""

    name: str
    role: WorkerRole
    version: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise WorkerValidationError("WorkerMetadata.name must not be empty")
        if not isinstance(self.role, WorkerRole):
            raise WorkerValidationError("WorkerMetadata.role must be a WorkerRole")
        if not isinstance(self.version, str):
            raise WorkerValidationError("WorkerMetadata.version must be a string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise WorkerValidationError("WorkerMetadata.description must not be empty")
        if not self.version.strip() or self.version.strip().lower() in {"latest", "dev"}:
            raise WorkerValidationError("WorkerMetadata.version must be explicit and stable")


@dataclass(frozen=True)
class WorkerContext:
    """Structured context for one worker execution."""

    run_id: str
    requirement: str
    project_context: str
    prior_outputs: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    metadata: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise WorkerValidationError("WorkerContext.run_id must not be empty")
        if not isinstance(self.requirement, str) or not self.requirement.strip():
            raise WorkerValidationError("WorkerContext.requirement must not be empty")
        if not isinstance(self.project_context, str):
            raise WorkerValidationError("WorkerContext.project_context must be a string")
        if not isinstance(self.prior_outputs, tuple):
            raise WorkerValidationError("WorkerContext.prior_outputs must be a tuple")
        for entry in self.prior_outputs:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise WorkerValidationError("WorkerContext.prior_outputs must contain string pairs")
            key, value = entry
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                raise WorkerValidationError("WorkerContext.prior_outputs must contain string pairs")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                raise WorkerValidationError("WorkerContext.metadata must be string-to-string")

    @classmethod
    def build(
        cls,
        *,
        run_id: str,
        requirement: str,
        project_context: str = "",
        prior_outputs: tuple[tuple[str, str], ...] = (),
        metadata: dict[str, str] | None = None,
    ) -> WorkerContext:
        """Build a WorkerContext with immutable metadata."""
        return cls(
            run_id=run_id,
            requirement=requirement,
            project_context=project_context,
            prior_outputs=tuple(prior_outputs),
            metadata=MappingProxyType(dict(metadata or {})),
        )


@dataclass(frozen=True)
class WorkerResult:
    """Structured result returned by a Worker."""

    worker_name: str
    worker_role: WorkerRole
    success: bool
    output: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    metadata: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))
    error_type: str | None = None
    error_message: str | None = None
    requires_review: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.worker_name, str) or not self.worker_name.strip():
            raise WorkerValidationError("WorkerResult.worker_name must not be empty")
        if not isinstance(self.worker_role, WorkerRole):
            raise WorkerValidationError("WorkerResult.worker_role must be a WorkerRole")
        if not isinstance(self.success, bool):
            raise WorkerValidationError("WorkerResult.success must be a bool")
        if not isinstance(self.output, tuple):
            raise WorkerValidationError("WorkerResult.output must be a tuple")
        for entry in self.output:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise WorkerValidationError("WorkerResult.output must contain string pairs")
            key, value = entry
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                raise WorkerValidationError("WorkerResult.output must contain string pairs")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                raise WorkerValidationError("WorkerResult.metadata must be string-to-string")
        if self.success and (self.error_type or self.error_message or self.requires_review):
            raise WorkerValidationError("Successful WorkerResult must not carry error fields")
        if not self.success and not self.error_message:
            raise WorkerValidationError("Failed WorkerResult must include error_message")
        if self.error_message is not None:
            object.__setattr__(self, "error_message", sanitize_worker_text(self.error_message))

    @classmethod
    def success_result(
        cls,
        *,
        worker_name: str,
        worker_role: WorkerRole,
        output: tuple[tuple[str, str], ...] = (),
        metadata: dict[str, str] | None = None,
    ) -> WorkerResult:
        """Build a successful WorkerResult."""
        return cls(
            worker_name=worker_name,
            worker_role=worker_role,
            success=True,
            output=tuple(output),
            metadata=MappingProxyType(dict(metadata or {})),
        )

    @classmethod
    def failure_result(
        cls,
        *,
        worker_name: str,
        worker_role: WorkerRole,
        error_type: str,
        error_message: str,
        requires_review: bool = True,
        metadata: dict[str, str] | None = None,
    ) -> WorkerResult:
        """Build a failed WorkerResult."""
        return cls(
            worker_name=worker_name,
            worker_role=worker_role,
            success=False,
            metadata=MappingProxyType(dict(metadata or {})),
            error_type=error_type,
            error_message=error_message,
            requires_review=requires_review,
        )


def sanitize_worker_text(text: str) -> str:
    """Redact secrets and strip control characters from worker text."""
    return _strip_control(_redact_secrets(text))

"""Revision lifecycle — determines when and how agent outputs can be revised."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from specflow.agents.models import AgentRole, RevisionPolicy


@dataclass(frozen=True)
class RevisionTask:
    """A persisted unit of revision work targeting exactly one agent.

    One revision round can contain multiple tasks (one per target agent).
    ``revision_id`` identifies the task; ``finding_ids`` reference the
    structured review findings that drive it.  The two ID spaces never mix.
    """

    revision_id: str
    run_id: str
    target_agent_id: str
    target_role: AgentRole
    round_number: int
    finding_ids: tuple[str, ...]
    prior_output_hash: str
    status: str = "scheduled"  # scheduled | running | completed | failed
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    result_artifact: str | None = None
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable snapshot for revision-tasks.json."""
        return {
            "revision_id": self.revision_id,
            "run_id": self.run_id,
            "target_agent_id": self.target_agent_id,
            "target_role": self.target_role.value,
            "round_number": self.round_number,
            "finding_ids": list(self.finding_ids),
            "prior_output_hash": self.prior_output_hash,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result_artifact": self.result_artifact,
            "failure_reason": self.failure_reason,
        }


class RevisionController:
    """Manages the revision lifecycle for a multi-agent workflow.

    The controller consults a :class:`RevisionPolicy` to decide which
    roles are revisable and how many revision rounds are allowed.
    """

    def __init__(self, policy: RevisionPolicy) -> None:
        self._policy = policy
        self._round: int = 0
        self._tasks: list[RevisionTask] = []

    # ── Public properties ───────────────────────────────────────────

    @property
    def policy(self) -> RevisionPolicy:
        """The revision policy in effect."""
        return self._policy

    @property
    def exhausted(self) -> bool:
        """``True`` when the number of completed revision rounds reaches the limit."""
        return self._round >= self._policy.max_total_rounds

    @property
    def current_round(self) -> int:
        """The revision round we are currently on (0 = none yet)."""
        return self._round

    @property
    def tasks(self) -> tuple[RevisionTask, ...]:
        """All revision tasks created so far."""
        return tuple(self._tasks)

    # ── Public API ──────────────────────────────────────────────────

    def is_revisable(self, role: AgentRole) -> bool:
        """Whether the given *role* can be asked to revise its output."""
        return self._policy.is_revisable(role)

    def create_revision_task(
        self,
        *,
        run_id: str,
        round_number: int,
        target_agent_id: str,
        target_role: AgentRole,
        finding_ids: tuple[str, ...],
        prior_output_hash: str,
    ) -> RevisionTask | None:
        """Create and record a revision task within an already-open round."""
        if self._round < 1:
            raise ValueError("begin_round() must be called before creating tasks")
        if not finding_ids:
            raise ValueError("Revision task requires at least one finding")
        if not prior_output_hash:
            raise ValueError("Revision task requires a prior output hash")
        if not self.is_revisable(target_role):
            return None

        task = RevisionTask(
            revision_id=f"revision-{round_number}-{target_agent_id}-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            target_agent_id=target_agent_id,
            target_role=target_role,
            round_number=round_number,
            finding_ids=finding_ids,
            prior_output_hash=prior_output_hash,
        )
        self._tasks.append(task)
        return task

    def begin_round(self) -> int | None:
        """Open the next revision round when budget remains.

        Returns the new 1-based round number, or ``None`` when the revision
        budget is already exhausted (caller must move to a terminal state).
        """
        if self.exhausted:
            return None
        self._round += 1
        return self._round

    def mark_running(self, revision_id: str) -> None:
        """Mark one task as running (immutable snapshot is replaced)."""
        self._replace_task(
            revision_id,
            lambda task: replace(task, status="running"),
        )

    def mark_completed(
        self,
        revision_id: str,
        *,
        result_artifact: str,
    ) -> None:
        """Mark one task as completed with its result artifact."""
        self._replace_task(
            revision_id,
            lambda task: replace(
                task,
                status="completed",
                completed_at=datetime.now(UTC).isoformat(),
                result_artifact=result_artifact,
            ),
        )

    def mark_failed(self, revision_id: str, *, reason: str) -> None:
        """Mark one task as failed with a safe failure reason."""
        self._replace_task(
            revision_id,
            lambda task: replace(
                task,
                status="failed",
                completed_at=datetime.now(UTC).isoformat(),
                failure_reason=reason,
            ),
        )

    def _replace_task(self, revision_id: str, transform) -> None:
        for index, task in enumerate(self._tasks):
            if task.revision_id == revision_id:
                self._tasks[index] = transform(task)
                return
        raise ValueError(f"Unknown revision task: {revision_id}")


# Re-export the strict, schema-validated revision result contract.  The old
# local dataclass was replaced by ``specflow.revision.models.RevisionResult``.
from specflow.revision.models import RevisionResult  # noqa: E402,F401

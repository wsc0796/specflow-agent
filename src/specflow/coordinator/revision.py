"""Revision lifecycle — determines when and how agent outputs can be revised."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from specflow.agents.models import AgentRole, RevisionPolicy

from specflow.coordinator.exceptions import RevisionError


@dataclass(frozen=True)
class RevisionTask:
    """A single unit of revision work targeting one agent.

    Attributes
    ----------
    revision_id:
        Unique identifier for this revision task.
    target_agent_id:
        The agent whose output should be revised.
    target_role:
        The role of the target agent (used for policy checks).
    review_finding:
        A human-readable description of the issue found during review.
    instruction:
        Specific instructions on how the agent should revise its output.
    round_number:
        Which revision round this task belongs to (1-based).
    """

    revision_id: str
    target_agent_id: str
    target_role: AgentRole
    review_finding: str
    instruction: str
    round_number: int


@dataclass(frozen=True)
class RevisionResult:
    """The outcome of executing a single revision task.

    Attributes
    ----------
    task:
        The :class:`RevisionTask` that was executed.
    output:
        The revised output produced by the agent.
    success:
        Whether the revision completed without error.
    """

    task: RevisionTask
    output: dict[str, object]
    success: bool


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
        target_agent_id: str,
        target_role: AgentRole,
        finding: str,
        instruction: str,
    ) -> RevisionTask | None:
        """Create and record a new revision task.

        Returns ``None`` (without creating a task) when revisions are
        exhausted or the target role is not revisable.
        """
        if self.exhausted:
            return None
        if not self.is_revisable(target_role):
            return None

        self._round += 1
        task = RevisionTask(
            revision_id=str(uuid.uuid4()),
            target_agent_id=target_agent_id,
            target_role=target_role,
            review_finding=finding,
            instruction=instruction,
            round_number=self._round,
        )
        self._tasks.append(task)
        return task

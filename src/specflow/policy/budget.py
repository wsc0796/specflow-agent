"""Run-scoped, fail-closed enforcement for :class:`ExecutionPolicy`."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from specflow.policy.errors import ErrorCode
from specflow.policy.models import ExecutionPolicy


@dataclass
class ExecutionBudget:
    """Mutable counters for one run; limits are checked before work starts."""

    policy: ExecutionPolicy
    started_at: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    revisions: int = 0

    def check_wall_time(self) -> None:
        if time.monotonic() - self.started_at > self.policy.max_wall_time_seconds:
            raise RuntimeError(ErrorCode.BUDGET_WALL_TIME.value)

    def reserve_llm_call(self) -> None:
        self.check_wall_time()
        if self.llm_calls >= self.policy.max_llm_calls:
            raise RuntimeError(ErrorCode.BUDGET_LLM_CALLS.value)
        self.llm_calls += 1

    def reserve_revision(self) -> None:
        self.check_wall_time()
        if self.revisions >= self.policy.max_revisions:
            raise RuntimeError(ErrorCode.BUDGET_REVISION_EXHAUSTED.value)
        self.revisions += 1

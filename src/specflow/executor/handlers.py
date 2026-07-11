"""Agent Executor handler protocol."""

from __future__ import annotations

from typing import Protocol

from specflow.executor.models import ExecutionContext, StepResult


class StepHandler(Protocol):
    """Abstract executable step handler for T-013."""

    def execute(self, execution_context: ExecutionContext) -> StepResult:
        """Execute one deterministic workflow step."""
        ...

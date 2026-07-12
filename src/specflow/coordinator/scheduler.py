"""Multi-agent scheduler — stages execute sequentially, agents within a stage in parallel."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from specflow.coordinator.exceptions import ScheduleExecutionError

# Type alias: an executor is a callable that receives context and returns results.
AgentExecutor = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class StageExecutionResult:
    """Outcome of executing a single stage.

    Attributes
    ----------
    stage_index:
        Zero-based index of the stage within the execution sequence.
    agent_results:
        Mapping from ``agent_id`` to the dict returned by that agent's executor.
    started_at:
        ISO-8601 UTC timestamp captured when the stage began.
    completed_at:
        ISO-8601 UTC timestamp captured when all agents in the stage finished.
    """

    stage_index: int
    agent_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


class MultiAgentScheduler:
    """Executes a multi-stage agent workflow.

    Stages are run **sequentially** (stage N must finish before stage N+1 starts).
    Within each stage, agent executors run **concurrently** via a thread pool.
    """

    def __init__(self, max_parallel_workers: int = 10) -> None:
        """Initialise the scheduler.

        Parameters
        ----------
        max_parallel_workers:
            Maximum number of threads used for parallel agent execution
            within a single stage.
        """
        self._max_workers = max_parallel_workers

    # ── Public API ──────────────────────────────────────────────────

    def execute(
        self,
        stages: tuple[tuple[str, ...], ...],
        agent_executors: dict[str, AgentExecutor],
        context: dict[str, Any],
    ) -> tuple[StageExecutionResult, ...]:
        """Run all stages sequentially.

        Parameters
        ----------
        stages:
            Ordered tuple of stages.  Each stage is a tuple of ``agent_id``
            strings that will be executed concurrently.
        agent_executors:
            Mapping from ``agent_id`` to a callable ``(dict) -> dict``.
            Every agent ID appearing in *stages* must have an entry here.
        context:
            Base context dict passed (with accumulated prior outputs) to
            every agent executor.

        Returns
        -------
        tuple[StageExecutionResult, ...]
            One result per stage, in execution order.

        Raises
        ------
        ScheduleExecutionError
            If no executor is registered for an agent, or if any agent
            callable raises an exception.
        """
        results: list[StageExecutionResult] = []
        prior_outputs: dict[str, dict[str, Any]] = {}

        for stage_idx, stage_agent_ids in enumerate(stages):
            started_at = datetime.now(UTC).isoformat()
            agent_results: dict[str, dict[str, Any]] = {}

            # Validate all agents in this stage have executors
            for agent_id in stage_agent_ids:
                if agent_id not in agent_executors:
                    raise ScheduleExecutionError(f"No executor registered for agent {agent_id!r}")

            # Execute agents in this stage concurrently
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                future_map = {}
                for agent_id in stage_agent_ids:
                    agent_ctx: dict[str, Any] = {
                        **context,
                        "prior_outputs": dict(prior_outputs),
                    }
                    future = executor.submit(agent_executors[agent_id], agent_ctx)
                    future_map[future] = agent_id

                for future in as_completed(future_map):
                    agent_id = future_map[future]
                    try:
                        agent_results[agent_id] = future.result()
                    except Exception as exc:
                        raise ScheduleExecutionError(
                            f"Agent {agent_id!r} execution failed: {exc}"
                        ) from exc

            completed_at = datetime.now(UTC).isoformat()

            # Accumulate outputs so downstream stages can access them
            prior_outputs.update(agent_results)

            results.append(
                StageExecutionResult(
                    stage_index=stage_idx,
                    agent_results=agent_results,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            )

        return tuple(results)

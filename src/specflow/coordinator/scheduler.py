"""Multi-agent scheduler — stages execute sequentially, agents within a stage in parallel."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from specflow.coordinator.exceptions import ScheduleExecutionError
from specflow.coordinator.execution_lanes import LaneManager
from specflow.policy.models import ExecutionLanePolicy, LaneLimits, SpecFlowError

# Type alias: an executor is a callable that receives context and returns results.
AgentExecutor = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class AgentExecutionTiming:
    """Submission and completion timestamps for one agent in a stage."""

    submitted_at: str
    completed_at: str = ""


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
    agent_timings: dict[str, AgentExecutionTiming] = field(default_factory=dict)


class MultiAgentScheduler:
    """Executes a multi-stage agent workflow.

    Stages are run **sequentially** (stage N must finish before stage N+1 starts).
    Within each stage, agent executors run **concurrently** via a thread pool.
    """

    def __init__(
        self, max_parallel_workers: int = 10, *, lane_manager: LaneManager | None = None
    ) -> None:
        """Initialise the scheduler.

        Parameters
        ----------
        max_parallel_workers:
            Maximum number of threads used for parallel agent execution
            within a single stage.
        """
        self._max_workers = max_parallel_workers
        self._lanes = lane_manager

    # ── Public API ──────────────────────────────────────────────────

    def execute(
        self,
        stages: tuple[tuple[str, ...], ...],
        agent_executors: dict[str, AgentExecutor],
        context: dict[str, Any],
        *,
        deadline: float | None = None,
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
        deadline:
            Optional absolute deadline on the lane manager's monotonic clock.
            When set, each stage waits at most the remaining budget for its
            agents. Queued work is cancelled; already-started synchronous work
            is allowed to exit before control returns, because Python threads
            cannot be safely force-cancelled.

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
        if self._max_workers <= 0:
            raise ValueError("max_parallel_workers must be positive")
        lanes = self._lanes or LaneManager(
            ExecutionLanePolicy(local_tool=LaneLimits(self._max_workers, self._max_workers))
        )
        try:
            return self._execute_stages(stages, agent_executors, context, deadline, lanes)
        finally:
            if self._lanes is None:
                lanes.shutdown()

    def _execute_stages(self, stages, agent_executors, context, deadline, lanes):
        results: list[StageExecutionResult] = []
        supplied_prior_outputs = context.get("prior_outputs", {})
        if not isinstance(supplied_prior_outputs, dict):
            raise ScheduleExecutionError("context.prior_outputs must be a mapping")
        prior_outputs: dict[str, dict[str, Any]] = dict(supplied_prior_outputs)

        for stage_idx, stage_agent_ids in enumerate(stages):
            started_at = datetime.now(UTC).isoformat()
            agent_results: dict[str, dict[str, Any]] = {}
            agent_timings: dict[str, AgentExecutionTiming] = {}

            # Validate all agents in this stage have executors
            for agent_id in stage_agent_ids:
                if agent_id not in agent_executors:
                    raise ScheduleExecutionError(f"No executor registered for agent {agent_id!r}")

            # Track only this stage's accepted handles. On failure cancel its
            # queued work and drain started work without shutting down lanes
            # that may also serve another run.
            future_map = {}
            try:
                remaining = None
                if deadline is not None:
                    remaining = max(0.0, deadline - lanes.clock())
                if remaining is not None and remaining <= 0:
                    raise ScheduleExecutionError(
                        "TIME_BUDGET_EXCEEDED: stage exceeded the wall-clock budget"
                    )

                remaining_agents = iter(stage_agent_ids)

                def submit_next():
                    agent_id = next(remaining_agents, None)
                    if agent_id is None:
                        return None
                    agent_ctx: dict[str, Any] = {
                        **context,
                        "prior_outputs": dict(prior_outputs),
                    }
                    submitted_at = datetime.now(UTC).isoformat()
                    future = lanes.submit(
                        "local_tool", agent_executors[agent_id], agent_ctx, deadline=deadline
                    )
                    future_map[future] = agent_id
                    agent_timings[agent_id] = AgentExecutionTiming(submitted_at=submitted_at)
                    return future

                pending = set()
                for _ in range(min(self._max_workers, len(stage_agent_ids))):
                    pending.add(submit_next())
                while pending:
                    remaining = None if deadline is None else max(0.0, deadline - lanes.clock())
                    done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                    if not done:
                        raise SpecFlowError("TIME_BUDGET_EXCEEDED", "Stage deadline exhausted.")
                    for future in done:
                        agent_id = future_map[future]
                        agent_results[agent_id] = lanes.wait_for(future, deadline=deadline)
                        agent_timings[agent_id].completed_at = datetime.now(UTC).isoformat()
                    for _ in done:
                        future = submit_next()
                        if future is not None:
                            pending.add(future)
            except SpecFlowError as error:
                raise ScheduleExecutionError(
                    f"{error.code}: stage admission or execution failed"
                ) from error
            except ScheduleExecutionError:
                raise
            except Exception as error:
                raise ScheduleExecutionError("Agent execution failed") from error
            finally:
                lanes.cancel_and_wait(future_map)

            completed_at = datetime.now(UTC).isoformat()

            # Accumulate outputs so downstream stages can access them
            agent_results = {agent_id: agent_results[agent_id] for agent_id in stage_agent_ids}
            prior_outputs.update(agent_results)

            results.append(
                StageExecutionResult(
                    stage_index=stage_idx,
                    agent_results=agent_results,
                    started_at=started_at,
                    completed_at=completed_at,
                    agent_timings=agent_timings,
                )
            )

        return tuple(results)

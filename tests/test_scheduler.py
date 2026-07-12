"""Tests for MultiAgentScheduler and StageExecutionResult."""

from __future__ import annotations

from typing import Any

import pytest

from specflow.coordinator.exceptions import ScheduleExecutionError
from specflow.coordinator.scheduler import MultiAgentScheduler, StageExecutionResult


def _make_executor(agent_id: str, fail: bool = False) -> Any:
    """Factory for deterministic agent executor callables."""

    def executor(context: dict[str, Any]) -> dict[str, Any]:
        if fail:
            msg = f"Intentional failure in {agent_id}"
            raise RuntimeError(msg)
        return {"agent_id": agent_id, "result": f"{agent_id}_output", "prior": context.get("prior_outputs", {})}

    return executor


class TestStageExecutionResult:
    """Verify StageExecutionResult dataclass."""

    def test_default_fields(self) -> None:
        result = StageExecutionResult(stage_index=0)
        assert result.stage_index == 0
        assert result.agent_results == {}
        assert result.started_at == ""
        assert result.completed_at == ""

    def test_populated_fields(self) -> None:
        result = StageExecutionResult(
            stage_index=1,
            agent_results={"a1": {"data": 42}},
            started_at="2025-01-01T00:00:00",
            completed_at="2025-01-01T00:00:01",
        )
        assert result.stage_index == 1
        assert result.agent_results["a1"]["data"] == 42
        assert result.started_at == "2025-01-01T00:00:00"


class TestMultiAgentScheduler:
    """Verify sequential stage and parallel agent execution."""

    # ── Sequential stage execution ──────────────────────────────────

    def test_sequential_stage_execution(self) -> None:
        """Stages execute in the order defined by the stages tuple."""
        scheduler = MultiAgentScheduler(max_parallel_workers=4)

        stages = (
            ("s1_agent",),
            ("s2_agent",),
            ("s3_agent",),
        )
        executors = {
            "s1_agent": _make_executor("s1_agent"),
            "s2_agent": _make_executor("s2_agent"),
            "s3_agent": _make_executor("s3_agent"),
        }

        results = scheduler.execute(stages, executors, {"base": "ctx"})

        assert len(results) == 3
        assert results[0].stage_index == 0
        assert results[1].stage_index == 1
        assert results[2].stage_index == 2

    def test_stage_order_determined_by_stages_tuple(self) -> None:
        """Different stage ordering produces different execution order."""
        scheduler = MultiAgentScheduler()

        stages = (
            ("first",),
            ("second",),
        )
        executors = {
            "first": _make_executor("first"),
            "second": _make_executor("second"),
        }
        results = scheduler.execute(stages, executors, {})
        assert results[0].agent_results["first"]["result"] == "first_output"
        assert results[1].agent_results["second"]["result"] == "second_output"

    def test_prior_outputs_passed_to_downstream_stages(self) -> None:
        """Agents in later stages receive outputs from earlier stages."""
        scheduler = MultiAgentScheduler()

        stages = (("stage1_a",), ("stage2_b",))
        executors = {
            "stage1_a": _make_executor("stage1_a"),
            "stage2_b": _make_executor("stage2_b"),
        }
        results = scheduler.execute(stages, executors, {"project": "test"})

        # Stage 1 result should be visible in stage 2's prior
        stage2_prior = results[1].agent_results["stage2_b"]["prior"]
        assert "stage1_a" in stage2_prior
        assert stage2_prior["stage1_a"]["result"] == "stage1_a_output"

    # ── Timestamps ──────────────────────────────────────────────────

    def test_timestamps_recorded_per_stage(self) -> None:
        """Each stage has valid started_at and completed_at timestamps."""
        scheduler = MultiAgentScheduler()

        stages = (("a1",), ("a2",))
        executors = {
            "a1": _make_executor("a1"),
            "a2": _make_executor("a2"),
        }
        results = scheduler.execute(stages, executors, {})

        for result in results:
            assert isinstance(result.started_at, str)
            assert len(result.started_at) > 0
            assert isinstance(result.completed_at, str)
            assert len(result.completed_at) > 0
            # completed_at should be >= started_at
            assert result.completed_at >= result.started_at

    def test_timestamps_iso_format(self) -> None:
        """Timestamps are in ISO-8601 format (contain 'T' and end with timezone offset or Z)."""
        scheduler = MultiAgentScheduler()

        stages = (("a1",),)
        executors = {"a1": _make_executor("a1")}
        results = scheduler.execute(stages, executors, {})

        for result in results:
            assert "T" in result.started_at
            assert "T" in result.completed_at

    # ── Error handling ──────────────────────────────────────────────

    def test_missing_executor_raises(self) -> None:
        """When an agent has no executor, ScheduleExecutionError is raised."""
        scheduler = MultiAgentScheduler()

        stages = (("unknown_agent",),)
        executors: dict[str, Any] = {}

        with pytest.raises(ScheduleExecutionError, match="No executor registered"):
            scheduler.execute(stages, executors, {})

    def test_agent_failure_raises(self) -> None:
        """When an agent executor raises, ScheduleExecutionError is raised."""
        scheduler = MultiAgentScheduler()

        stages = (("failing_agent",),)
        executors = {"failing_agent": _make_executor("failing_agent", fail=True)}

        with pytest.raises(ScheduleExecutionError, match="execution failed"):
            scheduler.execute(stages, executors, {})

    # ── Multiple agents in same stage ───────────────────────────────

    def test_parallel_agents_in_same_stage(self) -> None:
        """Multiple agents in one stage all execute and their results are stored."""
        scheduler = MultiAgentScheduler(max_parallel_workers=10)

        stages = (("a1", "a2", "a3"),)
        executors = {
            "a1": _make_executor("a1"),
            "a2": _make_executor("a2"),
            "a3": _make_executor("a3"),
        }
        results = scheduler.execute(stages, executors, {})

        assert len(results) == 1
        stage_result = results[0]
        assert set(stage_result.agent_results.keys()) == {"a1", "a2", "a3"}
        assert stage_result.agent_results["a1"]["result"] == "a1_output"
        assert stage_result.agent_results["a2"]["result"] == "a2_output"
        assert stage_result.agent_results["a3"]["result"] == "a3_output"

    # ── Empty stages ────────────────────────────────────────────────

    def test_empty_stage_tuple(self) -> None:
        """An empty stage (no agents) should produce a stage result with no agent results."""
        scheduler = MultiAgentScheduler()

        stages: tuple[tuple[str, ...], ...] = ((), ("a1",))
        executors = {"a1": _make_executor("a1")}
        results = scheduler.execute(stages, executors, {})

        assert len(results) == 2
        assert results[0].agent_results == {}
        assert results[1].agent_results["a1"]["result"] == "a1_output"

    # ── Context immutability ────────────────────────────────────────

    def test_base_context_not_mutated(self) -> None:
        """The base context dict should not be mutated by execution."""
        scheduler = MultiAgentScheduler()

        stages = (("a1",), ("a2",))
        executors = {
            "a1": _make_executor("a1"),
            "a2": _make_executor("a2"),
        }
        original_ctx: dict[str, Any] = {"base": "value"}
        scheduler.execute(stages, executors, original_ctx)

        assert original_ctx == {"base": "value"}
        assert "prior_outputs" not in original_ctx

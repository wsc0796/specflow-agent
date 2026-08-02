"""Tests for RevisionController and the persisted RevisionTask contract."""

from __future__ import annotations

import pytest

from specflow.agents.models import AgentRole, RevisionPolicy
from specflow.coordinator.revision import RevisionController, RevisionTask


def _task(controller: RevisionController, agent_id: str = "design-agent-v1") -> RevisionTask:
    task = controller.create_revision_task(
        run_id="run-test",
        round_number=controller.current_round,
        target_agent_id=agent_id,
        target_role=AgentRole.DESIGN,
        finding_ids=("F-00000001",),
        prior_output_hash="a" * 64,
    )
    assert task is not None
    return task


class TestRevisionTask:
    """Verify the persisted RevisionTask contract."""

    def test_frozen(self) -> None:
        task = RevisionTask(
            revision_id="revision-1",
            run_id="run-1",
            target_agent_id="agent-1",
            target_role=AgentRole.DESIGN,
            round_number=1,
            finding_ids=("F-00000001",),
            prior_output_hash="b" * 64,
        )
        with pytest.raises(AttributeError):
            task.revision_id = "revision-2"  # type: ignore[misc]

    def test_round_trip_snapshot(self) -> None:
        task = RevisionTask(
            revision_id="revision-abc",
            run_id="run-abc",
            target_agent_id="design-agent-v1",
            target_role=AgentRole.TEST_STRATEGY,
            round_number=2,
            finding_ids=("F-00000001", "F-00000002"),
            prior_output_hash="c" * 64,
        )
        snapshot = task.as_dict()
        assert snapshot["revision_id"] == "revision-abc"
        assert snapshot["round_number"] == 2
        assert snapshot["finding_ids"] == ["F-00000001", "F-00000002"]
        assert snapshot["status"] == "scheduled"

    def test_revision_id_is_distinct_from_finding_ids(self) -> None:
        """Revision IDs and finding IDs are different namespaces."""
        controller = RevisionController(RevisionPolicy(max_total_rounds=1))
        controller.begin_round()
        task = _task(controller)
        assert task.revision_id.startswith("revision-")
        assert not task.revision_id.startswith("F-")
        assert all(finding_id.startswith("F-") for finding_id in task.finding_ids)


class TestRevisionController:
    """Verify round-based revision lifecycle management."""

    def test_default_policy(self) -> None:
        policy = RevisionPolicy()
        controller = RevisionController(policy)
        assert controller.policy is policy
        assert controller.exhausted is False
        assert controller.current_round == 0
        assert controller.tasks == ()

    # ── Revisable roles ─────────────────────────────────────────────

    def test_is_revisable_for_revisable_roles(self) -> None:
        """DESIGN, TEST_STRATEGY, RISK_REVIEW are revisable by default."""
        policy = RevisionPolicy()
        controller = RevisionController(policy)

        assert controller.is_revisable(AgentRole.DESIGN) is True
        assert controller.is_revisable(AgentRole.TEST_STRATEGY) is True
        assert controller.is_revisable(AgentRole.RISK_REVIEW) is True

    def test_is_not_revisable_for_non_revisable_roles(self) -> None:
        """REPOSITORY_ANALYST, SYNTHESIS, REVIEW are not revisable by default."""
        policy = RevisionPolicy()
        controller = RevisionController(policy)

        assert controller.is_revisable(AgentRole.REPOSITORY_ANALYST) is False
        assert controller.is_revisable(AgentRole.SYNTHESIS) is False
        assert controller.is_revisable(AgentRole.REVIEW) is False

    # ── Rounds ──────────────────────────────────────────────────────

    def test_begin_round_increments_once_per_round(self) -> None:
        controller = RevisionController(RevisionPolicy(max_total_rounds=3))
        assert controller.begin_round() == 1
        assert controller.begin_round() == 2
        assert controller.begin_round() == 3
        assert controller.exhausted is True
        assert controller.begin_round() is None

    def test_multiple_tasks_share_one_round(self) -> None:
        """Multiple target agents in one round do not consume extra rounds."""
        controller = RevisionController(RevisionPolicy(max_total_rounds=2))
        assert controller.begin_round() == 1
        first = _task(controller, "design-agent-v1")
        second = _task(controller, "test-strategy-agent-v1")
        assert first.round_number == 1
        assert second.round_number == 1
        assert controller.current_round == 1
        assert controller.exhausted is False

    def test_creates_task_requires_open_round(self) -> None:
        controller = RevisionController(RevisionPolicy())
        with pytest.raises(ValueError, match="begin_round"):
            controller.create_revision_task(
                run_id="run-1",
                round_number=1,
                target_agent_id="a1",
                target_role=AgentRole.DESIGN,
                finding_ids=("F-00000001",),
                prior_output_hash="a" * 64,
            )

    def test_returns_none_for_non_revisable_role(self) -> None:
        controller = RevisionController(RevisionPolicy())
        controller.begin_round()
        task = controller.create_revision_task(
            run_id="run-1",
            round_number=1,
            target_agent_id="review-agent-v1",
            target_role=AgentRole.REVIEW,
            finding_ids=("F-00000001",),
            prior_output_hash="a" * 64,
        )
        assert task is None
        assert controller.current_round == 1

    def test_task_requires_finding_ids(self) -> None:
        controller = RevisionController(RevisionPolicy())
        controller.begin_round()
        with pytest.raises(ValueError, match="at least one finding"):
            controller.create_revision_task(
                run_id="run-1",
                round_number=1,
                target_agent_id="a1",
                target_role=AgentRole.DESIGN,
                finding_ids=(),
                prior_output_hash="a" * 64,
            )

    # ── Lifecycle transitions ───────────────────────────────────────

    def test_task_lifecycle_scheduled_running_completed(self) -> None:
        controller = RevisionController(RevisionPolicy(max_total_rounds=1))
        controller.begin_round()
        task = _task(controller)
        controller.mark_running(task.revision_id)
        running = controller.tasks[0]
        assert running.status == "running"
        controller.mark_completed(task.revision_id, result_artifact="revision-results.json")
        completed = controller.tasks[0]
        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert completed.result_artifact == "revision-results.json"

    def test_task_lifecycle_failed(self) -> None:
        controller = RevisionController(RevisionPolicy(max_total_rounds=1))
        controller.begin_round()
        task = _task(controller)
        controller.mark_failed(task.revision_id, reason="TEST_FAILURE")
        assert controller.tasks[0].status == "failed"
        assert controller.tasks[0].failure_reason == "TEST_FAILURE"

    def test_unknown_revision_id_rejected(self) -> None:
        controller = RevisionController(RevisionPolicy())
        with pytest.raises(ValueError, match="Unknown revision task"):
            controller.mark_completed("revision-nope", result_artifact="x.json")

    # ── exhausted property ──────────────────────────────────────────

    def test_exhausted_with_zero_max_rounds(self) -> None:
        controller = RevisionController(RevisionPolicy(max_total_rounds=0))
        assert controller.exhausted is True
        assert controller.begin_round() is None

    def test_exhausted_after_reaching_limit(self) -> None:
        controller = RevisionController(RevisionPolicy(max_total_rounds=1))
        assert controller.exhausted is False
        assert controller.begin_round() == 1
        assert controller.exhausted is True

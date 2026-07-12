"""Tests for RevisionController, RevisionTask, and RevisionResult."""

from __future__ import annotations

import pytest

from specflow.agents.models import AgentRole, RevisionPolicy
from specflow.coordinator.revision import RevisionController, RevisionResult, RevisionTask


class TestRevisionTask:
    """Verify RevisionTask frozen dataclass."""

    def test_frozen(self) -> None:
        task = RevisionTask(
            revision_id="r1",
            target_agent_id="agent-1",
            target_role=AgentRole.DESIGN,
            review_finding="Missing edge cases",
            instruction="Add edge case handling",
            round_number=1,
        )
        with pytest.raises(AttributeError):
            task.revision_id = "r2"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        task = RevisionTask(
            revision_id="rev-abc",
            target_agent_id="design-agent-v1",
            target_role=AgentRole.TEST_STRATEGY,
            review_finding="Not enough test cases",
            instruction="Add 3 more boundary tests",
            round_number=2,
        )
        assert task.revision_id == "rev-abc"
        assert task.target_agent_id == "design-agent-v1"
        assert task.target_role is AgentRole.TEST_STRATEGY
        assert task.review_finding == "Not enough test cases"
        assert task.instruction == "Add 3 more boundary tests"
        assert task.round_number == 2


class TestRevisionResult:
    """Verify RevisionResult frozen dataclass."""

    def test_frozen(self) -> None:
        task = RevisionTask(
            revision_id="r1",
            target_agent_id="a1",
            target_role=AgentRole.DESIGN,
            review_finding="f",
            instruction="fix it",
            round_number=1,
        )
        result = RevisionResult(task=task, output={"fixed": True}, success=True)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_successful_result(self) -> None:
        task = RevisionTask(
            revision_id="r1",
            target_agent_id="a1",
            target_role=AgentRole.DESIGN,
            review_finding="f",
            instruction="fix it",
            round_number=1,
        )
        result = RevisionResult(task=task, output={"data": "revised"}, success=True)
        assert result.task is task
        assert result.output == {"data": "revised"}
        assert result.success is True


class TestRevisionController:
    """Verify revision lifecycle management."""

    # ── Default policy ──────────────────────────────────────────────

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

    def test_custom_revisable_roles(self) -> None:
        """Only explicitly listed roles are revisable."""
        policy = RevisionPolicy(
            max_total_rounds=2,
            revisable_roles=frozenset({AgentRole.REPOSITORY_ANALYST}),
        )
        controller = RevisionController(policy)
        assert controller.is_revisable(AgentRole.REPOSITORY_ANALYST) is True
        assert controller.is_revisable(AgentRole.DESIGN) is False

    # ── Creating revision tasks for revisable roles ─────────────────

    def test_creates_task_for_revisable_role(self) -> None:
        """Creating a task for a revisable role returns a RevisionTask."""
        policy = RevisionPolicy(max_total_rounds=3)
        controller = RevisionController(policy)

        task = controller.create_revision_task(
            target_agent_id="design-agent-v1",
            target_role=AgentRole.DESIGN,
            finding="Missing error handling",
            instruction="Add try/except blocks",
        )

        assert task is not None
        assert task.target_agent_id == "design-agent-v1"
        assert task.target_role is AgentRole.DESIGN
        assert task.review_finding == "Missing error handling"
        assert task.instruction == "Add try/except blocks"
        assert task.round_number == 1
        assert isinstance(task.revision_id, str)
        assert len(task.revision_id) > 0

    def test_create_multiple_tasks_increments_round(self) -> None:
        """Each successful creation increments current_round."""
        policy = RevisionPolicy(max_total_rounds=3)
        controller = RevisionController(policy)

        t1 = controller.create_revision_task("a1", AgentRole.DESIGN, "f1", "i1")
        assert t1 is not None
        assert t1.round_number == 1
        assert controller.current_round == 1

        t2 = controller.create_revision_task("a2", AgentRole.TEST_STRATEGY, "f2", "i2")
        assert t2 is not None
        assert t2.round_number == 2
        assert controller.current_round == 2

    def test_tasks_are_recorded(self) -> None:
        """Created tasks are accessible via the tasks property."""
        policy = RevisionPolicy(max_total_rounds=3)
        controller = RevisionController(policy)

        controller.create_revision_task("a1", AgentRole.DESIGN, "f1", "i1")
        controller.create_revision_task("a2", AgentRole.TEST_STRATEGY, "f2", "i2")

        assert len(controller.tasks) == 2
        assert controller.tasks[0].target_agent_id == "a1"
        assert controller.tasks[1].target_agent_id == "a2"

    # ── Returns None for non-revisable roles ────────────────────────

    def test_returns_none_for_non_revisable_role(self) -> None:
        """Creating a task for REVIEW (non-revisable) returns None."""
        policy = RevisionPolicy()
        controller = RevisionController(policy)

        task = controller.create_revision_task(
            target_agent_id="review-agent-v1",
            target_role=AgentRole.REVIEW,
            finding="Some issue",
            instruction="Fix it",
        )

        assert task is None
        # round should not have incremented
        assert controller.current_round == 0

    def test_non_revisable_does_not_consume_round(self) -> None:
        """Attempting a task for non-revisable role does not increment round."""
        policy = RevisionPolicy(max_total_rounds=2)
        controller = RevisionController(policy)

        t1 = controller.create_revision_task("d1", AgentRole.DESIGN, "f", "i")
        assert t1 is not None
        assert controller.current_round == 1

        # Non-revisable — round should stay at 1
        t2 = controller.create_revision_task("r1", AgentRole.REVIEW, "f", "i")
        assert t2 is None
        assert controller.current_round == 1

    # ── Respects max_total_rounds ───────────────────────────────────

    def test_respects_max_total_rounds(self) -> None:
        """After max_total_rounds tasks, create_revision_task returns None."""
        policy = RevisionPolicy(max_total_rounds=2)
        controller = RevisionController(policy)

        t1 = controller.create_revision_task("a1", AgentRole.DESIGN, "f", "i")
        assert t1 is not None
        assert controller.exhausted is False

        t2 = controller.create_revision_task("a2", AgentRole.TEST_STRATEGY, "f", "i")
        assert t2 is not None
        # After exactly max_total_rounds, exhausted is True (2 >= 2)
        assert controller.exhausted is True

        t3 = controller.create_revision_task("a3", AgentRole.RISK_REVIEW, "f", "i")
        assert t3 is None

    def test_exhausted_with_zero_max_rounds(self) -> None:
        """With max_total_rounds=0, everything is exhausted immediately."""
        policy = RevisionPolicy(max_total_rounds=0)
        controller = RevisionController(policy)

        assert controller.exhausted is True
        task = controller.create_revision_task("a1", AgentRole.DESIGN, "f", "i")
        assert task is None

    # ── exhausted property ──────────────────────────────────────────

    def test_exhausted_property_initial(self) -> None:
        policy = RevisionPolicy(max_total_rounds=5)
        controller = RevisionController(policy)
        assert controller.exhausted is False

    def test_exhausted_after_reaching_limit(self) -> None:
        policy = RevisionPolicy(max_total_rounds=1)
        controller = RevisionController(policy)

        assert controller.exhausted is False
        controller.create_revision_task("a1", AgentRole.DESIGN, "f", "i")
        assert controller.exhausted is True

    def test_exhausted_not_reset_by_failed_attempt(self) -> None:
        """Non-revisable attempts don't change exhausted state."""
        policy = RevisionPolicy(max_total_rounds=1)
        controller = RevisionController(policy)

        controller.create_revision_task("a1", AgentRole.DESIGN, "f", "i")
        assert controller.exhausted is True

        # Attempt non-revisable
        result = controller.create_revision_task("r1", AgentRole.REVIEW, "f", "i")
        assert result is None
        assert controller.exhausted is True

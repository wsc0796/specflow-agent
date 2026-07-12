"""Static validator for compiled structural plans.

Runs structural consistency checks **before** any handoff or runtime
execution takes place.  Checks are purely static — no payloads or
AgentHandoff instances are needed.
"""

from __future__ import annotations

from typing import Any

from specflow.plan.exceptions import PlanValidationError
from specflow.plan.models import CompiledStructuralPlan


class PlanValidator:
    """Structural validator for :class:`CompiledStructuralPlan`.

    Checks performed:

    * **Agent set identity** — the set of agents in ``plan.agents`` must
      match the set of agent IDs across all execution stages exactly.
    * **No duplicates across stages** — each agent appears in at most one
      execution stage.
    * **No intra-stage dependencies** — two agents in the same execution
      stage must not have a dependency edge between them.
    * **Schema ID existence** — when a ``schema_registry`` is provided,
      every agent's ``input_schema_id`` and ``output_schema_id`` must be
      registered.
    """

    def validate(
        self,
        plan: CompiledStructuralPlan,
        schema_registry: Any = None,
    ) -> None:
        """Run all static checks on *plan*.

        Parameters
        ----------
        plan:
            The compiled structural plan to validate.
        schema_registry:
            Optional schema registry.  When provided every agent's
            ``input_schema_id`` and ``output_schema_id`` are checked
            for existence.

        Raises
        ------
        PlanValidationError
            On the first check that fails.
        """
        self._check_agent_set_identity(plan)
        self._check_no_duplicate_across_stages(plan)
        self._check_no_intra_stage_dependencies(plan)
        if schema_registry is not None:
            self._check_schema_ids(plan, schema_registry)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_agent_set_identity(plan: CompiledStructuralPlan) -> None:
        """Every agent in *plan.agents* appears in *execution_stages* and vice versa."""
        plan_ids = {a.agent_id for a in plan.agents}
        stage_ids: set[str] = set()
        for stage in plan.execution_stages:
            stage_ids.update(stage)

        missing_in_stages = plan_ids - stage_ids
        missing_in_plan = stage_ids - plan_ids

        if missing_in_stages:
            raise PlanValidationError(
                f"Agents missing from execution stages: {sorted(missing_in_stages)}"
            )
        if missing_in_plan:
            raise PlanValidationError(
                f"Agents in stages not declared in plan.agents: {sorted(missing_in_plan)}"
            )

    @staticmethod
    def _check_no_duplicate_across_stages(plan: CompiledStructuralPlan) -> None:
        """No agent ID appears in more than one execution stage."""
        seen: set[str] = set()
        for stage in plan.execution_stages:
            for agent_id in stage:
                if agent_id in seen:
                    raise PlanValidationError(
                        f"Agent {agent_id!r} appears in multiple execution stages"
                    )
                seen.add(agent_id)

    @staticmethod
    def _check_no_intra_stage_dependencies(
        plan: CompiledStructuralPlan,
    ) -> None:
        """No dependency edge has both endpoints in the same stage."""
        # Build a set of (dependent, dependency) pairs
        dep_pairs: set[tuple[str, str]] = set()
        for dep in plan.dependencies:
            for dep_id in dep.depends_on:
                dep_pairs.add((dep.agent_id, dep_id))

        for stage in plan.execution_stages:
            stage_set = frozenset(stage)
            for a_id, depends_on_id in dep_pairs:
                if a_id in stage_set and depends_on_id in stage_set:
                    raise PlanValidationError(
                        f"Intra-stage dependency: {a_id!r} depends on "
                        f"{depends_on_id!r} but both are in the same stage"
                    )

    @staticmethod
    def _check_schema_ids(
        plan: CompiledStructuralPlan,
        schema_registry: Any,
    ) -> None:
        """Every agent's input/output schema ID exists in the registry."""
        for agent in plan.agents:
            try:
                schema_registry.get(agent.input_schema_id)
            except Exception:
                raise PlanValidationError(
                    f"Agent {agent.agent_id!r} references unknown "
                    f"input_schema_id={agent.input_schema_id!r}"
                )
            try:
                schema_registry.get(agent.output_schema_id)
            except Exception:
                raise PlanValidationError(
                    f"Agent {agent.agent_id!r} references unknown "
                    f"output_schema_id={agent.output_schema_id!r}"
                )

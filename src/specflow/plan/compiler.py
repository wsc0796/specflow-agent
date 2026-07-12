from __future__ import annotations

from collections import deque

from specflow.plan.exceptions import PlanCompilationError
from specflow.plan.hash_utils import (
    StructuralHashInput,
    compute_structure_hash,
)
from specflow.plan.models import CompiledStructuralPlan, StructuralDelegationSpec


class PlanCompiler:
    """Compiles a StructuralDelegationSpec into a CompiledStructuralPlan.

    Performs DAG validation (cycle detection, missing agent references),
    topological sorting via Kahn's algorithm, and grouping into execution
    stages suitable for parallel execution.
    """

    def compile(self, spec: StructuralDelegationSpec) -> CompiledStructuralPlan:
        agent_ids = {a.agent_id for a in spec.agents}
        dep_map: dict[str, set[str]] = {}
        for d in spec.dependencies:
            if d.agent_id not in agent_ids:
                raise PlanCompilationError(
                    f"Dependency references unknown agent_id={d.agent_id!r}"
                )
            for dep_id in d.depends_on:
                if dep_id not in agent_ids:
                    raise PlanCompilationError(
                        f"Agent {d.agent_id!r} depends on unknown agent_id={dep_id!r}"
                    )
            dep_map[d.agent_id] = set(d.depends_on)

        # Every agent must have a dep entry (possibly empty)
        for a_id in agent_ids:
            dep_map.setdefault(a_id, set())

        # Kahn's algorithm for topological sort + cycle detection + stage grouping
        in_degree: dict[str, int] = {a_id: 0 for a_id in agent_ids}
        for a_id, deps in dep_map.items():
            in_degree[a_id] = len(deps)

        # Build reverse adjacency: who depends on me?
        reverse_deps: dict[str, list[str]] = {a_id: [] for a_id in agent_ids}
        for a_id, deps in dep_map.items():
            for dep_id in deps:
                reverse_deps[dep_id].append(a_id)

        queue: deque[str] = deque()
        for a_id, degree in in_degree.items():
            if degree == 0:
                queue.append(a_id)

        visited_count = 0
        stages: list[list[str]] = []

        while queue:
            current_stage: list[str] = []
            # Process all nodes with current in_degree == 0 in this pass
            stage_queue: deque[str] = deque()
            while queue:
                node = queue.popleft()
                current_stage.append(node)
                stage_queue.append(node)
                visited_count += 1

            # Decrease in_degree for successors
            while stage_queue:
                node = stage_queue.popleft()
                for successor in reverse_deps[node]:
                    in_degree[successor] -= 1
                    if in_degree[successor] == 0:
                        queue.append(successor)

            stages.append(sorted(current_stage))

        if visited_count != len(agent_ids):
            raise PlanCompilationError(
                "Cycle detected in agent dependency graph"
            )

        execution_stages = tuple(tuple(stage) for stage in stages)

        # Build hash input
        hash_input = StructuralHashInput(
            agents=[
                {
                    "agent_id": a.agent_id,
                    "role": a.role.value if hasattr(a.role, "value") else str(a.role),
                    "version": a.version,
                }
                for a in spec.agents
            ],
            dependencies=[
                {
                    "agent_id": d.agent_id,
                    "depends_on": sorted(d.depends_on),
                }
                for d in spec.dependencies
            ],
            stages=[list(stage) for stage in execution_stages],
            revision_policy={
                "max_total_rounds": spec.revision_policy.max_total_rounds,
                "revisable_roles": sorted(
                    r.value if hasattr(r, "value") else str(r)
                    for r in spec.revision_policy.revisable_roles
                ),
                "final_authority_role": (
                    spec.revision_policy.final_authority_role.value
                    if hasattr(spec.revision_policy.final_authority_role, "value")
                    else str(spec.revision_policy.final_authority_role)
                ),
            },
            constraints=[
                {
                    "agent_id": c.agent_id,
                    "max_execution_seconds": c.max_execution_seconds,
                    "max_token_budget": c.max_token_budget,
                    "max_revision_rounds": c.max_revision_rounds,
                }
                for c in spec.constraints
            ],
        )
        structure_hash = compute_structure_hash(hash_input)

        return CompiledStructuralPlan(
            plan_id=spec.plan_id,
            agents=spec.agents,
            dependencies=spec.dependencies,
            execution_stages=execution_stages,
            constraints=spec.constraints,
            revision_policy=spec.revision_policy,
            structure_hash=structure_hash,
        )

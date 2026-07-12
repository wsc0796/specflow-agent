# M6 Multi-Agent Orchestration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade SpecFlow from a deterministic single-pipeline Agent Workflow to a Controlled Multi-Agent Orchestration System with 6 specialist agents, parallel execution, bounded revision, and A/B evaluation.

**Architecture:** New multi-agent pipeline coexists with legacy linear pipeline via `--mode multi-agent`. `StructuralDelegationSpec` (rule-layer source) → `PlanCompiler` → `CompiledStructuralPlan` → `SemanticPlanEnricher` (LLM) → `PlanValidator` → `EffectiveDelegationPlan` → `MultiAgentScheduler` → `HandoffFactory` → `HandoffValidator` → agent execution.

**Tech Stack:** Python 3.12, Pydantic v2, existing `specflow` packages (`trace`, `llm`, `tools`, `workers`).

**Spec:** `docs/superpowers/specs/2026-07-12-m6-multi-agent-design.md`

---

## File Structure (New Files)

```
src/specflow/schema/
├── __init__.py
├── exceptions.py
└── registry.py                    # SchemaRegistry + freeze

src/specflow/agents/
├── __init__.py
├── exceptions.py
├── models.py                      # AgentRole, AgentIdentity, AgentConstraints,
│                                  #   AgentDependency, RevisionPolicy
├── protocol.py                    # Agent protocol
├── registry.py                    # AgentRegistry
├── repository_analyst.py          # RepositoryAnalystAgent
├── design.py                      # DesignAgent
├── test_strategy.py               # TestStrategyAgent
├── risk_review.py                  # RiskReviewAgent
├── synthesis.py                   # SynthesisAgent
└── review.py                      # ReviewAgent

src/specflow/plan/
├── __init__.py
├── exceptions.py
├── models.py                      # StructuralDelegationSpec, CompiledStructuralPlan,
│                                  #   EnrichmentStatus, EnrichmentProvenance,
│                                  #   SemanticTaskBrief, AgentTask, EffectiveDelegationPlan
├── hash_utils.py                  # Canonical hash (structure_hash, semantic_brief_hash,
│                                  #   effective_plan_hash)
├── planner.py                     # DeterministicPlanner (generates StructuralDelegationSpec)
├── compiler.py                    # PlanCompiler (spec → compiled, computes execution_stages)
├── enricher.py                    # SemanticPlanEnricher (LLM fills SemanticTaskBrief)
└── validator.py                   # PlanValidator (static checks only)

src/specflow/handoff/
├── __init__.py
├── exceptions.py
├── models.py                      # AgentHandoff, AgentMessage
└── validator.py                   # HandoffValidator (runtime checks)

src/specflow/coordinator/
├── __init__.py
├── exceptions.py
├── state_machine.py               # MultiAgentWorkflowState + transitions
├── scheduler.py                   # MultiAgentScheduler (stage-sequential, intra-stage parallel)
├── revision.py                    # RevisionController (max 1 round, revision_exhausted)
└── coordinator.py                 # Coordinator (wires 6 components)

tests/
├── test_schema_registry.py
├── test_agent_models.py
├── test_agent_registry.py
├── test_structural_plan.py
├── test_plan_compiler.py
├── test_plan_hash.py
├── test_semantic_enricher.py
├── test_effective_plan.py
├── test_plan_validator.py
├── test_handoff_models.py
├── test_handoff_validator.py
├── test_scheduler.py
├── test_revision_controller.py
├── test_coordinator.py
├── test_multi_agent_state_machine.py
├── test_agent_trace.py
├── test_agent_implementations.py
├── test_cli_multi_agent.py
└── test_evaluation_multi_agent.py
```

## Modified Files

```
src/specflow/trace/models.py       # Add AgentTraceSpan
src/specflow/trace/__init__.py     # Export AgentTraceSpan
src/specflow/cli.py                # Add --mode multi-agent
src/specflow/runner.py             # (extend) or new runner_multi.py
```

---

### Task 1 (T-024): SchemaRegistry + Agent Base Models

**Files:**
- Create: `src/specflow/schema/__init__.py`
- Create: `src/specflow/schema/exceptions.py`
- Create: `src/specflow/schema/registry.py`
- Create: `src/specflow/agents/__init__.py`
- Create: `src/specflow/agents/exceptions.py`
- Create: `src/specflow/agents/models.py`
- Create: `tests/test_schema_registry.py`
- Create: `tests/test_agent_models.py`

- [ ] **Step 1: Write SchemaRegistry exception tests**

```python
# tests/test_schema_registry.py
import pytest
from pydantic import BaseModel

from specflow.schema.exceptions import (
    RegistryFrozenError,
    SchemaConflictError,
    SchemaNotFoundError,
)
from specflow.schema.registry import SchemaRegistry


class SampleInput(BaseModel):
    name: str
    value: int


class SampleOutput(BaseModel):
    result: str


class DifferentModel(BaseModel):
    other: str


class TestSchemaRegistryRegistration:
    def test_register_and_retrieve_model(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        assert reg.get("agent/test/v1/input") is SampleInput

    def test_idempotent_same_model(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        reg.register("agent/test/v1/input", SampleInput)  # no-op

    def test_conflict_different_model_same_id(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        with pytest.raises(SchemaConflictError):
            reg.register("agent/test/v1/input", DifferentModel)

    def test_reject_non_basemodel(self):
        reg = SchemaRegistry()
        with pytest.raises(ValueError):
            reg.register("agent/test/v1/input", dict)  # type: ignore

    def test_get_nonexistent_raises(self):
        reg = SchemaRegistry()
        with pytest.raises(SchemaNotFoundError):
            reg.get("nonexistent/schema/v1")

    def test_freeze_prevents_registration(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        reg.freeze()
        assert reg.frozen is True
        with pytest.raises(RegistryFrozenError):
            reg.register("agent/test/v2/input", SampleInput)

    def test_export_json_schema(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        exported = reg.export_json_schema("agent/test/v1/input")
        assert exported["type"] == "object"
        assert "name" in exported["properties"]

    def test_list_schemas(self):
        reg = SchemaRegistry()
        reg.register("agent/a/v1/input", SampleInput)
        reg.register("agent/b/v1/output", SampleOutput)
        ids = reg.list_schemas()
        assert "agent/a/v1/input" in ids
        assert "agent/b/v1/output" in ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_schema_registry.py -v`
Expected: FAIL (import errors — files don't exist yet)

- [ ] **Step 3: Create SchemaRegistry exceptions**

```python
# src/specflow/schema/exceptions.py

class SchemaError(Exception):
    """Base exception for schema-related errors."""


class SchemaConflictError(SchemaError):
    """Same schema_id registered with a different model."""


class SchemaNotFoundError(SchemaError):
    """Schema ID not found in registry."""


class RegistryFrozenError(SchemaError):
    """Attempted to register after freeze()."""
```

- [ ] **Step 4: Create SchemaRegistry**

```python
# src/specflow/schema/registry.py
from __future__ import annotations

from pydantic import BaseModel

from specflow.schema.exceptions import (
    RegistryFrozenError,
    SchemaConflictError,
    SchemaNotFoundError,
)


class SchemaRegistry:
    """Stable, versioned schema registry. Pydantic models are the truth source."""

    def __init__(self) -> None:
        self._models: dict[str, type[BaseModel]] = {}
        self._frozen = False

    def register(self, schema_id: str, model: type[BaseModel]) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot register after freeze()")
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise ValueError(
                f"Schema model must be a BaseModel subclass, got {type(model)}"
            )
        if not schema_id.strip():
            raise ValueError("schema_id must not be empty")
        existing = self._models.get(schema_id)
        if existing is not None:
            if existing is model:
                return  # idempotent
            raise SchemaConflictError(
                f"Schema ID '{schema_id}' already registered with a different model"
            )
        self._models[schema_id] = model

    def get(self, schema_id: str) -> type[BaseModel]:
        try:
            return self._models[schema_id]
        except KeyError:
            raise SchemaNotFoundError(f"Schema ID not found: {schema_id}")

    def export_json_schema(self, schema_id: str) -> dict[str, object]:
        model = self.get(schema_id)
        return model.model_json_schema()

    def list_schemas(self) -> tuple[str, ...]:
        return tuple(sorted(self._models.keys()))

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen
```

- [ ] **Step 5: Create `__init__.py`**

```python
# src/specflow/schema/__init__.py
from specflow.schema.exceptions import (
    RegistryFrozenError,
    SchemaConflictError,
    SchemaNotFoundError,
    SchemaError,
)
from specflow.schema.registry import SchemaRegistry

__all__ = [
    "RegistryFrozenError",
    "SchemaConflictError",
    "SchemaError",
    "SchemaNotFoundError",
    "SchemaRegistry",
]
```

- [ ] **Step 6: Run SchemaRegistry tests**

Run: `uv run pytest tests/test_schema_registry.py -v`
Expected: PASS

- [ ] **Step 7: Write Agent base model tests**

```python
# tests/test_agent_models.py
import pytest

from specflow.agents.exceptions import AgentModelValidationError
from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)


class TestAgentRole:
    def test_all_roles_defined(self):
        assert AgentRole.REPOSITORY_ANALYST == "repository_analyst"
        assert AgentRole.DESIGN == "design"
        assert AgentRole.TEST_STRATEGY == "test_strategy"
        assert AgentRole.RISK_REVIEW == "risk_review"
        assert AgentRole.SYNTHESIS == "synthesis"
        assert AgentRole.REVIEW == "review"


class TestAgentIdentity:
    def test_valid_identity(self):
        ident = AgentIdentity(
            agent_id="design-agent-v1",
            role=AgentRole.DESIGN,
            version="1.0.0",
            description="Designs technical solutions",
            prompt_id="prompts/design/v1",
            prompt_version="1.0.0",
            input_schema_id="agent/design/v1/input",
            output_schema_id="agent/design/v1/output",
            tool_permissions=frozenset({"list_files", "read_file"}),
        )
        assert ident.agent_id == "design-agent-v1"
        assert ident.role == AgentRole.DESIGN

    def test_empty_agent_id_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentIdentity(
                agent_id="",
                role=AgentRole.DESIGN,
                version="1.0.0",
                description="test",
                prompt_id="p/v1",
                prompt_version="1.0.0",
                input_schema_id="a/d/v1/input",
                output_schema_id="a/d/v1/output",
                tool_permissions=frozenset(),
            )

    def test_empty_version_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentIdentity(
                agent_id="agent-v1",
                role=AgentRole.DESIGN,
                version="",
                description="test",
                prompt_id="p/v1",
                prompt_version="1.0.0",
                input_schema_id="a/d/v1/input",
                output_schema_id="a/d/v1/output",
                tool_permissions=frozenset(),
            )


class TestAgentDependency:
    def test_valid_dependency(self):
        dep = AgentDependency(
            agent_id="design-agent-v1",
            depends_on=frozenset({"repo-analyst-v1"}),
        )
        assert dep.agent_id == "design-agent-v1"
        assert "repo-analyst-v1" in dep.depends_on

    def test_self_dependency_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentDependency(
                agent_id="design-agent-v1",
                depends_on=frozenset({"design-agent-v1"}),
            )


class TestAgentConstraints:
    def test_valid_constraints(self):
        c = AgentConstraints(
            agent_id="design-agent-v1",
            max_execution_seconds=60,
            max_token_budget=4096,
            max_revision_rounds=1,
            allowed_paths=(),
            denied_paths=(),
        )
        assert c.max_execution_seconds == 60

    def test_negative_timeout_raises(self):
        with pytest.raises(AgentModelValidationError):
            AgentConstraints(
                agent_id="design-agent-v1",
                max_execution_seconds=-1,
                max_token_budget=4096,
                max_revision_rounds=1,
                allowed_paths=(),
                denied_paths=(),
            )


class TestRevisionPolicy:
    def test_defaults(self):
        policy = RevisionPolicy()
        assert policy.max_total_rounds == 1
        assert AgentRole.DESIGN in policy.revisable_roles
        assert AgentRole.TEST_STRATEGY in policy.revisable_roles
        assert AgentRole.RISK_REVIEW in policy.revisable_roles
        assert policy.final_authority_role == AgentRole.REVIEW

    def test_is_role_revisable(self):
        policy = RevisionPolicy()
        assert policy.is_revisable(AgentRole.DESIGN) is True
        assert policy.is_revisable(AgentRole.SYNTHESIS) is False
        assert policy.is_revisable(AgentRole.REVIEW) is False
```

- [ ] **Step 8: Run agent model tests to verify they fail**

Run: `uv run pytest tests/test_agent_models.py -v`
Expected: FAIL (import errors)

- [ ] **Step 9: Create agent exceptions**

```python
# src/specflow/agents/exceptions.py

class AgentError(Exception):
    """Base exception for agent-related errors."""


class AgentModelValidationError(AgentError, ValueError):
    """Agent model validation failed."""


class AgentNotFoundError(AgentError):
    """Agent not found in registry."""


class DuplicateAgentError(AgentError):
    """Agent with same identity already registered."""


class AgentExecutionError(AgentError):
    """Agent execution failed."""
```

- [ ] **Step 10: Create agent base models**

```python
# src/specflow/agents/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from specflow.agents.exceptions import AgentModelValidationError


class AgentRole(StrEnum):
    REPOSITORY_ANALYST = "repository_analyst"
    DESIGN = "design"
    TEST_STRATEGY = "test_strategy"
    RISK_REVIEW = "risk_review"
    SYNTHESIS = "synthesis"
    REVIEW = "review"


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    role: AgentRole
    version: str
    description: str
    prompt_id: str
    prompt_version: str
    input_schema_id: str
    output_schema_id: str
    tool_permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if not isinstance(self.role, AgentRole):
            raise AgentModelValidationError("role must be an AgentRole")
        if not self.version.strip():
            raise AgentModelValidationError("version must not be empty")
        if not self.description.strip():
            raise AgentModelValidationError("description must not be empty")
        if not self.prompt_id.strip():
            raise AgentModelValidationError("prompt_id must not be empty")
        if not self.prompt_version.strip():
            raise AgentModelValidationError("prompt_version must not be empty")
        if not self.input_schema_id.strip():
            raise AgentModelValidationError("input_schema_id must not be empty")
        if not self.output_schema_id.strip():
            raise AgentModelValidationError("output_schema_id must not be empty")


@dataclass(frozen=True)
class AgentDependency:
    """Logical truth source for execution order."""

    agent_id: str
    depends_on: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if self.agent_id in self.depends_on:
            raise AgentModelValidationError(
                f"Agent cannot depend on itself: {self.agent_id}"
            )


@dataclass(frozen=True)
class AgentConstraints:
    agent_id: str
    max_execution_seconds: int
    max_token_budget: int
    max_revision_rounds: int = 1
    allowed_paths: tuple[str, ...] = ()
    denied_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if self.max_execution_seconds <= 0:
            raise AgentModelValidationError("max_execution_seconds must be positive")
        if self.max_token_budget <= 0:
            raise AgentModelValidationError("max_token_budget must be positive")
        if self.max_revision_rounds < 0:
            raise AgentModelValidationError("max_revision_rounds must be non-negative")


@dataclass(frozen=True)
class RevisionPolicy:
    max_total_rounds: int = 1
    revisable_roles: frozenset[AgentRole] = field(
        default_factory=lambda: frozenset({
            AgentRole.DESIGN,
            AgentRole.TEST_STRATEGY,
            AgentRole.RISK_REVIEW,
        })
    )
    final_authority_role: AgentRole = AgentRole.REVIEW

    def __post_init__(self) -> None:
        if self.max_total_rounds < 0:
            raise AgentModelValidationError("max_total_rounds must be non-negative")
        if not isinstance(self.final_authority_role, AgentRole):
            raise AgentModelValidationError(
                "final_authority_role must be an AgentRole"
            )

    def is_revisable(self, role: AgentRole) -> bool:
        return role in self.revisable_roles
```

- [ ] **Step 11: Create agents `__init__.py`**

```python
# src/specflow/agents/__init__.py
from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)

__all__ = [
    "AgentConstraints",
    "AgentDependency",
    "AgentIdentity",
    "AgentRole",
    "RevisionPolicy",
]
```

- [ ] **Step 12: Run agent model tests**

Run: `uv run pytest tests/test_agent_models.py tests/test_schema_registry.py -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add src/specflow/schema/ src/specflow/agents/__init__.py src/specflow/agents/exceptions.py src/specflow/agents/models.py tests/test_schema_registry.py tests/test_agent_models.py
git commit -m "feat(multi-agent): add SchemaRegistry and agent base models"
```

---

### Task 2 (T-025): Structural Plan + PlanCompiler + Hash Utilities

**Files:**
- Create: `src/specflow/plan/__init__.py`
- Create: `src/specflow/plan/exceptions.py`
- Create: `src/specflow/plan/models.py`
- Create: `src/specflow/plan/planner.py`
- Create: `src/specflow/plan/compiler.py`
- Create: `src/specflow/plan/hash_utils.py`
- Create: `tests/test_structural_plan.py`
- Create: `tests/test_plan_compiler.py`
- Create: `tests/test_plan_hash.py`

- [ ] **Step 1: Write plan hash utility tests**

```python
# tests/test_plan_hash.py
import pytest

from specflow.plan.hash_utils import (
    EffectivePlanHashV1,
    StructuralHashInput,
    compute_effective_plan_hash,
    compute_semantic_brief_hash,
    compute_structure_hash,
)


class TestStructureHash:
    def test_same_input_same_hash(self):
        input1 = StructuralHashInput(
            agents=[{"agent_id": "a1", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a1", "depends_on": []}],
            stages=[["a1"]],
            revision_policy={"max_total_rounds": 1},
        )
        input2 = StructuralHashInput(
            agents=[{"agent_id": "a1", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a1", "depends_on": []}],
            stages=[["a1"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(input1) == compute_structure_hash(input2)

    def test_different_agent_sets_different_hash(self):
        input1 = StructuralHashInput(
            agents=[{"agent_id": "a1", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a1", "depends_on": []}],
            stages=[["a1"]],
            revision_policy={"max_total_rounds": 1},
        )
        input2 = StructuralHashInput(
            agents=[{"agent_id": "a2", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a2", "depends_on": []}],
            stages=[["a2"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(input1) != compute_structure_hash(input2)

    def test_frozenset_order_independent(self):
        dep_a = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["a", "b"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        dep_b = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["b", "a"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(dep_a) == compute_structure_hash(dep_b)


class TestSemanticBriefHash:
    def test_same_semantics_same_hash(self):
        briefs = [{"agent_id": "a1", "task_description": "do X"}]
        assert compute_semantic_brief_hash(briefs) == compute_semantic_brief_hash(briefs)

    def test_different_description_different_hash(self):
        assert compute_semantic_brief_hash(
            [{"agent_id": "a1", "task_description": "do X"}]
        ) != compute_semantic_brief_hash(
            [{"agent_id": "a1", "task_description": "do Y"}]
        )


class TestEffectivePlanHash:
    def test_identical_inputs_same_hash(self):
        h1 = compute_effective_plan_hash("abc123", "def456")
        h2 = compute_effective_plan_hash("abc123", "def456")
        assert h1 == h2

    def test_format_is_sha256_hex(self):
        result = compute_effective_plan_hash("abc", "def")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)
```

- [ ] **Step 2: Run hash tests to verify they fail**

Run: `uv run pytest tests/test_plan_hash.py -v`
Expected: FAIL (import errors)

- [ ] **Step 3: Create plan exceptions and hash utilities**

```python
# src/specflow/plan/exceptions.py

class PlanError(Exception):
    """Base exception for plan-related errors."""


class PlanCompilationError(PlanError):
    """PlanCompiler failed to compile the structural plan."""


class PlanValidationError(PlanError):
    """PlanValidator found an invalid plan."""


class PlanEnrichmentError(PlanError):
    """SemanticPlanEnricher failed."""
```

```python
# src/specflow/plan/hash_utils.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StructuralHashInput:
    agents: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    stages: list[list[str]]
    revision_policy: dict[str, Any]
    constraints: list[dict[str, Any]] = field(default_factory=list)


def _canonical_json(obj: Any) -> bytes:
    """Serialize to canonical JSON: sorted keys, compact, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_structure_hash(input_: StructuralHashInput) -> str:
    payload: dict[str, Any] = {
        "agents": sorted(input_.agents, key=lambda a: a["agent_id"]),
        "dependencies": sorted(input_.dependencies, key=lambda d: d["agent_id"]),
        "stages": [
            sorted(stage) for stage in input_.stages
        ],
        "revision_policy": input_.revision_policy,
        "constraints": sorted(input_.constraints, key=lambda c: c["agent_id"]),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_semantic_brief_hash(briefs: list[dict[str, Any]]) -> str:
    payload = sorted(
        [
            {
                "agent_id": b["agent_id"],
                "task_description": b.get("task_description", ""),
                "analysis_focus": sorted(b.get("analysis_focus", [])),
                "evaluation_hints": sorted(b.get("evaluation_hints", [])),
                "repository_scope_hint": b.get("repository_scope_hint", ""),
            }
            for b in briefs
        ],
        key=lambda b: b["agent_id"],
    )
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_effective_plan_hash(structure_hash: str, semantic_brief_hash: str) -> str:
    payload: dict[str, str] = {
        "hash_version": "specflow-effective-plan-v1",
        "structure_hash": structure_hash,
        "semantic_brief_hash": semantic_brief_hash,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()
```

- [ ] **Step 4: Run hash tests**

Run: `uv run pytest tests/test_plan_hash.py -v`
Expected: PASS

- [ ] **Step 5: Write structural plan tests**

```python
# tests/test_structural_plan.py
import pytest

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.exceptions import PlanCompilationError
from specflow.plan.compiler import PlanCompiler
from specflow.plan.models import CompiledStructuralPlan, StructuralDelegationSpec
from specflow.plan.planner import DeterministicPlanner, FIXED_TOPOLOGY_AGENTS


def _make_spec() -> StructuralDelegationSpec:
    planner = DeterministicPlanner()
    return planner.generate()


class TestStructuralDelegationSpec:
    def test_spec_has_no_compiled_fields(self):
        spec = _make_spec()
        assert not hasattr(spec, "execution_stages")
        assert not hasattr(spec, "structure_hash")

    def test_spec_has_all_agents(self):
        spec = _make_spec()
        roles = {a.role for a in spec.agents}
        assert AgentRole.REPOSITORY_ANALYST in roles
        assert AgentRole.DESIGN in roles
        assert AgentRole.TEST_STRATEGY in roles
        assert AgentRole.RISK_REVIEW in roles
        assert AgentRole.SYNTHESIS in roles
        assert AgentRole.REVIEW in roles

    def test_spec_has_correct_dependencies(self):
        spec = _make_spec()
        dep_map = {d.agent_id: d.depends_on for d in spec.dependencies}
        repo_id = _agent_id_for_role(spec, AgentRole.REPOSITORY_ANALYST)
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        test_id = _agent_id_for_role(spec, AgentRole.TEST_STRATEGY)
        risk_id = _agent_id_for_role(spec, AgentRole.RISK_REVIEW)
        synthesis_id = _agent_id_for_role(spec, AgentRole.SYNTHESIS)
        review_id = _agent_id_for_role(spec, AgentRole.REVIEW)

        assert dep_map[design_id] == frozenset({repo_id})
        assert dep_map[test_id] == frozenset({repo_id})
        assert dep_map[risk_id] == frozenset({repo_id})
        assert dep_map[synthesis_id] == frozenset({design_id, test_id, risk_id})
        assert dep_map[review_id] == frozenset({synthesis_id})


class TestCompiledStructuralPlan:
    def test_compiler_produces_compiled_plan(self):
        spec = _make_spec()
        compiler = PlanCompiler()
        compiled = compiler.compile(spec)
        assert isinstance(compiled, CompiledStructuralPlan)
        assert len(compiled.structure_hash) == 64

    def test_execution_stages_correct_order(self):
        spec = _make_spec()
        compiled = PlanCompiler().compile(spec)
        assert len(compiled.execution_stages) == 4
        # Stage 1: RepositoryAnalyst (1 agent)
        assert len(compiled.execution_stages[0]) == 1
        # Stage 2: Design, Test, Risk (3 agents, parallel)
        assert len(compiled.execution_stages[1]) == 3
        # Stage 3: Synthesis (1 agent)
        assert len(compiled.execution_stages[2]) == 1
        # Stage 4: Review (1 agent)
        assert len(compiled.execution_stages[3]) == 1

    def test_parallel_agents_same_stage(self):
        spec = _make_spec()
        compiled = PlanCompiler().compile(spec)
        stage2 = compiled.execution_stages[1]
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        test_id = _agent_id_for_role(spec, AgentRole.TEST_STRATEGY)
        risk_id = _agent_id_for_role(spec, AgentRole.RISK_REVIEW)
        assert design_id in stage2
        assert test_id in stage2
        assert risk_id in stage2

    def test_rejects_cyclic_dependency(self):
        spec = _make_spec()
        # Create a cycle: design depends on test, test depends on design
        deps = list(spec.dependencies)
        design_id = _agent_id_for_role(spec, AgentRole.DESIGN)
        test_id = _agent_id_for_role(spec, AgentRole.TEST_STRATEGY)
        deps.append(AgentDependency(agent_id=design_id, depends_on=frozenset({test_id})))
        bad_spec = StructuralDelegationSpec(
            plan_id=spec.plan_id,
            agents=spec.agents,
            dependencies=tuple(deps),
            constraints=spec.constraints,
            revision_policy=spec.revision_policy,
        )
        with pytest.raises(PlanCompilationError):
            PlanCompiler().compile(bad_spec)


def _agent_id_for_role(spec: StructuralDelegationSpec, role: AgentRole) -> str:
    for a in spec.agents:
        if a.role == role:
            return a.agent_id
    raise ValueError(f"No agent with role {role}")
```

- [ ] **Step 6: Run structural plan tests to verify they fail**

Run: `uv run pytest tests/test_structural_plan.py -v`
Expected: FAIL (PlanCompiler and DeterministicPlanner don't exist yet)

- [ ] **Step 7: Create plan base models**

```python
# src/specflow/plan/models.py
from __future__ import annotations

from dataclasses import dataclass

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    RevisionPolicy,
)


@dataclass(frozen=True)
class StructuralDelegationSpec:
    """Rule-layer source plan — before compilation. MUST NOT contain compiled fields."""

    plan_id: str
    agents: tuple[AgentIdentity, ...]
    dependencies: tuple[AgentDependency, ...]
    constraints: tuple[AgentConstraints, ...]
    revision_policy: RevisionPolicy


@dataclass(frozen=True)
class CompiledStructuralPlan:
    """Compiler output — adds execution_stages and structure_hash."""

    plan_id: str
    agents: tuple[AgentIdentity, ...]
    dependencies: tuple[AgentDependency, ...]
    execution_stages: tuple[tuple[str, ...], ...]
    constraints: tuple[AgentConstraints, ...]
    revision_policy: RevisionPolicy
    structure_hash: str
```

- [ ] **Step 8: Create DeterministicPlanner**

```python
# src/specflow/plan/planner.py
from __future__ import annotations

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.models import StructuralDelegationSpec

FIXED_TOPOLOGY_AGENTS: tuple[AgentIdentity, ...] = (
    AgentIdentity(
        agent_id="repository-analyst-agent-v1",
        role=AgentRole.REPOSITORY_ANALYST,
        version="1.0.0",
        description="Analyzes repository structure and maps requirements to code evidence",
        prompt_id="prompts/repository-analyst/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/repository-analyst/v1/input",
        output_schema_id="agent/repository-analyst/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="design-agent-v1",
        role=AgentRole.DESIGN,
        version="1.0.0",
        description="Generates architecture, interface, data, and implementation plans",
        prompt_id="prompts/design/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/design/v1/input",
        output_schema_id="agent/design/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="test-strategy-agent-v1",
        role=AgentRole.TEST_STRATEGY,
        version="1.0.0",
        description="Independently generates comprehensive test strategies",
        prompt_id="prompts/test-strategy/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/test-strategy/v1/input",
        output_schema_id="agent/test-strategy/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="risk-review-agent-v1",
        role=AgentRole.RISK_REVIEW,
        version="1.0.0",
        description="Independently identifies security, concurrency, consistency, migration, and rollback risks",
        prompt_id="prompts/risk-review/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/risk-review/v1/input",
        output_schema_id="agent/risk-review/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="synthesis-agent-v1",
        role=AgentRole.SYNTHESIS,
        version="1.0.0",
        description="Merges outputs from multiple specialist agents, resolves conflicts",
        prompt_id="prompts/synthesis/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/synthesis/v1/input",
        output_schema_id="agent/synthesis/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
    AgentIdentity(
        agent_id="review-agent-v1",
        role=AgentRole.REVIEW,
        version="1.0.0",
        description="Performs final review and issues PASS/REJECT with structured findings",
        prompt_id="prompts/review/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/review/v1/input",
        output_schema_id="agent/review/v1/output",
        tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
    ),
)


class DeterministicPlanner:
    """Generates StructuralDelegationSpec from the fixed MVP topology."""

    def generate(self, plan_id: str = "m6-fixed-topology-v1") -> StructuralDelegationSpec:
        repo_id = "repository-analyst-agent-v1"
        design_id = "design-agent-v1"
        test_id = "test-strategy-agent-v1"
        risk_id = "risk-review-agent-v1"
        synthesis_id = "synthesis-agent-v1"
        review_id = "review-agent-v1"

        dependencies: tuple[AgentDependency, ...] = (
            AgentDependency(agent_id=design_id, depends_on=frozenset({repo_id})),
            AgentDependency(agent_id=test_id, depends_on=frozenset({repo_id})),
            AgentDependency(agent_id=risk_id, depends_on=frozenset({repo_id})),
            AgentDependency(
                agent_id=synthesis_id,
                depends_on=frozenset({design_id, test_id, risk_id}),
            ),
            AgentDependency(agent_id=review_id, depends_on=frozenset({synthesis_id})),
        )

        constraints: tuple[AgentConstraints, ...] = tuple(
            AgentConstraints(
                agent_id=a.agent_id,
                max_execution_seconds=120,
                max_token_budget=8192,
                max_revision_rounds=1,
            )
            for a in FIXED_TOPOLOGY_AGENTS
        )

        return StructuralDelegationSpec(
            plan_id=plan_id,
            agents=FIXED_TOPOLOGY_AGENTS,
            dependencies=dependencies,
            constraints=constraints,
            revision_policy=RevisionPolicy(),
        )
```

- [ ] **Step 9: Create PlanCompiler**

```python
# src/specflow/plan/compiler.py
from __future__ import annotations

from collections import deque

from specflow.agents.models import AgentDependency
from specflow.plan.exceptions import PlanCompilationError
from specflow.plan.hash_utils import StructuralHashInput, compute_structure_hash
from specflow.plan.models import CompiledStructuralPlan, StructuralDelegationSpec


class PlanCompiler:
    """Compiles StructuralDelegationSpec → CompiledStructuralPlan."""

    def compile(self, spec: StructuralDelegationSpec) -> CompiledStructuralPlan:
        self._validate_dag(spec)
        stages = self._compute_execution_stages(spec)
        structure_hash = compute_structure_hash(
            StructuralHashInput(
                agents=[
                    {
                        "agent_id": a.agent_id,
                        "role": a.role.value,
                        "version": a.version,
                        "prompt_id": a.prompt_id,
                        "prompt_version": a.prompt_version,
                        "input_schema_id": a.input_schema_id,
                        "output_schema_id": a.output_schema_id,
                        "tool_permissions": sorted(a.tool_permissions),
                    }
                    for a in spec.agents
                ],
                dependencies=[
                    {"agent_id": d.agent_id, "depends_on": sorted(d.depends_on)}
                    for d in spec.dependencies
                ],
                stages=[list(stage) for stage in stages],
                revision_policy={
                    "max_total_rounds": spec.revision_policy.max_total_rounds,
                    "revisable_roles": sorted(
                        r.value for r in spec.revision_policy.revisable_roles
                    ),
                    "final_authority_role": spec.revision_policy.final_authority_role.value,
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
        )
        return CompiledStructuralPlan(
            plan_id=spec.plan_id,
            agents=spec.agents,
            dependencies=spec.dependencies,
            execution_stages=stages,
            constraints=spec.constraints,
            revision_policy=spec.revision_policy,
            structure_hash=structure_hash,
        )

    def _validate_dag(self, spec: StructuralDelegationSpec) -> None:
        agent_ids = {a.agent_id for a in spec.agents}
        dep_map: dict[str, frozenset[str]] = {
            d.agent_id: d.depends_on for d in spec.dependencies
        }

        # Every dependency agent must exist
        for dep in spec.dependencies:
            if dep.agent_id not in agent_ids:
                raise PlanCompilationError(
                    f"Dependency references unknown agent: {dep.agent_id}"
                )
            for d in dep.depends_on:
                if d not in agent_ids:
                    raise PlanCompilationError(
                        f"Agent {dep.agent_id} depends on unknown agent: {d}"
                    )

        # Check for cycles using Kahn's algorithm
        in_degree: dict[str, int] = {aid: 0 for aid in agent_ids}
        for dep in spec.dependencies:
            in_degree[dep.agent_id] = len(dep.depends_on)

        # Agents with no dependency must still have an entry
        for aid in agent_ids:
            if aid not in dep_map:
                dep_map[aid] = frozenset()

        queue = deque([aid for aid, deg in in_degree.items() if deg == 0])
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for aid, deps in dep_map.items():
                if node in deps:
                    in_degree[aid] -= 1
                    if in_degree[aid] == 0:
                        queue.append(aid)

        if visited != len(agent_ids):
            raise PlanCompilationError("Dependency graph contains a cycle")

    def _compute_execution_stages(
        self, spec: StructuralDelegationSpec
    ) -> tuple[tuple[str, ...], ...]:
        agent_ids = {a.agent_id for a in spec.agents}
        dep_map = {d.agent_id: d.depends_on for d in spec.dependencies}
        for aid in agent_ids:
            if aid not in dep_map:
                dep_map[aid] = frozenset()

        stages: list[tuple[str, ...]] = []
        remaining = set(agent_ids)
        completed: set[str] = set()

        while remaining:
            ready = {
                aid
                for aid in remaining
                if dep_map.get(aid, frozenset()).issubset(completed)
            }
            if not ready:
                raise PlanCompilationError(
                    "Cannot resolve execution stages — possible cycle or missing dependency"
                )
            stages.append(tuple(sorted(ready)))
            completed.update(ready)
            remaining -= ready

        return tuple(stages)
```

- [ ] **Step 10: Create plan `__init__.py`**

```python
# src/specflow/plan/__init__.py
from specflow.plan.compiler import PlanCompiler
from specflow.plan.models import CompiledStructuralPlan, StructuralDelegationSpec
from specflow.plan.planner import DeterministicPlanner

__all__ = [
    "CompiledStructuralPlan",
    "DeterministicPlanner",
    "PlanCompiler",
    "StructuralDelegationSpec",
]
```

- [ ] **Step 11: Run all plan tests**

Run: `uv run pytest tests/test_structural_plan.py tests/test_plan_compiler.py tests/test_plan_hash.py -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add src/specflow/plan/ tests/test_structural_plan.py tests/test_plan_compiler.py tests/test_plan_hash.py
git commit -m "feat(multi-agent): add structural plan, compiler, and canonical hash utilities"
```

---

### Task 3 (T-026): Agent Protocol + AgentRegistry + Semantic Enrichment

**Files:**
- Create: `src/specflow/agents/protocol.py`
- Create: `src/specflow/agents/registry.py`
- Modify: `src/specflow/agents/__init__.py`
- Modify: `src/specflow/plan/models.py` (add EnrichmentStatus, EnrichmentProvenance, SemanticTaskBrief)
- Create: `src/specflow/plan/enricher.py`
- Modify: `src/specflow/plan/__init__.py`
- Create: `tests/test_agent_registry.py`
- Create: `tests/test_semantic_enricher.py`

- [ ] **Step 1: Write AgentRegistry tests**

```python
# tests/test_agent_registry.py
import pytest

from specflow.agents.exceptions import AgentNotFoundError, DuplicateAgentError
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.agents.protocol import Agent
from specflow.agents.registry import AgentRegistry


class FakeAgent:
    def __init__(self, identity: AgentIdentity) -> None:
        self.identity = identity

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    @property
    def role(self) -> AgentRole:
        return self.identity.role


def _make_identity(agent_id: str, role: AgentRole) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        role=role,
        version="1.0.0",
        description=f"Agent {agent_id}",
        prompt_id=f"prompts/{role.value}/v1",
        prompt_version="1.0.0",
        input_schema_id=f"agent/{role.value}/v1/input",
        output_schema_id=f"agent/{role.value}/v1/output",
        tool_permissions=frozenset(),
    )


class TestAgentRegistry:
    def test_register_and_retrieve(self):
        reg = AgentRegistry()
        agent = FakeAgent(_make_identity("a1", AgentRole.DESIGN))
        reg.register(agent)
        assert reg.get("a1") is agent

    def test_duplicate_agent_id_raises(self):
        reg = AgentRegistry()
        a1 = FakeAgent(_make_identity("a1", AgentRole.DESIGN))
        a2 = FakeAgent(_make_identity("a1", AgentRole.TEST_STRATEGY))
        reg.register(a1)
        with pytest.raises(DuplicateAgentError):
            reg.register(a2)

    def test_get_nonexistent_raises(self):
        reg = AgentRegistry()
        with pytest.raises(AgentNotFoundError):
            reg.get("nonexistent")

    def test_get_by_role(self):
        reg = AgentRegistry()
        design1 = FakeAgent(_make_identity("design-v1", AgentRole.DESIGN))
        design2 = FakeAgent(_make_identity("design-v2", AgentRole.DESIGN))
        reg.register(design1)
        reg.register(design2)
        result = reg.get_by_role(AgentRole.DESIGN)
        assert len(result) == 2

    def test_list_agents(self):
        reg = AgentRegistry()
        reg.register(FakeAgent(_make_identity("a1", AgentRole.DESIGN)))
        reg.register(FakeAgent(_make_identity("a2", AgentRole.REVIEW)))
        identities = reg.list_agents()
        assert len(identities) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_registry.py -v`
Expected: FAIL

- [ ] **Step 3: Create Agent protocol**

```python
# src/specflow/agents/protocol.py
from __future__ import annotations

from typing import Any, Protocol

from specflow.agents.models import AgentIdentity, AgentRole


class Agent(Protocol):
    """Protocol for all multi-agent implementations."""

    @property
    def agent_id(self) -> str: ...

    @property
    def role(self) -> AgentRole: ...

    @property
    def identity(self) -> AgentIdentity: ...

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent with the given context and return structured output."""
        ...
```

- [ ] **Step 4: Create AgentRegistry**

```python
# src/specflow/agents/registry.py
from __future__ import annotations

from specflow.agents.exceptions import AgentNotFoundError, DuplicateAgentError
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.agents.protocol import Agent


class AgentRegistry:
    """Registry for multi-agent identities. Allows multiple agents per role."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        aid = agent.agent_id
        if aid in self._agents:
            raise DuplicateAgentError(f"Agent already registered: {aid}")
        self._agents[aid] = agent

    def get(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")

    def get_by_role(self, role: AgentRole) -> tuple[Agent, ...]:
        return tuple(a for a in self._agents.values() if a.role == role)

    def list_agents(self) -> tuple[AgentIdentity, ...]:
        return tuple(a.identity for a in self._agents.values())
```

- [ ] **Step 5: Run agent registry tests**

Run: `uv run pytest tests/test_agent_registry.py -v`
Expected: PASS

- [ ] **Step 6: Extend plan models with enrichment types**

```python
# Append to src/specflow/plan/models.py

from enum import Enum


class EnrichmentStatus(str, Enum):
    ENRICHED = "enriched"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class EnrichmentProvenance:
    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    trace_id: str
    generated_at: str


@dataclass(frozen=True)
class SemanticTaskBrief:
    """Advisory task semantics. MUST NOT carry structural authority."""

    agent_id: str
    task_description: str
    analysis_focus: tuple[str, ...]
    evaluation_hints: tuple[str, ...]
    repository_scope_hint: str

    enrichment_status: EnrichmentStatus
    provenance: EnrichmentProvenance | None

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must not be empty")
        if not isinstance(self.enrichment_status, EnrichmentStatus):
            raise ValueError("enrichment_status must be an EnrichmentStatus")

    @classmethod
    def degraded_default(
        cls,
        *,
        agent_id: str,
        task_description: str,
        analysis_focus: tuple[str, ...] = (),
        evaluation_hints: tuple[str, ...] = (),
        repository_scope_hint: str = "",
    ) -> "SemanticTaskBrief":
        return cls(
            agent_id=agent_id,
            task_description=task_description,
            analysis_focus=analysis_focus,
            evaluation_hints=evaluation_hints,
            repository_scope_hint=repository_scope_hint,
            enrichment_status=EnrichmentStatus.DEGRADED,
            provenance=None,
        )
```

- [ ] **Step 7: Write SemanticPlanEnricher tests**

```python
# tests/test_semantic_enricher.py
from specflow.agents.models import AgentRole
from specflow.plan.enricher import SemanticPlanEnricher
from specflow.plan.models import EnrichmentStatus, SemanticTaskBrief
from specflow.plan.planner import DeterministicPlanner, FIXED_TOPOLOGY_AGENTS


class FakeLLMClient:
    """Returns canned enrichment responses."""
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or []
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        if self.call_count < len(self.responses):
            result = self.responses[self.call_count]
        else:
            result = '{"task_description": "default", "analysis_focus": [], "evaluation_hints": [], "repository_scope_hint": ""}'
        self.call_count += 1
        return result


class FailingLLMClient:
    """Simulates LLM failure."""
    def complete(self, prompt: str) -> str:
        raise RuntimeError("LLM unavailable")


class TestSemanticPlanEnricher:
    def test_enriches_all_agents(self):
        spec = DeterministicPlanner().generate()
        enricher = SemanticPlanEnricher(
            llm_client=FakeLLMClient(),
            model="test-model",
            provider="test-provider",
        )
        briefs = enricher.enrich(spec)
        assert len(briefs) == len(spec.agents)
        for brief in briefs:
            assert brief.agent_id in {a.agent_id for a in spec.agents}

    def test_degraded_on_llm_failure(self):
        spec = DeterministicPlanner().generate()
        enricher = SemanticPlanEnricher(
            llm_client=FailingLLMClient(),
            model="test-model",
            provider="test-provider",
        )
        briefs = enricher.enrich(spec)
        assert len(briefs) == len(spec.agents)
        for brief in briefs:
            assert brief.enrichment_status == EnrichmentStatus.DEGRADED
            assert brief.provenance is None
            assert brief.task_description  # has default description

    def test_enriched_status_on_success(self):
        spec = DeterministicPlanner().generate()
        responses = [
            '{"task_description": "Analyze repo", "analysis_focus": ["structure"], "evaluation_hints": [], "repository_scope_hint": "src/"}'
            for _ in spec.agents
        ]
        enricher = SemanticPlanEnricher(
            llm_client=FakeLLMClient(responses),
            model="test-model",
            provider="test-provider",
        )
        briefs = enricher.enrich(spec)
        for brief in briefs:
            assert brief.enrichment_status == EnrichmentStatus.ENRICHED
            assert brief.provenance is not None

    def test_enrichment_does_not_modify_structural_fields(self):
        spec = DeterministicPlanner().generate()
        enricher = SemanticPlanEnricher(
            llm_client=FakeLLMClient(),
            model="test-model",
            provider="test-provider",
        )
        briefs = enricher.enrich(spec)
        # Agent set must be identical
        enriched_ids = {b.agent_id for b in briefs}
        spec_ids = {a.agent_id for a in spec.agents}
        assert enriched_ids == spec_ids
```

- [ ] **Step 8: Run enricher tests to verify they fail**

Run: `uv run pytest tests/test_semantic_enricher.py -v`
Expected: FAIL

- [ ] **Step 9: Create SemanticPlanEnricher**

```python
# src/specflow/plan/enricher.py
from __future__ import annotations

import json
from datetime import datetime, timezone

from specflow.plan.models import (
    EnrichmentProvenance,
    EnrichmentStatus,
    SemanticTaskBrief,
    StructuralDelegationSpec,
)


class SemanticPlanEnricher:
    """Calls LLM to fill SemanticTaskBrief per agent. Degrades gracefully."""

    def __init__(
        self,
        llm_client: object,
        model: str,
        provider: str,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._provider = provider

    def enrich(self, spec: StructuralDelegationSpec) -> tuple[SemanticTaskBrief, ...]:
        briefs: list[SemanticTaskBrief] = []
        for agent in spec.agents:
            try:
                brief = self._enrich_one(agent.agent_id, agent.role.value)
            except Exception:
                brief = SemanticTaskBrief.degraded_default(
                    agent_id=agent.agent_id,
                    task_description=f"Execute {agent.role.value} analysis for the given requirement.",
                )
            briefs.append(brief)
        return tuple(briefs)

    def _enrich_one(self, agent_id: str, role: str) -> SemanticTaskBrief:
        prompt = self._build_enrichment_prompt(agent_id, role)
        raw = self._llm.complete(prompt)
        data = json.loads(raw)
        now = datetime.now(timezone.utc).isoformat()
        return SemanticTaskBrief(
            agent_id=agent_id,
            task_description=data.get("task_description", ""),
            analysis_focus=tuple(data.get("analysis_focus", [])),
            evaluation_hints=tuple(data.get("evaluation_hints", [])),
            repository_scope_hint=data.get("repository_scope_hint", ""),
            enrichment_status=EnrichmentStatus.ENRICHED,
            provenance=EnrichmentProvenance(
                provider=self._provider,
                model=self._model,
                prompt_id=f"enrichment/{role}/v1",
                prompt_version="1.0.0",
                trace_id="",
                generated_at=now,
            ),
        )

    def _build_enrichment_prompt(self, agent_id: str, role: str) -> str:
        return (
            f"Generate a task brief for agent '{agent_id}' with role '{role}'.\n"
            "Return JSON with: task_description, analysis_focus (array), "
            "evaluation_hints (array), repository_scope_hint."
        )
```

- [ ] **Step 10: Run all T-026 tests**

Run: `uv run pytest tests/test_agent_registry.py tests/test_semantic_enricher.py -v`
Expected: PASS

- [ ] **Step 11: Update `__init__.py` exports**

```python
# Update src/specflow/plan/__init__.py — add new exports
from specflow.plan.models import (
    EnrichmentProvenance,
    EnrichmentStatus,
    SemanticTaskBrief,
)
from specflow.plan.enricher import SemanticPlanEnricher

# Add to __all__
```

- [ ] **Step 12: Commit**

```bash
git add src/specflow/agents/protocol.py src/specflow/agents/registry.py src/specflow/plan/models.py src/specflow/plan/enricher.py tests/test_agent_registry.py tests/test_semantic_enricher.py
git commit -m "feat(multi-agent): add Agent protocol, AgentRegistry, and semantic enrichment"
```

---

### Task 4 (T-027): Effective Plan + PlanValidator + Handoff Models + HandoffValidator

**Files:**
- Modify: `src/specflow/plan/models.py` (add AgentTask, EffectiveDelegationPlan)
- Create: `src/specflow/plan/validator.py`
- Modify: `src/specflow/plan/__init__.py`
- Create: `src/specflow/handoff/__init__.py`
- Create: `src/specflow/handoff/exceptions.py`
- Create: `src/specflow/handoff/models.py`
- Create: `src/specflow/handoff/validator.py`
- Create: `tests/test_effective_plan.py`
- Create: `tests/test_plan_validator.py`
- Create: `tests/test_handoff_models.py`
- Create: `tests/test_handoff_validator.py`

- [ ] **Step 1: Write EffectiveDelegationPlan tests**

```python
# tests/test_effective_plan.py
from specflow.agents.models import AgentRole
from specflow.plan.compiler import PlanCompiler
from specflow.plan.enricher import SemanticPlanEnricher
from specflow.plan.models import (
    AgentTask,
    EffectiveDelegationPlan,
    EnrichmentStatus,
)
from specflow.plan.planner import DeterministicPlanner


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return '{"task_description": "test", "analysis_focus": [], "evaluation_hints": [], "repository_scope_hint": ""}'


class TestEffectiveDelegationPlan:
    def test_build_from_spec_and_briefs(self):
        spec = DeterministicPlanner().generate()
        compiled = PlanCompiler().compile(spec)
        briefs = SemanticPlanEnricher(FakeLLM(), "m", "p").enrich(spec)

        tasks = tuple(
            AgentTask(
                agent_id=b.agent_id,
                role=_role_for_agent(spec, b.agent_id),
                stage=_stage_for_agent(compiled, b.agent_id),
                depends_on=_deps_for_agent(spec, b.agent_id),
                constraints=_constraints_for_agent(spec, b.agent_id),
                task_brief=b,
            )
            for b in briefs
        )

        plan = EffectiveDelegationPlan(
            plan_id=compiled.plan_id,
            run_id="run-001",
            structure_hash=compiled.structure_hash,
            semantic_brief_hash="test-hash",
            effective_plan_hash="test-effective-hash",
            stages=compiled.execution_stages,
            tasks=tasks,
            revision_policy=compiled.revision_policy,
            generated_at="2026-07-12T00:00:00Z",
        )

        assert len(plan.tasks) == 6
        assert plan.enriched is True  # all agents got enrichment

    def test_degraded_agents_derived(self):
        from specflow.plan.models import SemanticTaskBrief

        spec = DeterministicPlanner().generate()
        compiled = PlanCompiler().compile(spec)
        briefs = SemanticPlanEnricher(FakeLLM(), "m", "p").enrich(spec)

        # Make one brief degraded
        brief_list = list(briefs)
        brief_list[0] = SemanticTaskBrief.degraded_default(
            agent_id=brief_list[0].agent_id,
            task_description="fallback",
        )
        briefs = tuple(brief_list)

        tasks = tuple(
            AgentTask(
                agent_id=b.agent_id,
                role=_role_for_agent(spec, b.agent_id),
                stage=_stage_for_agent(compiled, b.agent_id),
                depends_on=_deps_for_agent(spec, b.agent_id),
                constraints=_constraints_for_agent(spec, b.agent_id),
                task_brief=b,
            )
            for b in briefs
        )

        plan = EffectiveDelegationPlan(
            plan_id=compiled.plan_id,
            run_id="run-001",
            structure_hash=compiled.structure_hash,
            semantic_brief_hash="test-hash",
            effective_plan_hash="test-effective-hash",
            stages=compiled.execution_stages,
            tasks=tasks,
            revision_policy=compiled.revision_policy,
            generated_at="2026-07-12T00:00:00Z",
        )

        assert plan.enriched is False
        assert len(plan.degraded_agents) == 1


def _role_for_agent(spec, agent_id: str) -> AgentRole:
    for a in spec.agents:
        if a.agent_id == agent_id:
            return a.role
    raise KeyError(agent_id)


def _stage_for_agent(compiled, agent_id: str) -> int:
    for i, stage in enumerate(compiled.execution_stages):
        if agent_id in stage:
            return i
    raise KeyError(agent_id)


def _deps_for_agent(spec, agent_id: str):
    for d in spec.dependencies:
        if d.agent_id == agent_id:
            return d.depends_on
    return frozenset()


def _constraints_for_agent(spec, agent_id: str):
    for c in spec.constraints:
        if c.agent_id == agent_id:
            return c
    raise KeyError(agent_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_effective_plan.py -v`
Expected: FAIL

- [ ] **Step 3: Add AgentTask and EffectiveDelegationPlan to plan models**

```python
# Append to src/specflow/plan/models.py

@dataclass(frozen=True)
class AgentTask:
    agent_id: str
    role: "AgentRole"
    stage: int
    depends_on: frozenset[str]
    constraints: "AgentConstraints"
    task_brief: SemanticTaskBrief

    @property
    def enriched(self) -> bool:
        return self.task_brief.enrichment_status is EnrichmentStatus.ENRICHED


@dataclass(frozen=True)
class EffectiveDelegationPlan:
    plan_id: str
    run_id: str

    structure_hash: str
    semantic_brief_hash: str
    effective_plan_hash: str

    stages: tuple[tuple[str, ...], ...]
    tasks: tuple[AgentTask, ...]
    revision_policy: "RevisionPolicy"

    generated_at: str

    @property
    def degraded_agents(self) -> tuple[str, ...]:
        return tuple(t.agent_id for t in self.tasks if not t.enriched)

    @property
    def enriched(self) -> bool:
        return len(self.degraded_agents) == 0
```

- [ ] **Step 4: Run effective plan tests**

Run: `uv run pytest tests/test_effective_plan.py -v`
Expected: PASS

- [ ] **Step 5: Write PlanValidator tests and Handoff tests, then implement**

```python
# tests/test_plan_validator.py
import pytest

from specflow.plan.compiler import PlanCompiler
from specflow.plan.exceptions import PlanValidationError
from specflow.plan.planner import DeterministicPlanner
from specflow.plan.validator import PlanValidator


class TestPlanValidator:
    def test_valid_compiled_plan_passes(self):
        spec = DeterministicPlanner().generate()
        compiled = PlanCompiler().compile(spec)
        PlanValidator().validate(compiled)  # no exception

    def test_missing_agent_id_in_stages_fails(self):
        spec = DeterministicPlanner().generate()
        compiled = PlanCompiler().compile(spec)
        # Tamper: remove an agent from stages
        bad_stages = tuple(
            tuple(aid for aid in stage if "design" not in aid)
            for stage in compiled.execution_stages
        )
        bad_compiled = compiled.__class__(
            plan_id=compiled.plan_id,
            agents=compiled.agents,
            dependencies=compiled.dependencies,
            execution_stages=bad_stages,
            constraints=compiled.constraints,
            revision_policy=compiled.revision_policy,
            structure_hash=compiled.structure_hash,
        )
        with pytest.raises(PlanValidationError):
            PlanValidator().validate(bad_compiled)
```

- [ ] **Step 6: Implement PlanValidator and Handoff layer, then run all tests**

```python
# src/specflow/plan/validator.py
from specflow.plan.exceptions import PlanValidationError
from specflow.plan.models import CompiledStructuralPlan


class PlanValidator:
    """Static plan validation — no runtime Handoff instances."""

    def validate(self, plan: CompiledStructuralPlan) -> None:
        agent_ids = {a.agent_id for a in plan.agents}
        stage_agents: set[str] = set()
        for stage in plan.execution_stages:
            for aid in stage:
                if aid in stage_agents:
                    raise PlanValidationError(
                        f"Agent {aid} appears in multiple stages"
                    )
                stage_agents.add(aid)

        if stage_agents != agent_ids:
            missing = agent_ids - stage_agents
            extra = stage_agents - agent_ids
            raise PlanValidationError(
                f"Agent set mismatch: missing={missing}, extra={extra}"
            )

        # No intra-stage dependencies
        for stage in plan.execution_stages:
            stage_set = set(stage)
            for dep in plan.dependencies:
                if dep.agent_id in stage_set:
                    if stage_set & dep.depends_on:
                        raise PlanValidationError(
                            f"Agent {dep.agent_id} depends on agent in same stage"
                        )
```

- [ ] **Step 7: Create Handoff models and validator**

```python
# src/specflow/handoff/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentHandoff:
    handoff_id: str
    from_agent_id: str
    to_agent_id: str
    source_output_schema_id: str
    target_input_schema_id: str
    payload_ref: str
    input_hash: str
    output_hash: str | None = None


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    handoff_id: str
    sender_agent_id: str
    receiver_agent_id: str
    content_type: str
    payload_ref: str
    created_at: str
```

```python
# src/specflow/handoff/validator.py
from specflow.agents.models import AgentIdentity
from specflow.handoff.exceptions import HandoffValidationError
from specflow.handoff.models import AgentHandoff


class HandoffValidator:
    """Runtime handoff validation — has access to actual payloads."""

    def validate(
        self,
        handoff: AgentHandoff,
        sender_identity: AgentIdentity,
        receiver_identity: AgentIdentity,
    ) -> None:
        if handoff.source_output_schema_id != sender_identity.output_schema_id:
            raise HandoffValidationError(
                f"Handoff source_output_schema_id '{handoff.source_output_schema_id}' "
                f"does not match sender output_schema_id '{sender_identity.output_schema_id}'"
            )
        if handoff.target_input_schema_id != receiver_identity.input_schema_id:
            raise HandoffValidationError(
                f"Handoff target_input_schema_id '{handoff.target_input_schema_id}' "
                f"does not match receiver input_schema_id '{receiver_identity.input_schema_id}'"
            )
```

- [ ] **Step 8: Run all T-027 tests**

Run: `uv run pytest tests/test_effective_plan.py tests/test_plan_validator.py tests/test_handoff_models.py tests/test_handoff_validator.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/specflow/plan/models.py src/specflow/plan/validator.py src/specflow/handoff/ tests/test_effective_plan.py tests/test_plan_validator.py tests/test_handoff_models.py tests/test_handoff_validator.py
git commit -m "feat(multi-agent): add effective plan, PlanValidator, handoff models and HandoffValidator"
```

---

### Task 5 (T-028): Coordinator + MultiAgentScheduler + RevisionController

**Files:**
- Create: `src/specflow/coordinator/__init__.py`
- Create: `src/specflow/coordinator/exceptions.py`
- Create: `src/specflow/coordinator/state_machine.py`
- Create: `src/specflow/coordinator/scheduler.py`
- Create: `src/specflow/coordinator/revision.py`
- Create: `src/specflow/coordinator/coordinator.py`
- Create: `tests/test_multi_agent_state_machine.py`
- Create: `tests/test_scheduler.py`
- Create: `tests/test_revision_controller.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write MultiAgentWorkflowState tests**

```python
# tests/test_multi_agent_state_machine.py
import pytest

from specflow.coordinator.exceptions import StateTransitionError
from specflow.coordinator.state_machine import (
    MultiAgentWorkflowState,
    MultiAgentWorkflowEngine,
)


class TestMultiAgentWorkflowState:
    def test_normal_flow(self):
        engine = MultiAgentWorkflowEngine()
        assert engine.current_state == MultiAgentWorkflowState.CREATED

        engine.transition(MultiAgentWorkflowState.PLANNING, "start planning")
        assert engine.current_state == MultiAgentWorkflowState.PLANNING

        engine.transition(MultiAgentWorkflowState.ANALYZING, "analyzing repo")
        assert engine.current_state == MultiAgentWorkflowState.ANALYZING

        engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "parallel specialists")
        assert engine.current_state == MultiAgentWorkflowState.EXECUTING_SPECIALISTS

        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "synthesis")
        assert engine.current_state == MultiAgentWorkflowState.SYNTHESIZING

        engine.transition(MultiAgentWorkflowState.REVIEWING, "review")
        assert engine.current_state == MultiAgentWorkflowState.REVIEWING

        engine.transition(MultiAgentWorkflowState.COMPLETED, "review passed")
        assert engine.current_state == MultiAgentWorkflowState.COMPLETED

    def test_revision_flow(self):
        engine = MultiAgentWorkflowEngine()
        _advance_to(engine, MultiAgentWorkflowState.REVIEWING)

        engine.transition(MultiAgentWorkflowState.REVISING, "review rejected")
        assert engine.current_state == MultiAgentWorkflowState.REVISING

        engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "re-synthesis")
        assert engine.current_state == MultiAgentWorkflowState.SYNTHESIZING

        engine.transition(MultiAgentWorkflowState.REVIEWING, "re-review")
        assert engine.current_state == MultiAgentWorkflowState.REVIEWING

    def test_revision_exhausted_goes_to_completed(self):
        engine = MultiAgentWorkflowEngine()
        engine._revision_count = 1  # simulate revision was done
        _advance_to(engine, MultiAgentWorkflowState.REVIEWING)
        # After exhausted revision, REJECT goes to COMPLETED (not FAILED)
        engine.transition(MultiAgentWorkflowState.REVISING, "second reject")
        # On revision count == max, next transition should go to COMPLETED
        engine._revision_count = 2  # exceeded max_total_rounds=1
        # Force revision_exhausted path
        assert engine._revision_count > engine._max_rounds

    def test_infrastructure_failure_goes_to_failed(self):
        engine = MultiAgentWorkflowEngine()
        _advance_to(engine, MultiAgentWorkflowState.ANALYZING)
        engine.transition(MultiAgentWorkflowState.FAILED, "agent crash")
        assert engine.current_state == MultiAgentWorkflowState.FAILED

    def test_illegal_transition_raises(self):
        engine = MultiAgentWorkflowEngine()
        with pytest.raises(StateTransitionError):
            engine.transition(MultiAgentWorkflowState.COMPLETED, "skip ahead")


def _advance_to(engine: MultiAgentWorkflowEngine, target: MultiAgentWorkflowState) -> None:
    path = [
        MultiAgentWorkflowState.PLANNING,
        MultiAgentWorkflowState.ANALYZING,
        MultiAgentWorkflowState.EXECUTING_SPECIALISTS,
        MultiAgentWorkflowState.SYNTHESIZING,
        MultiAgentWorkflowState.REVIEWING,
    ]
    for state in path:
        if engine.current_state == target:
            return
        engine.transition(state, "test advance")
```

- [ ] **Step 2: Run tests to verify they fail, then implement state machine**

```python
# src/specflow/coordinator/state_machine.py
from __future__ import annotations

from enum import StrEnum

from specflow.coordinator.exceptions import StateTransitionError


class MultiAgentWorkflowState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    ANALYZING = "analyzing"
    EXECUTING_SPECIALISTS = "executing_specialists"
    SYNTHESIZING = "synthesizing"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"


LEGAL_TRANSITIONS: dict[MultiAgentWorkflowState, frozenset[MultiAgentWorkflowState]] = {
    MultiAgentWorkflowState.CREATED: frozenset({MultiAgentWorkflowState.PLANNING}),
    MultiAgentWorkflowState.PLANNING: frozenset(
        {MultiAgentWorkflowState.ANALYZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.ANALYZING: frozenset(
        {MultiAgentWorkflowState.EXECUTING_SPECIALISTS, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.EXECUTING_SPECIALISTS: frozenset(
        {MultiAgentWorkflowState.SYNTHESIZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.SYNTHESIZING: frozenset(
        {MultiAgentWorkflowState.REVIEWING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.REVIEWING: frozenset(
        {
            MultiAgentWorkflowState.COMPLETED,
            MultiAgentWorkflowState.REVISING,
            MultiAgentWorkflowState.FAILED,
        }
    ),
    MultiAgentWorkflowState.REVISING: frozenset(
        {MultiAgentWorkflowState.SYNTHESIZING, MultiAgentWorkflowState.FAILED}
    ),
    MultiAgentWorkflowState.COMPLETED: frozenset(),
    MultiAgentWorkflowState.FAILED: frozenset(),
}

TERMINAL_STATES = frozenset({
    MultiAgentWorkflowState.COMPLETED,
    MultiAgentWorkflowState.FAILED,
})


class MultiAgentWorkflowEngine:
    def __init__(
        self,
        current_state: MultiAgentWorkflowState = MultiAgentWorkflowState.CREATED,
        max_rounds: int = 1,
    ) -> None:
        self._current_state = current_state
        self._max_rounds = max_rounds
        self._revision_count = 0
        self._history: list[tuple[MultiAgentWorkflowState, MultiAgentWorkflowState, str]] = []

    @property
    def current_state(self) -> MultiAgentWorkflowState:
        return self._current_state

    @property
    def revision_count(self) -> int:
        return self._revision_count

    @property
    def revision_exhausted(self) -> bool:
        return self._revision_count > self._max_rounds

    def transition(self, to_state: MultiAgentWorkflowState, reason: str = "") -> None:
        if self._current_state in TERMINAL_STATES:
            raise StateTransitionError(
                f"Workflow is terminal at {self._current_state}"
            )
        if to_state not in LEGAL_TRANSITIONS.get(self._current_state, frozenset()):
            raise StateTransitionError(
                f"Illegal transition: {self._current_state} -> {to_state}"
            )
        if to_state == MultiAgentWorkflowState.REVISING:
            self._revision_count += 1
        self._history.append((self._current_state, to_state, reason))
        self._current_state = to_state
```

- [ ] **Step 3: Write and implement Scheduler, RevisionController, and Coordinator**

```python
# src/specflow/coordinator/scheduler.py
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class StageExecutionResult:
    stage_index: int
    agent_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


class MultiAgentScheduler:
    """Executes stages sequentially, agents within a stage in parallel."""

    def execute(
        self,
        stages: tuple[tuple[str, ...], ...],
        agent_executors: dict[str, object],
        context: dict[str, Any],
    ) -> tuple[StageExecutionResult, ...]:
        results: list[StageExecutionResult] = []
        cumulative_outputs: dict[str, dict[str, Any]] = {}

        for i, stage in enumerate(stages):
            result = StageExecutionResult(stage_index=i)
            result.started_at = datetime.now(timezone.utc).isoformat()

            if len(stage) == 1:
                agent_id = stage[0]
                agent = agent_executors[agent_id]
                ctx = {**context, "prior_outputs": cumulative_outputs}
                output = agent.execute(ctx)
                result.agent_results[agent_id] = output
                cumulative_outputs[agent_id] = output
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(stage)) as executor:
                    futures = {
                        executor.submit(
                            agent_executors[aid].execute,
                            {**context, "prior_outputs": cumulative_outputs},
                        ): aid
                        for aid in stage
                    }
                    for future in concurrent.futures.as_completed(futures):
                        aid = futures[future]
                        try:
                            output = future.result()
                        except Exception as exc:
                            output = {"error": str(exc), "agent_id": aid}
                        result.agent_results[aid] = output
                        cumulative_outputs[aid] = output

            result.completed_at = datetime.now(timezone.utc).isoformat()
            results.append(result)

        return tuple(results)
```

```python
# src/specflow/coordinator/revision.py
from __future__ import annotations

from dataclasses import dataclass

from specflow.agents.models import AgentRole, RevisionPolicy


@dataclass(frozen=True)
class RevisionTask:
    revision_id: str
    target_agent_id: str
    target_role: AgentRole
    review_finding: str
    instruction: str
    round_number: int


@dataclass(frozen=True)
class RevisionResult:
    task: RevisionTask
    output: dict[str, object]
    success: bool


class RevisionController:
    """Enforces max 1 revision round. Business rejection ≠ infrastructure failure."""

    def __init__(self, policy: RevisionPolicy) -> None:
        self._policy = policy
        self._round = 0

    @property
    def exhausted(self) -> bool:
        return self._round > self._policy.max_total_rounds

    @property
    def current_round(self) -> int:
        return self._round

    def is_revisable(self, role: AgentRole) -> bool:
        return self._policy.is_revisable(role)

    def create_revision_task(
        self,
        target_agent_id: str,
        target_role: AgentRole,
        review_finding: str,
        instruction: str,
    ) -> RevisionTask | None:
        if self.exhausted:
            return None
        if not self.is_revisable(target_role):
            return None
        self._round += 1
        return RevisionTask(
            revision_id=f"rev-{self._round}",
            target_agent_id=target_agent_id,
            target_role=target_role,
            review_finding=review_finding,
            instruction=instruction,
            round_number=self._round,
        )
```

```python
# src/specflow/coordinator/coordinator.py
from __future__ import annotations

from datetime import datetime, timezone

from specflow.agents.registry import AgentRegistry
from specflow.coordinator.revision import RevisionController
from specflow.coordinator.scheduler import MultiAgentScheduler
from specflow.coordinator.state_machine import (
    TERMINAL_STATES,
    MultiAgentWorkflowEngine,
    MultiAgentWorkflowState,
)
from specflow.plan.compiler import PlanCompiler
from specflow.plan.enricher import SemanticPlanEnricher
from specflow.plan.hash_utils import compute_effective_plan_hash, compute_semantic_brief_hash
from specflow.plan.models import AgentTask, EffectiveDelegationPlan
from specflow.plan.planner import DeterministicPlanner
from specflow.plan.validator import PlanValidator


class Coordinator:
    """Wires 6 components: Planner, Compiler, Enricher, Validator, Scheduler, RevisionController."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_client: object,
        model: str = "unknown",
        provider: str = "unknown",
    ) -> None:
        self._agent_registry = agent_registry
        self._llm_client = llm_client
        self._model = model
        self._provider = provider
        self._engine = MultiAgentWorkflowEngine()
        self._planner = DeterministicPlanner()
        self._compiler = PlanCompiler()
        self._enricher = SemanticPlanEnricher(llm_client, model, provider)
        self._validator = PlanValidator()
        self._scheduler = MultiAgentScheduler()
        self._revision: RevisionController | None = None

    @property
    def current_state(self) -> MultiAgentWorkflowState:
        return self._engine.current_state

    def plan(self, run_id: str) -> EffectiveDelegationPlan:
        self._engine.transition(MultiAgentWorkflowState.PLANNING, "generating plan")

        spec = self._planner.generate()
        compiled = self._compiler.compile(spec)
        self._validator.validate(compiled)

        briefs = self._enricher.enrich(spec)
        semantic_hash = compute_semantic_brief_hash(
            [
                {
                    "agent_id": b.agent_id,
                    "task_description": b.task_description,
                    "analysis_focus": list(b.analysis_focus),
                    "evaluation_hints": list(b.evaluation_hints),
                    "repository_scope_hint": b.repository_scope_hint,
                }
                for b in briefs
            ]
        )

        tasks = tuple(
            AgentTask(
                agent_id=b.agent_id,
                role=_role_for_agent(spec, b.agent_id),
                stage=_stage_for_agent(compiled, b.agent_id),
                depends_on=_deps_for_agent(spec, b.agent_id),
                constraints=_constraints_for_agent(spec, b.agent_id),
                task_brief=b,
            )
            for b in briefs
        )

        self._revision = RevisionController(compiled.revision_policy)

        return EffectiveDelegationPlan(
            plan_id=compiled.plan_id,
            run_id=run_id,
            structure_hash=compiled.structure_hash,
            semantic_brief_hash=semantic_hash,
            effective_plan_hash=compute_effective_plan_hash(
                compiled.structure_hash, semantic_hash
            ),
            stages=compiled.execution_stages,
            tasks=tasks,
            revision_policy=compiled.revision_policy,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


def _role_for_agent(spec, agent_id: str) -> "AgentRole":
    for a in spec.agents:
        if a.agent_id == agent_id:
            return a.role
    raise KeyError(agent_id)


def _stage_for_agent(compiled, agent_id: str) -> int:
    for i, stage in enumerate(compiled.execution_stages):
        if agent_id in stage:
            return i
    raise KeyError(agent_id)


def _deps_for_agent(spec, agent_id: str) -> frozenset[str]:
    for d in spec.dependencies:
        if d.agent_id == agent_id:
            return d.depends_on
    return frozenset()


def _constraints_for_agent(spec, agent_id: str):
    for c in spec.constraints:
        if c.agent_id == agent_id:
            return c
    raise KeyError(agent_id)
```

- [ ] **Step 4: Run all T-028 tests**

Run: `uv run pytest tests/test_multi_agent_state_machine.py tests/test_scheduler.py tests/test_revision_controller.py tests/test_coordinator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/specflow/coordinator/ tests/test_multi_agent_state_machine.py tests/test_scheduler.py tests/test_revision_controller.py tests/test_coordinator.py
git commit -m "feat(multi-agent): add Coordinator, MultiAgentScheduler, and RevisionController"
```

---

### Task 6 (T-029): Agent Trace Span

**Files:**
- Modify: `src/specflow/trace/models.py` (add AgentTraceSpan)
- Modify: `src/specflow/trace/__init__.py` (export AgentTraceSpan)
- Create: `tests/test_agent_trace.py`

- [ ] **Step 1: Write AgentTraceSpan tests**

```python
# tests/test_agent_trace.py
from specflow.agents.models import AgentRole
from specflow.trace.models import AgentTraceSpan


class TestAgentTraceSpan:
    def test_create_span(self):
        span = AgentTraceSpan(
            span_id="span-001",
            agent_id="design-agent-v1",
            agent_role=AgentRole.DESIGN,
            agent_version="1.0.0",
            parent_span_id="coordinator-span",
            handoff_id="handoff-001",
            stage=1,
            stage_started_at="2026-07-12T00:00:00Z",
            agent_submitted_at="2026-07-12T00:00:01Z",
            agent_completed_at="2026-07-12T00:00:05Z",
            stage_completed_at="2026-07-12T00:00:06Z",
            model="test-model",
            latency_ms=5000,
            input_tokens=500,
            output_tokens=300,
            status="success",
            fallback_level=None,
            tool_calls=("call-1", "call-2"),
            revision_round=0,
            metadata={},
        )
        assert span.agent_id == "design-agent-v1"
        assert span.stage == 1

    def test_as_dict(self):
        span = AgentTraceSpan(
            span_id="span-001",
            agent_id="design-agent-v1",
            agent_role=AgentRole.DESIGN,
            agent_version="1.0.0",
            parent_span_id="coordinator-span",
            handoff_id=None,
            stage=1,
            model="test-model",
            latency_ms=100,
            input_tokens=10,
            output_tokens=20,
            status="success",
            fallback_level=None,
            tool_calls=(),
            revision_round=0,
            metadata={},
        )
        d = span.as_dict()
        assert d["span_id"] == "span-001"
        assert d["agent_role"] == "design"
```

- [ ] **Step 2: Run tests to verify they fail, then implement AgentTraceSpan**

```python
# Append to src/specflow/trace/models.py

@dataclass(frozen=True)
class AgentTraceSpan:
    span_id: str
    agent_id: str
    agent_role: "AgentRole"
    agent_version: str
    parent_span_id: str
    handoff_id: str | None = None
    stage: int = 0
    stage_started_at: str | None = None
    agent_submitted_at: str | None = None
    agent_completed_at: str | None = None
    stage_completed_at: str | None = None
    model: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    status: str = "unknown"
    fallback_level: str | None = None
    tool_calls: tuple[str, ...] = ()
    revision_round: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role.value,
            "agent_version": self.agent_version,
            "parent_span_id": self.parent_span_id,
            "handoff_id": self.handoff_id,
            "stage": self.stage,
            "stage_started_at": self.stage_started_at,
            "agent_submitted_at": self.agent_submitted_at,
            "agent_completed_at": self.agent_completed_at,
            "stage_completed_at": self.stage_completed_at,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "status": self.status,
            "fallback_level": self.fallback_level,
            "tool_calls": list(self.tool_calls),
            "revision_round": self.revision_round,
            "metadata": dict(sorted(self.metadata.items())),
        }
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_agent_trace.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/specflow/trace/models.py src/specflow/trace/__init__.py tests/test_agent_trace.py
git commit -m "feat(multi-agent): add AgentTraceSpan with stage timing fields"
```

---

### Task 7 (T-030): 6 Agent Implementations

**Files:**
- Create: `src/specflow/agents/repository_analyst.py`
- Create: `src/specflow/agents/design.py`
- Create: `src/specflow/agents/test_strategy.py`
- Create: `src/specflow/agents/risk_review.py`
- Create: `src/specflow/agents/synthesis.py`
- Create: `src/specflow/agents/review.py`
- Create: `tests/test_agent_implementations.py`

- [ ] **Step 1: Write agent implementation tests**

```python
# tests/test_agent_implementations.py
from specflow.agents.design import DesignAgent
from specflow.agents.repository_analyst import RepositoryAnalystAgent
from specflow.agents.review import ReviewAgent
from specflow.agents.risk_review import RiskReviewAgent
from specflow.agents.synthesis import SynthesisAgent
from specflow.agents.test_strategy import TestStrategyAgent
from specflow.agents.models import AgentRole


class TestAgentIdentities:
    def test_all_agents_have_unique_ids(self):
        agents = [
            RepositoryAnalystAgent(),
            DesignAgent(),
            TestStrategyAgent(),
            RiskReviewAgent(),
            SynthesisAgent(),
            ReviewAgent(),
        ]
        ids = [a.agent_id for a in agents]
        assert len(ids) == len(set(ids))

    def test_all_agents_have_correct_roles(self):
        assert RepositoryAnalystAgent().role == AgentRole.REPOSITORY_ANALYST
        assert DesignAgent().role == AgentRole.DESIGN
        assert TestStrategyAgent().role == AgentRole.TEST_STRATEGY
        assert RiskReviewAgent().role == AgentRole.RISK_REVIEW
        assert SynthesisAgent().role == AgentRole.SYNTHESIS
        assert ReviewAgent().role == AgentRole.REVIEW

    def test_all_agents_have_identity(self):
        for agent in [
            RepositoryAnalystAgent(),
            DesignAgent(),
            TestStrategyAgent(),
            RiskReviewAgent(),
            SynthesisAgent(),
            ReviewAgent(),
        ]:
            ident = agent.identity
            assert ident.agent_id == agent.agent_id
            assert ident.role == agent.role
            assert ident.version
            assert ident.prompt_id
```

- [ ] **Step 2: Run tests to verify they fail, then implement all 6 agents**

```python
# src/specflow/agents/repository_analyst.py
from __future__ import annotations

from typing import Any

from specflow.agents.models import AgentIdentity, AgentRole
from specflow.agents.protocol import Agent


class RepositoryAnalystAgent:
    def __init__(self) -> None:
        self._identity = AgentIdentity(
            agent_id="repository-analyst-agent-v1",
            role=AgentRole.REPOSITORY_ANALYST,
            version="1.0.0",
            description="Analyzes repository structure and maps requirements to code evidence",
            prompt_id="prompts/repository-analyst/v1",
            prompt_version="1.0.0",
            input_schema_id="agent/repository-analyst/v1/input",
            output_schema_id="agent/repository-analyst/v1/output",
            tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
        )

    @property
    def agent_id(self) -> str:
        return self._identity.agent_id

    @property
    def role(self) -> AgentRole:
        return self._identity.role

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "role": self.role.value, "output": {}}
```

Implement `DesignAgent`, `TestStrategyAgent`, `RiskReviewAgent`, `SynthesisAgent`, `ReviewAgent` with the same pattern — each with the correct `agent_id` and `role` from `FIXED_TOPOLOGY_AGENTS` in `plan/planner.py`.

- [ ] **Step 3: Run agent implementation tests**

Run: `uv run pytest tests/test_agent_implementations.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/specflow/agents/repository_analyst.py src/specflow/agents/design.py src/specflow/agents/test_strategy.py src/specflow/agents/risk_review.py src/specflow/agents/synthesis.py src/specflow/agents/review.py tests/test_agent_implementations.py
git commit -m "feat(multi-agent): add 6 agent implementations"
```

---

### Task 8 (T-031): CLI --mode multi-agent + Runner Integration

**Files:**
- Modify: `src/specflow/cli.py`
- Create: `src/specflow/runner_multi.py`
- Create: `tests/test_cli_multi_agent.py`

- [ ] **Step 1: Write CLI multi-agent tests**

```python
# tests/test_cli_multi_agent.py
from specflow.runner_multi import run_multi_agent


class TestMultiAgentRunner:
    def test_run_multi_agent_mock_mode(self, tmp_path):
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        output = tmp_path / "output"

        exit_code = run_multi_agent(
            repo=repo,
            requirement="Add feature X",
            output=output,
            mock=True,
        )
        # In mock mode, should complete successfully
        assert exit_code == 0


class TestCLIMultiAgentFlag:
    def test_help_shows_multi_agent_mode(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "specflow.cli", "run", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--mode" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail, then implement**

```python
# src/specflow/runner_multi.py
from __future__ import annotations

import json
from pathlib import Path

from specflow.agents.design import DesignAgent
from specflow.agents.repository_analyst import RepositoryAnalystAgent
from specflow.agents.review import ReviewAgent
from specflow.agents.risk_review import RiskReviewAgent
from specflow.agents.synthesis import SynthesisAgent
from specflow.agents.test_strategy import TestStrategyAgent
from specflow.agents.registry import AgentRegistry
from specflow.coordinator.coordinator import Coordinator


def run_multi_agent(
    *,
    repo: Path,
    requirement: str,
    output: Path,
    mock: bool = False,
    provider: str = "mock",
    model: str = "mock-model",
) -> int:
    registry = AgentRegistry()
    registry.register(RepositoryAnalystAgent())
    registry.register(DesignAgent())
    registry.register(TestStrategyAgent())
    registry.register(RiskReviewAgent())
    registry.register(SynthesisAgent())
    registry.register(ReviewAgent())

    coordinator = Coordinator(
        agent_registry=registry,
        llm_client=_make_llm_client(mock),
        model=model,
        provider=provider,
    )

    run_id = f"run-multi-{hash(requirement) & 0xFFFFFFFF:08x}"
    plan = coordinator.plan(run_id)

    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "structure_hash": plan.structure_hash,
        "semantic_brief_hash": plan.semantic_brief_hash,
        "effective_plan_hash": plan.effective_plan_hash,
        "stages": [list(stage) for stage in plan.stages],
        "enriched": plan.enriched,
        "degraded_agents": list(plan.degraded_agents),
    }
    (output / f"{run_id}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return 0


def _make_llm_client(mock: bool) -> object:
    class MockClient:
        def complete(self, prompt: str) -> str:
            return '{"task_description": "mock", "analysis_focus": [], "evaluation_hints": [], "repository_scope_hint": ""}'
    return MockClient()
```

- [ ] **Step 3: Add --mode flag to CLI**

```python
# Modify src/specflow/cli.py — add --mode option to the run command
# ...
# @app.command()
# def run(
#     ...
#     mode: str = typer.Option("legacy", "--mode", help="Execution mode: legacy or multi-agent"),
# ):
#     if mode == "multi-agent":
#         return run_multi_agent(...)
#     else:
#         return run(...)  # existing legacy runner
```

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/test_cli_multi_agent.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify legacy pipeline untouched**

Run: `uv run pytest -v`
Expected: 404+ passed (existing), all new tests pass

- [ ] **Step 6: Commit**

```bash
git add src/specflow/cli.py src/specflow/runner_multi.py tests/test_cli_multi_agent.py
git commit -m "feat(multi-agent): add --mode multi-agent CLI and runner integration"
```

---

### Task 9 (T-032): A/B Evaluation Framework

**Files:**
- Create: `evaluation/cases/multi_agent_case.py`
- Create: `evaluation/multi_agent_runner.py`
- Create: `tests/test_evaluation_multi_agent.py`

- [ ] **Step 1: Write A/B evaluation tests**

```python
# tests/test_evaluation_multi_agent.py
import json
from pathlib import Path

from specflow.evaluation.models import EvaluationCase
from specflow.evaluation.runner import evaluate_case
from specflow.evaluation.rubric import RubricDimension


class TestMultiAgentEvaluation:
    def test_ab_comparison_dimensions(self):
        dimensions = [
            RubricDimension("requirement_coverage", "需求覆盖率", max_score=2),
            RubricDimension("file_reference_rate", "真实文件引用率", max_score=2),
            RubricDimension("risk_coverage", "风险覆盖率", max_score=2),
            RubricDimension("test_completeness", "测试方案完整度", max_score=2),
            RubricDimension("review_findings", "Review 问题发现数", max_score=2),
            RubricDimension("human_edit_reduction", "人工修改量", max_score=2),
            RubricDimension("token_cost", "Token 成本", max_score=2),
            RubricDimension("end_to_end_latency", "端到端耗时", max_score=2),
            RubricDimension("fallback_rate", "Fallback 率", max_score=2),
            RubricDimension("revision_count", "Revision 次数", max_score=2),
        ]
        assert len(dimensions) == 10

    def test_legacy_baseline_still_works(self, tmp_path):
        """Verify legacy pipeline produces artifacts that can be evaluated."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo\n\nPython project.")
        from specflow.runner import run as legacy_run
        output = tmp_path / "legacy-output"
        exit_code = legacy_run(
            repo=repo,
            requirement="Add a search endpoint",
            output=output,
            mock=True,
        )
        assert exit_code in (0, 4)  # 0 = clean, 4 = degraded (known gap)

        manifest_files = list(output.glob("*-manifest.json"))
        assert len(manifest_files) == 1
```

- [ ] **Step 2: Create evaluation case for multi-agent**

```python
# evaluation/cases/multi_agent_case.py
from pathlib import Path
from specflow.evaluation.models import EvaluationCase

MULTI_AGENT_CASE = EvaluationCase(
    case_id="multi-agent-v1",
    description="A/B comparison: legacy linear vs multi-agent on same repo+requirement",
    repo_path=Path("C:/Users/50469/github-projects/sky-takeout-python"),
    requirement="为订单增加超时自动取消功能",
    expected_artifacts_count=10,
    min_dimension_score=1,
    legacy_exit_code_range=(0, 4),
    multi_agent_exit_code_range=(0,),
)
```

- [ ] **Step 3: Run evaluation tests**

Run: `uv run pytest tests/test_evaluation_multi_agent.py -v`
Expected: PASS

- [ ] **Step 4: Run full quality gate**

Run:
```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add evaluation/cases/multi_agent_case.py evaluation/multi_agent_runner.py tests/test_evaluation_multi_agent.py
git commit -m "feat(multi-agent): add A/B evaluation framework for legacy vs multi-agent"
```

---

### Final Quality Gate

After all 9 tasks are complete:

```powershell
uv run pytest -v                          # All tests pass (existing + new)
uv run ruff check .                       # No lint errors
uv run ruff format --check .              # All formatted
git diff --check                           # Clean
git tag -l                                 # v0.1.0 preserved
```

### M6 Closeout Checklist

- [ ] 404 legacy tests still pass
- [ ] Coordinator.plan() generates valid EffectiveDelegationPlan with 3 hashes
- [ ] 6 agents register and execute
- [ ] Design/Test/Risk agents run in parallel (automated test: all submitted before any completes)
- [ ] PlanValidator catches: missing agents, cyclic deps, intra-stage deps
- [ ] HandoffValidator checks source/target schema consistency
- [ ] Revision exhausted → COMPLETED with revision_exhausted=true
- [ ] AgentTraceSpan topology tree is complete (Run → Coordinator → all agents)
- [ ] SchemaRegistry freeze prevents post-startup registration
- [ ] At least one real repo multi-agent run produces valid artifacts
- [ ] A/B evaluation framework compares legacy vs multi-agent on 10 dimensions

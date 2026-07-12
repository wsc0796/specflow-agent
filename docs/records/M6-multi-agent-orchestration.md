# M6 Multi-Agent Orchestration

**Date:** 2026-07-12
**Status:** IN PROGRESS — execution closure pending
**Previous milestone:** M5 Product Vertical Slice (v0.1.0)

## Delivered capabilities

M6 (Multi-Agent Orchestration) delivers a Controlled Multi-Agent Orchestration System
alongside the existing linear pipeline:

1. **SchemaRegistry (T-024):** Versioned Pydantic model registry with freeze semantics,
   object-identity idempotent registration, and JSON Schema export.
2. **Agent Base Models (T-024):** AgentRole (6 roles), AgentIdentity (with prompt/schema
   references), AgentDependency, AgentConstraints, RevisionPolicy — all frozen dataclasses
   with `__post_init__` validation.
3. **Structural Plan + Compiler (T-025):** `StructuralDelegationSpec` (rule-layer source),
   `CompiledStructuralPlan` (compiler output with execution_stages + structure_hash).
   `DeterministicPlanner` generates the fixed 6-agent topology. `PlanCompiler` uses
   Kahn's algorithm for DAG validation, cycle detection, and topological stage grouping.
   Three canonical hash functions (SHA-256 + Canonical JSON).
4. **Agent Protocol + Registry + Enrichment (T-026):** `Agent` Protocol with identity
   and execute contract. `AgentRegistry` with role-based queries. `SemanticPlanEnricher`
   calls LLM to fill `SemanticTaskBrief` per agent; degrades gracefully on failure.
5. **Effective Plan + Handoff (T-027):** `EffectiveDelegationPlan` with 3-layer hash
   lineage. `AgentTask` with derived `enriched` property. `PlanValidator` (static checks).
   `AgentHandoff` with `source_output_schema_id`/`target_input_schema_id`.
   `HandoffValidator` (runtime schema consistency).
6. **Coordinator + Scheduler + Revision (T-028):** `Coordinator` wires 6 components
   (Planner → Compiler → Validator → Enricher → Hash → Plan). `MultiAgentScheduler`
   executes stages sequentially, agents within stage in parallel via ThreadPoolExecutor.
   `RevisionController` enforces max 1 round, `revision_exhausted` semantics.
   `MultiAgentWorkflowEngine` with 9-state machine.
7. **Agent Trace Span (T-029):** `AgentTraceSpan` with stage timing fields
   (stage_started_at, agent_submitted_at, agent_completed_at) for parallel proof.
8. **6 Agent Implementations (T-030):** RepositoryAnalyst, Design, TestStrategy,
   RiskReview, Synthesis, Review — each with unique identity matching fixed topology.
9. **CLI Multi-Agent Mode (T-031):** `specflow run --mode multi-agent` with
   `runner_multi.py`. Legacy `--mode legacy` pipeline untouched (zero changes).
10. **A/B Evaluation Framework (T-032):** 10-dimension comparison rubric
    (requirement coverage, file reference rate, risk coverage, test completeness,
    review findings, human edit reduction, token cost, latency, fallback rate,
    revision count). `ABComparisonResult` with delta calculation.

## Mock Provider validation evidence

- **Provider:** mock
- **Repository:** specflow-agent (self)
- **Requirement:** 为项目添加多Agent编排能力
- **Run ID:** run-multi-c710aa7a
- **Exit code:** 0
- **Manifest:** valid JSON with all 3 hashes (structure, semantic_brief, effective_plan)
- **Stages:** 4 stages — repo-analyst (1) → design/test/risk (3, parallel) → synthesis (1) → review (1)
- **Enrichment:** degraded (all 6 agents used rule-layer defaults in mock mode)

## Architecture

```
specflow run
    ├── --mode legacy (default)  → AgentExecutor → Analyze → Generate → Review
    └── --mode multi-agent       → Coordinator → RepositoryAnalyst
                                                    ↓
                                      Design ‖ TestStrategy ‖ RiskReview
                                                    ↓
                                              SynthesisAgent
                                                    ↓
                                              ReviewAgent → PASS/REJECT
```

## Key Design Decisions

- **M6-ADR-001:** Deterministic Structure + LLM Semantic Enrichment. Rule layer owns
  execution authority (agents, dependencies, stages, budget, permissions). LLM only
  fills advisory `SemanticTaskBrief` fields.
- **Dual pipeline coexistence:** Legacy `AgentExecutor` preserved as T-029 A/B baseline.
  New `MultiAgentWorkflowState` independent of legacy `WorkflowState`.
- **`AgentDependency` is the logical truth source.** `execution_stages` is compiled.
  `ParallelGroup` is a derived view — not an independent structural input.
- **`RevisionPolicy.revisable_roles` uses `AgentRole` enum** — upgrading an agent
  implementation does not require changing the policy.
- **Business rejection ≠ infrastructure failure.** Second REJECT → COMPLETED
  with `revision_exhausted=true`. Only agent crashes, schema failures, and
  scheduler errors enter FAILED.
- **PlanValidator (static) vs HandoffValidator (runtime):** Static checks run before
  execution; runtime handoff checks have access to actual payloads.

## Quality gates

```text
uv run pytest -v:             578 passed, 2 skipped
uv run ruff check .:          All checks passed
uv run ruff format --check .: All files formatted
git diff --check:             clean
```

## Commit IDs

- `707abdc` feat(multi-agent): add SchemaRegistry and agent base models
- `cc8f3ca` fix(multi-agent): validate empty path strings in AgentConstraints
- `2d35d71` feat(multi-agent): add structural plan, compiler, and canonical hash utilities
- `70711eb` fix(multi-agent): add __post_init__ validation and duplicate dependency check
- `f0128dd` feat(multi-agent): add Agent protocol, AgentRegistry, and semantic enrichment
- `fd327d0` fix(multi-agent): remove thread-safe claim, add trace_id uuid, validate EnrichmentProvenance
- `873bacb` feat(multi-agent): add effective plan, PlanValidator, handoff models and HandoffValidator
- `4d809f4` feat(multi-agent): add Coordinator, MultiAgentScheduler, and RevisionController
- `8374a42` feat(multi-agent): add AgentTraceSpan with stage timing fields
- `bd2320d` feat(multi-agent): add 6 agent implementations
- `03990e3` feat(multi-agent): add --mode multi-agent CLI and runner integration
- `a8c3e7e` feat(multi-agent): add A/B evaluation framework for legacy vs multi-agent
- `094dac1` chore: fix ruff import sorting

## Known limits

- No Live Provider multi-agent run yet (mock mode validated only)
- CLI runner uses minimal `ProjectContext` (scanner integration still deferred from M5)
- Chinese keyword extraction on English code repos yields 0 matches (M5 carry-forward)
- `SemanticPlanEnricher` prompt is minimal — real enrichment quality depends on prompt engineering
- Agent `execute()` methods are stubs — real LLM-backed agent execution not yet wired
- A/B comparison has framework but no real evaluation data yet
- `model` field reports "unknown" in manifest when `--model` not explicitly passed
- Same-input `run_id` reuse can leave stale error artifacts (M5 carry-forward)

## Closeout decision

**Not approved.** The planning, registry, scheduler, trace-model and A/B
foundations exist, but the executable runner is still being closed:

- Agent outputs, runtime handoffs, trace topology, and revision artifacts must
  be persisted and verified together.
- The A/B framework must run both modes on the same input and retain evidence.
- At least one real repository case and a Live Provider run remain required.

M6 must remain in progress until those acceptance gates are met. M7 has not begun.

# M6 A/B Comparison — Legacy vs Multi-Agent

**Date:** 2026-07-12
**Repository:** sky-takeout-python
**Requirement:** 为订单增加超时自动取消功能
**Provider:** Mock (both modes — fair comparison)

## Summary

| Dimension | Legacy Mode | Multi-Agent Mode |
|-----------|------------|-----------------|
| **Mode** | Serial 3-worker pipeline | 4-stage with 1 parallel stage |
| **Agents/Workers** | 3 (Analyze, Generate, Review) | 6 (RepoAnalyst, Design, Test, Risk, Synthesis, Review) |
| **Parallel execution** | None | Stage 2: Design ‖ TestStrategy ‖ RiskReview (3 agents) |
| **Agent communication** | Implicit `prior_outputs` | 7 structured AgentHandoffs with schema validation + canonical hash |
| **Trace granularity** | 3 LLM-call records | 8 spans: Run root + Coordinator + 6 AgentTraceSpans (stage timing) |
| **Hash lineage** | Per-artifact hash (analysis/generation/review) | 3-layer plan hash (structure + semantic_brief + effective_plan) |
| **State machine** | 6-state linear | 9-state with bounded Revision support |
| **Input tokens** | 1,384 | Mock (equivalent) |
| **Output tokens** | 488 | Mock (equivalent) |
| **Tool calls** | 3 | 3 |
| **Discovered files** | Mock-limited | 52 |
| **Artifact count** | 10 (analysis, generation, review, manifest, sources, tool-calls, trace, summary, spec, test-plan) | 5 (manifest, agent-outputs, handoffs, traces, sources) |
| **Semantic enrichment** | N/A | 6/6 agents enriched |
| **Review decision** | PASS | PASS |
| **Revision support** | No | Yes (max 1 round, revision_exhausted semantics) |

## Key differentiators

### What Multi-Agent adds

1. **Parallel specialist execution.** Design, Test Strategy, and Risk Review run concurrently,
   reducing end-to-end latency when using real providers.

2. **Structured handoffs.** 7 explicit agent-to-agent messages with schema validation
   (`source_output_schema_id` / `target_input_schema_id`) and canonical JSON hashing.

3. **Agent-level observability.** 6 AgentTraceSpans with `stage_started_at`,
   `agent_submitted_at`, `agent_completed_at` — provable parallel execution.

4. **Bounded revision.** Review can trigger at most 1 revision round targeting specific
   agents. Business rejection (REJECT) ≠ infrastructure failure (FAILED).

5. **Deterministic orchestration.** Coordinator owns execution authority — agent set,
   dependency graph, parallel groups, budgets, and permissions. LLM only enriches
   semantic task descriptions (M6-ADR-001).

### What Legacy still does better

1. **Artifact richness.** 10 artifacts vs 5 — includes Markdown summaries, technical spec,
   and test plan documents.

2. **Simplicity.** 3 workers, 1 file per worker, predictable serial execution.

## Live Provider note

A Live Provider multi-agent run was independently validated on the same repository
with DeepSeek v4-flash: 6/6 agents executed, 7 handoffs, 52 files discovered, PASS.
See `docs/records/M6-multi-agent-orchestration.md` for details.

The Live Provider legacy run on this repository encountered a worker execution failure
and was excluded from this comparison. Mock-mode comparison provides a fair, controlled
baseline for evaluating architectural differences independent of provider behavior.

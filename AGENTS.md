# SpecFlow Agent Development Rules

## Current phase

The project has completed all milestones through M7. M8 independent-review
remediation is complete and T-040/T-041 have closed the execution-policy and
strict payload-schema follow-up work:
- M3: Agent Runtime Foundation
- M4: Agent Workflow
- M5: Tool Use & Repository Intelligence
- M6: Multi-Agent Orchestration (Live Provider validated)
- M7: Evaluation, Demo & Resume (portfolio-ready)

771 passing tests, 3 skipped, 3 known warnings after T-069.
M8 production hardening remains limited to the implemented policy, schema,
fallback, evidence, and artifact boundaries; it does not claim a new
live-provider validation or deployment work. T-056 adds a separately specified
minimal mock-only Run API and SQLite lifecycle slice; T-057 safely classifies
interrupted `running` records on a subsequent single-process startup. It is not
a queue, background-worker, retry/resume system, or production deployment.
T-061 adds a separate append-only reviewer-decision table and bounded review
package endpoints for completed Runs. Reviewer labels are unverified metadata;
this is not authentication, authorization, multi-user workflow or PR automation.
T-063 aligns the final DLP boundary across legacy evidence and multi-agent
outputs. T-064 requires a non-empty ASCII API key at HTTP startup and protects
every route except `/health`, including documentation and OpenAPI routes. It
does not add user identity, authorization, or multi-tenant ownership.
T-065 removes local repository paths from Project API responses and logs legacy
error-artifact write failures without changing safe exit behavior.

All tasks T-001 through T-032 are completed. Implemented:
health endpoint, Project persistence API, safe scanning, deterministic technology
identification with evidence, sanitized PROJECT_CONTEXT.md generation, Prompt
Registry, Context Builder, Token Budget Manager, LLM Client abstraction, Trace
System, Fallback System, deterministic workflow state transitions,
deterministic Agent Executor step advancement, Worker Framework contracts,
Analyze/Generate/Review Workers with structured outputs and honest degraded
fallbacks, Tool Framework, Registry, and Executor contracts,
repository-root-bound read-only tools, OpenAI-compatible Provider,
bounded evidence collection pipeline, `specflow run` CLI with 10 structured
artifacts, deterministic real-repository evaluation layer with safe Live
Artifact import validation and 10-dimension human rubric,
**SchemaRegistry with freeze semantics, 6-agent fixed topology with parallel
execution, Coordinator with Planner→Compiler→Validator→Enricher pipeline,
deterministic structural plan + LLM semantic enrichment (M6-ADR-001),
structured AgentHandoff with schema validation, bounded Revision (max 1 round),
AgentTraceSpan with stage timing, and A/B evaluation framework (10 dimensions).**

The legacy `--mode legacy` pipeline (Analyze→Generate→Review) is preserved
unchanged as the T-029 A/B baseline. Multi-agent mode is accessed via
`--mode multi-agent`.

v1.0.0 is merged to `main` and v1.0.1 reconciles release metadata and CI.
The current local candidate is v1.1.1; it remains untagged and unpublished.
Future work requires a separately frozen task specification.
Future task IDs are not permission to implement future features.

## V5.1 learning contract

This repository is also the sole implementation track for the 30-day AI Agent
engineering study plan in `docs/study/ROADMAP_V5_1.md`. The objective is learner
ownership, not maximum feature throughput.

### Source of truth

Before each study task, read:

1. this file and `docs/00-SPEC-BASELINE.md`;
2. `docs/study/ROADMAP_V5_1.md`;
3. `docs/study/CURRENT.md`;
4. the relevant source, tests, task specification, and existing evidence.

For current implementation facts, source and tests override roadmap assumptions.
For allowed changes, the frozen baseline and mandatory workflow remain binding.
State discrepancies explicitly and mark claims that cannot be proven from the
repository as `unknown`.

### Learning modes

The active mode comes from `docs/study/CURRENT.md`. Do not infer a transition or
run several modes in one response.

- `SURVEY`: read-only source discovery. Report entry points, key symbols,
  inputs/outputs, state changes, dependencies, and exact file/symbol evidence.
  Do not supply a finished architecture conclusion; stop so the learner can
  trace and draw it.
- `TUTOR`: explain only concepts required for the current task and bind every
  explanation to this repository. State the problem solved, where it appears,
  common failure modes, and when not to use it.
- `FAULT`: design 3–5 safe, reproducible faults. Give only the trigger, what the
  learner should predict, legal terminal states, and Test/Trace/Log observation
  points. Do not reveal root cause or repair before the learner records a
  prediction.
- `PATCH`: enter only after the learner explicitly approves a proposed solution.
  Product-code changes additionally require a frozen task specification. List
  files first, make the smallest patch, avoid unrelated refactors, summarize the
  diff, give verification commands, and state remaining evidence gaps.
- `REVIEW`: remain read-only and seek counterexamples across correctness, state,
  failure semantics, retry/idempotency, permission, security, tests, evals, and
  observability. Running code is not sufficient proof of correctness.

`SURVEY`, `TUTOR`, `FAULT`, and `REVIEW` do not permit Codex to edit files.
Updating `CURRENT.md`, evidence cards, or ADRs is an administrative study change:
it requires an explicit user request and does not by itself enter `PATCH`.

### Ownership and evidence

Codex-generated diagrams, answers, bulk code, and unexplained patches do not
count as learner ownership. Ownership evidence must come from the learner's own
call-chain drawing, prediction, reproduced and located fault, design decision,
review of the critical diff, interpretation of Test/Eval results, or closed-note
explanation. Record that evidence under `docs/study/evidence/`.

Preserve these hard boundaries:

- agent-skeleton: at most 4 hours; diet-agent: at most 3 hours; cms-flow: at
  most 3 hours. They never become additional implementation tracks.
- Evaluation data is fixed at 20 Dev + 10 Holdout cases. Do not inspect or tune
  against Holdout before Day 21; after freezing the strategy, run Holdout once
  and do not tune from its result.
- Deterministic Fake Embedding proves only engineering contracts. Semantic
  retrieval claims require a real embedding provider; final end-to-end claims
  require the separately recorded live boundary.
- Thresholds are hypotheses tied to provider/index versions: record T0 on Day 8,
  calibrate only on Dev during Days 15–20, and freeze before Day 21 Holdout.

At the end of each mode, stop and wait for the learner's answer or explicit
transition. Codex may point to evidence and challenge the learner's work, but it
must not replace the act of understanding.

## Mandatory workflow

1. Read `docs/00-SPEC-BASELINE.md`, this file, and the active task spec before editing.
2. Implement one task at a time; keep changes small and testable.
3. Do not add dependencies unless the active task needs them.
4. Before completion, run `uv run pytest -v`, `uv run ruff check .`, and
   `uv run ruff format --check .`.
5. Write a completion report in `docs/reports/` and make one focused Git commit.
6. After every completed task, update its completion report. After every completed
   milestone, add a dated milestone record under `docs/records/` covering delivered
   capabilities, validation evidence, commit IDs, known limits, and the next gate.
7. After the milestone quality gate passes, push its reviewed commits and milestone
   record to the configured GitHub `origin`. Never push without a configured remote
   or after a failed quality gate; report that configuration blocker instead.

## Architecture constraints

- Use the `src/` layout.
- M4 work must proceed one task spec at a time. Do not introduce Worker
  orchestration without an explicit active Worker/Executor task spec.
- Do not add prompts, workers, LLM calls, workflow orchestration, Redis,
  LangGraph, vector stores, MCP, Java support, or automatic code changes before
  their explicitly assigned task.
- Keep HTTP-boundary code separate from future business and persistence layers.
- Never weaken tests merely to make them pass.

## Commands

```powershell
uv sync --all-groups
uv run uvicorn specflow.main:app --reload
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

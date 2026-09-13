# Current Study State

- Roadmap: [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md)
- Roadmap version: V5.3.2 Learning Effectiveness Patch
- Campaign phase: Understand & Correct (Day 1-7)
- Study status: DAY 7 COMPLETE: WEEK 1 OWNERSHIP GATE (IMPROVING)
- Day: 7
- Current mode: REVIEW
- Updated on: 2026-09-13

## Completed objective

Recover one concrete mock Multi-Agent path from test input through Evidence,
Agent stages, Review, Artifact, and terminal return; retest Day 4/5/6 partial
items on changed surfaces; produce Control Matrix v1; test Tool Permission
reachability; and complete one learner-predicted correctness-failure loop.

## Completed deliverables

- One source-grounded mock Run trace using
  `test_run_multi_agent_mock_mode`, with explicit test-evidence boundaries.
- Changed-surface Day 4/5/6 retests for path validation, Context visibility,
  and Handoff failure propagation.
- Control Matrix v1 covering Coordinator LLM, Specialist/Reviewer LLM,
  Evidence Tools, and Artifact Write with scoped `✓ / × / unknown` results.
- Tool Permission reachability judgment: no current standard
  `AgentRunner → ToolExecutor` path was proven.
- T-074: reproduced ignored `policy.repository.max_file_bytes`, froze a task,
  implemented one shared translation for both runners, and verified the fix at
  commit `952a952`.
- Retest Queue v1 with all role-critical Week 1 items retained as `improving`
  rather than promoted from AI-generated summaries.

## Evidence

- [Day 7 evidence card](evidence/day-07.md)
- `docs/study/control-coverage-backlog.md`
- `docs/tasks/T-074-repository-file-limit-policy-wiring.md`
- `docs/reports/T-074-completion-report.md`
- T-074 RED: `2 failed` because both ToolCall records had `truncated=false`.
- T-074 GREEN: `2 passed`; affected paths `107 passed, 1 skipped`.
- Full validation: `777 passed, 3 skipped, 3 known warnings`.
- Ruff lint, Ruff format, and `git diff --check`: passed.

## Completion boundary

Week 1 teaching content and the T-074 technical loop are complete. Learner
ownership is `improving / partial`: the learner personally reproduced and
located the failure, selected the design, challenged its consequences, and
reviewed the critical Diff; Codex authored the task specification, tests,
product Patch, report, and commit. This does not claim independent manual
product coding or `stable` closed-note mastery.

## Current mode contract

This record closes Day 7 in REVIEW. Do not extend T-074 or promote any
`improving` item to `stable` without a changed-surface retest. Any future study
task requires an explicit user transition and must re-read the current roadmap,
evidence, backlog, and relevant source/tests.

## Forbidden until an explicit transition

- Do not enter Day 8 or create Eval/Dataset assets.
- Do not start Repository RAG, Vector, Hybrid, Rerank, or external-donor work.
- Do not patch Control Coverage backlog items without a new reproduction,
  explicit approval, and frozen task specification.

## Stop condition

Day 7 content, T-074 validation, evidence capture, Control Matrix v1, and Retest
Queue v1 are complete. Remaining `improving` and `unknown` items are carried
forward rather than forced closed.

## Next action

Stop at Day 7. Wait for the learner to explicitly start Day 8 in a separate
teaching task; do not infer the transition from Week 1 completion.

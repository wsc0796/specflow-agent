# Current Study State

- Roadmap: [ROADMAP_V5_1.md](ROADMAP_V5_1.md)
- Study status: READY
- Day: 1
- Current mode: SURVEY
- Prepared on: 2026-09-05

## Today's only objective

Take ownership of the current SpecFlow baseline without adding a feature. Day 1
starts only when the learner explicitly says: “开始 Day 1，读取教学合同和
CURRENT，严格按当前模式推进。”

## Gate

Before Day 1 closes, the learner must have personally obtained and explained:

- branch, commit, and `git status`;
- pytest, Ruff, formatting, and benchmark baselines;
- a first-draft main call-chain diagram;
- the entry points for CLI/API, Evidence, Context, Coordinator, Handoff,
  Workflow, Eval, and Artifact.

## Current mode contract

`SURVEY` is read-only. Codex may locate files and symbols, describe inputs and
outputs, and ask tracing questions. It must not modify files or give the learner
a finished architecture diagram.

## Forbidden today

- Do not modify product code.
- Do not start Repository RAG implementation.
- Do not begin FAULT or PATCH before the learner completes and submits the first
  call-chain drawing.
- Do not turn unknowns into inferred architecture facts.

## Stop condition

Stop after identifying source entry points and asking the learner five questions
that require reading the code. Wait for the learner's own diagram or written
call chain before entering `REVIEW`.

## Next action

The learner starts Day 1 explicitly. Codex then performs only the baseline
`SURVEY` described above.

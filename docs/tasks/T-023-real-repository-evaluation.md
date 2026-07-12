# T-023 - Real Repository Cases and Evaluation

## Goal

Provide a deterministic evaluation layer for the existing repository-aware
pipeline. It must prove Mock contract behavior on cases grounded in a real local
repository and safely validate user-supplied Live Provider artifacts without
calling a provider.

## Building

- Versioned real-repository case definitions under `evaluation/cases/`.
- Evaluation models, a Mock contract runner, deterministic artifact validators,
  manual-quality rubric, and report rendering.
- A Live Artifact importer that validates an existing artifact directory only.
- Mock evaluation summaries and a documentation template with Live validation
  explicitly blocked pending a user-run command.

## Not building

- New Workers, Tools, provider calls, shell/Git tools, automatic repository
  modification, Agent loops, ReAct, LangGraph, RAG, Web UI, M6, or M5 closeout.

## Safety boundary

- Never enumerate, read, print, or depend on environment variables.
- Never read `.env`, credentials, or secrets files.
- Never execute a non-mock provider request.
- Case files contain only repository-relative paths; no private absolute paths.
- The Live importer reads existing artifacts only and does not repair them.

## Acceptance criteria

1. Cases are grounded in `sky-takeout-python` files or explicitly state why a
   planned capability is not yet implemented.
2. Mock evaluation checks the 10-artifact contract, hash lineage, traces,
   repository-relative evidence, and secret absence without scoring content as
   Live quality.
3. Live validation rejects mock manifests, incomplete artifacts, empty models,
   missing Worker traces/tool calls, external source paths, and secrets.
4. Automated findings and human rubric scores stay separate.
5. Live validation remains `blocked_live_validation` until user-supplied,
   non-mock artifacts are imported.
6. Tests, Ruff, format, and diff checks pass; M5 remains open.

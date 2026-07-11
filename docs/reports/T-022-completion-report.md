# T-022 completion report - CLI and Artifact Delivery

## Result

Implemented a `specflow run` CLI entry point that orchestrates the full pipeline
(evidence collection → AnalyzeWorker → artifact writing) and saves structured
JSON + Markdown artifacts to a deterministic output directory.

## Numbering note

This task maps to the attachment's T-021 CLI slice. The repository already used
T-021 for Repository-aware Agent Integration, so CLI delivery is recorded as
T-022 without rewriting published history.

## Architecture

```text
specflow run --repo <path> --requirement "<text>"
  → runner.run()
    → ToolRegistry + RepositoryToolSet
    → EvidenceCollector.collect()
    → ProjectContext + AnalyzeWorker
    → AgentExecutor.execute_until_complete()
    → ArtifactStore.write_run()
      → manifest.json, sources.json, analysis.json
      → generation.json, review.json, tool-calls.json, trace.json
      → technical-spec.md, test-plan.md, run-summary.md
```

## New modules

- `src/specflow/cli.py` — argparse CLI with `run` subcommand.
- `src/specflow/runner.py` — run orchestration service.
- `src/specflow/artifacts/` — ArtifactStore, RunManifest, Markdown renderers.

## Exit code contract

| Code | Condition |
|------|-----------|
| 0 | Workflow completed successfully |
| 2 | Missing repo, invalid repo, or provider config error |
| 3 | Evidence collection failure or workflow execution failure |
| 4 | Completed but degraded / requires human review |

## Artifact manifest

`manifest.json` records: schema_version, run_id, timestamps, status,
provider_type, model, requirement hash, evidence/analysis/generation/review
hashes, review_decision, degraded flag, tool_call_count, warnings.

## Safety

- Run IDs validated against path traversal (no `..` or absolute paths).
- Duplicate run directories rejected.
- API keys never appear in any artifact.
- Target repository never modified.
- Provider error bodies never exposed to artifacts.

## Tests

`tests/test_artifact_store.py`: 13 tests
`tests/test_cli.py`: 10 tests

## Quality gates

- `uv run pytest tests/test_artifact_store.py -v`: 13 passed.
- `uv run pytest tests/test_cli.py -v`: 10 passed.
- `uv run pytest -v`: 391 passed, 2 skipped, 1 warning.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 101 files already formatted.

## Mock CLI smoke test

```powershell
uv run specflow run --repo <temp-repo> --requirement "Add health check" --provider mock --output <temp-output>
```

Verified: CLI runs, artifacts created, exit code handled, no secrets leaked.

## Known limitations

- Runner currently wires only AnalyzeWorker (single-step pipeline).
- Generate and Review workers not yet integrated into the runner.
- No real provider smoke test (requires API key).

## Next task

T-023 Real Repository Cases and Evaluation.

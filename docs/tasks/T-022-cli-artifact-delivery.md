# T-022 - CLI and Artifact Delivery

## Goal

Provide a command-line entry point (`specflow run`) for end-to-end specification
generation and save structured artifacts to a deterministic output directory.

This task maps to the attachment's T-021 CLI slice because the repository already
used T-021 for Repository-aware Agent Integration.

## Building

- `specflow.cli` — argparse-based CLI with `run` subcommand.
- `specflow.runner` — orchestrates evidence collection + worker pipeline + artifacts.
- `specflow.artifacts` — ArtifactStore, RunManifest, Markdown renderers.
- `pyproject.toml` console script entry point.

## CLI

```powershell
uv run specflow run \
  --repo <path> \
  --requirement "<text>" \
  --output <dir> \
  --provider mock|openai-compatible \
  --mock
```

Parameters:
- `--repo` (required): Path to target repository.
- `--requirement` (required): Requirement text.
- `--output` (default: `./artifacts`): Output directory.
- `--provider` (default: `mock`): `mock` or `openai-compatible`.
- `--model` (optional): Model name override.
- `--max-files` (default: 5): Maximum files to read.
- `--mock` (flag): Force mock mode.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Workflow completed (PASS or REJECT) |
| 2 | Input or configuration error |
| 3 | Workflow execution failure |
| 4 | Completed but degraded / requires human review |

## Artifact output

```text
<output>/<run_id>/
├── manifest.json
├── analysis.json
├── generation.json
├── review.json
├── sources.json
├── tool-calls.json
├── trace.json
├── technical-spec.md
├── test-plan.md
└── run-summary.md
```

## Safety

- Run ID validated against path traversal.
- Duplicate run directories rejected.
- Failed writes clean up partial directories.
- API keys and secrets never appear in artifacts.
- Target repository is never modified.

## Testing

`tests/test_artifact_store.py` (13 tests):
- Manifest serialization, JSON validity, required fields.
- Store writes all 10 artifact files.
- Duplicate directory rejection, path traversal rejection.
- API key absence in manifest.
- Write failure cleanup.
- Markdown renderer content validation.

`tests/test_cli.py` (10 tests):
- --help, no-command, missing args error handling.
- Mock run with temp repo produces artifacts.
- Provider config missing reports clearly.
- API key never in output.
- Same-input stability, target repo immutability.

## Explicitly not implemented

- No Generate or Review worker in the runner pipeline (single AnalyzeWorker path).
- No T-023 real case evaluation.

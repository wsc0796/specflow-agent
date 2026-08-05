# T-063 Live Provider Evaluation v1 - Preflight

## Status

`BLOCKED` - the frozen suite and credential-safe harness are ready, but this
shell has no configured real Provider or Provider-specific pricing rule. No
Provider request was sent and no Live quality metric has been generated.

## Frozen Inputs

| Item | Result | Evidence |
| --- | --- | --- |
| Quality task count | 5 | `evals/live-provider-v1/tasks/` |
| Runtime control count | 1 | `evals/live-provider-v1/controls/budget-guard.yaml` |
| Target repository | `wsc0796/sky-takeout-python` | Suite lock |
| Target commit | `4ede5d01039be8c703e4cc2cc94f18084ebf1ba1` | `preflight_live_suite` |
| Target worktree | Clean | `preflight_live_suite` |
| Sensitive-path control | Passed | `.env`, credentials, key, and private-key probes denied by policy |

`suite-lock.json` hashes every task file. A modified task is rejected before a
Provider client is constructed.

Each future execution writes a batch manifest before its first Provider call.
The manifest binds the planned task IDs, task hashes, suite-lock hash, clean
SpecFlow commit, deterministic-result hashes, raw response capture, tool calls,
traces, and runner Artifact hashes. Report generation consumes only those
declared attempts and rejects changed, duplicate, incomplete, or test-double
evidence.

## Provider Gate

Only environment-variable presence was checked; no secret value or local
credential file was read.

| Required input | Result |
| --- | --- |
| `SPECFLOW_LLM_BASE_URL` | Missing |
| `SPECFLOW_LLM_API_KEY` | Missing |
| `SPECFLOW_LLM_MODEL` | Missing |
| Explicit pricing rule | Missing |

The evaluator therefore exits with code `2` before creating a Provider client
or run directory. This is intentional and is not recorded as a model failure.

## Harness Evidence

- Each attempt will retain `task.yaml`, a non-secret `config.json`, redacted
  `raw_provider_response.json`, `tool_calls.jsonl`, `trace.jsonl`, runner
  artifacts, `deterministic-result.json`, and pending `human-review.yaml`.
- The local ignored run root will also retain `batches/<batch_id>.json`, which
  prevents old attempts from being mixed into a new report.
- `raw_provider_response.json` is an opt-in, response-only capture after
  redaction. It never contains a request body, request headers, or API key.
- The six-agent runner is unchanged on normal CLI paths; the evaluator uses a
  private LLM-client injection hook solely to attach its recorder.
- The call-budget control requires at least one real Provider response and a
  safe budget failure; it is excluded from quality success-rate calculations
  but included in a cost estimate when Provider usage is complete.
- A missing Provider usage value makes the batch cost unavailable, rather than
  reporting an understated zero.

## Local Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | `760 passed, 3 skipped, 3 warnings` |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | `209 files already formatted` |
| `uv run python scripts/check_secrets.py` | Passed |
| `uv build` | Passed |
| Installed-wheel smoke | Passed |
| `git diff --check` | Passed |
| Frozen target preflight | Commit, clean worktree, and path policy passed |
| Missing-credential evaluator run | Exit `2`; no Provider client or run directory created |

## Next Gate

Provide the three `SPECFLOW_LLM_*` values in the authorized shell and a
provider/model-matched, untracked pricing rule based on the provider's published
pricing source. Then run the frozen suite, complete human review for each run,
and generate `docs/reports/live-provider-evaluation-v1.md`. Do not use Mock
output as a substitute.

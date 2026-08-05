# T-062 File Mapping — PR #4 (`codex/t062-runtime-hardening-status`)

Every file changed by PR #4 mapped to the T-062 specification
(`docs/tasks/T-062-runtime-boundary-remediation.md`). 34 files, +1754/-97.

## Acceptance keys

| Key | Acceptance |
| --- | --- |
| A1 | Project saved before allowlist activation cannot be run outside the configured roots |
| A2 | Concurrency-rejected requests do not consume per-minute run quota |
| A3 | Safe runner `error_code` (e.g. `TIME_BUDGET_EXCEEDED`) survives into the Run record |
| A4 | On stage deadline expiry the scheduler cancels queued work and waits for started work to exit |
| A5 | Focused tests, full pytest, Ruff, format, secret scan, build and `git diff --check` recorded |
| R | Release-realism fix agreed during review (not a T-062 acceptance) |

## Mapping

| File | Purpose | Acceptance | Keep |
| --- | --- | --- | --- |
| `src/specflow/runs.py` | Revalidate project path at run boundary (A1); safe error_code from run manifest (A3); commit-rollback guard | A1, A3 | Keep |
| `src/specflow/main.py` | Wire `ApiSecurity` into app; engine dispose on shutdown; single `/health` (R) | A1, R | Keep |
| `src/specflow/api_security.py` | RunRateLimiter counts only permit-holders (A2); allowlist/reviewer/API-key boundary; non-ASCII key fails closed (R) | A2, A1, R | Keep |
| `src/specflow/coordinator/scheduler.py` | `deadline` budget, cancel queued futures, `shutdown(wait=True)` before returning (A4) | A4 | Keep |
| `src/specflow/runner_multi.py` | Wire deadline (A4); persist safe error codes (A3); atomic artifact writes + integrity manifest; DLP final scan; real LLMResponse mock for end-to-end token budget | A3, A4 | Keep |
| `src/specflow/policy/runtime_guard.py` | Thread-safe LLM-call budget; `remaining_time()` for scheduler deadline | A4 | Keep |
| `src/specflow/context.py` | DLP coverage the README already claims (AWS/GitHub/GitLab/Slack/Google/Azure/PEM/DSN/assignments) | A5 (claims reconciliation) | Keep |
| `src/specflow/tools/sanitization.py` | DLP final-scan entry used by runner_multi | A5 | Keep |
| `src/specflow/tools/repository_policy.py` | Path-policy extension for allowlist revalidation | A1 | Keep |
| `src/specflow/projects.py` | Allowlist validation on project registration | A1 | Keep |
| `src/specflow/agents/adapter.py` | Token-usage accounting no longer swallows missing fields | A4 (budget accuracy) | Keep |
| `src/specflow/db.py` | SQLite `busy_timeout` for concurrent writer threads | A4 | Keep |
| `src/specflow/artifacts/models.py` | Lint surfaced by anchoring the package (unused imports, UTC alias) | R | Keep |
| `src/specflow/artifacts/renderers.py` | Formatting surfaced by anchoring the package | R | Keep |
| `src/specflow/artifacts/store.py` | Lint surfaced by anchoring the package (unused imports) | R | Keep |
| `tests/test_api_security.py` | Allowlist recheck (A1); quota semantics (A2); Unicode key, oversized key, quotas doc lock (R); default-quota guard | A1, A2, R | Keep |
| `tests/test_runs.py` | Path revalidation + safe error_code persistence (A1, A3) | A1, A3 | Keep |
| `tests/test_scheduler.py` | Deadline cancel-and-wait behavior (A4) | A4 | Keep |
| `tests/test_execution_policy.py` | Budget interaction under scheduler deadlines | A4 | Keep |
| `tests/test_cli_multi_agent.py` | CLI multi-agent run still correct end-to-end | A4, A5 | Keep |
| `tests/test_context.py` | DLP extension coverage | A5 | Keep |
| `tests/test_agent_adapter.py` | Token-usage regression | A4 | Keep |
| `tests/test_repository_tools.py` | Path-policy coverage | A1 | Keep |
| `tests/test_mcp_server.py` | API surface unaffected by boundary changes | A5 | Keep |
| `tests/test_app_routes.py` | Single `/health` regression (R) | R | Keep |
| `scripts/smoke_installed_wheel.py` | Repeatable installed-wheel smoke: clean venv, boot, mock run, artifact check (R) | R | Keep |
| `README.md` | Security-boundary docs, quotas, verification numbers | A5 | Keep |
| `CHANGELOG.md` | T-062 entry | A5 | Keep |
| `AGENTS.md` | Workflow-rule update | A5 | Keep |
| `.env.example` | New security/limit variables documented | A5 | Keep |
| `.gitignore` | Anchor runtime artifact dirs; `src/specflow/artifacts` ships again (R) | R | Keep |
| `docs/tasks/T-062-runtime-boundary-remediation.md` | Acceptance updated to match final scope | A5 | Keep |
| `docs/reports/T-062-completion-report.md` | Completion report | A5 | Keep |
| `docs/reports/T-062-file-mapping.md` | This table | A5 | Keep |

## Splits / follow-ups (not folded into T-062)

- `artifacts-ab/` is tracked in git and leaks into the sdist; removing it
  (``git rm -r --cached artifacts-ab``) is deferred to a separate follow-up PR
  so the diff stays reviewable.
- The installed-wheel smoke runs in CI (`.github/workflows/ci.yml`, `smoke` job).

## Verification log (2026-08-05, Windows 11)

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 752 passed, 3 skipped |
| `uv run ruff check .` | pass |
| `uv build` | wheel + sdist built |
| Wheel contains `specflow/artifacts/*` | yes (5 files) |
| `python scripts/smoke_installed_wheel.py` | PASS |
| `git diff --check` | pass |

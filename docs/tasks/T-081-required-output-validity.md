# T-081 — Required output validity and evidence correction (D1)

- Date: 2026-09-11
- BASE_SHA: `1b44127747a7f7b8bfd9118eb56006d867986b39` (`origin/main`, fetched before work)
- Authorization: the owner's D1/D2 repair instruction, not an independent approval.
- Status: scoped execution; this document fixes the minimum contract before code changes.
- T-070–T-080 are already allocated on the M9/M10 specification branch.

## Scope and invariants

Use existing AgentRunner, role payload schemas, stage validation, failure envelopes,
CLI exit codes and Run API mappings. Preserve the topology and revision limit.
Do not merge PR #5/#6 or the separate runtime-correctness branch. No live calls,
release, automatic merge, evidence-hash or artifact-publication redesign.

1. Required invalid output or explicit execution/schema failure must stop before
   its consumers execute. A later PASS cannot rehabilitate it (INV-1/INV-2).
2. All role summaries must contain non-whitespace text. Design needs at least one
   nonblank architecture, implementation, API or data-model change explanation.
   Test strategy needs a nonblank test scenario, edge case or regression check.
   Synthesis needs a nonblank consolidated design. These are minimum presence
   checks, not semantic scoring. Empty optional risks/findings remain valid (INV-3).
3. No-op/insufficient-information has no separate success contract in this
   baseline. It may be explicitly explained in these fields (including how to
   check the no-op or resolve missing information); a title alone cannot stand
   in for an implementation plan. No new status or keyword heuristic is added.
4. Plan enrichment degradation is distinct from execution degradation; valid
   outputs and business REJECT retain the existing lifecycle semantics (INV-4).

## Modification surface

- `src/specflow/schema/agent_payloads.py`, `src/specflow/runner_multi.py`:
  tighten existing boundaries only where the baseline regression fails.
- `src/specflow/agents/adapter.py`: expose the authoritative output schema in the
  provider request, only if the recording fake confirms it is missing.
- Deterministic Design/TestStrategy/Synthesis mock payloads and dependent fixtures:
  satisfy the same minimum contract without claiming real generated quality.
- Relevant tests, safe synthetic fixture, directly affected claims and reports.

## Acceptance and evidence

`tests/test_required_output_validity.py` runs the real CLI/AgentRunner and downstream
validation with an offline recording provider: every role's empty/missing/blank
payload, invalid JSON/schema/provider failure, valid outputs, plan degradation,
empty risks/findings and REJECT. Stage injection covers false success/schema flags.
Existing `test_cli_multi_agent.py` covers bounded revision. The Run API regression
must call its real runner and check failed state and unavailable review package.
Before tests, block real HTTP transports; MockTransport/TestClient remain usable.

Record passing baseline protections honestly; do not manufacture red tests.
Keep original live artifacts read-only; publish only field-level summaries and
separate raw/derived hashes. Missing run identity is unknown, not proof of absence.
Run targeted tests, full pytest, Ruff check/format, diff check, secret scan and
staged review. Build and identify this task's wheel separately. Deliver a focused
commit and independent PR, then stop D1 without merging.

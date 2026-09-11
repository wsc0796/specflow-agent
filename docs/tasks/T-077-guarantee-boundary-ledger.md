# T-077 — Guarantee Boundary Ledger and Declaration Registry

**Status:** DRAFT FOR FREEZE. Implementation requires the M10 specification
freeze plus a new focused session.

## Goal

Extract the runtime guarantee declarations currently scattered across
specifications, reports, and the README into one versioned, mechanically
checkable declaration registry, and bind each declaration to its evidence source
and current judgement state, so that "claimed to hold" and "demonstrated to
hold" become distinguishable by machine.

## Requirements

- **REQ-077-1 — Extract, do not invent.** Every ledger entry carries a
  declaration source reference (file path plus section or identifier) and the
  source excerpt. A declaration with no source must not be added.

- **REQ-077-2 — Stable declaration identity.** Each declaration has a stable ID,
  a bounded category (security, boundary, failure semantics, integrity,
  single-process limit), and a short bounded description. These fields are
  subject to REQ-M9-5.

- **REQ-077-3 — Evidence references must resolve.** An evidence reference points
  at a concrete test node, report path, or command. References must be
  mechanically resolvable. A reference that cannot be resolved yields
  `unverified`; it must never silently pass.

- **REQ-077-4 — Separate judgement from justification.** The ledger records the
  current judgement (`verified`, `unverified`, `not_applicable`) and its basis
  separately. A judgement of `verified` is not permitted while resolvable
  evidence is absent.

- **REQ-077-5 — `unverified` is an explicit result.** The ledger must express
  and retain `unverified`. Downgrading a judgement so the summary reads better
  violates REQ-M10-7.

- **REQ-077-6 — Validation is read-only, offline, and deterministic.** The
  validation command calls no LLM, performs no network access, scans no
  unauthorized path, and does not modify the repository. Repeated runs against
  the same checkout state produce identical results.

- **REQ-077-7 — Conform to the existing artifact boundary.** The ledger artifact
  is written through the existing safe-artifact boundary (atomic write,
  integrity hash, completion marker) and obeys the existing DLP rules and size
  limits.

- **REQ-077-8 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/ledger.py`, `src/specflow/assurance/models.py`,
  and the minimum CLI wiring in `src/specflow/cli.py`. Expected tests are
  `tests/test_assurance_ledger.py` and `tests/test_cli.py`. If validation would
  require an LLM, network access, a new dependency, or write permission, stop and
  amend the specification with evidence before editing.

- **REQ-077-9 — The first declaration set must cover the M9 boundary clauses.**
  Batch 1 must include: fail-closed required-agent behavior; no silent discard;
  the DLP boundary on metrics and traces; the single-process guarantee; artifact
  integrity (atomic write, SHA-256, `_COMPLETE` marker); mock-mode determinism;
  and repository read-only behavior. Each entry is marked according to its true
  evidence state, and several are expected to be `unverified`.

## Boundaries

The following are explicit non-goals for T-077:

- Do not implement fault injection (that is T-078). The ledger may reference
  evidence that does not yet exist, but must mark it `unverified`.
- Do not parse natural language to "understand" declarations. Use bounded
  deterministic matching plus an explicit maintainable list.
- Do not change any product runtime behavior, topology, schema, DLP rule,
  policy, or artifact contract.
- Do not add a dependency, call an LLM, or access the network.
- Do not retroactively edit existing reports or specifications to make a
  reference resolve.
- Do not attach an improvement roadmap or remediation promise to an
  `unverified` result.

## Acceptance

- **AC-077-1:** The ledger contains every declaration listed in REQ-077-9, each
  with a source reference, stable ID, bounded category, and judgement state.
- **AC-077-2:** Missing resolvable evidence yields `unverified`; tests prove an
  unresolvable reference cannot produce `verified`.
- **AC-077-3:** Repeated runs produce a byte-identical ledger artifact without
  modifying the repository.
- **AC-077-4:** Tests prove ledger fields contain no requirement text, prompt,
  repository content, absolute path, credential, or provider data.
- **AC-077-5:** The ledger artifact obeys the existing atomic-write, integrity
  hash, and completion-marker contract.
- **AC-077-6:** Existing CLI/mock, artifact, DLP, policy, and benchmark tests
  remain green.
- **AC-077-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-077-8:** `docs/reports/T-077-completion-report.md` records the
  declaration list, source mapping, judgement distribution including the
  `unverified` count, validation semantics, and known limits. One focused commit
  is created, then work stops before T-078.

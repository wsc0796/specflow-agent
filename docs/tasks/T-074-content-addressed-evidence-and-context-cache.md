# T-074 — Content-Addressed Evidence and Context Cache

**Status:** FROZEN. Implementation requires T-073 to be closed and a new focused
session.

## Goal

Reuse only deterministic, repository-derived evidence and context intermediates
through a bounded, auditable, content-addressed local cache whose versioned keys
prove source/config equivalence, without reusing stale Agent or provider output.

## Requirements

- **REQ-074-1 — Limit cacheable values.** Cache only deterministic,
  repository-derived intermediates such as a sanitized source-hash manifest,
  safe scan/profile result, evidence-selection result, or rendered repository
  context that can be reproduced without an LLM. Agent outputs, semantic plan
  enrichment, provider responses, reviews, decisions, traces, manifests, and
  final artifact bundles are never cacheable.
- **REQ-074-2 — Use a strong versioned lookup key.** The key must be a
  canonical SHA-256 over at least the safe repository snapshot/source hashes,
  exact requirement hash when selection depends on it, evidence/scanner/tool
  configuration, relevant execution-policy fields, detector/selector/sanitizer
  versions, and cache schema version. Repository path, run ID, time, TTL, and
  output directory are not proof of content equivalence.
- **REQ-074-3 — Verify values on reuse.** A hit must validate the cache schema,
  key, value hash, source-hash manifest, size bounds, and required fields before
  reuse. Any mismatch, stale source, partial write, unsupported version, symlink,
  unsafe path, malformed JSON, or DLP failure is a miss followed by safe
  recomputation; it is never returned as evidence.
- **REQ-074-4 — Keep reusable payloads run-neutral.** Cached values must not
  persist a prior run ID, owner/follower identity, absolute repository root,
  artifact directory, timestamp as truth, requirement text, or provider data.
  Current-run identity and bounded audit records are reconstructed after a hit,
  and the existing final DLP scan still runs before prompt or artifact use.
- **REQ-074-5 — Make storage bounded and atomic.** Use only an application-owned
  local/in-process cache with bounded entry/value size and deterministic paths
  derived from safe hashes. Writes use same-directory temporary files plus
  atomic replacement. Cache write failure must not corrupt a valid run; cache
  read/validation failure must not bypass evidence collection.
- **REQ-074-6 — Coordinate concurrent work.** Reuse the T-070 single-flight
  ownership contract so concurrent misses for the same content key do not
  perform duplicate population. Failed population releases ownership, does not
  publish a partial entry, and allows later recomputation.
- **REQ-074-7 — Make reuse auditable.** Record bounded cache status (`hit`,
  `miss`, `invalid`, `write_failed`, `bypassed`), cache schema version, safe key
  hash, validation outcome, and time saved where measurable in T-073 metrics or
  manifest audit fields. A hit must not be indistinguishable from fresh
  collection.
- **REQ-074-8 — Preserve evidence truth.** Cache reuse must produce the same
  evidence/context contract as fresh collection, including selected files,
  excerpts, source hashes, truncation/warnings, and safe tool-call audit
  semantics. If exact audit reconstruction is impossible, cache the lower-level
  deterministic input and rerun the higher-level collector.
- **REQ-074-9 — Expected implementation surface.** Expected production files
  are a focused `src/specflow/evidence/cache.py`,
  `src/specflow/evidence/collector.py`, `src/specflow/evidence/models.py`,
  `src/specflow/runner.py`, `src/specflow/runner_multi.py`, and minimal policy,
  artifact, single-flight, and metrics integration. Expected tests are
  `tests/test_evidence_cache.py`, `tests/test_evidence_collector.py`,
  `tests/test_runner_dlp.py`, `tests/test_cli.py`,
  `tests/test_cli_multi_agent.py`, and `tests/test_benchmark.py`. If a proposed
  value cannot be proven deterministic or run-neutral, exclude it rather than
  broadening this spec.

## Boundaries

The following are explicit non-goals for T-074:

- Depends on closed T-073 and preserves all T-070 through T-073 contracts.
- No Redis, database cache, distributed cache, network service, background
  refresh, stale-while-revalidate, probabilistic reuse, or TTL-only validity.
- No Agent output, LLM response, semantic plan, review result, final artifact,
  error outcome, or human decision cache.
- No cache hit based only on repository path, requirement text, modification
  time, TTL, provider/model name, or a previous successful run.
- No bypass of safe repository tools/scanner, source verification, schema
  validation, DLP, artifact size limits, or audit records.
- No Java/Maven cache specialization before T-076.

## Acceptance

- **AC-074-1:** Unit tests prove stable key generation and key separation for
  source content, requirement, evidence config, relevant policy, sanitizer,
  selector/detector, and cache schema version changes.
- **AC-074-2:** A verified hit avoids duplicate deterministic collection and
  reconstructs the same safe evidence/context contract with current-run audit
  identity.
- **AC-074-3:** Source change, hash mismatch, wrong schema version, malformed or
  oversized entry, symlink/path escape, partial write, DLP rejection, and missing
  field all produce safe miss/recompute behavior.
- **AC-074-4:** Concurrent miss tests prove one population, atomic publication,
  owner failure cleanup, no partial hit, and successful later retry.
- **AC-074-5:** Tests prove that prior run IDs, absolute paths, requirements,
  prompts, credentials, provider data, and Agent outputs are absent from cache
  values and audit fields.
- **AC-074-6:** Cache write failure leaves the run behavior honest and explicit;
  evidence recomputation failure remains an evidence/runtime failure rather than
  an empty success.
- **AC-074-7:** Existing evidence determinism, DLP, repository read-only, CLI,
  artifact, benchmark, and T-070 through T-073 tests remain green.
- **AC-074-8:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-074-9:** `docs/reports/T-074-completion-report.md` records cacheable
  values, key schema, validation/failure behavior, tests, and known
  single-process/local-storage limits. One focused implementation commit is
  created, then work stops before T-075.

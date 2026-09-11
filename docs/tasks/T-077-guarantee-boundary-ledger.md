# T-077 — Guarantee Boundary Ledger and Declaration Registry

**Status:** DRAFT FOR FREEZE — REVISION 2. Implementation requires the M10
specification freeze **and** that the declaration sources named in REQ-M10-6 are
reproducible at the frozen base commit. If a cited declaration cannot be
reproduced at that commit, stop and amend the specification; do not reconstruct
it from memory, from a chat transcript, or by guessing.

## Goal

Extract the runtime guarantee declarations currently scattered across
specifications, reports, and the README into one versioned, mechanically
checkable declaration registry, and bind each declaration to its evidence source
and current judgement state, so that "claimed to hold", "demonstrated to hold",
and "contradicted" become distinguishable by machine.

## Requirements

### Declarations and sources

- **REQ-077-1 — Extract, do not invent.** Every ledger entry carries a
  declaration source reference (file path plus section or identifier) and the
  declaration's own bounded identifier. A declaration with no reproducible
  source must not be added.

- **REQ-077-2 — Stable declaration identity.** Each declaration has a stable ID,
  a bounded category (security, boundary, failure semantics, integrity,
  single-process limit), and a short bounded description. These fields are
  subject to REQ-M9-5.

- **REQ-077-3 — Excerpt allowance is explicit, not interpretive.** The ledger may
  store a bounded excerpt only from **SpecFlow's own curated declaration
  sources**: files this repository maintains — specifications under `docs/`,
  completion reports under `docs/reports/`, the README, and the CHANGELOG.
  Excerpts must never be taken from an analyzed target repository, from
  `EvidenceBundle` content, from tool output, from prompt text, or from provider
  responses. The excerpt field is bounded by a configured maximum length and
  passes the existing sanitization and DLP rules. Where an excerpt is not stored,
  the entry carries the source reference, declaration ID, and a bounded
  human-written description instead. This requirement explicitly resolves the
  apparent conflict between storing excerpts and the REQ-M9-5 content
  prohibition by defining what an excerpt is allowed to be.

- **REQ-077-4 — Evidence references must resolve to produced evidence.** An
  evidence reference points at a concrete test node, report path, or command
  **together with a recorded execution outcome and the commit or version it was
  produced against**. Applying REQ-M10-2:

  | Situation | Required state |
  | --- | --- |
  | Declaration exists; no evidence targets it | `declared` |
  | Evidence exists and was produced; version binding matches; assertions map to the declaration clause | eligible for `verified` |
  | Test node or command name exists but no recorded execution outcome | `declared` — never `verified` |
  | Evidence was produced against a different commit or configuration | `declared` — never `verified` |
  | Evidence is a skipped or conditionally disabled test | `declared` — never `verified` |
  | A recorded observation contradicts the declaration | `refuted` |
  | Declaration does not apply to the verified configuration | `not_applicable` |

- **REQ-077-5 — Judgement and justification are separate fields.** The ledger
  records the state (`verified`, `declared`, `refuted`, `not_applicable`) and its
  basis separately. `verified` is not permitted while any of the four
  REQ-M10-2 conditions is unmet.

- **REQ-077-6 — `refuted` is preserved through every rollup.** A contradiction
  must survive aggregation. No summary, count, percentage, or score may fold
  `refuted` into `declared`, `unverified`, `not_applicable`, or any "known
  issues" bucket that is not separately reported. Downgrading a judgement so a
  summary reads better violates REQ-M10-5.

### Validation mechanics

- **REQ-077-7 — Validation is offline and read-only with respect to everything
  except its declared output directory.** The validation command calls no LLM,
  performs no network access, and scans no unauthorized path. It does not modify
  the target repository, does not modify SpecFlow's tracked sources, and does not
  modify any existing run artifact. It writes only inside an explicitly provided
  output directory, through the existing safe-artifact boundary. This
  requirement distinguishes three separate things that revision 1 conflated:

  | Boundary | Rule |
  | --- | --- |
  | Target repository under analysis | Read-only, always |
  | Validation computation itself | No writes outside the declared output directory |
  | Ledger output | Writable, but only inside the explicitly provided output directory |

- **REQ-077-8 — Determinism is defined over normalized content, not the whole
  package.** Repeated runs against the same checkout state must produce an
  identical **normalized ledger content**: the same declarations, states,
  evidence references, and ordering, with volatile fields removed. The existing
  completion marker records `completed_at` from the wall clock and therefore must
  not be expected to be byte-identical. Comparisons are defined on the normalized
  ledger body; the surrounding package metadata is excluded by specification.

- **REQ-077-9 — Conform to the existing artifact boundary.** The ledger artifact
  is written through the existing safe-artifact boundary (atomic write,
  integrity hash, completion marker) and obeys the existing DLP rules and size
  limits.

### Surface and scope

- **REQ-077-10 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/ledger.py`, `src/specflow/assurance/models.py`,
  and the minimum CLI wiring in `src/specflow/cli.py`. Expected tests are
  `tests/test_assurance_ledger.py` and `tests/test_cli.py`. If validation would
  require an LLM, network access, a new dependency, or write access outside the
  declared output directory, stop and amend the specification with evidence
  before editing.

- **REQ-077-11 — The first declaration set must cover the named boundary
  clauses.** Batch 1 must include: fail-closed required-agent behavior; no silent
  discard (M9 REQ-M9-4); the observability content boundary (M9 REQ-M9-5); the
  single-process guarantee (M9 REQ-M9-6); artifact integrity **as actually
  implemented in each pipeline**; mock-mode determinism; and repository
  read-only behavior.

  Artifact integrity must be listed as **two separate declarations**, because the
  two pipelines do not provide the same guarantee:

  | Declaration | Source of truth |
  | --- | --- |
  | Multi-agent run directory integrity | `runner_multi.py` `_finalize_run_directory`: per-file SHA-256 in `artifact-integrity.json`, completion marker written last, per-file atomic replace |
  | Legacy linear run directory integrity | `artifacts/store.py` `ArtifactStore.write_run` |

  Several entries are expected to be `declared` rather than `verified`. Recording
  that honestly is the deliverable, not a shortfall.

## Boundaries

The following are explicit non-goals for T-077:

- Do not implement fault injection (that is T-078). The ledger may reference
  evidence that does not yet exist, but must mark it `declared`.
- Do not parse natural language to "understand" declarations. Use bounded
  deterministic matching plus an explicit maintainable list.
- Do not change any product runtime behavior, topology, schema, DLP rule,
  policy, or artifact contract.
- Do not add a dependency, call an LLM, or access the network.
- Do not retroactively edit existing reports or specifications to make a
  reference resolve.
- Do not attach an improvement roadmap or remediation promise to a `declared` or
  `refuted` entry.
- Do not decide that a declaration holds because a similarly named test exists.
  REQ-077-4 governs.

## Acceptance

- **AC-077-1:** The ledger contains every declaration listed in REQ-077-11, each
  with a reproducible source reference, stable ID, bounded category, and state.
- **AC-077-2:** Tests prove each REQ-077-4 row is enforced: a resolvable-but-
  unexecuted reference, a version-mismatched reference, and a skipped test each
  yield `declared`, not `verified`.
- **AC-077-3:** A test proves a `refuted` entry survives aggregation and is not
  merged into `declared`, `not_applicable`, or a generic issues bucket.
- **AC-077-4:** A test proves an excerpt taken from an analyzed target
  repository, from `EvidenceBundle` content, or from prompt text cannot enter the
  ledger, while an excerpt from a curated `docs/` source can, subject to the
  configured length bound.
- **AC-077-5:** Repeated runs produce identical normalized ledger content while
  the package completion marker may differ; the comparison is defined on the
  normalized body.
- **AC-077-6:** Tests prove the command writes only inside the declared output
  directory and modifies no target repository file, no tracked source, and no
  existing run artifact.
- **AC-077-7:** The ledger artifact obeys the existing atomic-write, integrity
  hash, and completion-marker contract.
- **AC-077-8:** Existing CLI/mock, artifact, DLP, policy, and benchmark tests
  remain green.
- **AC-077-9:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-077-10:** `docs/reports/T-077-completion-report.md` records the
  declaration list, source mapping, state distribution including every `refuted`
  entry, the excerpt allowance as implemented, validation semantics, and known
  limits. One focused commit is created, then work stops before T-078.

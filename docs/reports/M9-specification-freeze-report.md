# M9 Specification Freeze Report — Runtime Resilience & Efficiency

**Date:** 2026-08-27

**Status:** PASS — specification only. Runtime implementation remains
unauthorized in this change.

## Files

- `docs/tasks/M9-runtime-resilience-efficiency.md`
- `docs/tasks/T-070-run-single-flight-and-early-idempotency.md`
- `docs/tasks/T-071-provider-resilience-guard.md`
- `docs/tasks/T-072-execution-lanes-and-bounded-admission.md`
- `docs/tasks/T-073-runtime-saturation-and-latency-metrics.md`
- `docs/tasks/T-074-content-addressed-evidence-and-context-cache.md`
- `docs/tasks/T-075-unified-run-preflight-validator.md`
- `docs/tasks/T-076-java-maven-repository-profile-and-cms-flow-benchmark.md`
- `docs/reports/M9-specification-freeze-report.md`

## Architecture Decisions

1. Single-flight is a process-local in-flight ownership mechanism, not a result
   cache or distributed lock. Owner/follower roles and shared outcomes are
   auditable.
2. Provider resilience is keyed by `(provider, model)` and wraps real provider
   attempts without owning a second retry/fallback loop. Mock mode never mutates
   breaker state.
3. Execution lanes govern bounded resources but do not replace the Coordinator,
   fixed topology, stage dependencies, or revision model. Accepted work can
   never use silent discard.
4. Metrics follow the behavior changes so owner/follower, breaker, queue,
   execution, provider, rejection, and saturation semantics have stable audit
   fields.
5. Cache reuse is limited to deterministic repository-derived intermediates
   verified by source/config/version hashes. Agent/provider/final artifacts are
   never cacheable.
6. Unified preflight composes existing validators before semantic enrichment or
   live provider calls; it does not become a competing validator system.
7. Java/Maven remains prohibited until T-076. T-076 authorizes only a modular,
   evidence-backed Java/Maven profile and a sanitized five-case `cms-flow`
   fixture, not general polyglot or build support.

## Dependencies

```text
T-070 single-flight
  → T-071 provider resilience
  → T-072 execution lanes/admission
  → T-073 runtime metrics
  → T-074 deterministic evidence/context cache
  → T-075 unified preflight
  → M9 runtime review
  → T-076 Java/Maven profile + sanitized benchmark
  → benchmark/release review
```

## Reference Transfer Boundary

The authorized `cms-flow` archive was inspected read-only. Useful concepts were
single-JVM in-flight cleanup, resource-keyed circuit state, bounded admission,
executor saturation snapshots, content-derived cache keys, and pre-execution
validation. Its production code is not copied. Its silent-discard executor
paths and fail-open prevalidator behavior are explicitly rejected for SpecFlow's
accepted work and fail-closed boundaries. Future T-076 fixture construction must
exclude its generated `target/`, IDE `.idea/`/`*.iml`, `.feisuan/` instruction
files, compiled output, local workspace data, credentials, and unnecessary
business assets.

## Unresolved Design Risks

- T-070 must prove an early repository snapshot token strong enough for safe
  concurrent equivalence without turning key derivation into an unbounded full
  repository read.
- T-070 Run API followers need distinct durable audit identities while safely
  referencing one owner artifact set; the final DTO/state-payload shape must be
  locked by tests before implementation.
- T-071 must integrate at one shared provider-attempt boundary; the current
  legacy FallbackManager and multi-agent AgentRunner have separate retry paths,
  so duplicate retry ownership is a primary review risk.
- T-072 must reconcile bounded queues with the existing deadline behavior that
  waits for already-started synchronous threads; Python cannot safely force-stop
  those calls.
- T-074 lookup-key computation may still require bounded repository hashing.
  Cache performance benefit must be measured honestly and never used to weaken
  source validation.
- T-076 needs an additive technology-profile representation that preserves all
  Python serialization while representing Maven modules/version/dependencies;
  mixed-language repositories remain explicitly out of scope.

## Validation

| Gate | Result |
| --- | --- |
| `uv run pytest -v` | passed: 771 passed, 3 skipped, 3 known warnings |
| `uv run ruff check .` | passed; one existing invalid `# noqa` warning reported |
| `uv run ruff format --check .` | passed: 208 files already formatted |
| `uv run python scripts/check_secrets.py` | passed |
| `git diff --cached --check` | passed |
| Documentation-only boundary review | passed: nine Markdown files, no runtime/test/fixture change |

## Runtime Implementation Confirmation

No runtime feature, dependency, test implementation, benchmark fixture, Java
support, generated artifact, or external publication is authorized or included
in this specification-freeze change.

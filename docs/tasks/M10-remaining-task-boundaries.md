# M10 — remaining task boundaries (T-079, T-080, T-081)

**Status:** BOUNDARY DEFINITION ONLY. These three entries state scope, dependency
gates, non-goals, and completion criteria. They deliberately do not specify
modules, data fields, or test names.

## Why these are not fully specified

REQ-M10-10 requires that a later task's field-level design follow observed
evidence rather than assumption:

- the unresolved-item fields in T-079 depend on which outcomes T-078 actually
  produces, in particular its `undetermined` entries;
- the probe method in T-081 depends on the milestone assurance review;
- the evidence-freshness assertion in T-080 must be sized against the real
  `EvidenceBundle` hash contract rather than a guess about it.

Pre-filling those details would contradict the milestone's own execution rule
(REQ-M10-8) and the repository rule that a task may not begin merely because its
ID appears in a milestone document. Each of these tasks must therefore be
specified in its own session after its predecessor closes.

---

## T-079 — Unresolved-Item Aggregation and Assurance Status

**Dependency gate:** T-078 closed.

**Goal:** Report the unresolved work a finished run leaves behind as a single
bounded, auditable health signal, so that a run carrying unresolved items is
reported as not fully healthy rather than merely carrying a non-zero count.

**Scope boundary:**

- Aggregate only items the existing runtime already records or can derive
  deterministically: degraded outcomes, `fallback_used`, exhausted revision
  budget, failed or unvalidated schema checks, pending human review decisions,
  cache `invalid` or `write_failed` states, and the `undetermined` conclusions
  produced by T-078.
- Keep the aggregate a report and an observation. It must not gate, block, fail,
  retry, or alter any run.

**Non-goals:**

- Do not add a health endpoint, monitoring backend, exporter, alert, or
  dashboard.
- Do not introduce thresholds that change run behavior, and do not convert the
  aggregate into an admission or preflight decision.
- Do not redefine any existing counter's meaning or relabel historical results.
- Do not add recovery, reconciliation, or compensation capability.
- Do not include requirement text, prompts, repository contents, absolute paths,
  credentials, or provider data.

**Completion criteria:**

- The aggregate is deterministic, bounded, DLP-safe, and covered by tests that
  prove every contributing path.
- Documentation states explicitly that the aggregate observes and does not gate.
- Targeted tests and the full quality gates pass; a completion report and one
  focused commit are produced.

---

## T-080 — Evidence Freshness and Snapshot Integrity Bound

**Dependency gate:** T-079 closed.

**Goal:** State and verify one additional boundary about evidence snapshot
integrity: that the evidence a run claims to have used is the evidence that was
actually current when the run acted, and that any field-coverage question in the
evidence hash contract is resolved explicitly rather than by assumption.

**Motivating observation (unverified):** `EvidenceBundle._calculate_hash()`
currently hashes `matched_files`, `selected_files`, `searched_terms`, excerpts,
and `truncated`. It does not hash `source_hashes`, `tool_call_records`,
`warnings`, `project_summary`, or `technology_stack`. This is a **source-code
inference, not an executed observation**, and must be confirmed by experiment
before it is treated as a finding.

**Scope boundary:**

- Establish which fields the evidence hash is required to cover and why, and
  record that decision explicitly.
- Establish whether evidence collection and artifact persistence can observe a
  repository state that changed in between, and state the resulting bound.
- Confine any change to the evidence and artifact boundary. Do not alter the
  agent topology, prompts, or provider path.

**Non-goals:**

- Do not introduce repository watching, file locking, filesystem snapshots, or
  any OS-level change-detection mechanism.
- Do not add a cache, TTL, or refresh mechanism; T-074 already owns caching.
- Do not claim that a freshness check makes concurrent repository modification
  impossible. The deliverable is a stated, tested bound, not a guarantee of
  exclusion.
- Do not rewrite the historical benchmark baseline as newly measured evidence.
- Do not change the evidence contract silently; a contract change requires its
  own recorded decision and regenerated fixtures where applicable.

**Completion criteria:**

- The hash-coverage decision and the freshness bound are both written down and
  each is backed by a test, not by prose alone.
- The unverified motivating observation above is either confirmed by experiment
  or withdrawn, and the report says which.
- Targeted tests and the full quality gates pass; a completion report and one
  focused commit are produced.

---

## T-081 — Multi-Process Boundary Probe (explicitly non-claiming)

**Dependency gate:** milestone assurance review approved.

**Goal:** Observe, under a bounded and clearly labelled experiment, what
happens to a run when a second process interacts with the same lifecycle store or
artifact directory, and record the observation so the single-process limit is
documented from evidence rather than from an assumption.

**Scope boundary:**

- This task is an observation and documentation task. It is explicitly
  **non-claiming**: it may not assert resilience, coordination, correctness, or
  safety under multiple processes.
- Its required output includes the statement that M10 provides single-process
  guarantees only, and that the observed multi-process behavior is neither
  supported nor guaranteed.

**Non-goals:**

- Do not implement multi-process coordination, distributed locks, single-flight
  across processes, shared rate limiting, a job queue, a background worker, or
  durable execution.
- Do not fix any defect the probe reveals. Record it as an unresolved risk and
  authorize nothing.
- Do not present the probe as a stress test, load test, or capacity result.
- Do not use the probe to justify or pre-announce a later milestone.

**Completion criteria:**

- The probe is deterministic where possible, or its non-determinism is stated
  explicitly with the reason.
- The report contains the single-process limitation statement required above and
  an unresolved-risk list.
- Targeted tests or documented manual reproduction steps pass the applicable
  quality gates; a completion report and one focused commit are produced.

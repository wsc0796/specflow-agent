# D1 evidence correction — 2026-09-11

## Facts versus claims

| Finding | Assessment basis | Actual identity/version | Current reproduction | Disposition |
|---|---|---|---|---|
| Empty `{}` required outputs accepted | Reported historical runs `0d5c2fd450ab`, `82160eef3e3a` | Original artifacts not located in authorized project/known artifact roots | At `1b441277`, all six role empty/missing-summary cases already fail through real AgentRunner | Preserve protection; add offline regression; missing artifacts do not disprove history |
| Blank/title-only outputs accepted | Current payload schema and recording provider | `1b441277` plus synthetic fixture, no network | Six blank-summary and six role-content cases reproduce | Tighten existing payload schemas |
| Explicit schema failure overwritten | `_validate_stage_results` | Current baseline stage injection | Consumer was called despite schema_validated=false | Stop before scheduling consumers |
| M6 is current strict-contract live validation | README / M6 / resume / demo | Two distinct old artifact sets, source/target commits unknown | Both have five unvalidated outputs | Narrow current claims and add dated historical correction |
| Provider knows required output structure | Recorded actual AgentRunner request | Current baseline | No role output schema in request | Include registry-derived JSON Schema and minimum requirements |
| Multi-agent is faster/better live | Historical mock A/B text | Mock comparison; legacy live failure recorded | No valid live pair or independent quality rating | Withdraw inference, preserve failed historical outcome |

## Original artifact identity

The original files remain read-only in the previously known `artifacts-live-multi`
and `artifacts-ab-live/multi` roots. Samples A and B both use
`run-multi-e5b97497dfd5`, matching manifest.run_id, but differ in timestamp and
manifest/output/handoff/trace hashes. They are not interchangeable.

| Field | A | B |
|---|---|---|
| Trace time (UTC, 2026-07-12) | 08:46:47–08:47:26 | 08:59:59–09:00:35 |
| Model in original | deepseek-v4-flash | deepseek-v4-flash |
| Provider/live mode | absent in original; M6 document says openai-compatible/live | absent in original |
| Source / target commit | unknown / unknown | unknown / unknown |
| Format | unversioned JSON | unversioned JSON |
| enriched / plan.degraded_agents | true / [] | true / [] |
| Execution | 6 success=true; no execution degraded field | same |
| Business output | all six nonempty; five schema_validated=false, Review=true | same |
| Review / workflow | PASS / completed | PASS / completed |
| Raw exit code | unknown (M6 document says 0) | unknown |
| Handoffs | 7, canonical output hashes match | 7, canonical output hashes match |

Review's historical business output is itself an envelope with nested review
content, not today's ReviewPayload. Do not describe these samples as six empty
objects, or as current strict-schema successes. The evidence establishes the
recorded old execution and hash consistency, not output usefulness.

`enriched` and `plan.degraded_agents` describe task-brief semantic enrichment.
Execution failure is the result envelope's success flag; business validity is
the role schema; permitted execution degradation can still carry valid output.
These are separate dimensions. No inference about failed execution follows from
plan degradation alone.

## Sources and safe derivative

- Runtime and current-claim snapshot: `1b44127747a7f7b8bfd9118eb56006d867986b39`.
- M6 record source: `ccd41bf5e20b`; A/B source: `c9d1af2ee505`.
- Historical implementation reference: `2199eee` allowed success=true after
  best-effort schema failure. This explains the old contract but does not assign
  an unknown artifact source commit.
- README/resume/demo phrasing traces include `a113f738e598`, `4894d0e2a66a`,
  `f20f48bbb16d`, `c6d779c22de2`, `ab25b1f9c166`.
- [Safe field-level summary](../evidence/t081/historical-output-summary.json)
  contains each original file's SHA-256 separately. It retains only status,
  top-level field names, shape/content-presence and list lengths. It removes
  business text, private requirements, absolute paths, repository source,
  original responses and unrelated metadata. Its hash is recorded separately
  in the completion report; it must not be attributed a raw-file hash.
- [Synthetic fixture](../../tests/fixtures/required-output-validity.json) is a
  newly authored status-route example, NOT an original historical execution.

Hashes identify bytes; they do not authenticate provenance or prove execution.
The unlocated historical runs remain unverified and are not replaced by new runs.

## Remaining quality gate (D3/D4, not completed here)

Reuse `docs/evaluation/live-ab/protocol.md` and its human rubric for order timeout,
cache invalidation and order idempotency. Before generating anything, fix each
target repository commit and independent facts/files/constraints, positive,
boundary/failure cases and prohibited suggestions. Accept multiple valid designs.
Then obtain provider/model, data-export authorization, request/token/cost caps,
retry limits and retention/redaction scope. Three cases × two pipelines are six
pipeline executions, not six provider calls. Count planning/retry calls and keep
failures in the statistics. No live run or independently rated output quality
was produced by T-081; schema validity and generator PASS are not quality proof.

# T-063 - Live Provider Evaluation v1

## Goal

Run a small, frozen, evidence-backed evaluation against one real
OpenAI-compatible LLM Provider. The result must distinguish deterministic
runtime checks from human quality review and must never represent Mock output
as live-model quality evidence.

## Allowed scope

- A six-task evaluation suite: five quality tasks and one budget-control task.
- Credential-safe response capture, evaluation-specific artifact normalization,
  deterministic validation, and report generation.
- Small internal hooks needed to inject an evaluation recording LLM client into
  the existing multi-agent runner. The public CLI and normal artifact policy
  remain unchanged.
- Focused tests, a completion report, and a separate review PR.

## Non-goals

- A production benchmark, deployment, distributed rate limiter, or new Agent.
- New tools, a framework migration, RAG, or automatic code modification.
- Storing API keys, request headers, raw prompts, or unredacted Provider data.
- Treating an Agent review decision as the final human evaluation outcome.

## Frozen Suite

The five quality tasks under `evals/live-provider-v1/tasks/` target
`wsc0796/sky-takeout-python` at commit
`4ede5d01039be8c703e4cc2cc94f18084ebf1ba1`. Their bytes are locked in
`suite-lock.json`. The control under `controls/budget-guard.yaml` proves a
real Provider run is stopped by the call budget and is reported separately
from the quality sample.

Each quality task must contain:

- `task_id`
- `repository`
- `repository_commit`
- `user_request`
- `expected_files`
- `required_evidence`
- `required_output_fields`
- `forbidden_assumptions`
- `timeout_seconds`
- `human_notes`

The target repository must be at the recorded commit with a clean worktree
before any Provider request is made.

Every live batch is recorded before its first Provider request. Its manifest
binds the batch ID, suite-lock hash, clean SpecFlow commit, frozen task hashes,
and hashes for each immutable evidence file. Reports load only the
manifest-declared attempts and reject incomplete, duplicate, or changed
evidence. Test doubles may exercise the harness internally, but their
`test_double` provenance cannot generate a live Provider report.

## Acceptance

1. The harness rejects Mock mode, incomplete Provider configuration, an
   invalid pricing rule, an unlocked/modified task, a wrong target commit, or
   a dirty target repository before a Provider client is created.
2. Every attempt persists a task copy, non-secret config, redacted Provider
   response bodies, tool-call JSONL, trace JSONL, runner artifacts,
   deterministic result, and a pending human-review template.
3. Raw response capture is opt-in for this evaluator only, thread-safe, and
   redacts credential values, authorization syntax, sensitive key/value pairs,
   and absolute file paths. It does not capture requests or headers.
4. Deterministic validation reports runtime completion, schema result,
   artifact-integrity result, tool/path boundary result, parseable file
   references, required-evidence coverage, forbidden-assumption hits, token
   usage, end-to-end latency, cost estimate rule, and safe failure category.
   Required evidence is covered only when an Agent output cites the path,
   `sources.json` contains a hash for the collected source path, and that hash
   matches the sanitized content from the frozen target commit.
5. The generated report includes sample count, completion rate, schema success
   rate, file-reference validity, required-evidence coverage, P50/P95 latency,
   input/output tokens, cost estimate, failure categories, failure examples,
   human-review method, and limits. It labels unfinished human review as
   pending rather than PASS.
6. The five quality tasks and the budget control are run only with an actual
   configured Provider. A missing credential or pricing source is a BLOCKED
   state, not a failed or fabricated evaluation.
   The budget control cannot be skipped in a v1 report.
7. Focused tests, full pytest, Ruff checks, formatting, secret scan, build,
   and `git diff --check` have recorded outcomes.

## Known limits

- Five quality tasks are a small, repository-specific sample; they do not
  establish production reliability or model accuracy.
- P50/P95 are descriptive statistics over completed live quality samples only.
- Cost is an estimate based on the user-supplied, versioned pricing rule and
  Provider-reported token counts. It includes declared quality and control
  attempts only when every Provider request reports usage; otherwise it is
  unavailable rather than treated as zero.

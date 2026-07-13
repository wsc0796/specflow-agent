# T-040 — ExecutionPolicy and Error Taxonomy

## Goal
Establish a unified, deterministic, testable execution policy layer managing
time/call/token/revision/artifact limits, a classified error taxonomy, safe
error messages, and a RuntimeGuard for budget enforcement.

## In Scope
- Split ExecutionPolicy into RepositoryPolicy, TokenPolicy, RetryPolicy, ArtifactPolicy
- Add SpecFlowError with safe_message, details, internal_error_id
- Add RunOutcome with unified status mapping
- Add RuntimeGuard for budget consumption checks
- Integrate into Multi-Agent runner (policy_hash in manifest, guard checks)
- Default conservative policy

## Out of Scope
- Strict schema (T-041)
- Typed fallback (T-042)
- Real tokenizer (T-043)
- Full redaction (T-044)
- Persistence (T-045)
- API service (T-046)

## Acceptance Criteria
- 637 existing tests still pass
- New targeted tests for policy, guard, outcome
- Multi-Agent Mock Run produces manifest with policy_hash
- Legacy Mock Run not regressed

# M8 Production Hardening — Review Remediation Scope

## Goal

Resolve the independent review findings for the multi-agent runtime without
changing the target repository or adding API/deployment capabilities.

## Allowed scope

- Execution policy and classified retry boundaries.
- Strict input/output schemas, required-agent failure handling, review and
  revision handoff integrity.
- Evidence safety, artifact redaction, metrics, traces, and regression tests.
- README, AGENTS, M8 report, and milestone record updates.

## Forbidden scope

- API service, authentication, rate limiting, Docker, or deployment work.
- Legacy raw pass-through, default review PASS, security-error retry, hidden
  failures, or user-visible exception text.
- Any target-repository modification.

## Acceptance

Run the full pytest/Ruff/diff gates, then use the documented CLI syntax for a
legacy mock and a six-agent multi-agent mock against the specified read-only
target repository. Record artifact contract evidence in the completion report.

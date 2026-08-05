# T-063 — DLP Pipeline Parity

## Goal

Make the final DLP boundary consistent across the preserved legacy pipeline and
the multi-agent artifact and handoff path.

## Allowed scope

- Apply the existing `final_dlp_scan` before legacy evidence is supplied to a
  worker or live provider.
- Apply the same complete DLP ruleset to string values in multi-agent outputs
  before schema validation, handoff creation, and artifact persistence.
- Add focused regression tests and reconcile the README's pipeline statement.

## Non-goals

- Authentication, authorization, deployment, or rate-limit architecture.
- New DLP patterns, external services, or dependencies.
- Changes to agent topology, schemas, provider behavior, or legacy workflow
  sequencing.

## Acceptance

1. Both runners explicitly pass collected evidence through `final_dlp_scan`
   before it can enter an LLM context.
2. Multi-agent output values redact standalone provider tokens, JWTs, and
   assignment-style secrets while preserving the absolute-path redaction.
3. Sanitized outputs remain the payload source for handoffs and persisted
   `agent-outputs.json`.
4. Focused tests, full pytest, Ruff checks, formatting, `git diff --check`,
   and a secret scan have recorded outcomes.

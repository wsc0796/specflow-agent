# Frozen Decisions

- D-001: `max_provider_call_attempts` defaults to 24.
- D-002: 48 requires explicit Live, Evaluation, or high-retry experiment configuration.
- D-003: A second REJECT after revision exhaustion enters `NEEDS_HUMAN_REVIEW`.
- D-004: Missing provider usage makes aggregate token totals unknown, never zero.
- D-005: Stage agents may not update the benchmark baseline.
- D-006: Historical trigger snapshots and terminal run snapshots are separate facts.
- D-007: Mock smoke validates contracts and harness mechanics, not model quality or fairness.
- D-008: Live and paid evaluation calls require explicit provider/model and USD cost caps.
- D-009: Final Sol release verdict at the verified remediation commit is `NOT_READY`.
- D-010: Uncommitted HTTP API auth changes from a separate workspace are not
  evidence and are not integrated; authentication requires a new scoped task,
  result commit, and independent audit.

# Study ADRs

Use this directory for decisions that affect the 30-day learning track, such as
the Repository RAG contract, vector storage, no-answer policy, provider/index
version binding, and whether benchmark evidence justifies Hybrid or Rerank.

## Naming

Use `ADR-NNN-short-title.md`, starting with `ADR-001`.

## Required sections

Each ADR records:

1. status and decision date;
2. the concrete problem and non-goals;
3. the decision and the evidence available at that time;
4. alternatives considered and why they were rejected;
5. consequences, rollback conditions, and unresolved risks;
6. links to the relevant task, test, benchmark, trace, or evidence card.

Do not present an initial hypothesis as a validated decision. In particular,
the Day 8 no-answer rule is `T0` until calibrated on the Dev set. Holdout data
must remain sealed until the Day 21 strategy freeze, and a Holdout result must
never be used to tune the frozen version.

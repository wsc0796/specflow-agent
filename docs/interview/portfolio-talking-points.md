# SpecFlow Agent Interview Talking Points

## 30-second introduction

I built a controlled multi-agent system for repository analysis and technical
specification generation. The multi-agent path uses a fixed six-agent topology,
schema-validated handoffs and bounded execution policy. I kept the legacy
pipeline as an A/B baseline and added a reproducible 12-case benchmark so a
reviewer can inspect real artifacts instead of trusting a diagram.

## Why fixed topology instead of dynamic agents?

The problem has stable dependencies: repository analysis first, three specialist
views in parallel, synthesis, then review. A fixed topology makes dependencies,
permissions and termination conditions auditable. The LLM can enrich task
content but cannot change the graph or increase the revision budget.

## How do you control unreliable model output?

Sender output and receiver input are validated against strict Pydantic payload
schemas. Missing schemas, invalid fields and unknown fields fail closed on the
multi-agent path. The runtime records safe error codes and artifacts rather than
passing unvalidated text downstream.

## How do you control cost and runaway execution?

`RuntimeGuard` is the multi-agent budget authority. It enforces LLM-call,
input/output-token, total-token, revision, concurrency, wall-time and artifact
limits. The legacy runner stays separate as the A/B compatibility baseline.

## How do you evaluate it?

The portfolio benchmark has 12 committed fixture-grounded cases. It reports
schema pass rate, completion/degraded/fallback rates, token totals, latency and
error-code counts. The committed baseline is mock-only: it proves reproducible
runtime contracts, not model quality or real token cost.

## What are the limits?

The current portfolio release has no new live-provider result because credentials
were unavailable. It does not include persistence, an API service, deployment or
dynamic agent routing. Those are deliberately deferred until benchmark or user
evidence identifies a concrete need.

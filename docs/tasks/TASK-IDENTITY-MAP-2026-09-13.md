# Task identity reconciliation — 2026-09-13

This mapping is part of the owner-approved isolated runtime-repair integration.
The frozen M9/M10 meanings of T-070 through T-080 remain authoritative and unchanged.
Renumbering another PR's tasks does not complete any M9/M10 dependency.

The incoming PR #9 source is
`c6c893c3a723a3f62c33265394ed1fcbf1c6029b`. These new identifiers were checked
against the pinned main and PR #6/#7/#8/#9/#10 trees and were unoccupied.

| PR #9 original ID | Integration ID | Task | Report |
| --- | --- | --- | --- |
| T-070 | LEARN-001 | [V5.1 learning environment](LEARN-001-v5-1-learning-environment.md) | [Historical report](../reports/LEARN-001-completion-report.md) |
| T-071 | LEARN-002 | [V5.3 learning upgrade](LEARN-002-v5-3-learning-environment-upgrade.md) | [Historical report](../reports/LEARN-002-completion-report.md) |
| T-072 | T-083 | [No-evidence fail-closed boundary](T-083-no-evidence-fail-closed.md) | [Source implementation report](../reports/T-083-completion-report.md) |
| T-073 | T-084 | [Handoff integrity failure observability](T-084-handoff-integrity-failure-observability.md) | [Source implementation report](../reports/T-084-completion-report.md) |

The T-083/T-084 requirement and acceptance IDs follow the new numbering. Only
identity and links change; their original failure conditions and boundaries do
not change. Source branch names (including `codex/t072-no-evidence-fail-closed`),
dates, commit references and original validation counts are retained as historical
facts. New source-note blocks identify the original path and number explicitly.

`docs/reports/T-070-completion-report.md` continues to describe M9 single-flight
and its A01 repair. No runtime completion report is fabricated for M9 T-071,
T-072 or T-073. The historical LEARN-002 V5.3 migration is not the current learning
mode: the active roadmap remains V5.3.2. Study CURRENT/evidence updates in this
integration change links/identifiers only, not learner progress or ownership.

The T-084 original implementation and the later study-record synchronization at
`2c6e0a9` remain distinct historical changes. Their reports do not claim that the
original product patch included that later administrative study change.

T-081 and T-082 remain the separately reviewed output-validity and prompt-package
repairs from PR #7 and PR #10. Integrated execution evidence belongs in
[the integration report](../reports/runtime-repairs-integration-2026-09-13.md),
not in the historical standalone validation counts.

# T-060 — Portfolio Application Materials

**Goal:** create a current, evidence-bounded resume V0 and three-minute project
talk for internship applications without changing SpecFlow product behavior.

**Allowed scope:** README plus current `docs/resume/` and `docs/demo/` material,
this task record and its completion report.

**Facts allowed in current materials:** v1.1.0 unreleased candidate; 671 passed,
2 skipped; 12-case mock contract benchmark; fixed six-agent topology;
RuntimeGuard; schema-validated handoffs; read-only evidence pipeline; current
CI gates.

**Historical-only fact:** the M6 DeepSeek live-provider run may be named only as
separate historical validation, never as v1.1.0 benchmark or release evidence.

**Forbidden scope:** product code, tests, package version, Agent runtime,
provider behavior, release tags, and claims about production deployment,
semantic accuracy, cost reduction, or user traffic.

**Verification:** current release metadata test, full pytest, Ruff check/format,
secret scan, and `git diff --check`.

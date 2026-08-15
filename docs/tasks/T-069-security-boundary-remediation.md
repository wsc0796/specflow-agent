# T-069 — Security Boundary Remediation

## Goal

Close the independent-review gaps in repository path validation, prompt-data
trust, HTTP allowlist defaults, and tracked-file credential scanning without
expanding the product scope.

## Requirements

- **REQ-069-1:** Repository scanning must reject Windows reparse-point escapes
  and roots inside ignored directories.
- **REQ-069-2:** Repository-derived prompt content must be explicitly delimited
  and treated as untrusted data.
- **REQ-069-3:** HTTP repository validation must fail closed when no allowed
  roots are configured; CLI and MCP behavior must remain unchanged.
- **REQ-069-4:** The credential gate must scan tracked documentation and tests,
  detect supported assignment/cloud-key forms, and permit DLP test fixtures only
  when their source representation cannot be mistaken for a committed secret.
- **REQ-069-5:** The HTTP synchronous execution and timeout boundary must be
  documented honestly.

## Boundaries

- No asynchronous worker, queue, deployment, identity, authorization, or
  multi-tenant behavior is added.
- No live-provider run or external publication is authorized.

## Acceptance

- **AC-069-1:** Full pytest passes with only the documented Windows skips.
- **AC-069-2:** Ruff check and format gates pass.
- **AC-069-3:** The tracked-file credential scan passes on the final tree and
  rejects a temporary detection probe.
- **AC-069-4:** Prompt templates contain the untrusted-data boundary marker.
- **AC-069-5:** Git diff inspection contains only the scoped remediation,
  supporting tests, release metadata, and completion records.

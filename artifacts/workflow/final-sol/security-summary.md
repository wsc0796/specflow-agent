# Security Summary

- MCP real subprocess covers invalid arguments, unknown tools, traversal, sensitive
  file rejection, secret non-disclosure, structured error type, and clean EOF.
- Tool execution remains routed through `ToolExecutor` and repository policy.
- Secret scan now covers all tracked UTF-8 text, including docs and tests.
- Test-only allowlists are limited to explicit fake redaction markers and assertions.
- Tracked Pilot debug output was removed and ignored; release artifacts no longer
  contain the audited developer-local repository roots.
- No credential value was copied into Final Sol artifacts.

Residual: MCP publication schemas do not encode every instance-specific runtime limit;
runtime enforcement remains fail-closed and the Claim is qualified.

The current HTTP API does not claim authentication or authorization. Separate
uncommitted hardening changes were not integrated and require a fresh audited task.

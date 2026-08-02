# Claim-Evidence Ledger

This ledger describes only behavior directly supported by the current repository and its tests.
Mock-provider evidence is not live-provider validation or evidence of output-quality improvement.

| Claim | Status | Code evidence | Test evidence | Allowed now | Notes |
| --- | --- | --- | --- | --- | --- |
| Task Brief uses a strict, versioned schema | VERIFIED | `specflow.plan.models.SemanticTaskBrief` and related strict Pydantic models | `tests/test_semantic_enricher.py`, `tests/test_task_brief_execution.py` | Yes | Identity and status fields are code-owned; model output is limited to `TaskBriefDraft`. |
| Six roles consume only their own Task Brief | VERIFIED | `runner_multi._validated_inputs`, `agents.adapter.AgentRunner.execute` | `TestMultiAgentRunner.test_real_agent_requests_persist_consumed_events_and_task_brief_artifact` | Yes | Verified with the real request-construction path and a deterministic fake provider, not a live provider. |
| Task Brief observably affects the worker LLM request | VERIFIED | `agents.adapter._build_user_message` | `test_task_brief_change_changes_only_target_real_llm_request_section` | Yes | Only the target Role Task Brief section changes; requirement, evidence, prior output, and output contract remain equal. |
| Task Brief generation, consumption, artifact, and hash are auditable | VERIFIED | `TaskBriefArtifact`, `TaskBriefTraceEvent`, multi-agent manifest wiring | `tests/test_cli_multi_agent.py`, `tests/test_task_brief_execution.py` | Yes | Trace remains metadata-only and the manifest hash is revalidated from the artifact. |
| All LLM calls use one RuntimeGuard budget | REJECTED | Phase 0 found enrichment calls outside unified Guard accounting | Not covered in Phase 1 | No | Deferred to Phase 3; default budget was not changed. |
| Review findings drive revision | REJECTED | Phase 0 found findings absent from revision input | Not covered in Phase 1 | No | Phase 2 scope; no Review/Revision behavior changed here. |
| Task Brief improves result quality | PENDING | No comparative quality evidence | Mock contract tests only | No | Requires a separately approved evaluation against a fixed dataset. |
| Six agents outperform a single agent | PENDING | No controlled comparison proving causality | Existing mock benchmark is contract-only | No | Do not infer quality from topology or test count. |
| Mock benchmark is live validation | REJECTED | Benchmark mode is `mock_contract` | 12-case mock benchmark | No | Mock results demonstrate deterministic contract stability only. |
| Interrupted Runs resume execution | REJECTED | Current startup handling classifies interrupted records as failed | No execution-resume test | No | Classification is not resume. |
| Production-ready | REJECTED | Single-process, mock-only API and unresolved runtime limits | No production validation | No | Authentication, deployment, unified budgeting, and live reliability remain unproven. |

## Phase 2 additions (finding-driven revision)

| Claim | Status | Code evidence | Test evidence | Allowed now | Notes |
| --- | --- | --- | --- | --- | --- |
| Review findings use a strict, structured schema with stable IDs | VERIFIED | `specflow.revision.models.ReviewFinding`, `derive_finding_id` | `tests/test_finding_driven_revision.py::TestFindingSchema` | Yes | `extra="forbid"`; legacy string findings are rejected, never promoted. |
| Real review findings drive the target agent's revision request | VERIFIED | `runner_multi` finding grouping, `agents.adapter._build_revision_user_message` | `test_findings_prior_output_and_round_enter_real_request`, `test_changing_finding_changes_only_findings_section` | Yes | Captured on the real `LLMRequest`; only the findings section changes when a finding changes. |
| Revision uses prior output, Task Brief, evidence, and an explicit round | VERIFIED | `RevisionInput`, `RevisionContext`, revision prompt sections | `TestRevisionRequestWiring` | Yes | Prior output hash is derived and verified; mismatch fails before any provider call. |
| Every finding has exactly one auditable resolution | VERIFIED | `RevisionResult.build` | `TestRevisionResultSchema` | Yes | Missing, unknown, or duplicate resolution IDs are rejected. |
| Bounded revision ends in NEEDS_HUMAN_REVIEW after a second rejection | VERIFIED | `MultiAgentWorkflowState.NEEDS_HUMAN_REVIEW`, runner terminal state | `test_golden_needs_human_review_case`, state machine tests | Yes | Never marked as ordinary COMPLETED. |
| Findings, revisions, and resolutions replay through artifact/trace/manifest | VERIFIED | `review-findings.json`, `revision-*.json`, `finding-resolutions.json`, manifest hashes | `test_manifest_records_revision_artifact_hashes`, trace assertions | Yes | Trace is metadata-only; prompt content is never persisted. |
| Revision improves overall output quality | REJECTED | No comparative evidence | Mock contract tests only | No | Requires the separately approved Phase 6/7 evaluation. |

## Phase 3 additions (unified invocation and budget)

| Claim | Status | Code evidence | Test evidence | Allowed now | Notes |
| --- | --- | --- | --- | --- | --- |
| Multi-agent runtime provider calls use one controlled entry | VERIFIED | `specflow.invoker.GuardedModelInvoker`, enricher + AgentRunner wiring | `tests/test_runtime_budget.py::TestStaticGate`, trace event assertions | Yes | Static gate prevents new direct `.complete()` calls; legacy 3-worker is a frozen A/B baseline. |
| Agent invocation and provider attempt are distinct metrics | VERIFIED | `RuntimeGuard` counters + `snapshot()` | `test_agent_invocation_and_provider_attempt_are_separate` | Yes | One invocation may contain multiple attempts (retries). |
| Retry attempts are independently audited | VERIFIED | invoker retry loop, MODEL_CALL_RETRYING/FAILED/SUCCEEDED events | `TestRetryAccounting` | Yes | Failures are never overwritten by the final success. |
| Tokens come from provider usage; missing usage is unknown, not 0 | VERIFIED | `LLMResponse.usage` optional, provider parse, guard token accounting | `TestTokenAccounting` | Yes | `token_usage_known=false`, `unknown_calls` increment. |
| Budget failures fail closed with terminal snapshots and partial traces | VERIFIED_AT_COMMIT | reserve/release atomicity, current terminal snapshot plus separate triggering snapshot | `TestFailureArtifacts`, `test_failed_manifest_uses_terminal_agent_snapshot` | Yes | Verified at `06b1cf2`; active counts are restored and failure envelopes increment `failed`. |
| Token aggregates remain unknown when any provider usage is missing | VERIFIED_AT_COMMIT | nullable aggregate plus `known_*` subtotals in `RuntimeGuard.snapshot()` | mixed known/unknown and failed-retry tests in `test_runtime_budget.py` | Yes | Verified at `06b1cf2`; partial known totals are never presented as complete totals. |
| Retry token reserve is enforced | VERIFIED_AT_COMMIT | retry identity on `ProviderAttempt`; normal/retry total limits | reserve boundary tests in `test_runtime_budget.py` | Yes | Initial attempts cannot consume the reserve; retry attempts may use it. |
| Default provider-attempt budget supports bounded request paths | VERIFIED_AT_COMMIT | effective default and alias are 24; normal path 12; single-target revision path 15 | `tests/test_budget_calibration.py` | Qualified | Verified at `06b1cf2`. Multi-target revision cost is `12 + targets + 2`; 48 requires explicit configuration. |
| All LLM calls (including legacy 3-worker) use the unified invoker | REJECTED | legacy `workers/` + `runner.py` untouched | Static gate allowlist | No | Legacy pipeline is the frozen Phase 6 A/B baseline. |

## Phase 5 additions (MCP and release)

| Claim | Status | Code evidence | Test evidence | Allowed now | Notes |
| --- | --- | --- | --- | --- | --- |
| MCP tools/list publishes the Tool-owned input schema | VERIFIED_AT_COMMIT | `Tool.input_schema`, `McpToolCatalog` reads `registry.input_schema` | `test_catalog_schema_is_the_tool_owned_schema` | Qualified | Verified at `06b1cf2`; this is a publication source, not proof that instance-specific policy limits cannot be stricter. |
| MCP published schemas and runtime policy validation cannot drift | PARTIALLY_VERIFIED | runtime enforcement remains fail-closed | non-default repository policy audit | No | Instance-specific limits are not encoded in every published schema. Do not claim a single validation source until this is redesigned. |
| MCP tools/call reuses ToolExecutor and the repository security policy | VERIFIED_AT_COMMIT | `McpServer._handle_tools_call` -> `ToolExecutor` | MCP/tool suite 102 passed, 1 skipped | Yes | Verified at `06b1cf2`; no protocol-layer business logic. |
| MCP protocol negotiation and stdio have real subprocess coverage | VERIFIED_AT_COMMIT | explicit initialize lifecycle and supported-version negotiation | expanded `test_stdio_subprocess_smoke`; MCP/tool suite 102 passed, 1 skipped | Yes | Verified at `06b1cf2`; covers valid call, invalid args, unknown tool, traversal, sensitive file rejection, redaction, and clean EOF. |
| Tool failures expose a machine-readable error type | VERIFIED | `tool_result_to_mcp` `structuredContent.error_type` | MCP adapter tests | Yes | Additive; text stays for compatibility. |
| Core type-check gate (pyright) | DEFER | 46 errors across 6 files, dominated by runner_multi.py | `artifacts/workflow/final-sol-backlog.md` | No | Not forced; backlogged for Sol. |

## Phase 6/7 additions (evaluation)

| Claim | Status | Code evidence | Test evidence | Allowed now | Notes |
| --- | --- | --- | --- | --- | --- |
| Pilot mock harness mechanics are deterministic | VERIFIED_AT_COMMIT | `evaluation.pilot` candidate derivation, cost collector, blind pack | `tests/test_pilot_harness.py`; fixed 15-run smoke | Qualified | Verified at `06b1cf2`; single mock receives requirement only, legacy uses native artifacts, and reviewer pack withholds the seed. This is not a fair quality comparison. |
| 5-case pilot dataset is authored and grounded in the fixture repo | VERIFIED_AT_COMMIT | `evaluation/pilot/cases/*.json` | loader and gold-isolation tests | Qualified | Verified at `06b1cf2`; expected labels are scorer-only in the implemented mock single path. Live protocol is not frozen. |
| Three pipelines have a frozen fair comparison protocol | REJECTED | `frozen-config.json` remains `DRAFT_PENDING_USER_APPROVAL`; pipeline capabilities differ | independent evaluation audit | No | No quality or cost comparison may be published from the mock smoke. |
| 30-case formal dataset drafted | PARTIALLY_VERIFIED | `evaluation/formal/dataset.jsonl` + deterministic generator | 30 unique rows; generator rerun byte-stable | Qualified | Dataset authoring only. No committed formal runner or six-run dry-run evidence exists; protocol freeze is pending. |
| Pilot/Formal live-provider execution | BLOCKED | no cost cap / provider approval | `limitations.md` | No | HARD_BLOCKER: `SPECFLOW_LIVE_MAX_COST_USD` / `SPECFLOW_EVAL_MAX_COST_USD` absent. |
| Live-provider validation | BLOCKED | no explicit cost ceiling or model approval | `live-summary.md` (handoff) | No | Verifier + templates ready; run not executed. |
| Six-agent quality improvement | REJECTED | no comparative evidence | — | No | Requires the blocked paid evaluation. |
| Release-ready | REJECTED | — | — | No | Single-process, mock-verified, evaluation pending. |

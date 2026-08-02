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
| Budget failures fail closed with snapshots and partial traces | VERIFIED | reserve/release atomicity, failed manifests | `TestFailureArtifacts`, runner planning-failure snapshot | Yes | Active count restored on every path; never max+1. |
| Default provider-attempt budget supports the live path | VERIFIED | default `max_provider_call_attempts=24`; normal path 12, one revision 15 | `tests/test_budget_calibration.py` | Yes | 48 is never a global default; only explicit Live/Evaluation/experiment config. |
| All LLM calls (including legacy 3-worker) use the unified invoker | REJECTED | legacy `workers/` + `runner.py` untouched | Static gate allowlist | No | Legacy pipeline is the frozen Phase 6 A/B baseline. |

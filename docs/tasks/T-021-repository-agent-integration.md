# T-021 - Repository-aware Agent Integration

## Goal

Wire the M5 Tool Framework and real repository tools into the existing M4 Agent
Workflow so that Analyze/Generate/Review workers consume real repository evidence
instead of only static project context.

This task maps to the attachment's T-020 Agent Integration slice because the
repository had already assigned T-020 to the OpenAI-compatible Provider.

## Building

- `EvidenceExcerpt` — one bounded, sanitized excerpt from a repository file.
- `ToolCallRecord` — sanitized record of one tool execution.
- `EvidenceCollectionConfig` — bounded configuration for evidence collection.
- `EvidenceBundle` — complete deterministic evidence bundle with stable hash.
- `EvidenceCollector` — uses ToolExecutor to collect repository evidence.
- `extract_keywords` — deterministic keyword extraction from requirement text.
- Integration tests verifying the full pipeline works with Mock LLM.

## Evidence collection pipeline

```text
Requirement
  → extract_keywords (deterministic)
  → list_files (discover candidate files)
  → search_code (for each keyword, bounded)
  → rank_files (by match count + path relevance)
  → read_file (top N, bounded)
  → EvidenceBundle (with stable hash)
  → serialized_context → WorkerContext → AnalyzeWorker
```

## Safety constraints

- Tool call count bounded by `max_tool_calls` (default 30).
- Search keywords bounded by `max_search_keywords` (default 10).
- Selected files bounded by `max_selected_files` (default 5).
- Total evidence characters bounded by `max_total_evidence_chars`.
- Sensitive files never enter evidence.
- No subprocess, no shell, no network access.
- Repository is never modified.

## Keyword extraction

Deterministic extraction supports:
- snake_case identifiers
- CamelCase identifiers
- kebab-case and dot.path patterns
- Chinese compound words (2-6 characters)
- English words (3+ characters, filtered by stop words)
- Technology hints for language/framework terms

## Integration design

The EvidenceCollector integrates with the existing Agent Executor + Worker
pipeline without modifying M4 contracts. Evidence is collected once before
the AnalyzeWorker runs, serialized via `EvidenceBundle.serialized_context()`,
and injected into `WorkerContext.project_context` for consumption by workers.

## Testing

`tests/test_evidence_collector.py` (15 tests):
- Keyword extraction from mixed language, bounded, with technology hints
- Evidence collection: listing, matching, reading, determinism, hash stability
- Bounded tool calls, sensitive file exclusion, serialized context limits
- File ranking by match relevance, subprocess prohibition, immutability

`tests/test_repository_agent_integration.py` (8 tests):
- PASS/REJECT full workflow with evidence in context
- EvidenceCollector integration with Agent Executor pipeline
- State history completeness, single worker execution, determinism
- No sensitive leaks, no real network

## Explicitly not implemented

- No Agent Loop or ReAct pattern.
- No automatic tool selection by LLM.
- No write, delete, shell, Git, or network tools.
- No Worker modification.
- No CLI entry point.
- No artifact store.
- No real repository smoke test.
- No T-022 implementation.

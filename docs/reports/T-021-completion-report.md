# T-021 completion report - Repository-aware Agent Integration

## Result

Implemented a bounded, deterministic evidence collection pipeline that uses the
M5 Tool Framework to gather real repository evidence and feeds it into the
existing M4 Agent Workflow.

## Numbering note

This task maps to the attachment's T-020 Agent Integration slice. The repository
already used T-020 for the OpenAI-compatible Provider, so the agent integration
is recorded as T-021 without rewriting published history.

## Architecture

```text
Requirement
  → extract_keywords (deterministic, no LLM)
  → ToolExecutor → list_files
  → ToolExecutor → search_code (per keyword, bounded)
  → rank_files (match count + path relevance + stable tie-break)
  → ToolExecutor → read_file (top N, bounded, sanitized)
  → EvidenceBundle (stable hash)
  → serialized_context → WorkerContext.project_context
  → AnalyzeWorker → GenerateWorker → ReviewWorker
```

## New modules

`src/specflow/evidence/`:
- `models.py` — EvidenceExcerpt, ToolCallRecord, EvidenceCollectionConfig, EvidenceBundle
- `collector.py` — EvidenceCollector (uses ToolExecutor, enforces bounds)
- `keywords.py` — extract_keywords (snake_case, CamelCase, Chinese, English)
- `exceptions.py` — EvidenceError, EvidenceCollectionError, EvidenceLimitError

## EvidenceBundle contract

- `run_id`, `requirement`, `repository_root` — required, validated
- `project_summary`, `technology_stack` — from scanner context
- `searched_terms` — deterministic keywords extracted from requirement
- `matched_files`, `selected_files` — ranked, bounded
- `excerpts` — EvidenceExcerpt with path, line, excerpt, match_count
- `source_hashes` — content hashes for read files
- `tool_call_records` — sanitized ToolCallRecord per call
- `truncated`, `warnings` — transparency flags
- `evidence_hash` — SHA-256 of stable payload for determinism verification
- `serialized_context()` — bounded text block for prompt injection
- `as_dict()` — JSON-serializable for artifact storage

## Bounded execution

Default limits enforced by EvidenceCollectionConfig:
- max_search_keywords: 10
- max_search_matches: 100
- max_selected_files: 5
- max_file_bytes: 262,144
- max_total_evidence_chars: 50,000
- max_tool_calls: 30

## Safety

- ToolCallRecord summaries are sanitized (no secrets).
- Sensitive files (.env, .pem, id_rsa, etc.) never enter evidence.
- No subprocess, shell, or network calls.
- Repository is never modified.
- EvidenceBundle.as_dict() sanitizes all text fields.

## Tests

`tests/test_evidence_collector.py`: 15 tests
`tests/test_repository_agent_integration.py`: 8 tests

Coverage:
- Keyword extraction (mixed language, bounded, tech hints)
- Evidence collection (listing, searching, reading, determinism)
- Bounded tool calls, file ranking, hash stability
- Sensitive file exclusion, subprocess prohibition, immutability
- PASS/REJECT full workflow with evidence in context
- State history completeness, single execution per worker
- No sensitive leaks, no real network, determinism

## Quality gates

- `uv run pytest tests/test_evidence_collector.py -v`: 15 passed.
- `uv run pytest tests/test_repository_agent_integration.py -v`: 8 passed.
- `uv run pytest -v`: 368 passed, 2 skipped, 1 warning.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 97 files already formatted.

The 2 skipped tests and 1 warning are pre-existing (symlink privileges on
Windows, FastAPI/Starlette TestClient deprecation).

## Explicitly not implemented

- No Agent Loop or ReAct pattern.
- No automatic tool selection by LLM.
- No write, delete, shell, Git, or network tools.
- No Worker modification (contracts unchanged).
- No CLI entry point.
- No artifact store.
- No real repository smoke test.
- No T-022 implementation.

## Next task

T-022 CLI and Artifact Delivery.

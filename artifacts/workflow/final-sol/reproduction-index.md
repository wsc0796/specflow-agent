# Reproduction Index

Run from repository root at `06b1cf2`:

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pytest -q tests/test_mcp_server.py tests/test_mcp_adapter.py tests/test_tool_framework.py tests/test_repository_tools.py
uv run python scripts/check_secrets.py
uv build
uv run specflow --version
uv run specflow run --help
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output <tmp> --baseline <tmp>/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json <tmp>/baseline.json
uv run python scripts/build_phase7_dataset.py
git diff --exit-code -- evaluation/formal/dataset.jsonl evaluation/formal/dataset-card.md
```

Pilot unit and gold-isolation evidence is in `tests/test_pilot_harness.py`.
Raw mock run output remains generated/ignored by policy and is not release evidence.

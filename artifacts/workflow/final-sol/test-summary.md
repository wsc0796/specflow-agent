# Test Summary

- `uv run pytest -q`: 803 passed, 2 skipped, 3 known warnings.
- Affected cross-module matrix: 208 passed, 1 Windows symlink skip.
- MCP/ToolExecutor/repository tool matrix: 102 passed, 1 Windows symlink skip.
- Ruff check: pass.
- Ruff format check: 210 files already formatted.
- Build: source distribution and wheel for 1.1.0 pass.
- CLI: `specflow --version` and `specflow run --help` pass.
- No new skip or xfail was added to hide a failure.

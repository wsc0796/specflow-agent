"""Safe artifact directory writer."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath

from specflow.artifacts.exceptions import ArtifactExistsError, ArtifactWriteError
from specflow.artifacts.models import RunManifest
from specflow.artifacts.renderers import (
    render_run_summary,
    render_technical_spec,
    render_test_plan,
)
from specflow.evidence import EvidenceBundle
from specflow.tools.sanitization import sanitize_tool_text


class ArtifactStore:
    """Write structured artifacts into one output directory."""

    def __init__(self, output_root: Path) -> None:
        self._root = output_root

    def write_run(
        self,
        *,
        run_id: str,
        manifest: RunManifest,
        evidence: EvidenceBundle,
        analysis_json: str,
        generation_json: str,
        review_json: str,
        tool_calls_json: str,
        trace_json: str,
    ) -> Path:
        """Write a complete run directory atomically."""
        run_dir = self._resolve_run_dir(run_id)
        if run_dir.exists():
            raise ArtifactExistsError(f"Run directory already exists: {run_dir}")

        run_dir.mkdir(parents=True, exist_ok=False)
        try:
            _write_json(run_dir / "manifest.json", manifest.as_dict())
            _write_json(run_dir / "sources.json", evidence.as_dict())
            _write_text(run_dir / "analysis.json", analysis_json)
            _write_text(run_dir / "generation.json", generation_json)
            _write_text(run_dir / "review.json", review_json)
            _write_text(run_dir / "tool-calls.json", tool_calls_json)
            _write_text(run_dir / "trace.json", trace_json)

            tech_spec = render_technical_spec(manifest, analysis_json)
            _write_text(run_dir / "technical-spec.md", tech_spec)

            test_plan = render_test_plan(analysis_json, generation_json)
            _write_text(run_dir / "test-plan.md", test_plan)

            summary = render_run_summary(manifest, evidence)
            _write_text(run_dir / "run-summary.md", summary)
        except Exception:
            if run_dir.exists():
                _remove_tree(run_dir)
            raise

        return run_dir

    def _resolve_run_dir(self, run_id: str) -> Path:
        if not run_id or not run_id.strip():
            raise ArtifactWriteError("run_id must not be empty")
        safe = run_id.strip().replace("\\", "/")
        parts = PurePosixPath(safe).parts
        if any(part in {"", ".", ".."} for part in parts):
            raise ArtifactWriteError("run_id must not traverse directories")
        normalized = safe.replace("/", "-")
        if not normalized:
            raise ArtifactWriteError("run_id resolved to empty path")
        return self._root / normalized


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(content, encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.iterdir(), key=lambda p: p.is_dir(), reverse=True):
        if child.is_dir():
            _remove_tree(child)
        else:
            child.unlink()
    path.rmdir()

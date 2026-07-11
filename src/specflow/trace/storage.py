"""JSON trace storage."""

from __future__ import annotations

import json
from pathlib import Path

from specflow.trace.exceptions import TraceError
from specflow.trace.models import LLMTrace


class JsonTraceStorage:
    """Store trace records as JSON files under a controlled root."""

    def __init__(self, traces_root: Path | str = ".traces") -> None:
        self._root = Path(traces_root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def write(self, trace: LLMTrace) -> Path:
        if not trace.run_id.strip() or "/" in trace.run_id or "\\" in trace.run_id:
            raise TraceError("trace.run_id must be a safe filename component")
        self._root.mkdir(parents=True, exist_ok=True)
        path = (self._root / f"{trace.run_id}.json").resolve()
        try:
            path.relative_to(self._root)
        except ValueError:
            raise TraceError("Trace path escapes trace root")
        path.write_text(
            json.dumps(trace.as_dict(), ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return path

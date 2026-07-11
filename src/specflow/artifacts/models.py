"""Artifact store models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from specflow.artifacts.exceptions import ArtifactWriteError
from specflow.tools.sanitization import sanitize_tool_text


@dataclass(frozen=True)
class RunManifest:
    """Structured manifest for one complete run."""

    schema_version: str = "1.0.0"
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    status: str = "unknown"
    provider_type: str = "mock"
    model: str = ""
    repository_root: str = ""
    requirement: str = ""
    requirement_hash: str = ""
    evidence_hash: str = ""
    analysis_hash: str = ""
    generation_hash: str = ""
    review_hash: str = ""
    review_decision: str = ""
    degraded: bool = False
    requires_review: bool = False
    tool_call_count: int = 0
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping with sanitized values."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "provider_type": self.provider_type,
            "model": sanitize_tool_text(self.model),
            "repository_root": self.repository_root,
            "requirement": sanitize_tool_text(self.requirement),
            "requirement_hash": self.requirement_hash,
            "evidence_hash": self.evidence_hash,
            "analysis_hash": self.analysis_hash,
            "generation_hash": self.generation_hash,
            "review_hash": self.review_hash,
            "review_decision": self.review_decision,
            "degraded": self.degraded,
            "requires_review": self.requires_review,
            "tool_call_count": self.tool_call_count,
            "warnings": [sanitize_tool_text(w) for w in self.warnings],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StructuralHashInput:
    agents: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    stages: list[list[str]]
    revision_policy: dict[str, Any]
    constraints: list[dict[str, Any]] = field(default_factory=list)


def _canonical_json(obj: Any) -> bytes:
    """Serialize to canonical JSON: sorted keys, compact, UTF-8."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def compute_structure_hash(input_: StructuralHashInput) -> str:
    """SHA-256 of canonical JSON of sorted structural fields."""
    payload = {
        "agents": sorted(input_.agents, key=lambda a: a["agent_id"]),
        "dependencies": sorted(
            [
                {**d, "depends_on": sorted(d["depends_on"])}
                for d in input_.dependencies
            ],
            key=lambda d: d["agent_id"],
        ),
        "stages": [sorted(stage) for stage in input_.stages],
        "revision_policy": input_.revision_policy,
        "constraints": sorted(input_.constraints, key=lambda c: c["agent_id"]),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_semantic_brief_hash(briefs: list[dict[str, Any]]) -> str:
    """SHA-256 of canonical JSON of semantic task briefs. Excludes provenance/timestamps."""
    payload = sorted(
        [
            {
                "agent_id": b["agent_id"],
                "task_description": b.get("task_description", ""),
                "analysis_focus": sorted(b.get("analysis_focus", [])),
                "evaluation_hints": sorted(b.get("evaluation_hints", [])),
                "repository_scope_hint": b.get("repository_scope_hint", ""),
            }
            for b in briefs
        ],
        key=lambda b: b["agent_id"],
    )
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_effective_plan_hash(structure_hash: str, semantic_brief_hash: str) -> str:
    """SHA-256 of versioned envelope containing both hashes."""
    payload = {
        "hash_version": "specflow-effective-plan-v1",
        "structure_hash": structure_hash,
        "semantic_brief_hash": semantic_brief_hash,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()

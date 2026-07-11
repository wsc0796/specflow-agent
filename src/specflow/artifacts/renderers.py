"""Markdown artifact renderers."""

from __future__ import annotations

import json
from typing import Any

from specflow.artifacts.models import RunManifest
from specflow.evidence import EvidenceBundle
from specflow.tools.sanitization import sanitize_tool_text


def render_technical_spec(manifest: RunManifest, analysis_json: str) -> str:
    """Render a technical specification Markdown document."""
    analysis = _safe_parse_json(analysis_json)
    lines: list[str] = []
    lines.append("# Technical Specification\n")
    lines.append(f"## Requirement\n\n{manifest.requirement}\n")
    lines.append(f"## Requirement Summary\n\n{_field(analysis, 'requirement_summary')}\n")

    goals = _list_field(analysis, "goals")
    if goals:
        lines.append("## Goals\n")
        for g in goals:
            lines.append(f"- {g}")
        lines.append("")

    affected = _list_field(analysis, "affected_components")
    if affected:
        lines.append("## Affected Components\n")
        for c in affected:
            lines.append(f"- {c}")
        lines.append("")

    risks = _list_field(analysis, "risks")
    if risks:
        lines.append("## Risks\n")
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    acceptance = _list_field(analysis, "acceptance_criteria")
    if acceptance:
        lines.append("## Acceptance Criteria\n")
        for i, ac in enumerate(acceptance, start=1):
            lines.append(f"{i}. {ac}")
        lines.append("")

    if manifest.degraded:
        lines.append("> **Warning**: This output was generated in degraded mode and requires review.\n")

    lines.append(f"---\n*analysis_hash: {manifest.analysis_hash}*")
    return "\n".join(lines)


def render_test_plan(analysis_json: str, generation_json: str) -> str:
    """Render a test plan Markdown document."""
    analysis = _safe_parse_json(analysis_json)
    generation = _safe_parse_json(generation_json)
    lines: list[str] = []
    lines.append("# Test Plan\n")
    lines.append("## Scope\n")

    acceptance = _list_field(analysis, "acceptance_criteria")
    for i, ac in enumerate(acceptance, start=1):
        lines.append(f"- [{i}] {ac}")

    lines.append("")
    lines.append("## Unit Tests\n")
    test_items = _list_field(generation, "test_plan")
    for item in test_items:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("## Integration Tests\n")
    lines.append("- Verify end-to-end workflow with mock provider")
    lines.append("- Verify artifact completeness and validity")

    lines.append("")
    lines.append("## Error Scenarios\n")
    risks = _list_field(analysis, "risks")
    for risk in risks:
        lines.append(f"- {risk}")

    lines.append("")
    lines.append("## Regression Risk\n")
    lines.append("- Existing test suite (368+ tests) must continue to pass")
    lines.append("- No modification to target repository")

    return "\n".join(lines)


def render_run_summary(manifest: RunManifest, evidence: EvidenceBundle) -> str:
    """Render a run summary Markdown document."""
    lines: list[str] = []
    lines.append("# Run Summary\n")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Run ID | {manifest.run_id} |")
    lines.append(f"| Status | {manifest.status} |")
    lines.append(f"| Provider | {manifest.provider_type} |")
    lines.append(f"| Model | {manifest.model} |")
    lines.append(f"| Review Decision | {manifest.review_decision} |")
    lines.append(f"| Degraded | {manifest.degraded} |")
    lines.append(f"| Requires Review | {manifest.requires_review} |")
    lines.append(f"| Tool Calls | {manifest.tool_call_count} |")
    lines.append(f"| Files Read | {len(evidence.selected_files)} |")
    lines.append(f"| Evidence Hash | {manifest.evidence_hash[:16]}... |")
    lines.append("")

    if evidence.selected_files:
        lines.append("## Files Read\n")
        for f in evidence.selected_files:
            lines.append(f"- {f}")
        lines.append("")

    if evidence.tool_call_records:
        lines.append("## Tool Calls\n")
        for r in evidence.tool_call_records[:10]:
            lines.append(
                f"- `{r.tool_name}` ({r.status}) — {r.arguments_summary[:80]}"
            )
        if len(evidence.tool_call_records) > 10:
            lines.append(f"- ... and {len(evidence.tool_call_records) - 10} more")
        lines.append("")

    if manifest.warnings:
        lines.append("## Warnings\n")
        for w in manifest.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Capability Boundaries\n")
    lines.append("- Read-only repository access only (no write/delete/shell/git)")
    lines.append("- No automatic code modification")
    lines.append("- No Agent Loop or ReAct pattern")
    lines.append("- No multi-agent orchestration")

    return "\n".join(lines)


def _safe_parse_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _field(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    return sanitize_tool_text(str(value))


def _list_field(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list):
        return []
    return [sanitize_tool_text(str(item)) for item in value if str(item).strip()]

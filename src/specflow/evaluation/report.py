"""Small deterministic report serializer for committed Mock summaries."""

from __future__ import annotations

import json
from pathlib import Path

from specflow.evaluation.models import EvaluationReport


def report_as_dict(report: EvaluationReport) -> dict[str, object]:
    return {
        "mode": report.mode.value,
        "status": report.status.value,
        "live_validation_status": report.live_validation_status.value,
        "notes": list(report.notes),
        "runs": [
            {
                "case_id": run.case_id,
                "status": run.status.value,
                "finding_codes": [finding.code for finding in run.findings],
            }
            for run in report.runs
        ],
    }


def report_to_json(report: EvaluationReport) -> str:
    return json.dumps(report_as_dict(report), ensure_ascii=False, indent=2, sort_keys=True)


def write_report(report: EvaluationReport, output_path: Path) -> None:
    """Persist a compact summary; raw run artifacts stay outside version control."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_to_json(report), encoding="utf-8")

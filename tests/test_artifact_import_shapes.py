"""Malformed JSON shapes are validation failures, never crashes or successes."""

import json

import pytest
from test_live_validation_import import _artifact_dir

from specflow.evaluation import EvaluationStatus, validate_live_artifact_import


@pytest.mark.parametrize(
    "filename,payload",
    [
        ("manifest.json", []),
        ("manifest.json", None),
        ("manifest.json", {"status": [], "model": "fake", "provider_type": "real"}),
        ("manifest.json", {"status": "completed", "model": {}, "provider_type": "real"}),
        ("manifest.json", {"status": "completed", "model": "fake", "provider_type": []}),
        ("trace.json", None),
        ("trace.json", [{"metadata": None}]),
        ("trace.json", [{"metadata": []}]),
        ("trace.json", [{"metadata": {"worker_role": []}}]),
        ("trace.json", [None]),
        ("sources.json", None),
        ("sources.json", {"selected_files": None}),
        ("sources.json", {"selected_files": "app.py"}),
        ("sources.json", {"matched_files": {"app.py": True}}),
        ("sources.json", {"excerpts": None}),
        ("sources.json", {"selected_files": [None]}),
        ("sources.json", {"excerpts": [{"relative_path": []}]}),
        ("sources.json", {"excerpts": ["app.py"]}),
        ("sources.json", {"selected_files": ["bad\x00path"]}),
        ("tool-calls.json", None),
        ("tool-calls.json", [{"tool_name": {}, "call_id": "a", "status": "success"}]),
        ("analysis.json", None),
    ],
)
def test_invalid_shapes_return_failed_record(tmp_path, filename, payload):
    artifacts, repo = _artifact_dir(tmp_path)
    (artifacts / filename).write_text(json.dumps(payload), encoding="utf-8")
    record = validate_live_artifact_import(artifacts, repo)
    assert record.status == EvaluationStatus.FAILED
    assert record.findings


def test_valid_import_remains_valid(tmp_path):
    artifacts, repo = _artifact_dir(tmp_path)
    assert validate_live_artifact_import(artifacts, repo).status == EvaluationStatus.PASSED

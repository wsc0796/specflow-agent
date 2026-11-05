"""Snapshot tools: bounded evidence, fragment permissions and static support limits."""

import json

import pytest

from specflow.contract_review.common import ReviewError, canonical, digest
from specflow.contract_review.snapshot_tools import SnapshotTools


def source(identifier, path, body, roles=("implementation",)):
    return {
        "source_id": identifier,
        "path": path,
        "body": body,
        "body_hash": digest(body.encode()),
        "roles": list(roles),
    }


def test_list_pagination_is_scoped_and_does_not_read_source_body():
    values = {
        str(i): source(str(i), f"docs/{i}.md", "secret body", ("documentation",)) for i in range(4)
    }
    tools = SnapshotTools(values, "s")
    first = tools.execute("list_sources", {"limit": 2})
    assert "secret body" not in canonical(first)
    second = tools.execute("list_sources", {"limit": 2, "cursor": first["body"]["next_cursor"]})
    assert [item["source_id"] for item in first["body"]["items"] + second["body"]["items"]] == [
        "0",
        "1",
        "2",
        "3",
    ]
    child = SnapshotTools(values, "s", grants={"0": [{"kind": "full"}]})
    with pytest.raises(ReviewError):
        child.validate("list_sources", {"cursor": first["body"]["next_cursor"]})


@pytest.mark.parametrize(
    "arguments",
    [
        {"source_id": "s", "start_line": True, "end_line": 1},
        {"source_id": "s", "start_line": 1, "end_line": 201},
        {"source_id": "s", "start_line": 2, "end_line": 1},
        {"source_id": "s", "start_line": 1, "end_line": 1, "path": "../private"},
    ],
)
def test_bad_arguments_are_rejected_before_handler(arguments, monkeypatch):
    tools = SnapshotTools({"s": source("s", "file.md", "first\nsecond\n")}, "snap")
    monkeypatch.setattr(tools, "_read_source", lambda _: pytest.fail("rejected handler entered"))
    with pytest.raises(ReviewError):
        tools.execute("read_source", arguments)


def test_child_line_grant_does_not_expand_to_other_lines_or_files():
    values = {
        "s": source("s", "file.md", "outside\nallowed\nprivate\n"),
        "other": source("other", "other.md", "not allowed"),
    }
    tools = SnapshotTools(
        values, "snap", {"s": [{"kind": "lines", "start_line": 2, "end_line": 2}]}
    )
    assert (
        tools.execute("read_source", {"source_id": "s", "start_line": 2, "end_line": 2})["body"][
            "text"
        ]
        == "allowed\n"
    )
    for args in (
        {"source_id": "s", "start_line": 1, "end_line": 2},
        {"source_id": "other", "start_line": 1, "end_line": 1},
    ):
        with pytest.raises(ReviewError, match="允许范围"):
            tools.validate("read_source", args)
    result = tools.execute("search_sources", {"query": "private", "source_ids": ["s"]})
    assert result["result_kind"] == "empty"
    with pytest.raises(ReviewError):
        tools.validate("inspect_python_contract", {"source_id": "s", "selectors": ["routes"]})


def test_partial_line_is_not_misrepresented_as_fully_projected_source():
    tools = SnapshotTools({"s": source("s", "file.md", "x" * 9000 + "\n")}, "snap")
    result = tools.execute("read_source", {"source_id": "s", "start_line": 1, "end_line": 1})
    assert result["completeness"] == "truncated"
    assert result["source_refs"] == []
    assert len(result["body"]["text"]) == 8000
    assert result["body"]["next_range"] == [1, 1]


def test_search_is_literal_and_reports_cap_and_explicit_empty():
    tools = SnapshotTools({"s": source("s", "file.md", "a.*b\na.*b\nAXXB\n")}, "snap")
    result = tools.execute(
        "search_sources", {"query": "a.*b", "source_ids": ["s"], "max_matches": 1}
    )
    assert len(result["body"]["matches"]) == 1
    assert result["completeness"] == "truncated"
    empty = tools.execute("search_sources", {"query": "not-here", "source_ids": ["s"]})
    assert empty["result_kind"] == "empty" and empty["error"] is None


@pytest.mark.parametrize("mutator", ["hash", "syntax"])
def test_source_corruption_or_parse_error_never_becomes_empty(mutator):
    item = source("s", "data.json", "{invalid")
    if mutator == "hash":
        item["body_hash"] = "0" * 64
    result = SnapshotTools({"s": item}, "snap").execute("inspect_json_contract", {"source_id": "s"})
    assert result["result_kind"] == "dependency_error"
    assert result["error"]


def test_json_refs_only_resolve_explicit_local_grants_and_preserve_cycles():
    values = {
        "a": source(
            "a",
            "schemas/a.json",
            '{"x":{"$ref":"b.json#/value"},"y":{"$ref":"https://invalid.test/schema"}}',
        ),
        "b": source("b", "schemas/b.json", '{"value":{"type":"string"}}'),
    }
    tools = SnapshotTools(values, "snap")
    blocked = tools.execute("inspect_json_contract", {"source_id": "a"})
    assert "reference_not_allowed" in blocked["body"]["unsupported"]
    allowed = tools.execute(
        "inspect_json_contract", {"source_id": "a", "local_ref_source_ids": ["b"]}
    )
    assert allowed["body"]["resolved_refs"][0]["value"] == {"type": "string"}
    assert "external_reference" in allowed["body"]["unsupported"]
    cycle = source("c", "cycle.json", '{"$ref":"#"}')
    result = SnapshotTools({"c": cycle}, "snap").execute(
        "inspect_json_contract", {"source_id": "c"}
    )
    assert "reference_cycle" in result["body"]["unsupported"]


def test_json_pointer_grant_does_not_open_siblings():
    values = {
        "s": source("s", "file.json", '{"allow":{"x":1,"r":{"$ref":"#/secret"}},"secret":42}')
    }
    tools = SnapshotTools(values, "snap", {"s": [{"kind": "json_pointer", "pointer": "/allow"}]})
    with pytest.raises(ReviewError):
        tools.validate("inspect_json_contract", {"source_id": "s", "pointer": "/secret"})
    result = tools.execute("inspect_json_contract", {"source_id": "s", "pointer": "/allow"})
    assert "reference_not_allowed" in result["body"]["unsupported"]
    assert not result["body"]["resolved_refs"]


def test_tool_output_utf8_limit_is_applied_with_explicit_truncation():
    tools = SnapshotTools(
        {"s": source("s", "data.json", json.dumps({"text": "证" * 50000}, ensure_ascii=False))},
        "snap",
    )
    result = tools.execute("inspect_json_contract", {"source_id": "s"})
    assert len(canonical(result).encode("utf-8")) <= 64 * 1024
    assert result["completeness"] == "truncated" and result["source_refs"] == []


PYTHON = """from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
app = FastAPI()
router = APIRouter(prefix="/jobs")
app.include_router(router, prefix="/v2")
class Response(BaseModel):
    job_id: str
@router.post("", response_model=Response)
def create():
    return {"job_id": "j", "private": "filtered"}
@router.post("/{job_id}/cancel")
def cancel(job_id):
    state = "completed"
    if state != "queued":
        raise HTTPException(status_code=409, detail="JOB_NOT_CANCELLABLE")
    state = "cancelled"
    return {"state": state}
"""


def test_finite_python_facts_include_registration_model_filter_and_guard(tmp_path):
    marker = tmp_path / "never-executed.txt"
    text = PYTHON + f'\nopen({str(marker)!r}, "w").write("should not run")\n'
    result = SnapshotTools({"s": source("s", "api.py", text)}, "snap").execute(
        "inspect_python_contract",
        {"source_id": "s", "selectors": ["routes", "response_fields", "state_guards"]},
    )
    facts = result["body"]["facts"]
    assert any(item.get("path") == "/v2/jobs" for item in facts)
    assert any(
        item["kind"] == "response_model_fields" and item["fields"] == ["job_id"] for item in facts
    )
    assert not any(
        item["kind"] == "returned_fields" and "private" in item["fields"] for item in facts
    )
    assert any(item["kind"] == "raise" and "409" in item["text"] for item in facts)
    assert not marker.exists()


@pytest.mark.parametrize(
    "body",
    [
        'from fastapi import APIRouter\nr = APIRouter()\n@r.get("/x")\ndef f():\n return {"x":1}\n',
        "from fastapi import FastAPI\napp=FastAPI()\n@app.get(path_variable)\ndef f():\n retu"
        'rn {"x":1}\n',
        'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x",response_model_exclude={'
        '"x"})\ndef f():\n return {"x":1}\n',
        "from fastapi import FastAPI\nfrom pydantic import BaseModel,Field\napp=FastAPI()\ncl"
        'ass R(BaseModel):\n x:str=Field(alias="y")\n@app.get("/x",response_model=R)\ndef'
        ' f():\n return {"x":1}\n',
    ],
)
def test_dynamic_or_unsupported_python_is_reported_as_such(body):
    result = SnapshotTools({"s": source("s", "api.py", body)}, "snap").execute(
        "inspect_python_contract", {"source_id": "s", "selectors": ["routes", "response_fields"]}
    )
    assert result["result_kind"] == "unsupported"
    assert result["body"]["unsupported"]


def test_nested_return_is_not_reported_as_outer_response():
    body = (
        'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef f():\n'
        ' def hidden():\n  return {"wrong":1}\n return {"right":1}\n'
    )
    result = SnapshotTools({"s": source("s", "api.py", body)}, "snap").execute(
        "inspect_python_contract", {"source_id": "s", "selectors": ["response_fields"]}
    )
    fields = [
        fact["fields"] for fact in result["body"]["facts"] if fact["kind"] == "returned_fields"
    ]
    assert fields == [["right"]]


@pytest.mark.parametrize(
    "declarations",
    [
        "from fastapi import FastAPI\nfrom elsewhere import Factory as FastAPI\napp=FastAPI()",
        "import fastapi\nimport elsewhere as fastapi\napp=fastapi.FastAPI()",
        "from .fastapi import FastAPI\napp=FastAPI()",
        "app=fastapi.FastAPI()",
        "from fastapi import FastAPI\napp=FastAPI()\nimport elsewhere as app",
        "from fastapi import FastAPI\napp=FastAPI()\nfrom elsewhere import app",
        "from fastapi import FastAPI\napp=FastAPI()\napp: object = replacement",
        "from fastapi import FastAPI\napp=FastAPI()\napp += replacement",
        "from fastapi import FastAPI\napp=FastAPI()\nif enabled:\n import elsewhere as app",
    ],
)
def test_unresolved_or_rebound_import_and_instance_never_proves_a_route(declarations):
    body = declarations + '\n@app.get("/x")\ndef f():\n return {"x": 1}\n'
    result = SnapshotTools({"s": source("s", "api.py", body)}, "snap").execute(
        "inspect_python_contract", {"source_id": "s", "selectors": ["routes"]}
    )
    assert result["result_kind"] == "unsupported"
    assert not any(fact["kind"] == "route" for fact in result["body"]["facts"])


def test_function_local_rebinding_does_not_shadow_module_route_instance():
    body = (
        'import fastapi as fa\napp=fa.FastAPI()\n@app.get("/x")\ndef f():\n'
        ' app = "local"\n return {"x": app}\n'
    )
    result = SnapshotTools({"s": source("s", "api.py", body)}, "snap").execute(
        "inspect_python_contract", {"source_id": "s", "selectors": ["routes"]}
    )
    assert result["result_kind"] == "data"
    assert any(fact.get("path") == "/x" for fact in result["body"]["facts"])


@pytest.mark.parametrize(
    ("grants", "requested", "allowed"),
    [
        (
            [
                {"kind": "lines", "start_line": 1, "end_line": 1},
                {"kind": "lines", "start_line": 2, "end_line": 3},
            ],
            {"kind": "full"},
            True,
        ),
        (
            [
                {"kind": "lines", "start_line": 1, "end_line": 1},
                {"kind": "lines", "start_line": 3, "end_line": 3},
            ],
            {"kind": "full"},
            False,
        ),
        (
            [{"kind": "json_pointer", "pointer": "/a"}],
            {"kind": "json_pointer", "pointer": "/a/x"},
            True,
        ),
        (
            [{"kind": "json_pointer", "pointer": "/a"}],
            {"kind": "json_pointer", "pointer": "/ab"},
            False,
        ),
        (
            [{"kind": "json_pointer", "pointer": "/a~1b"}],
            {"kind": "json_pointer", "pointer": "/a~1b/x"},
            True,
        ),
        (
            [
                {"kind": "json_pointer", "pointer": "/a/x"},
                {"kind": "json_pointer", "pointer": "/a/y"},
            ],
            {"kind": "json_pointer", "pointer": "/a"},
            False,
        ),
    ],
)
def test_tool_permissions_and_report_evidence_share_fragment_coverage(grants, requested, allowed):
    from specflow.contract_review.report_validation import source_was_read

    item = source("s", "file.json", '{"a": {"x": 1,\n"y": 2},\n"a/b": {"x": 3}}')
    tools = SnapshotTools({"s": item}, "snap", {"s": grants})
    reference = {"source_id": "s", "selector": requested}
    reads = [{"source_id": "s", "selector": grant} for grant in grants]
    assert tools.permitted("s", requested) is allowed
    assert source_was_read(reference, reads, item["body"]) is allowed

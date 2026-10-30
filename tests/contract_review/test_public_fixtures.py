"""Validate frozen public inputs, never execute fixture applications or an LLM."""

import ast
import json
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "contract_review"
CASES = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
EARLY = {"CR02-F01", "CR02-F02", "CR02-C01", "CR02-C03", "CR02-H01", "CR02-H02"}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_manifest_retains_original_plan_and_separates_unrun_semantics():
    manifest = load("manifest.json")
    assert len(manifest["cases"]) == 24
    assert len({case["case_id"] for case in manifest["cases"]}) == 24
    assert {c["case_id"] for c in manifest["cases"] if c["selection"] == "early_slice"} == EARLY
    assert {c["case_id"] for c in CASES} == EARLY
    assert all(c["semantic_status"] == "NOT_RUN" for c in manifest["cases"])
    assert manifest["live_configuration"]["authorized"] is False
    assert manifest["live_configuration"]["model"] is None
    for case in manifest["cases"]:
        assert case["sample_id"] == case["trial_id"].replace("TR02-", "SP02-", 1)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_sources_and_checks_are_closed_and_parseable(case):
    sources = {source["path"]: source for source in case["sources"]}
    assert len(sources) == len(case["sources"])
    for path, source in sources.items():
        assert not PurePosixPath(path).is_absolute()
        assert ".." not in PurePosixPath(path).parts
        material = ROOT / "materials" / source["fixture"]
        assert material.resolve().is_relative_to((ROOT / "materials").resolve())
        body = material.read_text(encoding="utf-8")
        if path.endswith(".py"):
            ast.parse(body)
        elif path.endswith(".json"):
            json.loads(body)
        assert "CR02-" not in body
        assert "TR02-" not in body
    for target in case["request"]["targets"]:
        assert target["source_path"] in sources
        assert 1 <= len(target["checks"]) <= 20
        assert len({check["key"] for check in target["checks"]}) == len(target["checks"])
    for binding in case["request"]["authority_bindings"]:
        assert sources[binding["path"]]["role"] == "contract"
    assert case["request"]["ruleset_usage"] == {"mode": "none"}


def test_human_pair_has_identical_initial_material_but_opposite_later_answers():
    by_id = {case["case_id"]: case for case in CASES}
    first, second = by_id["CR02-H01"], by_id["CR02-H02"]
    assert first["request"] == second["request"]
    assert first["sources"] == second["sources"]
    answers = load("human-scripts.json")["answers"]
    assert "API v1" in answers["CR02-H01"]["text"]
    assert "API v2" in answers["CR02-H02"]["text"]
    assert all(answer["scope"] == "this_review" for answer in answers.values())
    for answer in answers.values():
        assert answer["text"] not in json.dumps(first["request"], ensure_ascii=False)
        for source in first["sources"]:
            assert answer["text"] not in (ROOT / "materials" / source["fixture"]).read_text(
                encoding="utf-8"
            )


def test_oracles_are_complete_and_not_part_of_source_selection():
    oracle = load("oracles.json")
    assert {case["case_id"] for case in oracle["cases"]} == EARLY
    assert all(case["required"] and case["forbidden"] for case in oracle["cases"])
    assert all(case["status"] == "NOT_RUN" for case in oracle["cases"])
    assert all("oracle" not in source["fixture"] for case in CASES for source in case["sources"])

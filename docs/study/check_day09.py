"""Check Day 9 data and optional existing evaluator cores; never run a case."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/study/datasets/v1"
CALIBRATION = ROOT / "docs/study/calibration/v1/fixtures.json"
REVISION = "08e5a66f8ea8216433c72744adab92aa07d99c45"
VERSION = "v1"
DISTRIBUTION = {
    "dev": dict(
        zip(
            (
                "exact_keyword",
                "semantic_rewrite",
                "multi_file",
                "no_answer",
                "safety_or_stale_index",
            ),
            (5, 5, 4, 3, 3),
            strict=True,
        )
    ),
    "holdout": dict(
        zip(
            (
                "exact_keyword",
                "semantic_rewrite",
                "multi_file",
                "no_answer",
                "safety_or_stale_index",
            ),
            (3, 3, 2, 1, 1),
            strict=True,
        )
    ),
}
EVALUATORS = {
    "contract_run_success",
    "source_reference_validity",
    "fact_evidence_coverage",
    "citation_support",
    "task_success",
    "token_cost_completeness",
    "safe_abstention",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def symbol_ranges(content: str) -> dict[str, tuple[int, int]]:
    result = {}
    for node in ast.parse(content).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = (node.lineno, node.end_lineno)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[f"{node.name}.{child.name}"] = (child.lineno, child.end_lineno)
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                result[target.id] = (node.lineno, node.end_lineno)
    return result


def validate_dataset(include_holdout: bool) -> dict:
    manifest = read_json(DATA / "manifest.json")
    holdout_manifest = read_json(DATA / "holdout-manifest.json")
    assert manifest["dataset_version"] == VERSION
    assert manifest["repository_revision"] == REVISION
    assert manifest["status"] == "frozen_v1"
    assert manifest["frozen"] is True
    expected = {
        "holdout_evidence_level": "frozen_internal_holdout",
        "case_count": 10,
        "used_for_tuning": False,
        "execution_policy": "run_once_after_freeze",
        "independent_creator": False,
        "independent_access_control": False,
        "execution_count": 0,
        "frozen": True,
    }
    for key, value in expected.items():
        assert holdout_manifest[key] == value, key
    assert holdout_manifest["dataset_version"] == VERSION
    assert holdout_manifest["repository_revision"] == REVISION
    tree = set(git("ls-tree", "-r", "--name-only", REVISION).splitlines())
    assert "docs/study/datasets/v1/dev.json" not in tree
    cases, source_cache, symbols = [], {}, {}
    locator_count = 0
    for split in ["dev", "holdout"] if include_holdout else ["dev"]:
        payload = read_json(DATA / f"{split}.json")
        part = payload["cases"]
        count = 20 if split == "dev" else 10
        prefix = "D" if split == "dev" else "H"
        expected_ids = [f"SF-RT-{prefix}{index:03d}" for index in range(1, count + 1)]
        assert [case["case_id"] for case in part] == expected_ids
        assert payload["case_count"] == count
        assert manifest["splits"][split]["case_ids"] == expected_ids
        assert Counter(c["category"] for c in part) == DISTRIBUTION[split]
        assert manifest["splits"][split]["category_counts"] == DISTRIBUTION[split]
        if split == "holdout":
            assert holdout_manifest["case_ids"] == expected_ids
            assert set(holdout_manifest["isolation_groups"]) == {c["isolation_group"] for c in part}
        for case in part:
            assert case["suite"] == "specflow_repository_tasks"
            assert case["split"] == split
            assert case["dataset_version"] == case["annotation_version"] == VERSION
            assert case["repository_revision"] == REVISION
            assert case["status"] == "frozen_v1"
            assert case["execution_status"] == "not_run"
            assert case["model_input_keys"] == ["requirement"]
            assert case["annotation_provenance"]["human_review_status"] in {
                "learner_reviewed",
                "ai_reviewed_not_individually_learner_reviewed",
            }
            assert case["annotation_provenance"]["learner_ownership_evidence"] is False
            assert case["requirement"].strip() and case["forbidden_claims"]
            assert case["legal_terminal_state"]["product_state_mapping"] == "unknown"
            assert case["answerability"] in {"answerable", "unanswerable", "safety_reject"}
            assert case["answerability"] != "answerable" or case["gold_evidence"]
            if case["category"] == "no_answer":
                assert case["answerability"] == "unanswerable"
            if case["category"] == "safety_or_stale_index":
                assert case["answerability"] == "safety_reject"
            basis = case["answerability_basis"]
            if basis["type"] == "required_source_absent":
                assert basis["path"] not in tree
            for path in basis.get("reference_paths", []):
                assert path in tree
            facts = {f["fact_id"] for f in case["gold_evidence"]}
            assert len(facts) == len(case["gold_evidence"])
            properties = case["expected_properties"]
            assert properties and len({p["property_id"] for p in properties}) == len(properties)
            for prop in properties:
                assert prop["statement"].strip() and prop["must"] is True
                assert set(prop["required_fact_ids"]) <= facts
            for fact in case["gold_evidence"]:
                assert fact["fact_statement"].strip() and fact["necessary_conditions"]
                assert fact["evidence_locators"]
                for loc in fact["evidence_locators"]:
                    path = loc["path"]
                    assert path in tree and path.startswith("src/specflow/")
                    assert loc["repository_revision"] == REVISION
                    if path not in source_cache:
                        source_cache[path] = git("show", f"{REVISION}:{path}")
                        symbols[path] = symbol_ranges(source_cache[path])
                        assert (ROOT / path).read_text(encoding="utf-8").splitlines() == (
                            source_cache[path].splitlines()
                        ), f"source drift: {path}"
                    lines = source_cache[path].splitlines()
                    start, end = loc["line_start"], loc["line_end"]
                    assert 1 <= start <= end <= len(lines), (case["case_id"], path)
                    symbol_start, symbol_end = symbols[path][loc["symbol"]]
                    assert symbol_start <= start <= end <= symbol_end, loc["symbol"]
                    assert loc["source_excerpt"] == "\n".join(lines[start - 1 : end])
                    locator_count += 1
        cases.extend(part)
    assert len({c["case_id"] for c in cases}) == len(cases)
    assert len({c["requirement"] for c in cases}) == len(cases)
    group_splits, fact_splits, canonical_facts = {}, {}, {}
    paths_by_split = {"dev": set(), "holdout": set()}
    for case in cases:
        group_splits.setdefault(case["isolation_group"], set()).add(case["split"])
        for fact in case["gold_evidence"]:
            fid = fact["fact_id"]
            fact_splits.setdefault(fid, set()).add(case["split"])
            assert canonical_facts.setdefault(fid, fact) == fact
            paths_by_split[case["split"]].update(loc["path"] for loc in fact["evidence_locators"])
    assert all(len(splits) == 1 for splits in group_splits.values())
    assert all(len(splits) == 1 for splits in fact_splits.values())
    assert not (paths_by_split["dev"] & paths_by_split["holdout"])
    return {
        "status": "passed",
        "dataset_status": "frozen_v1",
        "cases_checked": len(cases),
        "holdout_content_read": include_holdout,
        "holdout_read_purpose": (
            "Day 9 authoring validation only" if include_holdout else "not_read"
        ),
        "category_distribution": {
            split: dict(Counter(c["category"] for c in cases if c["split"] == split))
            for split in {c["split"] for c in cases}
        },
        "unique_gold_facts": len(canonical_facts),
        "source_locators_checked": locator_count,
        "cross_split_group_overlap": 0 if include_holdout else "not_checked",
        "cross_split_gold_id_overlap": 0 if include_holdout else "not_checked",
        "cross_split_gold_source_file_overlap": 0 if include_holdout else "not_checked",
        "semantic_near_duplicate_review": "AI reviewed; learner reviewed critical boundaries",
        "tested_model_input_projection": "not implemented; only data-side allowlist checked",
        "repository_revision": REVISION,
        "dataset_version": VERSION,
        "provider_calls": 0,
        "case_executions": 0,
    }


def validate_fixtures() -> list[dict]:
    payload = read_json(CALIBRATION)
    assert payload["fixture_version"] == VERSION
    assert payload["status"] == "frozen_v1_expected_results"
    fixtures = payload["fixtures"]
    assert len({f["fixture_id"] for f in fixtures}) == len(fixtures)
    assert {f["evaluator_id"] for f in fixtures} == EVALUATORS
    for evaluator in EVALUATORS:
        roles = {f["fixture_role"] for f in fixtures if f["evaluator_id"] == evaluator}
        assert {"should_pass", "should_fail", "unknown"} <= roles
    for fixture in fixtures:
        assert fixture["formal_case_ids"] == []
        assert fixture["suite"] == "specflow_evaluator_calibration"
        assert fixture["fixture_version"] == fixture["annotation_version"] == VERSION
        assert fixture["human_review_status"] in {"pending", "learner_reviewed"}
        if fixture["human_review_status"] == "learner_reviewed":
            assert fixture["human_review_notes"].strip()
        expected = fixture["expected"]
        assert expected["verdict"] in {"pass", "fail", "unknown", "N/A", None}
        if expected["verdict"] is None:
            assert fixture["evaluator_id"] == "fact_evidence_coverage"
            assert expected["value"] == expected["numerator"] / expected["denominator"]
            assert len(expected["matched_fact_ids"]) == expected["numerator"]
            assert expected["product_task_verdict"] == "unknown"
    return fixtures


def run_existing_cores(fixtures: list[dict]) -> dict:
    from specflow.evaluation.benchmark import BenchmarkCase, _read_run
    from specflow.evaluation.validators import _validate_sources

    # Only the two read-only helpers run. No case, Agent, baseline or Provider runs.
    temp_root = ROOT / "data/day09-calibration"
    temp_root.mkdir(parents=True, exist_ok=True)
    observations = []
    with (
        patch(
            "specflow.evaluation.benchmark.run_multi_agent",
            side_effect=AssertionError("Day 9 must not invoke a benchmark runner"),
        ),
        tempfile.TemporaryDirectory(dir=temp_root) as temp,
    ):
        base = Path(temp)
        for fixture in fixtures:
            invocation = fixture["core_invocation"]
            if invocation is None:
                observations.append(
                    {
                        "fixture_id": fixture["fixture_id"],
                        "execution_status": "not_run",
                        "reason": "scorer/profile wrapper unavailable; expectation only",
                        "raw": None,
                    }
                )
                continue
            work = base / fixture["fixture_id"]
            work.mkdir()
            inputs, expected = fixture["inputs"], fixture["expected"]
            if invocation == "specflow.evaluation.benchmark._read_run":
                for name, value in inputs["artifacts"].items():
                    assert name in {
                        "manifest.json",
                        "metrics.json",
                        "agent-outputs.json",
                        "handoffs.json",
                        "traces.json",
                        "sources.json",
                        "checkpoints.json",
                    }
                    (work / name).write_text(json.dumps(value), encoding="utf-8")
                case = BenchmarkCase(
                    fixture["fixture_id"],
                    "repository_understanding",
                    "Calibration",
                    "Calibration only",
                    ("placeholder.py",),
                )
                raw = _read_run(case, work, base)
                assert raw["status"] == expected["raw_status"]
                assert raw["error_codes"] == expected["error_codes"]
            elif invocation == "specflow.evaluation.validators._validate_sources":
                for name, content in inputs["repository_files"].items():
                    assert name == "calibration_module.py"
                    (work / name).write_text(content, encoding="utf-8")
                findings = []
                _validate_sources(inputs["sources"], work, findings)
                raw = {"finding_codes": sorted(f.code for f in findings)}
                assert raw["finding_codes"] == expected["finding_codes"]
            else:
                raise AssertionError(f"Unapproved core invocation: {invocation}")
            observations.append(
                {
                    "fixture_id": fixture["fixture_id"],
                    "execution_status": "executed_existing_core",
                    "matches_expected": True,
                    "raw": raw,
                }
            )
    return {
        "status": "passed",
        "fixtures_checked": len(fixtures),
        "existing_core_executions": sum(f["core_invocation"] is not None for f in fixtures),
        "semantic_scorers_executed": 0,
        "provider_calls": 0,
        "case_executions": 0,
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-holdout-authoring",
        action="store_true",
        help="Explicit Day 9 authoring access; never use during tuning.",
    )
    parser.add_argument("--execute-existing-core", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    report = validate_dataset(args.include_holdout_authoring)
    fixtures = validate_fixtures()
    report["fixtures_checked"] = len(fixtures)
    report["evaluator_count"] = len(EVALUATORS)
    calibration = run_existing_cores(fixtures) if args.execute_existing_core else None
    if args.output_dir:
        output = args.output_dir.resolve()
        assert output.is_relative_to(ROOT)
        output.mkdir(parents=True, exist_ok=True)
        (output / "day-09-data-validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if calibration:
            (output / "day-09-calibration-results.json").write_text(
                json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    print(
        json.dumps(
            {
                **report,
                "existing_core_executions": (
                    calibration["existing_core_executions"] if calibration else 0
                ),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

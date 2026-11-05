"""B1 exercises actual HTTP/worker/checkpoint boundaries with controlled model outputs."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.contract_review.profiles import dynamic_profile
from specflow.main import create_app

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "contract_review"


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evidence_module = load_script("review_evidence", "review_evidence.py")
prep = load_script("b1_public_case_prep", "run_public_case_prep.py")
PreparationError = evidence_module.PreparationError


@contextmanager
def local_client(tmp_path, prepared, adapter, profile):
    runtime = tmp_path / ("runtime-" + uuid.uuid4().hex)
    runtime.mkdir()
    profile = dynamic_profile(prep.PROFILE, profile["model"], delegation=False)
    profile["model_timeout_seconds"] = 3.0
    app = create_app(
        database_url=f"sqlite:///{(runtime / 'reviews.sqlite').as_posix()}",
        artifact_root=runtime / "artifacts",
        security=ApiSecurity(api_key="b1-synthetic-key", allowed_repository_roots=(str(tmp_path),)),
        contract_review_profiles={prep.PROFILE: profile},
        contract_review_adapter=adapter,
    )
    with TestClient(app, headers={"X-API-Key": "b1-synthetic-key"}) as client:
        yield client


class PublicHumanAdapter:
    execution_mode = "test"

    def __init__(self, fallback, *, two=False, variant="normal"):
        self.fallback, self.two, self.variant = fallback, two, variant
        self.scope_id = "scope_" + uuid.uuid4().hex[:10]
        self.material_id = "material_" + uuid.uuid4().hex[:10]

    def complete(self, payload):
        result = self.fallback.complete(payload)
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            return result
        action = json.loads(result["content"])
        report = action["report"]
        if not data["resolutions"] and self.variant != "missing":
            for index, (question_id, kind) in enumerate(
                [(self.scope_id, "scope_choice")]
                + ([(self.material_id, "missing_evidence")] if self.two else [])
            ):
                question = {
                    "id": question_id,
                    "kind": "missing_evidence" if self.variant == "wrong_kind" else kind,
                    "prompt": "请确认示例的 API 版本归属。" if not index else "请补充材料。",
                    "blocking": True,
                    "target_ids": [data["targets"][0]["target_id"]],
                    "finding_ids": [report["findings"][0]["id"]],
                    "work_item_ids": [],
                    "rule_refs": [],
                    "evidence_refs": [],
                    "why_blocking": "当前归属未明。",
                    "options": [],
                    "allowed_answer_types": ["clarify"],
                }
                if self.variant == "disallowed":
                    question["allowed_answer_types"] = ["select"]
                    question["options"] = [
                        {"id": "v1", "label": "v1", "consequence": "保留旧版。"},
                        {"id": "v2", "label": "v2", "consequence": "核对新版。"},
                    ]
                if self.variant == "wrong_target":
                    question["target_ids"] = ["foreign-target"]
                report["questions"].append(question)
        if data["resolutions"]:
            text = data["resolutions"][0]["answer"].get("text", "")
            report["summary"] = "受控替身收到原文：" + text
        result["content"] = json.dumps(action, ensure_ascii=False)
        return result


def prepared(tmp_path, case="CR02-F02"):
    return prep.prepare_case(REPO, tmp_path / ("case-" + uuid.uuid4().hex), case)


def spy_posts(monkeypatch, client):
    calls, original = [], client.post

    def post(path, **kwargs):
        calls.append((path, copy.deepcopy(kwargs.get("json"))))
        return original(path, **kwargs)

    monkeypatch.setattr(client, "post", post)
    return calls


def test_f02_materializes_original_four_sources_and_two_targets(tmp_path):
    result = prepared(tmp_path)
    original = prep.load_case(REPO, "CR02-F02")
    root = Path(result["case_root"])
    assert len(result["request"]["targets"]) == 2
    assert result["source_trial_id"] == "TR02-F02-COMMON-01"
    assert result["sample_id"] == "SP02-F02-COMMON-01"
    for source in original["sources"]:
        assert (root / source["path"]).read_bytes() == prep.git(
            REPO,
            "show",
            f"{prep.BASELINE}:benchmarks/contract_review/materials/{source['fixture']}",
        )
    tracked = prep.git(root, "ls-tree", "-r", "--name-only", "HEAD").decode().splitlines()
    assert sorted(tracked) == sorted(s["path"] for s in original["sources"])
    assert "oracle" not in json.dumps(result["request"]).lower()
    assert result["semantic_verdict"] == "NOT_RUN" and result["trial_consumed"] is False
    with pytest.raises(FileExistsError):
        prep.prepare_case(REPO, root.parent, "CR02-F02")


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", "CR02-F01"),
        ("source_trial_id", "TR02-F02-COMMON-999"),
        ("sample_id", "SP02-H01-COMMON-01"),
    ],
)
def test_case_and_trial_identity_mismatch_stops_before_submission(
    tmp_path, controlled_adapter, test_profile, monkeypatch, field, value
):
    result = prepared(tmp_path)
    with local_client(tmp_path, result, controlled_adapter(), test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        result[field] = value
        with pytest.raises(PreparationError):
            prep.run_case(client, result)
        assert posts == []


def test_preparation_does_not_load_auth_or_start_provider(tmp_path, monkeypatch, capsys):
    original = os.environ
    allowed = {"PATH", "SYSTEMROOT", "TEMP", "TMP"}

    class SafeEnvironment:
        def __contains__(self, name):
            assert name in allowed, "Preparation attempted to inspect another environment variable"
            return name in original

        def __getitem__(self, name):
            assert not any(word in name for word in ("KEY", "TOKEN", "SECRET", "AUTH"))
            if name not in allowed:
                raise KeyError(name)
            return original[name]

        def get(self, name, default=None):
            assert not any(word in name for word in ("KEY", "TOKEN", "SECRET", "AUTH"))
            return self[name] if name in allowed and name in original else default

    with monkeypatch.context() as patch:
        patch.setattr(prep.os, "environ", SafeEnvironment())
        patch.setattr(prep, "require_test_runtime", lambda _: pytest.fail("Started test runtime"))
        assert prep.main(["--case", "CR02-F02", "--output", str(tmp_path / "cli")]) == 0
    assert json.loads(capsys.readouterr().out)["business_model_http_attempts"] == 0
    with pytest.raises(SystemExit) as error:
        prep.main(["--case", "CR02-F02", "--output", str(tmp_path / "bad"), "--run"])
    assert error.value.code == 2
    assert not (tmp_path / "bad").exists()
    with pytest.raises(PreparationError, match="OUTSIDE_CHECKOUT"):
        prep.prepare_case(REPO, REPO / "forbidden-b1-output", "CR02-F02")


def test_f02_controlled_workflow_collects_report_without_semantic_pass(
    tmp_path, controlled_adapter, test_profile
):
    result = prepared(tmp_path)
    adapter = controlled_adapter()
    with local_client(tmp_path, result, adapter, test_profile) as client:
        evidence = prep.run_case(client, result)
        assert evidence.data["workflow_status"] == "completed_degraded"
        assert evidence.data["collection_complete"], evidence.data["gaps"]
        assert len(evidence.data["reports"]) == 1
        assert len(evidence.data["request_projections"]) == len(adapter.requests) == 2
        assert len(evidence.data["inputs"]) == len(evidence.data["jobs"]) == 1
        assert evidence.data["semantic_verdict"] == "NOT_RUN"
        assert evidence.data["mutations"] == []
        output = evidence.save(tmp_path / "f02-evidence")
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence.data


def test_human_answer_uses_report_question_id_and_allowed_type(
    tmp_path, controlled_adapter, test_profile, monkeypatch
):
    result = prepared(tmp_path, "CR02-H01")
    adapter = PublicHumanAdapter(controlled_adapter())
    with local_client(tmp_path, result, adapter, test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        evidence = prep.run_case(client, result)
        mutation = evidence.data["mutations"][0]
        assert mutation["body"]["answers"][0]["question_id"] == adapter.scope_id
        assert mutation["body"]["answers"][0]["answer_type"] == "clarify"
        assert mutation["body"]["answers"][0]["scope"] == "this_review"
        assert mutation["status"] == 202
        assert evidence.data["collection_complete"], evidence.data["gaps"]
        assert not any(path.endswith("/revisions") for path, _ in posts)


def test_partial_200_and_final_202_create_one_successor_without_revision_post(
    tmp_path, controlled_adapter, test_profile, monkeypatch
):
    result = prepared(tmp_path, "CR02-H01")
    adapter = PublicHumanAdapter(controlled_adapter(), two=True)
    with local_client(tmp_path, result, adapter, test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        evidence = prep.run_case(client, result)  # Only the predefined scope answer is automatic.
        review = evidence.data["accepted"]["review_id"]
        partial = evidence.data["mutations"][0]
        assert partial["status"] == 200 and partial["response"]["job_id"] is None
        assert len(evidence.data["jobs"]) == len(evidence.data["inputs"]) == 1
        extra_answer = [
            {
                "question_id": adapter.material_id,
                "scope": "this_review",
                "answer_type": "clarify",
                "text": "操作者明确补充的受控材料说明。",
            }
        ]
        completed = prep.submit_answers(evidence, review, extra_answer, "explicit-second-answer")
        replay = prep.submit_answers(evidence, review, extra_answer, "explicit-second-answer")
        assert completed["status"] == replay["status"] == 202
        assert completed["response"] == replay["response"]
        assert len(evidence.data["jobs"]) == len(evidence.data["inputs"]) == 2
        assert evidence.data["collection_complete"], evidence.data["gaps"]
        assert not any(path.endswith("/revisions") for path, _ in posts)
        assert (
            client.get(f"{prep.API}/{review}").json()["job_id"] == completed["response"]["job_id"]
        )


@pytest.mark.parametrize("case", ["CR02-H01", "CR02-H02"])
def test_h01_h02_original_answer_text_reaches_parent_and_fixed_review(
    tmp_path, controlled_adapter, test_profile, case
):
    result = prepared(tmp_path, case)
    adapter = PublicHumanAdapter(controlled_adapter())
    scripts = json.loads(
        prep.git(REPO, "show", f"{prep.BASELINE}:benchmarks/contract_review/human-scripts.json")
    )
    expected = scripts["answers"][case]["text"]
    with local_client(tmp_path, result, adapter, test_profile) as client:
        evidence = prep.run_case(client, result)
        states = evidence.data["states"]
        first = states[0]
        last = states[-1]
        assert first["current_input_revision_id"] != last["current_input_revision_id"]
        assert first["input_hash"] != last["input_hash"]
        assert first["execution_profile"] == last["execution_profile"]
        assert len(evidence.data["reports"]) == 2
        projections = list(evidence.data["request_projections"].values())
        before = [p for p in projections if p["input_hash"] == first["input_hash"]]
        after = [p for p in projections if p["input_hash"] == last["input_hash"]]
        assert {p["role"] for p in after} == {"analysis", "review"}
        assert all(expected in json.dumps(p["payload"], ensure_ascii=False) for p in after)
        assert all(expected not in json.dumps(p["payload"], ensure_ascii=False) for p in before)
        assert evidence.data["inputs"][first["current_input_revision_id"]]["first_state"] == first
        old = evidence.data["reports"][first["current_report_revision_id"]]["json"]
        assert (
            client.get(
                f"{prep.API}/{first['review_id']}/report",
                params={"report_revision_id": old["report_revision_id"]},
            ).json()
            == old
        )
        assert evidence.data["collection_complete"], evidence.data["gaps"]
        assert evidence.data["semantic_verdict"] == "NOT_RUN"
        evidence.save(tmp_path / ("evidence-" + case))


@pytest.mark.parametrize("variant", ["missing", "wrong_kind", "disallowed", "wrong_target"])
def test_missing_or_disallowed_question_stops_without_answer(
    tmp_path, controlled_adapter, test_profile, monkeypatch, variant
):
    result = prepared(tmp_path, "CR02-H01")
    adapter = PublicHumanAdapter(controlled_adapter(), variant=variant)
    with local_client(tmp_path, result, adapter, test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        evidence = prep.run_case(client, result)
        assert evidence.data["mutations"] == []
        assert not any(path.endswith("/resolution-batches") for path, _ in posts)
        assert evidence.data["semantic_verdict"] == "NOT_RUN"


def test_external_client_and_live_runtime_are_rejected_before_mutation(
    tmp_path, controlled_adapter, test_profile, monkeypatch
):
    import httpx

    result = prepared(tmp_path)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("External HTTP"))
    ) as client:
        with pytest.raises(PreparationError, match="IN_PROCESS"):
            prep.run_case(client, result)
    with local_client(tmp_path, result, controlled_adapter(), test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        client.app.state.contract_reviews.profiles[prep.PROFILE]["execution_mode"] = "live"
        with pytest.raises(PreparationError, match="CONTROLLED_B1_RUNTIME"):
            prep.run_case(client, result)
        assert posts == []


def test_prepared_request_or_source_mutation_is_rejected(
    tmp_path, controlled_adapter, test_profile, monkeypatch
):
    result = prepared(tmp_path)
    with local_client(tmp_path, result, controlled_adapter(), test_profile) as client:
        posts = spy_posts(monkeypatch, client)
        result["request"]["source"]["groups"] = []
        with pytest.raises(PreparationError, match="SOURCE_MISMATCH"):
            prep.run_case(client, result)
        assert posts == []


def test_direct_cli_prepares_without_importing_product_runtime(tmp_path):
    environment = {
        k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ
    }
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(SCRIPTS / "run_public_case_prep.py"),
            "--case",
            "CR02-F02",
            "--output",
            str(tmp_path / "direct-cli"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    record = json.loads(process.stdout)
    assert record["status"] == "PREPARED_NOT_DISPATCHED"
    assert record["business_model_http_attempts"] == 0

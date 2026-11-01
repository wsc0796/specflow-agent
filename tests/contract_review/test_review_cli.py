"""The thin client shares API authentication, errors and immutable evidence views."""

import json

import httpx
import pytest
from test_checkpoints import HumanAdapter, answer, batch, footprint, post, terminal, waiting
from test_decision_scope import confirm
from test_decision_scope import memory_client as memory_client
from test_verification_import import completed_review as completed_review
from test_verification_import import counts, evidence_body, next_input

from specflow.cli import main
from specflow.contract_review import cli as review_cli

URL = "/api/v1/contract-reviews"


@pytest.fixture
def invoke(monkeypatch, capsys):
    original_client = httpx.Client
    calls = []

    def run(client, args, *, options=(), response=None):
        # All tests use this separate, fixed fake credential; never the user's server environment.
        monkeypatch.setenv("CR07_TEST_KEY", client.headers["X-API-Key"])

        def handle(request):
            calls.append(request)
            if response is not None:
                return response(request)
            backend = client.request(
                request.method,
                "http://testserver" + request.url.raw_path.decode("ascii"),
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(
                backend.status_code, headers=backend.headers, content=backend.content
            )

        monkeypatch.setattr(
            httpx,
            "Client",
            lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
        )
        with pytest.raises(SystemExit) as exit_info:
            main(["contract-review", "--api-key-env", "CR07_TEST_KEY", *options, *args])
        captured = capsys.readouterr()
        assert "test-contract-key" not in captured.out + captured.err
        assert "test-key" not in captured.out + captured.err
        return exit_info.value.code, captured.out, captured.err, calls

    return run


def write_body(tmp_path, body, name="request.json"):
    path = tmp_path / name
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_cli_create_is_authenticated_http_and_success_replay_is_single_job(
    review_client, invoke, tmp_path
):
    client, domain, body = review_client
    args = ["create", "--body-file", write_body(tmp_path, body), "--idempotency-key", "cli-create"]
    code, output, _, calls = invoke(client, args)
    assert code == 0
    accepted = json.loads(output)
    before = footprint(domain, accepted["review_id"])
    code, output, _, calls = invoke(client, args)
    assert code == 0 and json.loads(output) == accepted
    assert footprint(domain, accepted["review_id"]) == before
    assert len(calls) == 2
    assert all(call.headers["X-API-Key"] == "test-contract-key" for call in calls)
    assert calls[0].headers["Idempotency-Key"] == "cli-create"
    assert json.loads(calls[0].content) == body


def test_cli_status_list_report_and_event_queries_show_existing_authority(completed_review, invoke):
    client, _, review_id, state, report = completed_review
    commands = [
        (["status", review_id], "current_step"),
        (["list", "--project-id", "project-test", "--limit", "1"], review_id),
        (["questions", review_id], "remaining_blocking_question_ids"),
        (["report", review_id], "# 契约审查报告"),
        (["report", review_id, "--format", "json"], report["report_revision_id"]),
        (["events", review_id, "--job-id", state["job_id"], "--limit", "1"], "next_cursor"),
    ]
    for args, expected in commands:
        code, output, error, _ = invoke(client, args)
        assert code == 0, error
        assert expected in output
    event_id = client.get(f"{URL}/{review_id}/events").json()["items"][0]["event_id"]
    code, output, _, _ = invoke(client, ["event", review_id, event_id])
    assert code == 0 and "payload" in json.loads(output)


def test_cli_answer_then_revision_share_existing_protocol(
    running_app, controlled_adapter, invoke, tmp_path
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, _, body):
        review_id, state, report = waiting(client, body)
        answers = batch(state, report, [answer(), answer("q_material")])
        args = [
            "resolve",
            review_id,
            "--body-file",
            write_body(tmp_path, answers),
            "--idempotency-key",
            "resolve",
        ]
        code, output, error, _ = invoke(client, args)
        assert code == 0, error
        assert json.loads(output)["accepted_resolution_ids"]
        state = terminal(client, review_id)
        revision = {
            "expected_version": state["version"],
            "base_input_revision_id": state["current_input_revision_id"],
            "change_reason": "本次明确修改请求。",
            "request": "新的本次请求。",
        }
        code, output, error, _ = invoke(
            client,
            [
                "revise",
                review_id,
                "--body-file",
                write_body(tmp_path, revision),
                "--idempotency-key",
                "revision",
            ],
        )
        assert code == 0, error
        assert json.loads(output)["input_revision_id"] != state["current_input_revision_id"]


def test_cli_three_import_conflicts_and_success_replay_keep_distinct_codes(
    completed_review, invoke, tmp_path
):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)

    def import_body(value, key):
        return invoke(
            client,
            [
                "import-evidence",
                review_id,
                "--body-file",
                write_body(tmp_path, value),
                "--idempotency-key",
                key,
            ],
        )

    before = counts(domain, review_id)
    for key, value, expected in (
        ("stale", {**body, "expected_version": state["version"] - 1}, "VERSION_CONFLICT"),
        ("baseline", {**body, "source_commit_sha": "0" * 40}, "VERIFICATION_BASELINE_MISMATCH"),
    ):
        code, output, error, _ = import_body(value, key)
        assert code == 3 and output == ""
        assert expected in error
        assert counts(domain, review_id) == before
    code, output, error, _ = import_body(body, "success")
    assert code == 0, error
    accepted = json.loads(output)
    assert accepted["status"] == "provided_not_independently_verified"
    revised = next_input(domain, review_id, selected=[])
    code, output, error, _ = import_body(body, "success")
    assert code == 0 and json.loads(output) == accepted, error
    before = counts(domain, review_id)
    code, output, error, _ = import_body(
        {**body, "expected_version": revised["version"]}, "wrong-current"
    )
    assert code == 3 and "VERIFICATION_TARGET_NOT_CURRENT" in error
    assert counts(domain, review_id) == before
    code, output, error, _ = invoke(
        client, ["evidence", review_id, "--evidence-id", accepted["evidence_id"]]
    )
    assert code == 0, error
    view = json.loads(output)
    assert view["origin"]["input_revision_id"] == report["input_revision_id"]
    assert view["current_adoption"] is None
    assert view["current_applicability"] is None
    assert view["applicable_to_current_input"] is None


@pytest.mark.parametrize(
    "basis,expected", [("same", True), ("changed", False), ("missing_dimension", None)]
)
def test_cli_external_evidence_origin_and_current_applicability_are_separate(
    completed_review, invoke, tmp_path, basis, expected
):
    client, domain, review_id, state, report = completed_review
    request = evidence_body(state, report)
    evidence = post(client, review_id, request, endpoint="verification-evidence").json()

    # Independent, explicit future input adoption; the original record is unchanged.
    def modify(frozen):
        if basis == "changed":
            frozen["commit_sha"] = "f" * 40
        elif basis == "missing_dimension":
            for target in frozen["target_manifest"]:
                target.pop("source_path", None)

    revised = next_input(domain, review_id, modify=modify, selected=[evidence["evidence_id"]])
    code, output, error, _ = invoke(client, ["evidence", review_id])
    assert code == 0, error
    view = json.loads(output)["items"][0]
    assert view["origin"]["input_revision_id"] == report["input_revision_id"]
    assert view["current_adoption"]["adopting_input_revision_id"] == revised["input_revision_id"]
    assert view["applicable_to_current_input"] is expected
    assert view["status"] == "provided_not_independently_verified"
    assert "procedure" in view and view["procedure"] == request["procedure"]
    assert domain.report(review_id, report["report_revision_id"]) == report


def test_cli_output_failure_never_erases_authority_or_overwrites_file(
    completed_review, invoke, tmp_path
):
    client, domain, review_id, _, report = completed_review
    path = tmp_path / "existing.md"
    path.write_text("原文件", encoding="utf-8")
    before = footprint(domain, review_id)
    code, output, error, _ = invoke(client, ["report", review_id], options=["--output", str(path)])
    assert code == 2 and output == "" and "输出失败" in error
    assert path.read_text(encoding="utf-8") == "原文件"
    assert domain.report(review_id) == report
    assert footprint(domain, review_id) == before
    exported = tmp_path / "report.md"
    code, output, error, _ = invoke(
        client, ["report", review_id], options=["--output", str(exported)]
    )
    assert code == 0 and not output, error
    assert exported.read_text(encoding="utf-8").startswith("# 契约审查报告")


def test_cli_preserves_current_history_boundary(completed_review, invoke):
    client, domain, review_id, _, report = completed_review
    next_input(domain, review_id, selected=[])
    code, output, error, _ = invoke(client, ["report", review_id])
    assert code == 3 and output == "" and "REPORT_NOT_AVAILABLE" in error
    code, output, error, _ = invoke(
        client, ["report", review_id, "--report-revision-id", report["report_revision_id"]]
    )
    assert code == 0 and report["input_revision_id"] in output, error


@pytest.mark.parametrize(
    "data",
    [
        b"{",
        b"[]",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"x" * (1024**2 + 1),
        b'{"a":' + b"[" * 20000 + b"0" + b"]" * 20000 + b"}",
    ],
    ids=["malformed", "array", "duplicate", "nonfinite", "oversize", "deep"],
)
def test_invalid_or_oversize_cli_body_has_zero_requests(review_client, invoke, tmp_path, data):
    client, _, _ = review_client
    path = tmp_path / "bad.json"
    path.write_bytes(data)
    code, _, _, calls = invoke(
        client, ["create", "--body-file", str(path), "--idempotency-key", "bad"]
    )
    assert code == 2 and calls == []


@pytest.mark.parametrize(
    "url",
    [
        "https://secret:credential@example.invalid",
        "http://localhost/?key=hidden",
        "file:///tmp/file",
        "http://localhost/prefix",
        "http://localhost:notaport",
        "http://localhost:%",
        "http://localhost:65536",
    ],
)
def test_invalid_server_addresses_do_not_send_credentials(review_client, invoke, url):
    client, _, _ = review_client
    code, output, error, calls = invoke(client, ["status", "review"], options=["--base-url", url])
    assert code == 2 and calls == [] and output == ""
    assert "secret" not in error and "credential" not in error


def test_cli_redirect_timeout_and_oversize_response_do_not_retry(
    review_client, invoke, monkeypatch
):
    client, _, _ = review_client
    code, _, error, calls = invoke(
        client,
        ["status", "r"],
        response=lambda request: httpx.Response(
            307, headers={"Location": "https://other.invalid"}, content=b"redirect"
        ),
    )
    assert code == 3 and len(calls) == 1 and "307" in error

    def timeout(request):
        raise httpx.ReadTimeout("do not echo this exception or credential")

    code, _, error, calls = invoke(client, ["status", "r"], response=timeout)
    assert code == 3 and len(calls) == 2 and "do not echo" not in error
    monkeypatch.setattr(review_cli, "RESPONSE_LIMIT", 20)
    code, _, _, calls = invoke(
        client,
        ["status", "r"],
        response=lambda request: httpx.Response(200, json={"body": "x" * 40}),
    )
    assert code == 2 and len(calls) == 3


def test_cli_has_no_retry_or_raw_credential_options_and_help_reads_no_credentials(
    monkeypatch, capsys
):
    original_get = review_cli.os.environ.get

    def forbidden(name, *args):
        if name in ("SPECFLOW_API_KEY", "CR07_TEST_KEY"):
            pytest.fail("Help must not read credentials")
        return original_get(name, *args)

    monkeypatch.setattr(review_cli.os.environ, "get", forbidden)
    with pytest.raises(SystemExit) as result:
        main(["contract-review", "--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "--api-key-env" in help_text and "--api-key " not in help_text
    assert "retry" not in help_text


def test_cli_publishes_and_queries_project_decisions_with_explicit_version(
    memory_client, invoke, tmp_path
):
    client, _, _ = memory_client
    path = write_body(tmp_path, confirm())
    code, output, error, _ = invoke(
        client,
        [
            "publish-decision",
            "--project-id",
            "project-test",
            "--body-file",
            path,
            "--idempotency-key",
            "publish",
        ],
    )
    assert code == 0, error
    decision = json.loads(output)
    code, output, error, _ = invoke(
        client,
        ["decisions", "--project-id", "project-test", "--ruleset-version", "1", "--limit", "1"],
    )
    assert code == 0, error
    view = json.loads(output)
    assert view["ruleset_version"] == 1
    assert view["items"][0]["project_decision_id"] == decision["project_decision_id"]
    assert view["items"][0]["actor_subject"] == "shared-service"


def test_cli_missing_fake_credential_fails_before_network(monkeypatch, capsys):
    monkeypatch.delenv("CR07_MISSING_TEST_KEY", raising=False)
    with pytest.raises(SystemExit) as result:
        main(["contract-review", "--api-key-env", "CR07_MISSING_TEST_KEY", "status", "r"])
    assert result.value.code == 2
    assert capsys.readouterr().out == ""


def test_cli_post_output_failure_keeps_accepted_result_and_original_key_replays(
    review_client, invoke, tmp_path
):
    client, domain, body = review_client
    output_path = tmp_path / "existing.json"
    output_path.write_text("keep", encoding="utf-8")
    args = [
        "create",
        "--body-file",
        write_body(tmp_path, body),
        "--idempotency-key",
        "accepted-before-output",
    ]
    code, output, error, _ = invoke(client, args, options=["--output", str(output_path)])
    assert code == 2 and not output and "服务端结果保持原状" in error
    items = client.get(URL, params={"project_id": "project-test"}).json()["items"]
    assert len(items) == 1
    before = footprint(domain, items[0]["review_id"])
    code, output, error, _ = invoke(client, args)
    assert code == 0, error
    assert json.loads(output)["review_id"] == items[0]["review_id"]
    assert footprint(domain, items[0]["review_id"]) == before
    assert output_path.read_text(encoding="utf-8") == "keep"

"""Deterministic integration contracts for T-070 (no overlap-by-sleep)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from specflow import runner_multi


@pytest.mark.parametrize("requirement_size", [0, 120000, 140000])
def test_legacy_overlapping_calls_share_execution(tmp_path, monkeypatch, requirement_size):
    from specflow import runner
    from specflow.single_flight import SingleFlightCoordinator

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text("def feature(): return 1\n")
    entered, release, joined = Event(), Event(), Event()
    coordinator = SingleFlightCoordinator()
    original = runner.EvidenceCollector.collect
    calls = []

    def collect(self, **kwargs):
        calls.append("evidence")
        entered.set()
        assert release.wait(5)
        return original(self, **kwargs)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    requirement = "feature" if not requirement_size else "feature " + "x" * requirement_size
    kwargs = dict(repo=repo, requirement=requirement, mock=True, _coordinator=coordinator)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(runner.run, output=tmp_path / "owner", **kwargs)
        try:
            assert entered.wait(5)
            follower = pool.submit(
                runner.run,
                output=tmp_path / "follower",
                **kwargs,
                _on_join=lambda audit: joined.set() if audit["role"] == "follower" else None,
            )
            assert joined.wait(5)
            assert not owner.done() and not follower.done()
        finally:
            release.set()
        first, second = owner.result(5), follower.result(5)
    assert first == second == (4 if requirement_size else 0)
    assert calls == ["evidence"]
    assert second.single_flight["role"] == "follower"
    assert first.artifact_directory == second.artifact_directory
    assert second.artifact_directory is not None
    manifest = second.artifact_directory / "manifest.json"
    if requirement_size == 140000:
        assert manifest.stat().st_size > 131072
    else:
        assert manifest.stat().st_size <= 131072
    assert len(list(second.artifact_directory.iterdir())) == 10
    assert not (tmp_path / "follower").exists()
    assert coordinator.active_count == 0


def test_run_result_keeps_int_compatibility_and_is_immutable():
    from specflow.single_flight import RunResult

    result = RunResult(4, single_flight={"role": "owner", "owner_run_id": "run-example"})
    assert isinstance(result, int) and result in {0, 4}
    assert result.result_status == "completed_degraded"
    with pytest.raises(AttributeError):
        result.error_code = "CHANGED"
    with pytest.raises(AttributeError):
        del result.artifact_directory
    metadata = result.single_flight
    metadata["role"] = "follower"
    assert result.single_flight["role"] == "owner"


@pytest.mark.parametrize(
    "code, state, error",
    [
        (0, "completed", None),
        (4, "completed_degraded", None),
        (2, "failed_security", "REPOSITORY_UNAVAILABLE"),
        (3, "failed_runtime", "RUNNER_FAILED"),
    ],
)
def test_run_result_carries_terminal_classification(code, state, error):
    from specflow.single_flight import RunResult

    result = RunResult(code)
    assert result.result_status == state
    assert result.error_code == error


def test_key_includes_summary_directory_existence(tmp_path):
    from specflow.single_flight import prepare_run

    args = dict(
        repo=tmp_path,
        requirement="x",
        mode="multi-agent",
        mock=True,
        provider="mock",
        model="mock-model",
    )
    before = prepare_run(**args)
    (tmp_path / "pyproject.toml").mkdir()
    assert prepare_run(**args) != before


def test_legacy_live_requested_model_changes_do_not_coalesce(tmp_path, monkeypatch):
    from specflow.llm import OpenAICompatibleConfig
    from specflow.single_flight import SingleFlightCoordinator, prepare_run

    config = OpenAICompatibleConfig("https://provider.invalid/v1", "test-only", "wire-model")
    monkeypatch.setattr(OpenAICompatibleConfig, "from_env", lambda: config)
    args = dict(
        repo=tmp_path,
        requirement="feature",
        mode="legacy",
        mock=False,
        provider="openai-compatible",
    )
    first = prepare_run(**args, model="requested-a")
    second = prepare_run(**args, model="requested-b")
    coordinator = SingleFlightCoordinator()
    with coordinator.claim(first, "owner-a"):
        with coordinator.claim(second, "owner-b") as other:
            assert other.owner
    assert coordinator.active_count == 0


@pytest.mark.parametrize(
    "change",
    [
        "requirement",
        "snapshot",
        "policy",
        "mode",
        "mock",
        "provider",
        "model",
        "endpoint",
        "effective_model",
        "credential",
        "timeout",
        "versions",
        "max_files",
    ],
)
def test_semantic_key_changes_never_join_existing_owner(tmp_path, monkeypatch, change):
    from dataclasses import replace

    from specflow.llm import OpenAICompatibleConfig
    from specflow.policy import DEFAULT_POLICY
    from specflow.single_flight import CONTRACT_VERSIONS, SingleFlightCoordinator, prepare_run

    config = OpenAICompatibleConfig("https://provider.invalid/v1", "test-only", "model-a")
    monkeypatch.setattr(OpenAICompatibleConfig, "from_env", lambda: config)
    args = dict(
        repo=tmp_path,
        requirement="feature",
        mode="multi-agent",
        mock=False,
        provider="openai-compatible",
        model="requested-a",
        policy=DEFAULT_POLICY,
    )
    (tmp_path / "feature.py").write_text("feature = 1\n")
    first = prepare_run(**args)
    if change == "requirement":
        args["requirement"] += " "  # exact, not normalized requirement
    elif change == "snapshot":
        (tmp_path / "feature.py").write_text("feature = 2\n")
    elif change == "policy":
        args["policy"] = replace(DEFAULT_POLICY, fail_on_schema_error=False)
    elif change == "mode":
        args["mode"] = "legacy"
    elif change == "mock":
        args["mock"] = True
    elif change == "provider":
        args["provider"] = "other-provider"
    elif change == "model":
        args["model"] = "requested-b"
    elif change == "endpoint":
        config = replace(config, base_url="https://other.invalid/v1")
    elif change == "effective_model":
        config = replace(config, model="model-b")
    elif change == "credential":
        config = replace(config, api_key="test-another-credential")
    elif change == "timeout":
        config = replace(config, timeout_seconds=12)
    elif change == "versions":
        args["versions"] = (*CONTRACT_VERSIONS, ("changed", "2"))
    elif change == "max_files":
        args["extra"] = {"max_files": 2}
    second = prepare_run(**args)
    assert first.key != second.key
    coordinator = SingleFlightCoordinator()
    with coordinator.claim(first, "owner-a") as owner:
        assert owner.owner
        with coordinator.claim(second, "owner-b") as other:
            assert other.owner
            assert coordinator.active_count == 2
    assert coordinator.active_count == 0
    assert "provider.invalid" not in repr(first)


@pytest.mark.parametrize(
    "contract",
    [
        "topology",
        "schema",
        "prompt",
        "enrichment",
        "sanitizer",
        "artifacts",
        "evidence",
    ],
)
def test_each_behavior_contract_version_is_part_of_key(tmp_path, contract):
    from specflow.single_flight import CONTRACT_VERSIONS, prepare_run

    args = dict(
        repo=tmp_path,
        requirement="x",
        mode="multi-agent",
        mock=True,
        provider="mock",
        model="mock-model",
    )
    changed = tuple(
        (name, "changed" if name == contract else value) for name, value in CONTRACT_VERSIONS
    )
    assert prepare_run(**args).key != prepare_run(**args, versions=changed).key


def test_snapshot_covers_raw_search_input_not_only_redacted_file_hash(tmp_path):
    from specflow.single_flight import repository_snapshot

    path = tmp_path / "feature.py"
    path.write_text('password = "first-word"\n')
    first = repository_snapshot(tmp_path)
    path.write_text('password = "other-word"\n')
    assert repository_snapshot(tmp_path) != first


def test_snapshot_does_not_expand_the_tool_read_window(tmp_path):
    from specflow.single_flight import repository_snapshot

    path = tmp_path / "feature.py"
    prefix = b"x" * 262145
    path.write_bytes(prefix + b"unread-a")
    first = repository_snapshot(tmp_path)
    path.write_bytes(prefix + b"unread-b")
    assert repository_snapshot(tmp_path) == first
    path.write_bytes(b"y" + prefix[1:] + b"unread-b")
    assert repository_snapshot(tmp_path) != first


def test_snapshot_ignores_sensitive_and_excluded_files(tmp_path):
    from specflow.single_flight import repository_snapshot

    first = repository_snapshot(tmp_path)
    (tmp_path / ".env").write_text("test-only")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.py").write_text("x")
    (tmp_path / "photo.png").write_bytes(b"image")
    assert repository_snapshot(tmp_path) == first


@pytest.mark.parametrize("limit", ["entries", "bytes", "read_error", "changed"])
def test_unsafe_snapshot_fails_before_evidence_or_ownership(tmp_path, monkeypatch, limit):
    import specflow.single_flight as sf

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "feature.py").write_text("feature = 1")
    if limit == "entries":
        monkeypatch.setattr(sf, "SNAPSHOT_MAX_ENTRIES", 1)
        (repo / "empty-directory").mkdir()
    elif limit == "bytes":
        monkeypatch.setattr(sf, "SNAPSHOT_MAX_BYTES", 1)
    elif limit == "read_error":
        monkeypatch.setattr(
            sf, "_read_text", lambda *_: (_ for _ in ()).throw(OSError("sensitive-read-input"))
        )
    else:
        original = sf._read_text

        def change_file(path, count):
            value = original(path, count)
            path.write_text("feature = 22")
            return value

        monkeypatch.setattr(sf, "_read_text", change_file)
    coordinator = sf.SingleFlightCoordinator()

    def forbidden(*args, **kwargs):
        pytest.fail("expensive work before a safe snapshot")

    monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", forbidden)
    result = runner_multi.run_multi_agent(
        repo=repo,
        requirement="feature",
        output=tmp_path / "out",
        mock=True,
        _coordinator=coordinator,
    )
    assert result == 2
    assert result.error_code == "SINGLE_FLIGHT_SNAPSHOT_UNAVAILABLE"
    assert coordinator.active_count == 0
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("failure", ["classified", "exception", "artifact", "cancelled"])
def test_owner_terminal_paths_release_followers_and_allow_later_execution(
    tmp_path,
    monkeypatch,
    failure,
    caplog,
):
    from specflow.policy import SpecFlowError
    from specflow.single_flight import SingleFlightCoordinator

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "feature.py").write_text("feature = 1")
    coordinator = SingleFlightCoordinator()
    entered, joined, release = Event(), Event(), Event()
    original = runner_multi._run_multi_agent_owned
    calls = []

    def failing(**kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        if failure == "classified":
            raise SpecFlowError("CALL_BUDGET_EXCEEDED", "safe")
        if failure == "cancelled":
            raise KeyboardInterrupt()
        raise OSError("private-path-requirement-secret")

    if failure == "artifact":
        original_write = runner_multi._safe_write

        def fail_write(*args, **kwargs):
            if args[1] == "manifest.json":
                return failing()
            return original_write(*args, **kwargs)

        monkeypatch.setattr(runner_multi, "_safe_write", fail_write)
    else:
        monkeypatch.setattr(runner_multi, "_run_multi_agent_owned", failing)
    kwargs = dict(repo=repo, requirement="feature", mock=True, _coordinator=coordinator)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(runner_multi.run_multi_agent, output=tmp_path / "one", **kwargs)
        try:
            assert entered.wait(5)
            follower = pool.submit(
                runner_multi.run_multi_agent,
                output=tmp_path / "two",
                **kwargs,
                _on_join=lambda meta: joined.set() if meta["role"] == "follower" else None,
            )
            assert joined.wait(5)
            assert coordinator.active_count == 1
        finally:
            release.set()
        second = follower.result(5)
        if failure == "cancelled":
            with pytest.raises(KeyboardInterrupt):
                owner.result(5)
            assert second.error_code == "RUN_CANCELLED"
            assert second.result_status == "cancelled"
        else:
            first = owner.result(5)
            assert first == second == 3
            assert first.error_code == second.error_code
    assert calls == [1]
    assert coordinator.active_count == 0
    assert "private-path-requirement-secret" not in caplog.text
    monkeypatch.setattr(runner_multi, "_run_multi_agent_owned", original)
    if failure == "artifact":
        monkeypatch.setattr(runner_multi, "_safe_write", original_write)
    result = runner_multi.run_multi_agent(output=tmp_path / "retry", **kwargs)
    assert result == 0
    assert result.single_flight["role"] == "owner"
    assert coordinator.active_count == 0


@pytest.mark.parametrize("cancelled", [False, True])
def test_follower_exit_keeps_the_owner_and_later_follower(tmp_path, monkeypatch, cancelled):
    from specflow.single_flight import Flight, SingleFlightCoordinator

    repo = tmp_path / "repo"
    repo.mkdir()
    entered, release, joined = Event(), Event(), Event()
    coordinator = SingleFlightCoordinator()
    original = runner_multi.EvidenceCollector.collect
    original_wait = Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return original(self, **kwargs)

    monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", collect)

    def stop_waiting(self, timeout):
        if cancelled:
            raise KeyboardInterrupt()
        return original_wait(self, 0)  # deterministic deadline, owner is held

    kwargs = dict(repo=repo, requirement="feature", mock=True, _coordinator=coordinator)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(runner_multi.run_multi_agent, output=tmp_path / "one", **kwargs)
        try:
            assert entered.wait(5)
            monkeypatch.setattr(Flight, "wait", stop_waiting)
            if cancelled:
                with pytest.raises(KeyboardInterrupt):
                    runner_multi.run_multi_agent(output=tmp_path / "two", **kwargs)
            else:
                result = runner_multi.run_multi_agent(output=tmp_path / "two", **kwargs)
                assert result == 3 and result.error_code == "SINGLE_FLIGHT_WAIT_TIMEOUT"
            assert coordinator.active_count == 1
            monkeypatch.setattr(Flight, "wait", original_wait)
            follower = pool.submit(
                runner_multi.run_multi_agent,
                output=tmp_path / "three",
                **kwargs,
                _on_join=lambda meta: joined.set() if meta["role"] == "follower" else None,
            )
            assert joined.wait(5)
            assert calls == [1] and not owner.done()
        finally:
            release.set()
        assert owner.result(5) == follower.result(5) == 0
    assert coordinator.active_count == 0


def test_partial_artifact_failure_is_not_shared_as_completed(tmp_path, monkeypatch):
    from specflow.policy import SpecFlowError

    repo = tmp_path / "repo"
    repo.mkdir()
    original = runner_multi._safe_write

    def fail_metrics(*args, **kwargs):
        if args[1] == "metrics.json":
            raise SpecFlowError("ARTIFACT_WRITE_FAILED", "safe")
        return original(*args, **kwargs)

    monkeypatch.setattr(runner_multi, "_safe_write", fail_metrics)
    result = runner_multi.run_multi_agent(
        repo=repo,
        requirement="x",
        output=tmp_path / "out",
        mock=True,
    )
    assert result == 3
    assert result.error_code == "ARTIFACT_WRITE_FAILED"
    assert result.artifact_directory is None


@pytest.mark.parametrize("failure_point", ["directory", "manifest.json", "_COMPLETE"])
def test_artifact_io_failure_is_an_explicit_runtime_result(tmp_path, monkeypatch, failure_point):
    from specflow.single_flight import SingleFlightCoordinator

    repo = tmp_path / "repo"
    repo.mkdir()
    original_write = runner_multi._safe_write
    original_mkdir = Path.mkdir

    def fail_write(directory, filename, *args, **kwargs):
        if filename == failure_point:
            raise OSError("test-artifact-io-failure")
        return original_write(directory, filename, *args, **kwargs)

    def fail_mkdir(path, *args, **kwargs):
        if failure_point == "directory" and path.name.startswith("run-multi-"):
            raise OSError("test-artifact-directory-failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(runner_multi, "_safe_write", fail_write)
    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    coordinator = SingleFlightCoordinator()
    result = runner_multi.run_multi_agent(
        repo=repo,
        requirement="x",
        output=tmp_path / "out",
        mock=True,
        _coordinator=coordinator,
    )
    assert result == 3 and result.result_status == "failed_runtime"
    assert result.error_code == "ARTIFACT_WRITE_FAILED"
    assert result.artifact_directory is None
    assert coordinator.active_count == 0


def test_missing_completion_marker_cannot_publish_success(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(runner_multi, "_finalize_run_directory", lambda *args: None)
    result = runner_multi.run_multi_agent(
        repo=repo, requirement="x", output=tmp_path / "out", mock=True
    )
    assert result == 3
    assert result.error_code == "ARTIFACT_WRITE_FAILED"
    assert result.artifact_directory is None


def test_primary_failure_survives_unavailable_diagnostic_artifacts(tmp_path, monkeypatch):
    from specflow.policy import SpecFlowError

    repo = tmp_path / "repo"
    repo.mkdir()

    def fail_stage(*args, **kwargs):
        raise SpecFlowError("CALL_BUDGET_EXCEEDED", "safe")

    def fail_write(*args, **kwargs):
        raise OSError("test-diagnostic-io-failure")

    monkeypatch.setattr(runner_multi, "_run_and_accumulate", fail_stage)
    monkeypatch.setattr(runner_multi, "_safe_write", fail_write)
    result = runner_multi.run_multi_agent(
        repo=repo, requirement="x", output=tmp_path / "out", mock=True
    )
    assert result == 3
    assert result.error_code == "CALL_BUDGET_EXCEEDED"
    assert result.artifact_directory is None


def test_completed_results_are_not_cached(tmp_path, monkeypatch):
    calls = []
    original = runner_multi.EvidenceCollector.collect

    def collect(self, **kwargs):
        calls.append(1)
        return original(self, **kwargs)

    monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", collect)
    repo = tmp_path / "repo"
    repo.mkdir()
    first = runner_multi.run_multi_agent(
        repo=repo, requirement="x", output=tmp_path / "a", mock=True
    )
    second = runner_multi.run_multi_agent(
        repo=repo, requirement="x", output=tmp_path / "b", mock=True
    )
    assert first == second == 0
    assert calls == [1, 1]
    assert first.single_flight["role"] == second.single_flight["role"] == "owner"
    assert first.artifact_directory != second.artifact_directory
    conflict = runner_multi.run_multi_agent(
        repo=repo, requirement="x", output=tmp_path / "a", mock=True
    )
    assert conflict == 3 and conflict.artifact_directory is None


def test_direct_overlapping_calls_share_execution_and_audit(tmp_path, monkeypatch):
    from specflow.single_flight import SingleFlightCoordinator

    coordinator = SingleFlightCoordinator()
    entered, release, joined = Event(), Event(), Event()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text("def feature(): return 1\n")
    original = runner_multi.EvidenceCollector.collect
    calls = []
    provider_calls, scheduler_calls, writes = [], [], []
    original_provider = runner_multi.MockLLMClient.complete
    original_schedule = runner_multi.MultiAgentScheduler.execute
    original_write = runner_multi._safe_write

    def provider_call(self, *args, **kwargs):
        provider_calls.append(1)
        return original_provider(self, *args, **kwargs)

    def schedule(self, *args, **kwargs):
        scheduler_calls.append(1)
        return original_schedule(self, *args, **kwargs)

    def write(*args, **kwargs):
        writes.append(args[1])
        return original_write(*args, **kwargs)

    monkeypatch.setattr(runner_multi.MockLLMClient, "complete", provider_call)
    monkeypatch.setattr(runner_multi.MultiAgentScheduler, "execute", schedule)
    monkeypatch.setattr(runner_multi, "_safe_write", write)

    def collect(self, **kwargs):
        calls.append("evidence")
        entered.set()
        assert release.wait(5)
        return original(self, **kwargs)

    monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", collect)

    def audit(metadata):
        if metadata["role"] == "follower":
            joined.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(
            runner_multi.run_multi_agent,
            repo=repo,
            requirement="feature",
            mock=True,
            output=tmp_path / "owner",
            _coordinator=coordinator,
            _on_join=audit,
        )
        try:
            assert entered.wait(5)
            follower = pool.submit(
                runner_multi.run_multi_agent,
                repo=repo,
                requirement="feature",
                mock=True,
                output=tmp_path / "follower",
                _coordinator=coordinator,
                _on_join=audit,
            )
            assert joined.wait(5)
            assert not owner.done() and not follower.done()
            assert calls == ["evidence"]
        finally:
            release.set()
        first, second = owner.result(5), follower.result(5)
    assert first == second == 0
    assert first.single_flight["role"] == "owner"
    assert second.single_flight["role"] == "follower"
    assert first.single_flight["owner_run_id"] == second.single_flight["owner_run_id"]
    assert first.artifact_directory == second.artifact_directory
    assert first.artifact_directory.is_relative_to(tmp_path / "owner")
    assert not (tmp_path / "follower").exists()
    assert len(provider_calls) == 6  # six normal enrichment calls, one owner's chain
    assert len(scheduler_calls) == 4
    assert len(writes) == len(set(writes)) == 9
    assert coordinator.active_count == 0


def test_api_single_flight_dto_is_durable_without_new_columns(tmp_path: Path):
    from test_runs import client_for, register_project

    from specflow.db import WorkflowRun

    repo = tmp_path / "repo"
    repo.mkdir()
    with client_for(tmp_path) as client:
        project = register_project(client, repo)
        response = client.post("/api/v1/runs", json={"project_id": project, "requirement": "x"})
        assert response.status_code == 201
        body = response.json()
        expected = {"role": "owner", "owner_run_id": body["id"]}
        assert body["single_flight"] == expected
        with client.app.state.database.factory() as session:
            row = session.get(WorkflowRun, body["id"])
            assert row.state_payload == {"mock": True, "single_flight": expected}
        assert client.get(f"/api/v1/runs/{body['id']}").json()["single_flight"] == expected


@pytest.mark.parametrize(
    "change", ["requirement", "snapshot", "policy", "mode", "provider", "model"]
)
def test_different_direct_inputs_execute_as_two_overlapping_owners(tmp_path, monkeypatch, change):
    from dataclasses import replace

    from specflow import runner
    from specflow.policy import DEFAULT_POLICY
    from specflow.single_flight import SingleFlightCoordinator

    coordinator = SingleFlightCoordinator()
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "feature.py"
    source.write_text("def feature(): return 1\n")
    first_entered, second_entered, release = Event(), Event(), Event()
    original = runner_multi.EvidenceCollector.collect
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        (first_entered if len(calls) == 1 else second_entered).set()
        assert release.wait(5)
        return original(self, **kwargs)

    monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", collect)
    args = dict(repo=repo, requirement="feature", mock=True, _coordinator=coordinator)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(runner_multi.run_multi_agent, output=tmp_path / "one", **args)
        try:
            assert first_entered.wait(5)
            execute = runner_multi.run_multi_agent
            if change == "requirement":
                args["requirement"] = "feature changed"
            elif change == "snapshot":
                source.write_text("def feature(): return 2\n")
            elif change == "policy":
                args["policy"] = replace(DEFAULT_POLICY, max_llm_calls=9)
            elif change == "mode":
                execute = runner.run
            elif change == "provider":
                args["provider"] = "openai-compatible"  # still explicitly mock=True
            elif change == "model":
                args["model"] = "mock-b"
            second = pool.submit(execute, output=tmp_path / "two", **args)
            assert second_entered.wait(5)
            assert not first.done() and not second.done()
            assert coordinator.active_count == 2
        finally:
            release.set()
        first_result, second_result = first.result(5), second.result(5)
    assert first_result == second_result == 0
    assert first_result.single_flight["role"] == second_result.single_flight["role"] == "owner"
    assert coordinator.active_count == 0

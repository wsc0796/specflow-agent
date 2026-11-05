"""One authorized F01 trial, using the existing API and worker.

Default execution prepares a non-secret run card. --run is still subject to
the frozen CNY 2 and verified off-peak-window preflight.
No launcher, credential store, model probe, retry endpoint or database mutation
is used to bypass that decision. Runtime artifacts are outside the checkout.
"""

from __future__ import annotations

import argparse
import copy
import json
import multiprocessing
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
from f01_trial_guard import (
    LAUNCHER_BASE,
    PROVIDER_BASE,
    REQUEST_MODEL,
    FlashPolicy,
    GuardedFlashAdapter,
    TrialLedger,
    TrialStopped,
    timestamp,
)

BASELINE = "ef2c53af26f0a02f61b4e7c8fa07e1d767a17029"
CASE = "CR02-F01"
SOURCE_TRIAL = "TR02-F01-COMMON-01"
SAMPLE = "SP02-F01-COMMON-01"
PROFILE = "pilot-f01-deepseek-flash-v3"
MATERIALS = (
    ("contracts/v2.json", "contract", "contract-v2.json"),
    ("src/api.py", "implementation", "api-correct.py"),
    ("docs/api.md", "documentation", "docs-id.md"),
    ("examples/client.py", "example", "example-id.py"),
)
TERMINAL = frozenset(("completed", "completed_degraded", "failed", "awaiting_decision"))


def _git(root, *args):
    environment = {
        key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if key in os.environ
    }
    environment.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="F01 fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="F01 fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "--no-lazy-fetch",
            "-c",
            "protocol.allow=never",
            "-c",
            "core.autocrlf=false",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(root),
            *args,
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        raise TrialStopped("FIXED_GIT_SOURCE_UNAVAILABLE")
    return result.stdout


def _save(path, body, *, update=False):
    raw = json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if not update:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name + ".new")
    _save(temporary, body)
    os.replace(temporary, path)


def load_case(repository):
    raw = _git(repository, "show", f"{BASELINE}:benchmarks/contract_review/cases.json")
    cases = json.loads(raw)
    selected = [case for case in cases if case["case_id"] == CASE]
    if len(selected) != 1:
        raise TrialStopped("F01_IDENTITY_MISMATCH")
    case = selected[0]
    if (
        case["trial_id"] != SOURCE_TRIAL
        or case["sample_id"] != SAMPLE
        or [(s["path"], s["role"], s["fixture"]) for s in case["sources"]] != list(MATERIALS)
        or case["request"]["target_api_version"] != "v2"
        or case["request"]["ruleset_usage"] != {"mode": "none"}
        or len(case["request"]["targets"]) != 2
    ):
        raise TrialStopped("F01_SCOPE_MISMATCH")
    for target, expected in zip(
        case["request"]["targets"], ("docs/api.md", "examples/client.py"), strict=True
    ):
        if (
            target["api_version"] != "v2"
            or target["endpoint"] != {"method": "POST", "path": "/exports"}
            or target["source_path"] != expected
            or len(target["checks"]) != 1
            or target["checks"][0]["key"] != "response_field"
        ):
            raise TrialStopped("F01_SCOPE_MISMATCH")
    return case


def prepare_case(repository, root, case):
    case_root = root / "case-repo"
    case_root.mkdir()
    for source in case["sources"]:
        body = _git(
            repository,
            "show",
            f"{BASELINE}:benchmarks/contract_review/materials/{source['fixture']}",
        )
        target = case_root / source["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    _git(case_root, "init", "-q")
    _git(case_root, "add", ".")
    _git(case_root, "commit", "-qm", "Frozen original F01 materials")
    sha = _git(case_root, "rev-parse", "HEAD").decode().strip()
    body = copy.deepcopy(case["request"])
    body.update(
        source={
            "kind": "git_commit",
            "commit_sha": sha,
            "groups": [{"role": role, "paths": [path]} for path, role, _ in MATERIALS],
        },
        execution_profile_id=PROFILE,
    )
    return case_root, body


def make_profile(adapter):
    from specflow.contract_review.profiles import dynamic_profile
    from specflow.contract_review.schemas import ExecutionProfile

    profile = dynamic_profile(
        PROFILE,
        REQUEST_MODEL,
        execution_mode=adapter.execution_mode,
        delegation=False,
        provider_binding=adapter.binding,
    )
    profile["analysis_prompt"] += (
        "\n证据引用与选源分开：source_catalog 的 ID、路径、哈希和行数只是目录元数据，"
        "可用于工具 arguments 选择来源，不证明已读取正文。reason.evidence_refs 只能引用"
        "已投影到模型请求中的正文片段或观察；工具已经执行但观察尚未投影也不算已读。"
        "只有目标或目录信息时，允许 evidence_refs=[]，据此先请求必要的读取工具。"
        "引用范围不得超过实际投影的片段。遇到 Referenced body was not projected 反馈时，"
        "移除未投影的引用，先读取所需正文，待观察进入后续请求再引用；"
        "添加其他引用不能使原有未读引用合法。\n"
        "引用字段的身份域不同，不可按名称相似互换："
        "reason.evidence_refs 是带 kind 的 MaterialRef；工具观察使用 "
        '{"kind":"observation","observation_id":"宿主提供的观察ID"}。'
        "findings[].observation_refs 和 check_results[].observation_refs 使用已投影工具观察的 "
        "observation_id 列表；source_refs 使用 source_id 加 selector，指向实际已投影正文片段。"
        "rule_refs 和 rule_uses[].adoption_id 引用 adoption_records 的规则采用身份，"
        "不是外部核验身份。findings[].verification_evidence_refs 和 "
        "acceptance_items[].evidence_refs 只接受当前 input 显式采用且已投影的外部核验 "
        "evidence_id，分别对应 verification_evidence_adoptions 与 verification_evidence，"
        "并须通过宿主的当前输入归属和目标适用性校验。工具 observation_id、规则 adoption_id "
        "及 source_id 均不能填入这两个外部核验字段，也不能自行将工具观察升级为外部核验。"
        "没有已采用且投影的外部核验记录时，这两个字段必须为 []；"
        "不要为了填字段而要求新增外部证据或执行测试，执行状态仍为 NOT_RUN。"
        "遇到 Unknown adopted evidence 时，检查这两个外部核验字段并移除错误身份；"
        "工具观察仅放在其允许的观察引用字段，不通过追加观察ID或规则ID修复外部引用。\n"
    )
    return ExecutionProfile.model_validate(profile).frozen()


def _serve(root_text, api_key, stop, connection):
    """Child owns its worker and physical I/O; parent owns its process lifetime."""
    ledger = None
    try:
        root = Path(root_text)
        policy = FlashPolicy()
        policy.require_first_dispatch()
        # Only reached after the amount gate passes. No secret is returned or logged.
        import uvicorn

        from specflow.api_security import ApiSecurity
        from specflow.llm.providers.config import OpenAICompatibleConfig
        from specflow.main import create_app

        credential = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not credential:
            raise TrialStopped("APPROVED_ENV_AUTH_UNAVAILABLE")
        config = OpenAICompatibleConfig(PROVIDER_BASE, credential, REQUEST_MODEL, 45)
        ledger = TrialLedger(policy, root / "trial-ledger.jsonl")
        adapter = GuardedFlashAdapter(config, ledger)
        app = create_app(
            database_url=f"sqlite:///{(root / 'reviews.sqlite').as_posix()}",
            artifact_root=root / "artifacts",
            security=ApiSecurity(
                api_key=api_key, allowed_repository_roots=(str(root / "case-repo"),)
            ),
            contract_review_profiles={PROFILE: make_profile(adapter)},
            contract_review_adapter=adapter,
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        server = uvicorn.Server(
            uvicorn.Config(app, log_config=None, log_level="critical", access_log=False)
        )

        def watch():
            stop.wait()
            server.should_exit = True

        threading.Thread(target=watch, daemon=True).start()
        connection.send({"port": sock.getsockname()[1]})
        server.run(sockets=[sock])
    except Exception as error:
        connection.send(
            {"error_code": error.code if isinstance(error, TrialStopped) else type(error).__name__}
        )
    finally:
        if ledger:
            ledger.close()
        connection.close()


def collect_review(client, review, job):
    """Use existing read APIs, preserving details instead of treating hashes as bodies."""
    base = f"/api/v1/contract-reviews/{review}"
    status = client.get(base)
    status.raise_for_status()
    status = status.json()
    collected = {"status": status, "events": [], "collection_complete": True}
    cursor = None
    while True:
        params = {"job_id": job, "limit": 20}
        if cursor:
            params["cursor"] = cursor
        page = client.get(base + "/events", params=params)
        page.raise_for_status()
        page = page.json()
        for event in page["items"]:
            detail = client.get(base + "/events/" + event["event_id"])
            if detail.status_code != 200:
                collected["collection_complete"] = False
                collected["events"].append({"metadata": event, "detail_status": detail.status_code})
            else:
                collected["events"].append(detail.json())
        cursor = page.get("next_cursor")
        if not cursor:
            break
        if len(collected["events"]) >= 2000:
            collected["collection_complete"] = False
            break
    if status.get("report_available"):
        params = {"report_revision_id": status["current_report_revision_id"]}
        response = client.get(base + "/report", params=params)
        response.raise_for_status()
        collected["report_json"] = response.json()
        response = client.get(base + "/report", params={**params, "format": "markdown"})
        response.raise_for_status()
        collected["report_markdown"] = response.text
    return collected


def submit_and_observe(
    client, case_root, body, *, trial_id=SOURCE_TRIAL, seconds=600, interval=0.25, on_accept=None
):
    project = client.post(
        "/api/v1/projects", json={"name": "Original F01 pilot", "repository_path": str(case_root)}
    )
    project.raise_for_status()
    body = {**body, "project_id": project.json()["id"]}
    started = time.monotonic()
    accepted = client.post(
        "/api/v1/contract-reviews",
        json=body,
        headers={"Idempotency-Key": trial_id},
    )
    accepted.raise_for_status()
    accepted = accepted.json()
    accepted_response = time.monotonic()
    review, job = accepted["review_id"], accepted["job_id"]
    if on_accept:
        on_accept(
            {
                "accepted": accepted,
                "submitted_body": body,
                "submitted_monotonic": started,
                "accepted_response_monotonic": accepted_response,
            }
        )
    observed = None
    while time.monotonic() - started < seconds:
        response = client.get(f"/api/v1/contract-reviews/{review}")
        response.raise_for_status()
        if response.json()["status"] in TERMINAL:
            observed = time.monotonic()
            break
        time.sleep(interval)
    evidence = collect_review(client, review, job)
    evidence.update(
        accepted=accepted,
        submitted_body=body,
        submitted_monotonic=started,
        accepted_response_monotonic=accepted_response,
        terminal_observed_monotonic=observed,
        submission_to_accepted_response_seconds=accepted_response - started,
        submit_to_terminal_observed_seconds=None if observed is None else observed - started,
        accepted_to_terminal_observed_seconds=None
        if observed is None
        else observed - accepted_response,
        polling_interval_seconds=interval,
        supervision_timeout=observed is None,
        semantic_verdict="PENDING_EVIDENCE_REVIEW",
    )
    return evidence


def _run_api(root, case_root, body, *, trial_id=SOURCE_TRIAL):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    stop = context.Event()
    api_key = secrets.token_hex(24)
    process = context.Process(target=_serve, args=(str(root), api_key, stop, child))
    process.start()
    child.close()
    cleanup = {"process_id": process.pid, "forced_stop": False}
    try:
        if not parent.poll(20):
            raise TrialStopped("LOCAL_API_START_TIMEOUT")
        ready = parent.recv()
        if "error_code" in ready:
            raise TrialStopped(ready["error_code"])
        with httpx.Client(
            base_url=f"http://127.0.0.1:{ready['port']}",
            headers={"X-API-Key": api_key},
            timeout=5,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            start = time.monotonic()
            while True:
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                if not process.is_alive() or time.monotonic() - start >= 20:
                    raise TrialStopped("LOCAL_API_START_TIMEOUT")
                time.sleep(0.05)
            result = submit_and_observe(
                client,
                case_root,
                body,
                trial_id=trial_id,
                on_accept=lambda value: _save(root / "accepted.json", value),
            )
            _save(root / "review-evidence.json", result)
            return result
    finally:
        cleanup_started = time.monotonic()
        stop.set()
        process.join(5)
        if process.is_alive():
            cleanup["forced_stop"] = True
            process.terminate()
            process.join(5)
        cleanup.update(
            local_process_exited=not process.is_alive(),
            exit_code=process.exitcode,
            cleanup_seconds=time.monotonic() - cleanup_started,
        )
        _save(root / "cleanup.json", cleanup)
        parent.close()


def trial_account(root):
    path = root / "trial-ledger.jsonl"
    if not path.exists():
        return {"business_model_http_attempts": 0, "ledger_available": False}
    from decimal import Decimal

    reservations, attempts, settled = {}, set(), Decimal("0")
    complete = True
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                complete = False
                break
            call = event.get("trial_call_id")
            if event["event"] == "reserved_before_adapter_http":
                reservations[call] = Decimal(event["reserved_cny"])
            elif event["event"] == "http_transport_entered":
                attempts.add(call)
            elif event["event"] == "usage_accounted":
                reservations.pop(call, None)
                settled += Decimal(event["cost_cny_upper"])
    return {
        "business_model_http_attempts": len(attempts),
        "ledger_available": True,
        "ledger_parse_complete": complete,
        "cost_cny_upper_accounted": str(settled),
        "unsettled_cny_reserved": str(sum(reservations.values(), Decimal("0"))),
        "provider_invoice_cost": None,
    }


def run_pilot(repository, output, *, live=False, trial_id=None):
    if trial_id is not None and (
        not isinstance(trial_id, str)
        or re.fullmatch(r"TR02-F01-COMMON-(?:0[1-9]|[1-9][0-9])", trial_id) is None
    ):
        raise TrialStopped("INVALID_F01_TRIAL_ID")
    if live and (trial_id is None or trial_id == SOURCE_TRIAL):
        raise TrialStopped("NEW_F01_TRIAL_ID_REQUIRED")
    trial_id = trial_id or SOURCE_TRIAL
    repository, output = repository.resolve(), output.resolve()
    if output == repository or repository in output.parents:
        raise TrialStopped("OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
    output.mkdir(parents=True, exist_ok=False)
    policy = FlashPolicy()
    record = {
        "case_id": CASE,
        "trial_id": trial_id,
        "source_trial_id": SOURCE_TRIAL,
        "sample_id": SAMPLE,
        "created_at": timestamp(),
        "requested_live_execution": live,
        "fixture_source_commit": BASELINE,
        "execution_checkout_head": None,
        "worktree_status": None,
        "materials": [{"path": p, "role": r, "fixture": f} for p, r, f in MATERIALS],
        "formal_targets": ["docs/api.md", "examples/client.py"],
        "implementation_role": "comparison evidence, not a formal target",
        "expected_criteria_source": "User-reviewed F01 criteria in this chat; not actual results",
        "profile_id": PROFILE,
        "trial_policy": policy.record(),
        "business_model_http_attempts": 0,
        "trial_consumed": False,
        "semantic_verdict": "NOT_RUN",
    }
    _save(output / "run.json", record)
    try:
        record["execution_checkout_head"] = _git(repository, "rev-parse", "HEAD").decode().strip()
        record["worktree_status"] = _git(repository, "status", "--short").decode()
        if (
            os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/") != LAUNCHER_BASE
            or os.environ.get("ANTHROPIC_MODEL") != REQUEST_MODEL
        ):
            raise TrialStopped("AUTHORIZED_CHANNEL_METADATA_MISMATCH")
        load_case(repository)
        policy.require_first_dispatch()
        if not live:
            record["status"] = "PREPARED_NOT_DISPATCHED"
        else:
            case_root, body = prepare_case(repository, output, load_case(repository))
            _save(output / "frozen-request.json", body)
            record["trial_consumed"] = True
            evidence = _run_api(output, case_root, body, trial_id=trial_id)
            record.update(status="OBSERVED", semantic_verdict="PENDING_EVIDENCE_REVIEW")
            record["review_id"] = evidence["accepted"]["review_id"]
            record["input_revision_id"] = evidence["accepted"]["input_revision_id"]
            record["job_id"] = evidence["accepted"]["job_id"]
    except Exception as error:
        record.update(
            status="BLOCKED_BEFORE_DISPATCH" if not record["trial_consumed"] else "FAILED",
            reason=error.code if isinstance(error, TrialStopped) else type(error).__name__,
        )
    record.update(trial_account(output))
    accepted_path = output / "accepted.json"
    if accepted_path.exists():
        accepted = json.loads(accepted_path.read_text(encoding="utf-8"))["accepted"]
        record.update(
            review_id=accepted["review_id"],
            input_revision_id=accepted["input_revision_id"],
            job_id=accepted["job_id"],
        )
    _save(output / "run.json", record, update=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trial-id", help="Explicit new F01 execution identity required for --run")
    parser.add_argument(
        "--run", action="store_true", help="Requires every frozen preflight to pass"
    )
    args = parser.parse_args()
    try:
        result = run_pilot(
            Path(__file__).resolve().parents[2], args.output, live=args.run, trial_id=args.trial_id
        )
    except Exception as error:
        result = {"status": "NOT_STARTED", "reason": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] in ("OBSERVED", "PREPARED_NOT_DISPATCHED") else 3


if __name__ == "__main__":
    raise SystemExit(main())
